import pytest

from lingneng.api.app import create_app
from lingneng.config.settings import LingNengSettings
from lingneng.runtime.fake_agent import FakeAgentRunAdapter
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from lingneng.session.run_store import LingNengRunStore
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def settings(tmp_path, **overrides) -> LingNengSettings:
    env = {
        "LINGNENG_APP_ENV": "test",
        "LINGNENG_RUNTIME_DIR": str(tmp_path),
        "LINGNENG_INTERNAL_API_KEY": "key",
    }
    env.update(overrides)
    return LingNengSettings.from_env(env)


def test_create_app_uses_fake_adapter_by_default(tmp_path):
    resolved_settings = settings(tmp_path)

    app = create_app(settings=resolved_settings)

    assert app.state.lingneng_settings is resolved_settings
    assert isinstance(app.state.lingneng_adapter, FakeAgentRunAdapter)
    assert isinstance(app.state.lingneng_run_store, LingNengRunStore)


def test_create_app_uses_hermes_adapter_for_hermes_mode(tmp_path):
    app = create_app(settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"))

    assert app.state.lingneng_adapter.__class__.__name__ == "HermesAgentRunAdapter"


class CapturingAgent:
    calls: list[dict] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        CapturingAgent.calls.append(kwargs)

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
        return {"final_response": "完成", "messages": []}


@pytest.mark.asyncio
async def test_hermes_adapter_constructs_agent_with_no_tool_lingneng_context(
    tmp_path,
):
    CapturingAgent.calls = []
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=CapturingAgent,
    )

    events = [event async for event in adapter.stream(request, resolved, "run-1")]

    kwargs = CapturingAgent.calls[0]
    assert kwargs["platform"] == "lingneng"
    assert kwargs["session_id"] == resolved.session_key
    assert kwargs["enabled_toolsets"] == []
    assert kwargs["quiet_mode"] is True
    assert kwargs["skip_context_files"] is True
    assert kwargs["skip_memory"] is True
    assert kwargs["session_db"].db_path == tmp_path / "sessions.sqlite3"
    assert events[-1].answer == "完成"


@pytest.mark.asyncio
async def test_hermes_adapter_does_not_pass_java_history_to_conversation_history(
    tmp_path,
):
    CapturingAgent.calls = []
    payload = full_payload()
    payload["history"].append(
        {"message_id": "h-3", "role": "user", "content": "Java 历史"}
    )
    request = ChatStreamRequest.model_validate(payload)
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=CapturingAgent,
    )

    [event async for event in adapter.stream(request, resolved, "run-1")]

    agent = adapter._last_agent_for_tests
    assert agent.run_args["user_message"] == request.query.content
    assert agent.run_args["system_message"] == request.system_prompt.content
    assert agent.run_args["persist_user_message"] == request.query.content
    assert agent.run_args["conversation_history"] == []
