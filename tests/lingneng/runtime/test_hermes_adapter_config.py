import subprocess
import sys

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


def test_runtime_package_import_does_not_load_run_agent():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import lingneng.runtime; "
                "print('hermes_state' in sys.modules, 'run_agent' in sys.modules)"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False False"


def test_session_package_lazy_hermes_store_export_still_works():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from lingneng.session import LingNengHermesSessionStore; "
                "print(LingNengHermesSessionStore.__name__)"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "LingNengHermesSessionStore"


def test_runtime_package_lazy_hermes_export_still_works():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from lingneng.runtime import HermesAgentRunAdapter; "
                "print(HermesAgentRunAdapter.__name__)"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "HermesAgentRunAdapter"


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


class KanbanEnvProbeAgent:
    seen_in_init: str | None = None
    seen_in_run: str | None = None

    def __init__(self, **kwargs):
        import os

        self.stream_delta_callback = kwargs.get("stream_delta_callback")
        KanbanEnvProbeAgent.seen_in_init = os.environ.get("HERMES_KANBAN_TASK")

    def run_conversation(
        self,
        user_message,
        system_message=None,
        conversation_history=None,
        task_id=None,
        stream_callback=None,
        persist_user_message=None,
    ):
        import os

        KanbanEnvProbeAgent.seen_in_run = os.environ.get("HERMES_KANBAN_TASK")
        return {"final_response": "完成", "messages": []}


class SideEffectingActivityAgent:
    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")
        self._last_activity_ts = 0.0
        self._last_activity_desc = ""

    def _touch_activity(self, desc: str) -> None:
        raise AssertionError(f"kanban side effect inherited: {desc}")

    def run_conversation(
        self,
        user_message,
        system_message=None,
        conversation_history=None,
        task_id=None,
        stream_callback=None,
        persist_user_message=None,
    ):
        self._touch_activity("probe")
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
    assert kwargs["disabled_toolsets"] == ["kanban"]
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


@pytest.mark.asyncio
async def test_hermes_adapter_excludes_env_injected_kanban_tools(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HERMES_KANBAN_TASK", "task-001")
    CapturingAgent.calls = []
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=CapturingAgent,
    )

    [event async for event in adapter.stream(request, resolved, "run-1")]

    from model_tools import get_tool_definitions

    kwargs = CapturingAgent.calls[0]
    definitions = get_tool_definitions(
        enabled_toolsets=kwargs["enabled_toolsets"],
        disabled_toolsets=kwargs.get("disabled_toolsets"),
        quiet_mode=True,
    )
    tool_names = [tool["function"]["name"] for tool in definitions]

    assert all(not name.startswith("kanban_") for name in tool_names)


@pytest.mark.asyncio
async def test_hermes_adapter_clears_kanban_worker_env_during_agent_run(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HERMES_KANBAN_TASK", "task-001")
    KanbanEnvProbeAgent.seen_in_init = "unset"
    KanbanEnvProbeAgent.seen_in_run = "unset"
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=KanbanEnvProbeAgent,
    )

    [event async for event in adapter.stream(request, resolved, "run-1")]

    assert KanbanEnvProbeAgent.seen_in_init is None
    assert KanbanEnvProbeAgent.seen_in_run is None
    assert __import__("os").environ["HERMES_KANBAN_TASK"] == "task-001"


@pytest.mark.asyncio
async def test_hermes_adapter_installs_lingneng_activity_tracker(tmp_path):
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=SideEffectingActivityAgent,
    )

    [event async for event in adapter.stream(request, resolved, "run-1")]

    agent = adapter._last_agent_for_tests
    assert agent._last_activity_desc == "probe"
    assert agent._last_activity_ts > 0.0
