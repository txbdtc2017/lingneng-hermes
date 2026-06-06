from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from hermes_state import SessionDB

from lingneng.config.settings import LingNengSettings
from lingneng.session.cleanup import run_lingneng_cleanup
from lingneng.session.hermes_session import LingNengHermesSessionStore
from lingneng.session.run_store import LingNengRunStore


SECRET_MESSAGE = "SECRET_MESSAGE_SHOULD_NOT_LOG"
SECRET_RUN_ANSWER = "SECRET_RUN_ANSWER_SHOULD_NOT_LOG"
SECONDS_PER_DAY = 24 * 60 * 60


def settings(tmp_path) -> LingNengSettings:
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_INTERNAL_API_KEY": "key",
        }
    )


def seed_session(
    db: SessionDB,
    session_id: str,
    *,
    source: str = "lingneng",
    age_days: int,
    ended: bool = True,
    end_reason: str = "completed",
    archived: bool = False,
    parent_session_id: str | None = None,
) -> str:
    db.create_session(
        session_id,
        source=source,
        user_id="user-1",
        parent_session_id=parent_session_id,
    )
    db.append_message(
        session_id=session_id,
        role="user",
        content=f"{SECRET_MESSAGE}:{session_id}",
    )
    if ended:
        db.end_session(session_id, end_reason)
    if archived:
        db.set_session_archived(session_id, True)

    timestamp = datetime.now(timezone.utc).timestamp() - age_days * SECONDS_PER_DAY
    set_session_times(
        db,
        session_id,
        started_at=timestamp - 60,
        ended_at=timestamp if ended else None,
    )
    return session_id


def set_session_times(
    db: SessionDB,
    session_id: str,
    *,
    started_at: float,
    ended_at: float | None,
) -> None:
    def update(conn) -> None:
        conn.execute(
            "UPDATE sessions SET started_at = ?, ended_at = ? WHERE id = ?",
            (started_at, ended_at, session_id),
        )

    db._execute_write(update)


def parent_session_id(db: SessionDB, session_id: str) -> str | None:
    session = db.get_session(session_id)
    assert session is not None
    return session["parent_session_id"]


def seed_run(
    store: LingNengRunStore,
    request_id: str,
    *,
    age_days: int,
) -> str:
    reservation = store.reserve_run("tenant:user:employee:conversation", request_id)
    store.mark_succeeded(reservation.record.run_id, SECRET_RUN_ANSWER)
    store.force_update_created_at(
        reservation.record.run_id,
        datetime.now(timezone.utc) - timedelta(days=age_days),
    )
    return reservation.record.run_id


def test_cleanup_prunes_only_expired_ended_lingneng_sessions(tmp_path):
    cleanup_settings = settings(tmp_path)
    db = SessionDB(cleanup_settings.session_db_path)
    run_store = LingNengRunStore(tmp_path / "runs.sqlite3")
    old_non_archived = seed_session(
        db,
        "old-non-archived",
        age_days=cleanup_settings.session_retention_days + 1,
    )
    recent_non_archived = seed_session(
        db,
        "recent-non-archived",
        age_days=cleanup_settings.session_retention_days - 1,
    )
    old_active = seed_session(
        db,
        "old-active",
        age_days=cleanup_settings.session_retention_days + 30,
        ended=False,
    )
    old_archived = seed_session(
        db,
        "old-archived",
        age_days=cleanup_settings.archived_session_retention_days + 1,
        archived=True,
    )
    recent_archived = seed_session(
        db,
        "recent-archived",
        age_days=cleanup_settings.archived_session_retention_days - 1,
        archived=True,
    )
    non_lingneng = seed_session(
        db,
        "old-cli-session",
        source="cli",
        age_days=cleanup_settings.session_retention_days + 1,
    )
    old_compression_parent = seed_session(
        db,
        "old-compression-parent",
        age_days=cleanup_settings.session_retention_days + 1,
        end_reason="compression",
    )
    recent_compression_child = seed_session(
        db,
        "recent-compression-child",
        age_days=cleanup_settings.session_retention_days - 1,
        parent_session_id=old_compression_parent,
    )
    session_store = LingNengHermesSessionStore(cleanup_settings, db=db)
    assert (
        session_store.resolve_active_session_id(old_compression_parent)
        == recent_compression_child
    )

    result = run_lingneng_cleanup(
        cleanup_settings,
        session_db=db,
        run_store=run_store,
    )

    assert result.session_retention_days == 90
    assert result.archived_session_retention_days == 180
    assert result.idempotency_retention_days == 7
    assert result.non_archived_sessions_pruned == 1
    assert result.archived_sessions_pruned == 1
    assert result.run_records_pruned == 0
    assert result.session_records_pruned == 2
    assert db.get_session(old_non_archived) is None
    assert db.get_messages(old_non_archived) == []
    assert db.get_session(old_archived) is None
    assert db.get_session(old_compression_parent) is not None
    assert db.get_session(recent_non_archived) is not None
    assert db.get_session(old_active) is not None
    assert db.get_session(recent_archived) is not None
    assert db.get_session(non_lingneng) is not None
    assert db.get_session(recent_compression_child) is not None
    assert parent_session_id(db, recent_compression_child) == old_compression_parent
    assert (
        session_store.resolve_active_session_id(old_compression_parent)
        == recent_compression_child
    )


def test_cleanup_prunes_run_store_rows_by_idempotency_retention(tmp_path):
    cleanup_settings = settings(tmp_path)
    db = SessionDB(cleanup_settings.session_db_path)
    run_store = LingNengRunStore(tmp_path / "runs.sqlite3")
    old_run_id = seed_run(
        run_store,
        "old-request",
        age_days=cleanup_settings.idempotency_retention_days + 1,
    )
    recent_run_id = seed_run(
        run_store,
        "recent-request",
        age_days=cleanup_settings.idempotency_retention_days - 1,
    )

    result = run_lingneng_cleanup(
        cleanup_settings,
        session_db=db,
        run_store=run_store,
    )

    assert result.non_archived_sessions_pruned == 0
    assert result.archived_sessions_pruned == 0
    assert result.run_records_pruned == 1
    assert run_store.get_by_run_id(old_run_id) is None
    assert run_store.get_by_run_id(recent_run_id) is not None
    assert run_store.count_runs() == 1


def test_cleanup_logs_counts_and_cutoffs_without_content_or_paths(tmp_path, caplog):
    cleanup_settings = settings(tmp_path)
    db = SessionDB(cleanup_settings.session_db_path)
    run_store = LingNengRunStore(tmp_path / "runs.sqlite3")
    seed_session(
        db,
        "old-logged-session",
        age_days=cleanup_settings.session_retention_days + 1,
    )
    seed_run(
        run_store,
        "old-logged-request",
        age_days=cleanup_settings.idempotency_retention_days + 1,
    )

    with caplog.at_level(logging.INFO, logger="lingneng.session.cleanup"):
        result = run_lingneng_cleanup(
            cleanup_settings,
            session_db=db,
            run_store=run_store,
        )

    matching_records = [
        record
        for record in caplog.records
        if getattr(record, "event_name", None) == "lingneng_cleanup_completed"
    ]
    assert len(matching_records) == 1
    record = matching_records[0]
    assert record.non_archived_sessions_pruned == result.non_archived_sessions_pruned
    assert record.archived_sessions_pruned == result.archived_sessions_pruned
    assert record.run_records_pruned == result.run_records_pruned
    assert record.session_cutoff_at == result.session_cutoff_at.isoformat()
    assert record.archived_session_cutoff_at == (
        result.archived_session_cutoff_at.isoformat()
    )
    assert record.idempotency_cutoff_at == result.idempotency_cutoff_at.isoformat()
    assert SECRET_MESSAGE not in caplog.text
    assert SECRET_RUN_ANSWER not in caplog.text
    assert str(tmp_path) not in caplog.text
