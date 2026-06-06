from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from lingneng.schemas.chat_events import Artifact
from lingneng.session.run_store import LingNengRunStore, RunStatus


ARTIFACT = {
    "artifact_id": "artifact-doc-1",
    "artifact_type": "document",
    "source": "document_generation",
    "file_name": "报告.pdf",
    "mime_type": "application/pdf",
    "url": "https://files.example.test/report.pdf",
    "object_key": "external/java-agent-file/artifact-doc-1",
    "format": "pdf",
    "target_format": "pdf",
    "conversion_required": False,
    "conversion_owner": None,
}
IMAGE_ARTIFACT = {
    **ARTIFACT,
    "artifact_id": "artifact-img-1",
    "artifact_type": "image",
    "source": "image_generation",
    "file_name": "poster.png",
    "mime_type": "image/png",
    "url": "https://files.example.test/poster.png",
    "object_key": "external/java-agent-file/artifact-img-1",
    "format": "png",
    "target_format": "png",
}


def test_first_request_creates_running_run(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")

    outcome = store.reserve_run("session-a", "req-1")

    assert outcome.created is True
    assert outcome.record.session_key == "session-a"
    assert outcome.record.request_id == "req-1"
    assert outcome.record.run_id.startswith("run_")
    assert outcome.record.status == RunStatus.RUNNING
    assert outcome.record.answer is None
    assert outcome.record.error_code is None
    assert outcome.record.error_message is None
    assert outcome.record.artifacts == []
    assert outcome.record.created_at.tzinfo is not None
    assert outcome.record.created_at.utcoffset() == timedelta(0)
    assert outcome.record.completed_at is None


def test_same_request_while_running_returns_existing_run(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    first = store.reserve_run("session-a", "req-1")
    second = store.reserve_run("session-a", "req-1")

    assert first.created is True
    assert second.created is False
    assert second.record.run_id == first.record.run_id
    assert second.record.status == RunStatus.RUNNING
    assert store.count_runs() == 1


def test_completed_run_stores_final_answer_and_reuses_existing_state(tmp_path):
    db_path = tmp_path / "runs.sqlite3"
    store = LingNengRunStore(db_path)
    first = store.reserve_run("session-a", "req-1")

    store.mark_succeeded(
        first.record.run_id,
        answer="完成",
        artifacts=[ARTIFACT],
    )
    repeated = store.reserve_run("session-a", "req-1")

    assert repeated.created is False
    assert repeated.record.status == RunStatus.SUCCEEDED
    assert repeated.record.answer == "完成"
    assert repeated.record.error_code is None
    assert repeated.record.error_message is None
    assert repeated.record.artifacts == [ARTIFACT]
    assert repeated.record.completed_at is not None
    assert repeated.record.completed_at.utcoffset() == timedelta(0)
    assert store.count_runs() == 1

    with sqlite3.connect(db_path) as conn:
        artifacts_json = conn.execute(
            "SELECT artifacts_json FROM lingneng_runs WHERE run_id = ?",
            (first.record.run_id,),
        ).fetchone()[0]
    assert "报告.pdf" in artifacts_json


def test_mark_succeeded_serializes_pydantic_and_dict_artifacts(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    first = store.reserve_run("session-a", "req-1")

    store.mark_succeeded(
        first.record.run_id,
        answer="完成",
        artifacts=[Artifact.model_validate(ARTIFACT), IMAGE_ARTIFACT],
    )
    record = store.get_by_run_id(first.record.run_id)

    assert record is not None
    assert record.artifacts == [ARTIFACT, IMAGE_ARTIFACT]


def test_invalid_stored_artifact_rows_are_filtered(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    first = store.reserve_run("session-a", "req-1")
    store.mark_succeeded(first.record.run_id, answer="完成", artifacts=[ARTIFACT])

    with sqlite3.connect(tmp_path / "runs.sqlite3") as conn:
        conn.execute(
            "UPDATE lingneng_runs SET artifacts_json = ? WHERE run_id = ?",
            (
                json.dumps(
                    [
                        ARTIFACT,
                        {**ARTIFACT, "artifact_id": "bad", "url": "file:///tmp/a"},
                        {"artifact_id": "missing-required-fields"},
                        "not-a-dict",
                    ],
                    ensure_ascii=False,
                ),
                first.record.run_id,
            ),
        )

    record = store.get_by_run_id(first.record.run_id)

    assert record is not None
    assert record.artifacts == [ARTIFACT]


def test_same_request_id_in_different_sessions_creates_separate_runs(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    first = store.reserve_run("session-a", "req-1")
    second = store.reserve_run("session-b", "req-1")

    assert first.created is True
    assert second.created is True
    assert first.record.run_id != second.record.run_id
    assert first.record.session_key == "session-a"
    assert second.record.session_key == "session-b"
    assert store.count_runs() == 2


def test_failed_run_stores_public_error(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    first = store.reserve_run("session-a", "req-1")

    store.mark_failed(first.record.run_id, "RUNTIME_ERROR", "运行失败")
    record = store.get_by_run_id(first.record.run_id)

    assert record is not None
    assert record.status == RunStatus.FAILED
    assert record.error_code == "RUNTIME_ERROR"
    assert record.error_message == "运行失败"
    assert record.completed_at is not None
    assert record.completed_at.utcoffset() == timedelta(0)


def test_mark_succeeded_missing_run_raises_state_error(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")

    with pytest.raises(RuntimeError, match="missing") as excinfo:
        store.mark_succeeded("missing", answer="不会写入")

    assert excinfo.type.__name__ == "RunStoreStateError"


def test_mark_failed_missing_run_raises_state_error(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")

    with pytest.raises(RuntimeError, match="missing") as excinfo:
        store.mark_failed("missing", "RUNTIME_ERROR", "不会写入")

    assert excinfo.type.__name__ == "RunStoreStateError"


def test_succeeded_run_cannot_be_marked_failed(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    first = store.reserve_run("session-a", "req-1")
    store.mark_succeeded(first.record.run_id, answer="完成")

    with pytest.raises(RuntimeError, match="invalid transition") as excinfo:
        store.mark_failed(first.record.run_id, "RUNTIME_ERROR", "不应覆盖")

    assert excinfo.type.__name__ == "RunStoreStateError"
    record = store.get_by_run_id(first.record.run_id)
    assert record is not None
    assert record.status == RunStatus.SUCCEEDED
    assert record.answer == "完成"
    assert record.error_code is None
    assert record.error_message is None


def test_failed_run_cannot_be_marked_succeeded(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    first = store.reserve_run("session-a", "req-1")
    store.mark_failed(first.record.run_id, "RUNTIME_ERROR", "运行失败")

    with pytest.raises(RuntimeError, match="invalid transition") as excinfo:
        store.mark_succeeded(first.record.run_id, answer="不应覆盖")

    assert excinfo.type.__name__ == "RunStoreStateError"
    record = store.get_by_run_id(first.record.run_id)
    assert record is not None
    assert record.status == RunStatus.FAILED
    assert record.answer is None
    assert record.error_code == "RUNTIME_ERROR"
    assert record.error_message == "运行失败"


def test_cleanup_older_than_deletes_rows_older_than_retention(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    old = datetime.now(timezone.utc) - timedelta(days=10)
    recent = datetime.now(timezone.utc) - timedelta(days=2)
    old_run = store.reserve_run("session-a", "old")
    recent_run = store.reserve_run("session-a", "recent")
    store.force_update_created_at(old_run.record.run_id, old)
    store.force_update_created_at(recent_run.record.run_id, recent)

    deleted = store.cleanup_older_than(days=7)

    assert deleted == 1
    assert store.get_by_run_id(old_run.record.run_id) is None
    assert store.get_by_run_id(recent_run.record.run_id) is not None
    assert store.count_runs() == 1
