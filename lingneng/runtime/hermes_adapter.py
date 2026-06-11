from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import threading
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, cast

from run_agent import AIAgent

from lingneng.config.settings import LingNengSettings
from lingneng.context.prompt import compose_lingneng_ephemeral_prompt
from lingneng.context.time import CurrentTimeContext, TimeContextService
from lingneng.events.bridge import (
    agent_step_completed,
    agent_step_skipped,
    agent_step_started,
    artifact_events_from_tool_result,
    answer_delta,
    dedupe_artifacts,
    dedupe_citations,
    final_answer,
    is_artifact_producing_tool,
    rag_events_from_tool_result,
    route_events_from_tool_result,
    run_started,
)
from lingneng.routing.store import LingNengRoutePendingStore
from lingneng.runtime.agent_adapter import LingNengStreamEvent
from lingneng.schemas.chat_events import AgentStepEvent, AnswerDeltaEvent, ErrorEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.hermes_session import LingNengHermesSessionStore
from lingneng.session.keys import ResolvedSessionKey
from lingneng.skills.loader import LingNengSkillLoader
from lingneng.tools.attachment_provider import build_attachment_processing_provider
from lingneng.tools.attachments import (
    AttachmentProcessingProvider,
    AttachmentPromptContext,
    attachment_processing_context,
    build_attachment_prompt_context,
)
from lingneng.tools.employee_handoff import (
    build_handoff_request_context,
    employee_handoff_context,
)
from lingneng.tools.chart_visualization import chart_visualization_context
from lingneng.tools.document_generation import document_generation_context
from lingneng.tools.image_generation import image_generation_context
from lingneng.tools.limits import tool_run_guard_context
from lingneng.tools.providers import build_lingneng_tool_providers
from lingneng.tools.rag import (
    HttpRagProvider,
    build_rag_request_context,
    rag_request_context,
)
from lingneng.tools.skill_tools import skill_tool_context
from lingneng.tools.web_search import web_search_context


_KANBAN_ENV_KEYS = (
    "HERMES_KANBAN_TASK",
    "HERMES_KANBAN_BOARD",
    "HERMES_KANBAN_DB",
    "HERMES_KANBAN_WORKSPACE",
    "HERMES_KANBAN_WORKSPACES_ROOT",
)
_KANBAN_ENV_LOCK = threading.RLock()
_KANBAN_ENV_ISOLATION_ACTIVE = False
_MINIMAL_RAG_GUIDANCE = (
    "Use retrieve_rag for internal learned business knowledge that needs factual "
    "support. Do not use it for realtime public facts."
)
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ThreadResult:
    final_response: str = ""
    error: BaseException | None = None


@contextlib.contextmanager
def _without_kanban_worker_env():
    global _KANBAN_ENV_ISOLATION_ACTIVE

    if (
        not _KANBAN_ENV_ISOLATION_ACTIVE
        and not any(key in os.environ for key in _KANBAN_ENV_KEYS)
    ):
        yield
        return

    with _KANBAN_ENV_LOCK:
        saved = {key: os.environ.get(key) for key in _KANBAN_ENV_KEYS}
        _KANBAN_ENV_ISOLATION_ACTIVE = True
        for key in _KANBAN_ENV_KEYS:
            os.environ.pop(key, None)
        try:
            yield
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            _KANBAN_ENV_ISOLATION_ACTIVE = False


def _install_lingneng_activity_tracker(agent: Any) -> None:
    if not hasattr(agent, "_touch_activity"):
        return

    def _touch_activity(desc: str) -> None:
        agent._last_activity_ts = time.time()
        agent._last_activity_desc = desc

    agent._touch_activity = _touch_activity


def _model_config_selection() -> tuple[str | None, str | None]:
    try:
        from hermes_cli.config import load_config

        config = load_config()
    except Exception:
        return None, None

    model_config = config.get("model") if isinstance(config, dict) else None
    if isinstance(model_config, str):
        model = model_config.strip()
        return None, model or None
    if not isinstance(model_config, dict):
        return None, None

    provider = str(model_config.get("provider") or "").strip() or None
    model = (
        str(model_config.get("default") or model_config.get("model") or "").strip()
        or None
    )
    return provider, model


def _resolved_agent_runtime_kwargs() -> dict[str, Any]:
    provider, model = _model_config_selection()
    try:
        from hermes_cli.runtime_provider import resolve_runtime_provider

        runtime = resolve_runtime_provider(
            requested=provider,
            target_model=model,
        )
    except Exception:
        return {}

    kwargs: dict[str, Any] = {}
    resolved_model = runtime.get("model") or model
    if resolved_model:
        kwargs["model"] = resolved_model
    for source_key, target_key in (
        ("provider", "provider"),
        ("base_url", "base_url"),
        ("api_key", "api_key"),
        ("api_mode", "api_mode"),
    ):
        value = runtime.get(source_key)
        if value:
            kwargs[target_key] = value
    return kwargs


def _build_route_pending_store(
    settings: LingNengSettings,
) -> LingNengRoutePendingStore | None:
    if settings.route_pending_db_path is None:
        return None
    try:
        return LingNengRoutePendingStore(
            settings.route_pending_db_path,
            ttl_seconds=settings.route_pending_ttl_seconds,
        )
    except Exception:
        _LOGGER.warning(
            "LingNeng route pending store unavailable; route confirmations "
            "will not be persisted."
        )
        return None


def _build_attachment_provider(
    settings: LingNengSettings,
) -> AttachmentProcessingProvider | None:
    try:
        return build_attachment_processing_provider(settings)
    except Exception:
        _LOGGER.warning(
            "LingNeng attachment provider construction failed; provider disabled."
        )
        return None


class HermesAgentRunAdapter:
    def __init__(
        self,
        settings: LingNengSettings,
        agent_cls: type = AIAgent,
        session_store: LingNengHermesSessionStore | None = None,
        time_context_service: TimeContextService | None = None,
    ) -> None:
        self.settings = settings
        self.agent_cls = agent_cls
        self.session_store = session_store or LingNengHermesSessionStore(settings)
        self.skill_loader = LingNengSkillLoader(settings)
        self.time_context_service = time_context_service
        self._last_agent_for_tests: Any | None = None

    async def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[LingNengStreamEvent]:
        yield run_started(run_id=run_id, request_id=request.request_id)

        queue: asyncio.Queue[LingNengStreamEvent | _ThreadResult]
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        sequence = 0
        tool_sequence = 0
        tool_progress_lock = threading.Lock()
        streamed_text: list[str] = []
        rag_citations: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        route_trace: dict[str, Any] | None = None
        buffered_answer_events: list[AnswerDeltaEvent] = []
        active_artifact_tools = 0
        answer_flush_scheduled = False
        time_context = _build_time_context(
            self.time_context_service,
            self.settings,
            request,
        )
        time_context_prompt = _time_context_prompt_text(self.settings, time_context)
        trace_time_context = time_context if time_context_prompt else None

        def on_delta(text: str | None) -> None:
            nonlocal sequence
            if not text:
                return
            with tool_progress_lock:
                sequence += 1
                streamed_text.append(text)
                buffered_answer_events.append(
                    answer_delta(text=text, sequence=sequence)
                )
                schedule_answer_flush_locked()

        def schedule_answer_flush_locked() -> None:
            nonlocal answer_flush_scheduled
            if answer_flush_scheduled:
                return
            answer_flush_scheduled = True
            loop.call_soon_threadsafe(defer_answer_flush)

        def defer_answer_flush() -> None:
            loop.call_soon(flush_pending_answer_events_if_ready)

        def flush_pending_answer_events_if_ready() -> None:
            nonlocal answer_flush_scheduled
            with tool_progress_lock:
                answer_flush_scheduled = False
                if active_artifact_tools or not buffered_answer_events:
                    return
                events = list(buffered_answer_events)
                buffered_answer_events.clear()
            for event in events:
                queue.put_nowait(event)

        def on_tool_progress(
            event_name: str,
            tool_name: str,
            preview: str | None = None,
            args: dict | None = None,
            **kwargs,
        ) -> None:
            nonlocal active_artifact_tools, route_trace, tool_sequence
            with tool_progress_lock:
                events: list[LingNengStreamEvent]
                if event_name == "tool.started":
                    tool_sequence += 1
                    if is_artifact_producing_tool(tool_name):
                        active_artifact_tools += 1
                    event = agent_step_started(
                        sequence=tool_sequence,
                        tool_name=tool_name,
                        preview=preview,
                    )
                    events = [event]
                elif event_name == "tool.completed":
                    tool_sequence += 1
                    event = agent_step_completed(
                        sequence=tool_sequence,
                        tool_name=tool_name,
                        duration=kwargs.get("duration"),
                        is_error=bool(kwargs.get("is_error")),
                        result=kwargs.get("result"),
                    )
                    rag_events, citations = rag_events_from_tool_result(
                        tool_name=tool_name,
                        result=kwargs.get("result"),
                        include_citations=request.stream_options.include_citations,
                        include_rag_context=request.stream_options.include_rag_context,
                    )
                    if citations:
                        rag_citations[:] = dedupe_citations(
                            [*rag_citations, *citations]
                        )
                    artifact_events = []
                    new_artifacts = []
                    if not bool(kwargs.get("is_error")):
                        artifact_events, new_artifacts = (
                            artifact_events_from_tool_result(
                                tool_name=tool_name,
                                result=kwargs.get("result"),
                                settings=self.settings,
                            )
                        )
                    if new_artifacts:
                        artifacts[:] = dedupe_artifacts(
                            [*artifacts, *new_artifacts]
                        )
                    route_events, next_route_trace = (
                        route_events_from_tool_result(
                            tool_name=tool_name,
                            result=kwargs.get("result"),
                        )
                    )
                    if next_route_trace is not None:
                        route_trace = next_route_trace
                    events = cast(
                        list[LingNengStreamEvent],
                        [event, *artifact_events, *rag_events, *route_events],
                    )
                    if is_artifact_producing_tool(tool_name):
                        active_artifact_tools = max(0, active_artifact_tools - 1)
                        if active_artifact_tools == 0 and buffered_answer_events:
                            events.extend(buffered_answer_events)
                            buffered_answer_events.clear()
                elif event_name in {"tool.skipped", "tool.blocked"}:
                    tool_sequence += 1
                    event = agent_step_skipped(
                        sequence=tool_sequence,
                        tool_name=tool_name,
                        reason=kwargs.get("reason"),
                    )
                    events = [event]
                    if is_artifact_producing_tool(tool_name):
                        active_artifact_tools = max(0, active_artifact_tools - 1)
                        if active_artifact_tools == 0 and buffered_answer_events:
                            events.extend(buffered_answer_events)
                            buffered_answer_events.clear()
                else:
                    return
                for event in events:
                    loop.call_soon_threadsafe(queue.put_nowait, event)

        def run_agent() -> _ThreadResult:
            try:
                with _without_kanban_worker_env():
                    active_session_id = self.session_store.resolve_active_session_id(
                        resolved_session
                    )
                    history = (
                        self.session_store.load_conversation_history_for_session_id(
                            active_session_id
                        )
                    )
                    handoff_context = build_handoff_request_context(
                        settings=self.settings,
                        request=request,
                        resolved_session=resolved_session,
                        pending_store=_build_route_pending_store(self.settings),
                    )
                    providers = build_lingneng_tool_providers(self.settings)
                    attachment_provider = _build_attachment_provider(self.settings)
                    with (
                        web_search_context(
                            self.settings,
                            provider=providers.web_search,
                        ),
                        document_generation_context(
                            self.settings,
                            provider=providers.document_generation,
                        ),
                        image_generation_context(
                            self.settings,
                            provider=providers.image_generation,
                        ),
                        chart_visualization_context(
                            self.settings,
                            provider=providers.chart_visualization,
                        ),
                        tool_run_guard_context(self.settings),
                        skill_tool_context(self.settings),
                        employee_handoff_context(handoff_context),
                        attachment_processing_context(provider=attachment_provider),
                    ):
                        _emit_attachment_started(
                            request=request,
                            on_tool_progress=on_tool_progress,
                        )
                        attachment_context = build_attachment_prompt_context(
                            self.settings,
                            request,
                        )
                        _emit_attachment_finished(
                            attachment_context,
                            request=request,
                            on_tool_progress=on_tool_progress,
                        )
                        ephemeral_system_prompt = _compose_ephemeral_system_message(
                            settings=self.settings,
                            trusted_runtime_context=time_context_prompt,
                            attachment_prompt=attachment_context.prompt_text,
                        )
                        agent = self._build_agent(
                            resolved_session,
                            active_session_id=active_session_id,
                            stream_delta_callback=on_delta,
                            tool_progress_callback=on_tool_progress,
                            ephemeral_system_prompt=ephemeral_system_prompt,
                        )
                        self._last_agent_for_tests = agent
                        rag_context = build_rag_request_context(
                            settings=self.settings,
                            request=request,
                            resolved_session=resolved_session,
                        )
                        with rag_request_context(
                            rag_context,
                            provider=_safe_build_rag_provider(self.settings),
                        ):
                            result = agent.run_conversation(
                                request.query.content,
                                system_message=self._build_system_message(request),
                                conversation_history=history,
                                task_id=run_id,
                                persist_user_message=request.query.content,
                            )
                return _ThreadResult(
                    final_response=_final_response_from_result(result)
                )
            except BaseException as exc:
                return _ThreadResult(error=exc)

        task = asyncio.create_task(asyncio.to_thread(run_agent))

        while True:
            if task.done() and queue.empty():
                result = task.result()
                if result.error is not None:
                    yield _public_runtime_error(run_id, request.request_id)
                    return
                final_text = result.final_response
                with tool_progress_lock:
                    pending_answer_events = list(buffered_answer_events)
                    buffered_answer_events.clear()
                    active_artifact_tools = 0
                    answer_flush_scheduled = False
                    final_route_trace = dict(route_trace) if route_trace else None
                for event in pending_answer_events:
                    yield event
                if not streamed_text:
                    sequence += 1
                    yield answer_delta(text=final_text, sequence=sequence)
                trace_summary: dict[str, Any] = {}
                if trace_time_context is not None:
                    trace_summary["time_context"] = trace_time_context.trace_summary()
                if final_route_trace:
                    trace_summary["route"] = final_route_trace
                yield final_answer(
                    run_id=run_id,
                    answer=final_text,
                    citations=(
                        rag_citations
                        if request.stream_options.include_citations
                        else []
                    ),
                    artifacts=artifacts,
                    settings=self.settings,
                    trace_summary=trace_summary,
                )
                return

            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.05)
            except asyncio.TimeoutError:
                continue
            yield item

    def _build_agent(
        self,
        resolved_session: ResolvedSessionKey,
        active_session_id: str | None = None,
        stream_delta_callback=None,
        tool_progress_callback=None,
        ephemeral_system_prompt: str = "",
    ):
        import lingneng.tools.toolset  # noqa: F401

        agent = self.agent_cls(
            **_resolved_agent_runtime_kwargs(),
            platform="lingneng",
            session_id=active_session_id or resolved_session.session_key,
            session_db=self.session_store.db,
            ephemeral_system_prompt=ephemeral_system_prompt,
            enabled_toolsets=["lingneng"],
            disabled_toolsets=["kanban"],
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            stream_delta_callback=stream_delta_callback,
            tool_progress_callback=tool_progress_callback,
        )
        _install_lingneng_activity_tracker(agent)
        return agent

    def _build_system_message(
        self,
        request: ChatStreamRequest,
    ) -> str:
        skill_prompt = _skill_prompt_text(self.skill_loader, request)
        return _compose_system_message(
            request.system_prompt.content,
            skill_prompt,
        )


def _final_response_from_result(result: Any) -> str:
    if isinstance(result, dict):
        value = result.get("final_response")
        return value if isinstance(value, str) else ""
    return ""


def _build_rag_provider(settings: LingNengSettings) -> HttpRagProvider | None:
    if not settings.rag_endpoint.strip():
        return None
    return HttpRagProvider(settings)


def _safe_build_rag_provider(settings: LingNengSettings) -> HttpRagProvider | None:
    try:
        return _build_rag_provider(settings)
    except Exception:
        _LOGGER.warning(
            "LingNeng RAG provider construction failed; provider disabled."
        )
        return None


def _build_time_context(
    service: TimeContextService | None,
    settings: LingNengSettings,
    request: ChatStreamRequest,
) -> CurrentTimeContext | None:
    if not settings.time_context_enabled:
        return None
    try:
        resolved_service = service or TimeContextService(settings)
        return resolved_service.build(request)
    except Exception:
        _LOGGER.warning(
            "LingNeng time context unavailable; continuing without time context."
        )
        return None


def _time_context_prompt_text(
    settings: LingNengSettings,
    time_context: CurrentTimeContext | None,
) -> str:
    if time_context is None:
        return ""
    try:
        return time_context.to_prompt_text(
            max_events=settings.time_context_max_events,
            max_chars=settings.time_context_prompt_max_chars,
        )
    except Exception:
        _LOGGER.warning(
            "LingNeng time context prompt unavailable; continuing without time context."
        )
        return ""


def _public_runtime_error(run_id: str, request_id: str) -> ErrorEvent:
    return ErrorEvent(
        run_id=run_id,
        request_id=request_id,
        code="RUNTIME_ERROR",
        message="Agent runtime failed",
        trace_id=f"trace_{uuid.uuid4().hex}",
        recoverable=False,
    )


def _skill_prompt_text(
    skill_loader: LingNengSkillLoader,
    request: ChatStreamRequest,
) -> str:
    try:
        return skill_loader.build_prompt_context(request).to_prompt_text()
    except Exception:
        return (
            "## LingNeng Skill Context\n\n"
            "### Skill Warnings\n"
            "- SKILL_CONTEXT_UNAVAILABLE: Skill prompt context could not be loaded."
        )


def _emit_attachment_started(
    *,
    request: ChatStreamRequest,
    on_tool_progress,
) -> None:
    if not request.attachments:
        return
    on_tool_progress(
        "tool.started",
        "attachment_processing",
        None,
        {"attachment_count": len(request.attachments)},
    )


def _emit_attachment_finished(
    attachment_context: AttachmentPromptContext,
    *,
    request: ChatStreamRequest,
    on_tool_progress,
) -> None:
    if not request.attachments:
        return
    if attachment_context.status == "succeeded":
        on_tool_progress(
            "tool.completed",
            "attachment_processing",
            None,
            None,
            is_error=False,
            result=None,
        )
        return
    if attachment_context.status == "failed":
        on_tool_progress(
            "tool.completed",
            "attachment_processing",
            None,
            None,
            is_error=True,
            result=None,
        )
        return
    on_tool_progress(
        "tool.skipped",
        "attachment_processing",
        None,
        None,
        reason="attachment_context_unavailable",
    )


def _compose_system_message(
    base_prompt: str,
    skill_prompt: str,
) -> str:
    parts = [base_prompt.strip()]
    if skill_prompt.strip():
        parts.append(skill_prompt.strip())
    return "\n\n".join(part for part in parts if part)


def _compose_ephemeral_system_message(
    *,
    settings: LingNengSettings,
    trusted_runtime_context: str = "",
    attachment_prompt: str = "",
) -> str:
    return compose_lingneng_ephemeral_prompt(
        trusted_runtime_context=trusted_runtime_context,
        untrusted_request_context=attachment_prompt,
        tool_public_guidance=_MINIMAL_RAG_GUIDANCE,
        max_section_chars=settings.prompt_section_max_chars,
    )
