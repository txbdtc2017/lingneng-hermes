from __future__ import annotations

from typing import Any

import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.hermes_session import LingNengHermesSessionStore
from lingneng.session.keys import ResolvedSessionKey, resolve_session_key
from lingneng.session.run_store import LingNengRunStore
from tests.lingneng.schemas.test_chat_request_schema import full_payload


ROOT_STALE_MESSAGE = "ROOT_STALE_MESSAGE_SHOULD_NOT_BE_USED"
CHILD_SUMMARY_MESSAGE = "COMPRESSED_CHILD_SUMMARY_VISIBLE"
JAVA_HISTORY_MESSAGE = "JAVA_HISTORY_SHOULD_NOT_BE_USED"


def settings(tmp_path) -> LingNengSettings:
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_INTERNAL_API_KEY": "key",
            "LINGNENG_AGENT_MODE": "hermes",
        }
    )


def request_with_java_history() -> ChatStreamRequest:
    payload = full_payload()
    payload["attachments"] = []
    payload["history"] = [
        {
            "message_id": "history-sentinel",
            "role": "user",
            "content": JAVA_HISTORY_MESSAGE,
        }
    ]
    return ChatStreamRequest.model_validate(payload)


def resolved_from(request: ChatStreamRequest) -> ResolvedSessionKey:
    return resolve_session_key(request)


def seed_compression_tip(
    store: LingNengHermesSessionStore,
    resolved: ResolvedSessionKey,
) -> str:
    root_session_id = resolved.session_key
    active_session_id = f"{root_session_id}#compression-tip"
    root_started_at = 1_700_000_000.0
    root_ended_at = root_started_at + 10.0
    child_started_at = root_ended_at + 1.0

    store.db.create_session(
        root_session_id,
        source="lingneng",
        user_id=resolved.user_id,
    )
    store.db.append_message(
        session_id=root_session_id,
        role="user",
        content=ROOT_STALE_MESSAGE,
    )
    store.db.end_session(root_session_id, "compression")
    store.db.create_session(
        active_session_id,
        source="lingneng",
        user_id=resolved.user_id,
        parent_session_id=root_session_id,
    )
    store.db.append_message(
        session_id=active_session_id,
        role="assistant",
        content=CHILD_SUMMARY_MESSAGE,
    )
    set_session_times(store, root_session_id, root_started_at, root_ended_at)
    set_session_times(store, active_session_id, child_started_at)
    return active_session_id


def set_session_times(
    store: LingNengHermesSessionStore,
    session_id: str,
    started_at: float,
    ended_at: float | None = None,
) -> None:
    assignments = ["started_at = ?"]
    params: list[float | str] = [started_at]
    if ended_at is not None:
        assignments.append("ended_at = ?")
        params.append(ended_at)
    params.append(session_id)

    def update(conn) -> None:
        conn.execute(
            f"UPDATE sessions SET {', '.join(assignments)} WHERE id = ?",
            params,
        )

    store.db._execute_write(update)


class CapturingCompressionAgent:
    instances: list["CapturingCompressionAgent"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.run_args: dict[str, Any] = {}
        type(self).instances.append(self)

    def run_conversation(
        self,
        user_message,
        system_message=None,
        conversation_history=None,
        task_id=None,
        stream_callback=None,
        persist_user_message=None,
    ):
        self.run_args = {
            "user_message": user_message,
            "system_message": system_message,
            "conversation_history": conversation_history,
            "task_id": task_id,
            "persist_user_message": persist_user_message,
        }
        return {"final_response": "compression-ok", "messages": []}


def history_text(history: list[dict[str, Any]]) -> str:
    return "\n".join(str(message.get("content", "")) for message in history)


def test_resolves_active_session_id_from_compression_tip(tmp_path):
    store = LingNengHermesSessionStore(settings(tmp_path))
    request = request_with_java_history()
    resolved = resolved_from(request)
    active_session_id = seed_compression_tip(store, resolved)

    assert store.resolve_active_session_id(resolved) == active_session_id
    assert store.resolve_active_session_id(resolved.session_key) == active_session_id


def test_resume_fallback_requires_compression_root(tmp_path):
    store = LingNengHermesSessionStore(settings(tmp_path))
    request = request_with_java_history()
    resolved = resolved_from(request)
    active_session_id = f"{resolved.session_key}#resume-child"

    store.db.create_session(
        resolved.session_key,
        source="lingneng",
        user_id=resolved.user_id,
    )
    store.db.create_session(
        active_session_id,
        source="lingneng",
        user_id=resolved.user_id,
        parent_session_id=resolved.session_key,
    )
    store.db.append_message(
        session_id=active_session_id,
        role="assistant",
        content=CHILD_SUMMARY_MESSAGE,
    )

    assert store.resolve_active_session_id(resolved) == resolved.session_key


def test_resolves_active_session_id_from_validated_resume_child_when_tip_lookup_misses(
    tmp_path,
    monkeypatch,
):
    store = LingNengHermesSessionStore(settings(tmp_path))
    request = request_with_java_history()
    resolved = resolved_from(request)
    active_session_id = f"{resolved.session_key}#resume-child"
    root_started_at = 1_700_000_000.0
    root_ended_at = root_started_at + 10.0
    child_started_at = root_ended_at + 1.0

    store.db.create_session(
        resolved.session_key,
        source="lingneng",
        user_id=resolved.user_id,
    )
    store.db.end_session(resolved.session_key, "compression")
    store.db.create_session(
        active_session_id,
        source="lingneng",
        user_id=resolved.user_id,
        parent_session_id=resolved.session_key,
    )
    store.db.append_message(
        session_id=active_session_id,
        role="assistant",
        content=CHILD_SUMMARY_MESSAGE,
    )
    set_session_times(store, resolved.session_key, root_started_at, root_ended_at)
    set_session_times(store, active_session_id, child_started_at)

    monkeypatch.setattr(
        store.db,
        "get_compression_tip",
        lambda _session_id: resolved.session_key,
    )

    assert store.resolve_active_session_id(resolved) == active_session_id


def test_resume_fallback_rejects_non_continuation_child_under_compression_root(
    tmp_path,
):
    store = LingNengHermesSessionStore(settings(tmp_path))
    request = request_with_java_history()
    resolved = resolved_from(request)
    active_session_id = f"{resolved.session_key}#resume-child"
    root_started_at = 1_700_000_000.0
    root_ended_at = root_started_at + 10.0
    child_started_before_parent_end = root_ended_at - 1.0

    store.db.create_session(
        resolved.session_key,
        source="lingneng",
        user_id=resolved.user_id,
    )
    store.db.end_session(resolved.session_key, "compression")
    store.db.create_session(
        active_session_id,
        source="lingneng",
        user_id=resolved.user_id,
        parent_session_id=resolved.session_key,
    )
    store.db.append_message(
        session_id=active_session_id,
        role="assistant",
        content=CHILD_SUMMARY_MESSAGE,
    )
    set_session_times(store, resolved.session_key, root_started_at, root_ended_at)
    set_session_times(store, active_session_id, child_started_before_parent_end)

    assert store.db.get_compression_tip(resolved.session_key) == resolved.session_key
    assert store.resolve_active_session_id(resolved) == resolved.session_key


def test_active_session_lookup_logs_sanitized_warning_on_lookup_failure(
    tmp_path,
    monkeypatch,
    caplog,
):
    store = LingNengHermesSessionStore(settings(tmp_path))
    request = request_with_java_history()
    resolved = resolved_from(request)

    def fail_lookup(session_id: str) -> str:
        raise RuntimeError("SECRET_DB_FAILURE_SHOULD_NOT_LOG")

    monkeypatch.setattr(store.db, "get_compression_tip", fail_lookup)

    with caplog.at_level("WARNING", logger="lingneng.session.hermes_session"):
        active_session_id = store.resolve_active_session_id(resolved)

    assert active_session_id == resolved.session_key
    assert "SECRET_DB_FAILURE_SHOULD_NOT_LOG" not in caplog.text
    assert caplog.records[0].lookup_stage == "compression_tip"
    assert caplog.records[0].error_type == "RuntimeError"


def test_load_conversation_history_reads_active_child_session(tmp_path):
    store = LingNengHermesSessionStore(settings(tmp_path))
    request = request_with_java_history()
    resolved = resolved_from(request)
    seed_compression_tip(store, resolved)

    history = store.load_conversation_history(resolved)

    assert history == [{"role": "assistant", "content": CHILD_SUMMARY_MESSAGE}]


@pytest.mark.asyncio
async def test_adapter_uses_active_child_session_and_excludes_java_history(tmp_path):
    CapturingCompressionAgent.instances = []
    resolved_settings = settings(tmp_path)
    store = LingNengHermesSessionStore(resolved_settings)
    request = request_with_java_history()
    resolved = resolved_from(request)
    active_session_id = seed_compression_tip(store, resolved)
    adapter = HermesAgentRunAdapter(
        settings=resolved_settings,
        agent_cls=CapturingCompressionAgent,
        session_store=store,
    )

    events = [event async for event in adapter.stream(request, resolved, "run-1")]

    assert events[-1].answer == "compression-ok"
    agent = CapturingCompressionAgent.instances[0]
    assert agent.kwargs["session_id"] == active_session_id
    conversation_history = agent.run_args["conversation_history"]
    combined_history = history_text(conversation_history)
    assert CHILD_SUMMARY_MESSAGE in combined_history
    assert ROOT_STALE_MESSAGE not in combined_history
    assert JAVA_HISTORY_MESSAGE not in combined_history


def test_ensure_session_and_run_store_keep_root_business_session_key(tmp_path):
    resolved_settings = settings(tmp_path)
    store = LingNengHermesSessionStore(resolved_settings)
    request = request_with_java_history()
    resolved = resolved_from(request)
    active_session_id = seed_compression_tip(store, resolved)
    run_store = LingNengRunStore(tmp_path / "runs.sqlite3")

    ensured_session_id = store.ensure_session(resolved)
    first = run_store.reserve_run(resolved.session_key, request.request_id)
    second = run_store.reserve_run(resolved.session_key, request.request_id)

    assert active_session_id != resolved.session_key
    assert ensured_session_id == resolved.session_key
    assert first.created is True
    assert second.created is False
    assert second.record.run_id == first.record.run_id
    assert second.record.session_key == resolved.session_key
