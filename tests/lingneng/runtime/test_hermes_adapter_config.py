import asyncio
import subprocess
import sys
import threading

import pytest

import lingneng.runtime.hermes_adapter as hermes_adapter_module
from lingneng.api.app import create_app
from lingneng.config.settings import LingNengSettings
from lingneng.runtime.fake_agent import FakeAgentRunAdapter
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.schemas.chat_events import FinalEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from lingneng.session.run_store import LingNengRunStore
from tests.lingneng.skills.test_skill_loader import write_skill
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


class RecordingSystemPromptAgent:
    system_message_seen = ""

    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")

    def run_conversation(
        self,
        user_message,
        system_message=None,
        conversation_history=None,
        task_id=None,
        stream_callback=None,
        persist_user_message=None,
    ):
        type(self).system_message_seen = system_message or ""
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


class ConcurrentKanbanEnvAgent:
    lock = threading.Lock()
    calls = 0
    first_started = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()
    check_second = threading.Event()
    second_seen_after_first: str | None = "unset"

    @classmethod
    def reset(cls) -> None:
        with cls.lock:
            cls.calls = 0
        cls.first_started = threading.Event()
        cls.release_first = threading.Event()
        cls.second_started = threading.Event()
        cls.check_second = threading.Event()
        cls.second_seen_after_first = "unset"

    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")

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

        with self.lock:
            type(self).calls += 1
            call_index = type(self).calls

        if call_index == 1:
            type(self).first_started.set()
            if not type(self).release_first.wait(timeout=5):
                raise AssertionError("first run was not released")
            return {"final_response": "first", "messages": []}

        type(self).second_started.set()
        if not type(self).check_second.wait(timeout=5):
            raise AssertionError("second run was not checked")
        type(self).second_seen_after_first = os.environ.get("HERMES_KANBAN_TASK")
        return {"final_response": "second", "messages": []}


@pytest.mark.asyncio
async def test_hermes_adapter_constructs_agent_with_lingneng_tool_context(
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
    assert kwargs["enabled_toolsets"] == ["lingneng"]
    assert kwargs["disabled_toolsets"] == ["kanban"]
    assert kwargs["quiet_mode"] is True
    assert kwargs["skip_context_files"] is True
    assert kwargs["skip_memory"] is True
    assert kwargs["session_db"].db_path == tmp_path / "sessions.sqlite3"
    assert events[-1].answer == "完成"


@pytest.mark.asyncio
async def test_hermes_adapter_injects_bounded_skill_prompt(tmp_path):
    skill_root = tmp_path / "skills"
    write_skill(
        skill_root,
        "employee-marketing-content-creator",
        kind="employee_base",
        employee_type="marketing_content_creator",
        display_name="内容创意师",
        body="## Role Identity\n你是内容创意师。",
    )
    write_skill(
        skill_root,
        "marketing-copy-generation",
        body="## When to Use\n写营销内容。",
    )
    payload = full_payload()
    payload["skill"]["skill_id"] = "marketing-copy-generation"
    payload["skill"]["inline"] = {"summary": "INLINE MUST NOT APPEAR"}
    request = ChatStreamRequest.model_validate(payload)
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(
            tmp_path / "runtime",
            LINGNENG_AGENT_MODE="hermes",
            LINGNENG_SKILL_ROOTS=str(skill_root),
        ),
        agent_cls=RecordingSystemPromptAgent,
    )
    RecordingSystemPromptAgent.system_message_seen = ""

    events = [event async for event in adapter.stream(request, resolved, "run-1")]

    assert isinstance(events[-1], FinalEvent)
    prompt = RecordingSystemPromptAgent.system_message_seen
    java_index = prompt.index("你是灵能营销内容员工。")
    skill_index = prompt.index("## LingNeng Skill Context")
    rag_index = prompt.index("## LingNeng RAG Guidance")
    assert java_index < skill_index < rag_index
    assert "employee-marketing-content-creator" in prompt
    assert "marketing-copy-generation" in prompt
    assert "写营销内容" in prompt
    assert "INLINE MUST NOT APPEAR" not in prompt
    assert "上一轮用户问题" not in prompt


@pytest.mark.asyncio
async def test_hermes_adapter_continues_when_skill_roots_missing(tmp_path):
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(
            tmp_path / "runtime",
            LINGNENG_AGENT_MODE="hermes",
            LINGNENG_SKILL_ROOTS=str(tmp_path / "missing"),
        ),
        agent_cls=RecordingSystemPromptAgent,
    )
    RecordingSystemPromptAgent.system_message_seen = ""

    events = [event async for event in adapter.stream(request, resolved, "run-1")]

    assert isinstance(events[-1], FinalEvent)
    prompt = RecordingSystemPromptAgent.system_message_seen
    assert "你是灵能营销内容员工。" in prompt
    assert "## LingNeng Skill Context" in prompt
    assert "SKILL_ROOT_MISSING" in prompt


@pytest.mark.asyncio
async def test_hermes_adapter_continues_when_skill_loader_errors(
    tmp_path,
    monkeypatch,
):
    class ExplodingSkillLoader:
        def __init__(self, settings):
            self.settings = settings

        def build_prompt_context(self, request):
            raise RuntimeError("private loader detail")

    monkeypatch.setattr(
        hermes_adapter_module,
        "LingNengSkillLoader",
        ExplodingSkillLoader,
        raising=False,
    )
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=RecordingSystemPromptAgent,
    )
    RecordingSystemPromptAgent.system_message_seen = ""

    events = [event async for event in adapter.stream(request, resolved, "run-1")]

    assert isinstance(events[-1], FinalEvent)
    prompt = RecordingSystemPromptAgent.system_message_seen
    assert "你是灵能营销内容员工。" in prompt
    assert "SKILL_CONTEXT_UNAVAILABLE" in prompt
    assert "private loader detail" not in prompt


def test_hermes_adapter_import_does_not_register_lingneng_tools_in_fake_mode():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import lingneng.runtime; "
                "print('lingneng.tools.toolset' in sys.modules)"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.stdout.strip() == "False"


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
    assert agent.run_args["system_message"].startswith(request.system_prompt.content)
    assert "## LingNeng RAG Guidance" in agent.run_args["system_message"]
    assert "Java 历史" not in agent.run_args["system_message"]
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
async def test_hermes_adapter_serializes_kanban_env_isolation(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HERMES_KANBAN_TASK", "task-001")
    ConcurrentKanbanEnvAgent.reset()
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    first_runtime_dir = tmp_path / "first"
    second_runtime_dir = tmp_path / "second"
    first_runtime_dir.mkdir()
    second_runtime_dir.mkdir()
    first_adapter = HermesAgentRunAdapter(
        settings=settings(first_runtime_dir, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=ConcurrentKanbanEnvAgent,
    )
    second_adapter = HermesAgentRunAdapter(
        settings=settings(second_runtime_dir, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=ConcurrentKanbanEnvAgent,
    )

    async def collect(adapter, run_id):
        return [event async for event in adapter.stream(request, resolved, run_id)]

    first_task = asyncio.create_task(collect(first_adapter, "run-1"))
    assert await asyncio.to_thread(
        ConcurrentKanbanEnvAgent.first_started.wait,
        5,
    )

    second_task = asyncio.create_task(collect(second_adapter, "run-2"))
    second_entered_before_release = await asyncio.to_thread(
        ConcurrentKanbanEnvAgent.second_started.wait,
        0.5,
    )
    assert second_entered_before_release is False
    ConcurrentKanbanEnvAgent.release_first.set()
    await first_task
    assert await asyncio.to_thread(
        ConcurrentKanbanEnvAgent.second_started.wait,
        5,
    )

    ConcurrentKanbanEnvAgent.check_second.set()
    await second_task

    assert ConcurrentKanbanEnvAgent.second_seen_after_first is None
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
