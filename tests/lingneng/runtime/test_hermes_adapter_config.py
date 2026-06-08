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
from lingneng.schemas.chat_events import AgentStepEvent, FinalEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from lingneng.session.run_store import LingNengRunStore
from lingneng.tools.attachments import (
    AttachmentProcessingResult,
    attachment_processing_context,
)
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


@pytest.mark.asyncio
async def test_hermes_adapter_passes_resolved_runtime_config_to_agent(
    tmp_path,
    monkeypatch,
):
    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    (hermes_home / "config.yaml").write_text(
        "\n".join(
            [
                "model:",
                "  provider: custom:lingneng-dev-llm",
                "  default: qwen3.6-35b-a3b",
                "  base_url: http://172.16.10.10:18400/v1",
                "  api_mode: chat_completions",
                "custom_providers:",
                "  - name: lingneng-dev-llm",
                "    base_url: http://172.16.10.10:18400/v1",
                "    model: qwen3.6-35b-a3b",
                "    key_env: OPENAI_API_KEY",
                "    api_mode: chat_completions",
                "",
            ]
        )
    )
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-runtime-key")
    CapturingAgent.calls = []
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=CapturingAgent,
    )

    [event async for event in adapter.stream(request, resolved, "run-1")]

    kwargs = CapturingAgent.calls[0]
    assert kwargs["model"] == "qwen3.6-35b-a3b"
    assert kwargs["provider"] == "custom"
    assert kwargs["base_url"] == "http://172.16.10.10:18400/v1"
    assert kwargs["api_mode"] == "chat_completions"
    assert kwargs["api_key"] == "sk-test-runtime-key"


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
    ephemeral_system_prompt_seen = ""
    init_kwargs_seen: dict = {}

    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")
        type(self).ephemeral_system_prompt_seen = (
            kwargs.get("ephemeral_system_prompt") or ""
        )
        type(self).init_kwargs_seen = kwargs

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


class PersistingSystemPromptAgent(RecordingSystemPromptAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session_db = kwargs["session_db"]
        self.session_id = kwargs["session_id"]

    def run_conversation(
        self,
        user_message,
        system_message=None,
        conversation_history=None,
        task_id=None,
        stream_callback=None,
        persist_user_message=None,
    ):
        self.session_db.ensure_session(self.session_id, source="lingneng-test")
        self.session_db.update_system_prompt(self.session_id, system_message or "")
        return super().run_conversation(
            user_message,
            system_message=system_message,
            conversation_history=conversation_history,
            task_id=task_id,
            stream_callback=stream_callback,
            persist_user_message=persist_user_message,
        )


class FakeAttachmentProvider:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def process(self, request):
        self.requests.append(request)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class BlockingAttachmentProvider:
    def __init__(self) -> None:
        self.entered = threading.Event()
        self.finished = threading.Event()
        self.release = threading.Event()

    def process(self, request):
        self.entered.set()
        if not self.release.wait(timeout=5):
            raise AssertionError("blocking attachment provider was not released")
        self.finished.set()
        return AttachmentProcessingResult(
            context_text="当前附件摘要",
            selected_count=1,
            processed_count=1,
        )


def effective_system_prompt(agent_cls=RecordingSystemPromptAgent) -> str:
    parts = [
        agent_cls.system_message_seen.strip(),
        agent_cls.ephemeral_system_prompt_seen.strip(),
    ]
    return "\n\n".join(part for part in parts if part)


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


class ConcurrentNoKanbanEnvAgent:
    lock = threading.Lock()
    calls = 0
    first_started = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()

    @classmethod
    def reset(cls) -> None:
        with cls.lock:
            cls.calls = 0
        cls.first_started = threading.Event()
        cls.release_first = threading.Event()
        cls.second_started = threading.Event()

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
        with self.lock:
            type(self).calls += 1
            call_index = type(self).calls

        if call_index == 1:
            type(self).first_started.set()
            if not type(self).release_first.wait(timeout=5):
                raise AssertionError("first run was not released")
            return {"final_response": "first", "messages": []}

        type(self).second_started.set()
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
async def test_hermes_adapter_reuses_skill_loader_instance(tmp_path, monkeypatch):
    class CountingPromptContext:
        def to_prompt_text(self):
            return ""

    class CountingSkillLoader:
        instances = []

        def __init__(self, settings):
            self.settings = settings
            self.build_request_ids = []
            type(self).instances.append(self)

        def build_prompt_context(self, request):
            self.build_request_ids.append(request.request_id)
            return CountingPromptContext()

    monkeypatch.setattr(
        hermes_adapter_module,
        "LingNengSkillLoader",
        CountingSkillLoader,
    )
    first_request = ChatStreamRequest.model_validate(full_payload())
    second_payload = full_payload()
    second_payload["request_id"] = "req-second"
    second_request = ChatStreamRequest.model_validate(second_payload)
    resolved = resolve_session_key(first_request)

    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=RecordingSystemPromptAgent,
    )

    assert len(CountingSkillLoader.instances) == 1
    [event async for event in adapter.stream(first_request, resolved, "run-1")]
    [event async for event in adapter.stream(second_request, resolved, "run-2")]

    assert len(CountingSkillLoader.instances) == 1
    assert CountingSkillLoader.instances[0].build_request_ids == [
        first_request.request_id,
        second_request.request_id,
    ]


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
    prompt = effective_system_prompt()
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
async def test_attachment_context_is_added_to_current_system_prompt_only(
    tmp_path,
):
    payload = full_payload()
    payload["history"] = [
        {
            "message_id": "h-history",
            "role": "user",
            "content": "history content marker",
        }
    ]
    payload["attachments"] = [
        {
            "file_id": "file-1",
            "file_name": "menu.pdf",
            "mime_type": "application/pdf",
            "size": 100,
            "download_url": "https://files.example.test/menu.pdf",
        }
    ]
    request = ChatStreamRequest.model_validate(payload)
    second_payload = full_payload()
    second_payload["request_id"] = "req-no-attachment"
    second_payload["attachments"] = []
    second_request = ChatStreamRequest.model_validate(second_payload)
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(
            tmp_path,
            LINGNENG_AGENT_MODE="hermes",
            LINGNENG_ATTACHMENT_ALLOWED_HOSTS="files.example.test",
        ),
        agent_cls=RecordingSystemPromptAgent,
    )
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(
            context_text="当前附件摘要",
            selected_count=1,
            processed_count=1,
        )
    )
    RecordingSystemPromptAgent.system_message_seen = ""

    with attachment_processing_context(provider=provider):
        events = [event async for event in adapter.stream(request, resolved, "run-1")]
    first_system_prompt = RecordingSystemPromptAgent.system_message_seen
    first_ephemeral_prompt = RecordingSystemPromptAgent.ephemeral_system_prompt_seen
    first_prompt = effective_system_prompt()
    [event async for event in adapter.stream(second_request, resolved, "run-2")]
    second_system_prompt = RecordingSystemPromptAgent.system_message_seen
    second_ephemeral_prompt = RecordingSystemPromptAgent.ephemeral_system_prompt_seen
    second_prompt = effective_system_prompt()

    assert isinstance(events[-1], FinalEvent)
    assert "当前附件摘要" in first_prompt
    assert "## LingNeng Current Request Attachments" in first_prompt
    assert "当前附件摘要" not in first_system_prompt
    assert "## LingNeng Current Request Attachments" not in first_system_prompt
    assert "## LingNeng RAG Guidance" not in first_system_prompt
    assert "当前附件摘要" in first_ephemeral_prompt
    assert "## LingNeng Current Request Attachments" in first_ephemeral_prompt
    assert "## LingNeng RAG Guidance" in first_ephemeral_prompt
    assert "history content marker" not in first_prompt
    assert "当前附件摘要" not in second_prompt
    assert "## LingNeng Current Request Attachments" not in second_prompt
    assert "## LingNeng RAG Guidance" not in second_system_prompt
    assert "## LingNeng RAG Guidance" in second_ephemeral_prompt
    assert [req.attachments[0].file_id for req in provider.requests] == ["file-1"]


@pytest.mark.asyncio
async def test_attachment_context_is_not_persisted_in_session_system_prompt(tmp_path):
    payload = full_payload()
    payload["attachments"] = [
        {
            "file_id": "file-1",
            "file_name": "menu.pdf",
            "mime_type": "application/pdf",
            "size": 100,
            "download_url": "https://files.example.test/menu.pdf",
        }
    ]
    request = ChatStreamRequest.model_validate(payload)
    second_payload = full_payload()
    second_payload["request_id"] = "req-no-attachment"
    second_payload["attachments"] = []
    second_request = ChatStreamRequest.model_validate(second_payload)
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(
            tmp_path,
            LINGNENG_AGENT_MODE="hermes",
            LINGNENG_ATTACHMENT_ALLOWED_HOSTS="files.example.test",
        ),
        agent_cls=PersistingSystemPromptAgent,
    )
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(
            context_text="当前附件摘要",
            selected_count=1,
            processed_count=1,
        )
    )

    with attachment_processing_context(provider=provider):
        [event async for event in adapter.stream(request, resolved, "run-1")]
    stored_prompt = adapter.session_store.db.get_session(resolved.session_key)[
        "system_prompt"
    ]
    [event async for event in adapter.stream(second_request, resolved, "run-2")]
    second_prompt = effective_system_prompt(PersistingSystemPromptAgent)

    assert "## LingNeng Current Request Attachments" not in stored_prompt
    assert "当前附件摘要" not in stored_prompt
    assert "## LingNeng RAG Guidance" not in stored_prompt
    assert "## LingNeng Current Request Attachments" not in second_prompt
    assert "当前附件摘要" not in second_prompt


@pytest.mark.asyncio
async def test_attachment_prompt_section_order_is_after_skill_before_rag(tmp_path):
    skill_root = tmp_path / "skills"
    write_skill(
        skill_root,
        "employee-marketing-content-creator",
        kind="employee_base",
        employee_type="marketing_content_creator",
        display_name="内容创意师",
        body="## Role Identity\n你是内容创意师。",
    )
    payload = full_payload()
    payload["attachments"] = [
        {
            "file_id": "file-1",
            "file_name": "menu.pdf",
            "mime_type": "application/pdf",
            "size": 100,
            "download_url": "https://files.example.test/menu.pdf",
        }
    ]
    request = ChatStreamRequest.model_validate(payload)
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(
            tmp_path / "runtime",
            LINGNENG_AGENT_MODE="hermes",
            LINGNENG_ATTACHMENT_ALLOWED_HOSTS="files.example.test",
            LINGNENG_SKILL_ROOTS=str(skill_root),
        ),
        agent_cls=RecordingSystemPromptAgent,
    )
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(
            context_text="当前附件摘要",
            selected_count=1,
            processed_count=1,
        )
    )
    RecordingSystemPromptAgent.system_message_seen = ""

    with attachment_processing_context(provider=provider):
        [event async for event in adapter.stream(request, resolved, "run-1")]

    prompt = effective_system_prompt()
    skill_index = prompt.index("## LingNeng Skill Context")
    attachment_index = prompt.index("## LingNeng Current Request Attachments")
    rag_index = prompt.index("## LingNeng RAG Guidance")
    assert skill_index < attachment_index < rag_index


@pytest.mark.asyncio
async def test_attachment_processing_emits_started_and_completed_steps(tmp_path):
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(
            tmp_path,
            LINGNENG_AGENT_MODE="hermes",
            LINGNENG_ATTACHMENT_ALLOWED_HOSTS="files.example.test",
        ),
        agent_cls=RecordingSystemPromptAgent,
    )
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(
            context_text="当前附件摘要",
            selected_count=1,
            processed_count=1,
        )
    )

    with attachment_processing_context(provider=provider):
        events = [event async for event in adapter.stream(request, resolved, "run-1")]

    attachment_steps = [
        event
        for event in events
        if isinstance(event, AgentStepEvent) and event.title == "attachment_processing"
    ]
    assert [event.status for event in attachment_steps] == ["started", "succeeded"]


@pytest.mark.asyncio
async def test_attachment_started_step_streams_before_provider_finishes(tmp_path):
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(
            tmp_path,
            LINGNENG_AGENT_MODE="hermes",
            LINGNENG_ATTACHMENT_ALLOWED_HOSTS="files.example.test",
            LINGNENG_ATTACHMENT_TIMEOUT_SECONDS="5",
        ),
        agent_cls=RecordingSystemPromptAgent,
    )
    provider = BlockingAttachmentProvider()

    with attachment_processing_context(provider=provider):
        stream = adapter.stream(request, resolved, "run-1")
        try:
            await anext(stream)
            started_event = await asyncio.wait_for(anext(stream), timeout=0.25)

            assert isinstance(started_event, AgentStepEvent)
            assert started_event.title == "attachment_processing"
            assert started_event.status == "started"
            assert not provider.finished.is_set()

            provider.release.set()
            remaining = [event async for event in stream]
        finally:
            provider.release.set()
            await stream.aclose()

    attachment_steps = [
        event
        for event in remaining
        if isinstance(event, AgentStepEvent) and event.title == "attachment_processing"
    ]
    assert [event.status for event in attachment_steps] == ["succeeded"]


@pytest.mark.asyncio
async def test_attachment_processing_emits_started_and_skipped_steps(tmp_path):
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(
            tmp_path,
            LINGNENG_AGENT_MODE="hermes",
            LINGNENG_ATTACHMENT_ALLOWED_HOSTS="files.example.test",
        ),
        agent_cls=RecordingSystemPromptAgent,
    )

    events = [event async for event in adapter.stream(request, resolved, "run-1")]

    attachment_steps = [
        event
        for event in events
        if isinstance(event, AgentStepEvent) and event.title == "attachment_processing"
    ]
    assert [event.status for event in attachment_steps] == ["started", "skipped"]


@pytest.mark.asyncio
async def test_attachment_processing_emits_started_and_failed_steps(tmp_path):
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(
            tmp_path,
            LINGNENG_AGENT_MODE="hermes",
            LINGNENG_ATTACHMENT_ALLOWED_HOSTS="files.example.test",
        ),
        agent_cls=RecordingSystemPromptAgent,
    )
    provider = FakeAttachmentProvider(
        RuntimeError("traceback secret-token /Users/rotas/private")
    )

    with attachment_processing_context(provider=provider):
        events = [event async for event in adapter.stream(request, resolved, "run-1")]

    attachment_steps = [
        event
        for event in events
        if isinstance(event, AgentStepEvent) and event.title == "attachment_processing"
    ]
    assert [event.status for event in attachment_steps] == ["started", "failed"]
    dumped = "".join(event.model_dump_json() for event in attachment_steps)
    assert "secret-token" not in dumped
    assert "/Users/rotas" not in dumped


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
    kwargs = CapturingAgent.calls[0]
    assert agent.run_args["user_message"] == request.query.content
    assert agent.run_args["system_message"].startswith(request.system_prompt.content)
    assert "## LingNeng RAG Guidance" not in agent.run_args["system_message"]
    assert "## LingNeng RAG Guidance" in kwargs["ephemeral_system_prompt"]
    assert "Java 历史" not in agent.run_args["system_message"]
    assert "Java 历史" not in kwargs["ephemeral_system_prompt"]
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
async def test_hermes_adapter_does_not_serialize_runs_when_kanban_env_absent(
    tmp_path,
    monkeypatch,
):
    for key in hermes_adapter_module._KANBAN_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    ConcurrentNoKanbanEnvAgent.reset()
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    first_runtime_dir = tmp_path / "first"
    second_runtime_dir = tmp_path / "second"
    first_runtime_dir.mkdir()
    second_runtime_dir.mkdir()
    first_adapter = HermesAgentRunAdapter(
        settings=settings(first_runtime_dir, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=ConcurrentNoKanbanEnvAgent,
    )
    second_adapter = HermesAgentRunAdapter(
        settings=settings(second_runtime_dir, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=ConcurrentNoKanbanEnvAgent,
    )

    async def collect(adapter, run_id):
        return [event async for event in adapter.stream(request, resolved, run_id)]

    first_task = asyncio.create_task(collect(first_adapter, "run-1"))
    assert await asyncio.to_thread(
        ConcurrentNoKanbanEnvAgent.first_started.wait,
        5,
    )
    second_task = asyncio.create_task(collect(second_adapter, "run-2"))
    second_entered_before_release = await asyncio.to_thread(
        ConcurrentNoKanbanEnvAgent.second_started.wait,
        0.5,
    )
    ConcurrentNoKanbanEnvAgent.release_first.set()
    await first_task
    await second_task

    assert second_entered_before_release is True


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
