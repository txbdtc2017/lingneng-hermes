from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.hermes_session import LingNengHermesSessionStore
from lingneng.session.keys import resolve_session_key
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def settings(tmp_path) -> LingNengSettings:
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_INTERNAL_API_KEY": "key",
        }
    )


def resolved_from(payload: dict):
    return resolve_session_key(ChatStreamRequest.model_validate(payload))


def test_session_db_path_is_lingneng_runtime_dir(tmp_path):
    store = LingNengHermesSessionStore(settings(tmp_path))

    assert store.db.db_path == tmp_path / "sessions.sqlite3"


def test_loads_existing_hermes_messages_as_conversation_history(tmp_path):
    store = LingNengHermesSessionStore(settings(tmp_path))
    resolved = resolved_from(full_payload())
    store.db.ensure_session(resolved.session_key, source="lingneng")
    store.db.append_message(
        session_id=resolved.session_key,
        role="user",
        content="上一轮问题",
    )
    store.db.append_message(
        session_id=resolved.session_key,
        role="assistant",
        content="上一轮回答",
    )
    store.db.append_message(
        session_id=resolved.session_key,
        role="assistant",
        content="我会调用工具",
        tool_calls=[
            {
                "id": "call-1",
                "type": "function",
                "function": {"name": "retrieve_rag", "arguments": "{}"},
            }
        ],
    )
    store.db.append_message(
        session_id=resolved.session_key,
        role="tool",
        content="工具结果",
        tool_name="retrieve_rag",
        tool_call_id="call-1",
        finish_reason="tool_complete",
    )
    store.db.append_message(
        session_id=resolved.session_key,
        role="system",
        content="不应进入历史",
    )

    history = store.load_conversation_history(resolved)

    assert history == [
        {"role": "user", "content": "上一轮问题"},
        {"role": "assistant", "content": "上一轮回答"},
        {
            "role": "assistant",
            "content": "我会调用工具",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "retrieve_rag", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "tool",
            "content": "工具结果",
            "tool_call_id": "call-1",
            "tool_name": "retrieve_rag",
            "finish_reason": "tool_complete",
        },
    ]


def test_same_conversation_reuses_same_session_key(tmp_path):
    store = LingNengHermesSessionStore(settings(tmp_path))
    first = resolved_from(full_payload())
    second = resolved_from(full_payload())

    store.ensure_session(first)
    store.ensure_session(second)

    assert first.session_key == second.session_key
    assert store.db.get_session(first.session_key) is not None


def test_different_employee_gets_different_session_key(tmp_path):
    store = LingNengHermesSessionStore(settings(tmp_path))
    first_payload = full_payload()
    second_payload = full_payload()
    second_payload["employee"]["employee_id"] = "emp-002"
    first = resolved_from(first_payload)
    second = resolved_from(second_payload)

    store.ensure_session(first)
    store.ensure_session(second)

    assert first.session_key != second.session_key
    assert store.db.get_session(first.session_key) is not None
    assert store.db.get_session(second.session_key) is not None


def test_java_history_is_not_loaded_or_persisted(tmp_path):
    store = LingNengHermesSessionStore(settings(tmp_path))
    payload = full_payload()
    payload["history"].append(
        {"message_id": "h-3", "role": "user", "content": "Java 历史"}
    )
    resolved = resolved_from(payload)

    store.ensure_session(resolved)
    history = store.load_conversation_history(resolved)

    assert history == []
    assert store.db.get_messages(resolved.session_key) == []
