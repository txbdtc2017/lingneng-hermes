from __future__ import annotations

from json import JSONDecodeError
import uuid
import time
from collections.abc import AsyncIterator
from typing import Any, NoReturn

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from lingneng.api.auth import ensure_chat_configuration_ready, verify_internal_key
from lingneng.api.sse import encode_sse, with_heartbeats
from lingneng.config.settings import LingNengSettings
from lingneng.observability.logging import (
    build_trace_context,
    build_trace_summary,
    enrich_trace_context,
    log_lingneng_event,
)
from lingneng.runtime.agent_adapter import AgentRunAdapter
from lingneng.schemas.chat_events import (
    AgentStepEvent,
    AnswerDeltaEvent,
    ArtifactCreatedEvent,
    CitationDeltaEvent,
    ErrorEvent,
    FinalEvent,
    RagContextEvent,
    RunStartedEvent,
)
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import ResolvedSessionKey, resolve_session_key
from lingneng.session.run_store import (
    LingNengRunStore,
    RunRecord,
    RunStatus,
    RunStoreStateError,
)


def register_routes(
    app: FastAPI,
    settings: LingNengSettings,
    adapter: AgentRunAdapter,
    run_store: LingNengRunStore,
) -> None:
    @app.get("/internal/agent/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/internal/agent/ready")
    def ready() -> dict[str, object]:
        return settings.ready_summary()

    @app.post("/internal/agent/chat/stream")
    async def chat_stream(
        raw_request: Request,
        x_internal_key: str | None = Header(default=None),
    ) -> StreamingResponse:
        request_started_at = time.monotonic()
        ensure_chat_configuration_ready(settings)
        verify_internal_key(settings, x_internal_key)

        try:
            request = await _parse_chat_request(raw_request)
        except HTTPException:
            _log_pre_stream_failure(
                settings,
                request_started_at,
                error_code="INVALID_CHAT_REQUEST",
            )
            raise

        try:
            resolved = _resolve_chat_session_key(request)
        except HTTPException:
            _log_pre_stream_failure(
                settings,
                request_started_at,
                error_code="INVALID_SESSION_KEY",
                request=request,
            )
            raise
        reservation = run_store.reserve_run(resolved.session_key, request.request_id)
        trace_context = build_trace_context(
            request,
            resolved,
            run_id=reservation.record.run_id,
            agent_mode=settings.agent_mode,
            status=reservation.record.status.value,
            duration_ms=_elapsed_ms(request_started_at),
            active_hermes_session_id=_active_hermes_session_id(adapter, resolved),
        )
        log_lingneng_event("request_accepted", trace_context)

        if not reservation.created:
            stream = _replay_or_duplicate_stream(
                reservation.record,
                request,
                trace_context,
                request_started_at,
            )
        else:
            stream = _adapter_stream(
                adapter,
                run_store,
                request,
                resolved,
                reservation.record.run_id,
                trace_context=trace_context,
                started_at=request_started_at,
            )

        return StreamingResponse(
            with_heartbeats(stream, settings.heartbeat_interval_seconds),
            media_type="text/event-stream",
        )


async def _replay_or_duplicate_stream(
    record: RunRecord,
    request: ChatStreamRequest,
    trace_context: dict[str, Any],
    started_at: float,
) -> AsyncIterator[str]:
    if record.status is RunStatus.RUNNING:
        duplicate_context = enrich_trace_context(
            trace_context,
            status=RunStatus.RUNNING.value,
            duration_ms=_elapsed_ms(started_at),
            error_code="REQUEST_ALREADY_RUNNING",
            recoverable=True,
        )
        log_lingneng_event("request_duplicate", duplicate_context)
        yield _duplicate_error_frame(
            record.run_id,
            request.request_id,
            "REQUEST_ALREADY_RUNNING",
            "Request is already running",
        )
        return

    if record.status is RunStatus.SUCCEEDED:
        answer = record.answer or ""
        replay_context = enrich_trace_context(
            trace_context,
            status=RunStatus.SUCCEEDED.value,
            duration_ms=_elapsed_ms(started_at),
            agent_step_count=0,
            citation_count=len(record.citations),
            artifact_count=len(record.artifacts),
            answer_chars=len(answer),
        )
        log_lingneng_event("request_replayed", replay_context)
        yield encode_sse(
            "run_started",
            RunStartedEvent(run_id=record.run_id, request_id=request.request_id),
        )
        yield encode_sse(
            "answer_delta",
            AnswerDeltaEvent(text=answer, sequence=1),
        )
        yield encode_sse(
            "final",
            FinalEvent(
                run_id=record.run_id,
                status="succeeded",
                answer=answer,
                citations=record.citations,
                artifacts=record.artifacts,
                trace_summary=build_trace_summary(replay_context),
            ),
        )
        return

    failed_context = enrich_trace_context(
        trace_context,
        status=RunStatus.FAILED.value,
        duration_ms=_elapsed_ms(started_at),
        error_code=record.error_code or "RUNTIME_ERROR",
        recoverable=False,
    )
    log_lingneng_event("request_replayed", failed_context)
    yield encode_sse(
        "error",
        ErrorEvent(
            run_id=record.run_id,
            request_id=request.request_id,
            code=record.error_code or "RUNTIME_ERROR",
            message=record.error_message or "Agent runtime failed",
            trace_id=_new_trace_id(),
            recoverable=False,
        ),
    )


def _duplicate_error_frame(
    run_id: str,
    request_id: str,
    code: str,
    message: str,
) -> str:
    return encode_sse(
        "error",
        ErrorEvent(
            run_id=run_id,
            request_id=request_id,
            code=code,
            message=message,
            trace_id=_new_trace_id(),
            recoverable=True,
        ),
    )


async def _adapter_stream(
    adapter: AgentRunAdapter,
    run_store: LingNengRunStore,
    request: ChatStreamRequest,
    resolved: ResolvedSessionKey,
    run_id: str,
    *,
    trace_context: dict[str, Any] | None = None,
    started_at: float | None = None,
) -> AsyncIterator[str]:
    current_run_id = run_id
    terminal_recorded = False
    stream_started_at = time.monotonic() if started_at is None else started_at
    context = trace_context or build_trace_context(
        request,
        resolved,
        run_id=run_id,
        status=RunStatus.RUNNING.value,
        active_hermes_session_id=resolved.session_key,
    )
    agent_step_count = 0
    citation_count = 0
    artifact_count = 0
    answer_chars = 0
    log_lingneng_event(
        "adapter_stream_started",
        enrich_trace_context(
            context,
            status=RunStatus.RUNNING.value,
            duration_ms=_elapsed_ms(stream_started_at),
        ),
    )
    try:
        async for event in adapter.stream(request, resolved, run_id):
            if hasattr(event, "run_id"):
                current_run_id = event.run_id

            if isinstance(event, FinalEvent):
                citation_count = max(citation_count, len(event.citations))
                artifact_count = max(artifact_count, len(event.artifacts))
                answer_chars = max(answer_chars, len(event.answer))
                completed_context = _stream_trace_context(
                    context,
                    started_at=stream_started_at,
                    status=event.status,
                    agent_step_count=agent_step_count,
                    citation_count=citation_count,
                    artifact_count=artifact_count,
                    answer_chars=answer_chars,
                )
                event = event.model_copy(
                    update={"trace_summary": build_trace_summary(completed_context)}
                )
                run_store.mark_succeeded(
                    event.run_id,
                    answer=event.answer,
                    artifacts=event.artifacts,
                    citations=event.citations,
                )
                terminal_recorded = True
                log_lingneng_event("adapter_stream_completed", completed_context)
                yield encode_sse("final", event)
                return

            if isinstance(event, ErrorEvent):
                failed_context = _stream_trace_context(
                    context,
                    started_at=stream_started_at,
                    status=RunStatus.FAILED.value,
                    agent_step_count=agent_step_count,
                    citation_count=citation_count,
                    artifact_count=artifact_count,
                    answer_chars=answer_chars,
                    error_code=event.code,
                    recoverable=event.recoverable,
                )
                _mark_failed_defensively(
                    run_store,
                    event.run_id,
                    event.code,
                    event.message,
                )
                terminal_recorded = True
                log_lingneng_event("adapter_stream_failed", failed_context)
                yield encode_sse("error", event)
                return

            if isinstance(event, AgentStepEvent):
                agent_step_count += 1
            elif isinstance(event, CitationDeltaEvent):
                citation_count += 1
            elif isinstance(event, ArtifactCreatedEvent):
                artifact_count += 1
            elif isinstance(event, AnswerDeltaEvent):
                answer_chars += len(event.text)

            yield encode_sse(_event_name(event), event)

        failed_context = _stream_trace_context(
            context,
            started_at=stream_started_at,
            status=RunStatus.FAILED.value,
            agent_step_count=agent_step_count,
            citation_count=citation_count,
            artifact_count=artifact_count,
            answer_chars=answer_chars,
            error_code="RUNTIME_ERROR",
            recoverable=False,
        )
        _mark_failed_defensively(
            run_store,
            current_run_id,
            "RUNTIME_ERROR",
            "Agent runtime failed",
        )
        terminal_recorded = True
        log_lingneng_event("adapter_stream_failed", failed_context)
        yield _runtime_error_frame(current_run_id, request.request_id)
    except Exception:
        failed_context = _stream_trace_context(
            context,
            started_at=stream_started_at,
            status=RunStatus.FAILED.value,
            agent_step_count=agent_step_count,
            citation_count=citation_count,
            artifact_count=artifact_count,
            answer_chars=answer_chars,
            error_code="RUNTIME_ERROR",
            recoverable=False,
        )
        _mark_failed_defensively(
            run_store,
            current_run_id,
            "RUNTIME_ERROR",
            "Agent runtime failed",
        )
        terminal_recorded = True
        log_lingneng_event("adapter_stream_failed", failed_context)
        yield _runtime_error_frame(current_run_id, request.request_id)
    finally:
        if not terminal_recorded:
            cancelled_context = _stream_trace_context(
                context,
                started_at=stream_started_at,
                status=RunStatus.FAILED.value,
                agent_step_count=agent_step_count,
                citation_count=citation_count,
                artifact_count=artifact_count,
                answer_chars=answer_chars,
                error_code="CLIENT_STREAM_CANCELLED",
                recoverable=True,
            )
            _mark_failed_defensively(
                run_store,
                current_run_id,
                "CLIENT_STREAM_CANCELLED",
                "Client disconnected before stream completed",
            )
            log_lingneng_event("client_stream_cancelled", cancelled_context)


async def _parse_chat_request(raw_request: Request) -> ChatStreamRequest:
    try:
        payload = await raw_request.json()
    except JSONDecodeError:
        _raise_invalid_chat_request()

    try:
        return ChatStreamRequest.model_validate(payload)
    except ValidationError:
        _raise_invalid_chat_request()


def _resolve_chat_session_key(request: ChatStreamRequest) -> ResolvedSessionKey:
    try:
        return resolve_session_key(request)
    except ValueError:
        _raise_invalid_chat_request()


def _event_name(
    event: (
        RunStartedEvent
        | AgentStepEvent
        | ArtifactCreatedEvent
        | CitationDeltaEvent
        | RagContextEvent
        | AnswerDeltaEvent
        | FinalEvent
        | ErrorEvent
    ),
) -> str:
    if isinstance(event, RunStartedEvent):
        return "run_started"
    if isinstance(event, AgentStepEvent):
        return "agent_step"
    if isinstance(event, ArtifactCreatedEvent):
        return "artifact_created"
    if isinstance(event, CitationDeltaEvent):
        return "citation_delta"
    if isinstance(event, RagContextEvent):
        return "rag_context"
    if isinstance(event, AnswerDeltaEvent):
        return "answer_delta"
    if isinstance(event, FinalEvent):
        return "final"
    if isinstance(event, ErrorEvent):
        return "error"
    _unsupported_event(event)


def _unsupported_event(event: object) -> NoReturn:
    raise ValueError(f"Unsupported LingNeng event model: {event.__class__.__name__}")


def _active_hermes_session_id(
    adapter: AgentRunAdapter,
    resolved: ResolvedSessionKey,
) -> str:
    session_store = getattr(adapter, "session_store", None)
    resolver = getattr(session_store, "resolve_active_session_id", None)
    if callable(resolver):
        try:
            active_session_id = resolver(resolved)
        except Exception:
            return resolved.session_key
        if isinstance(active_session_id, str) and active_session_id.strip():
            return active_session_id
    return resolved.session_key


def _log_pre_stream_failure(
    settings: LingNengSettings,
    started_at: float,
    *,
    error_code: str,
    request: ChatStreamRequest | None = None,
) -> None:
    trace_context: dict[str, Any] = {
        "status": RunStatus.FAILED.value,
        "duration_ms": _elapsed_ms(started_at),
        "agent_mode": settings.agent_mode,
        "error_code": error_code,
        "recoverable": False,
    }
    if request is not None:
        trace_context.update(
            {
                "request_id": request.request_id,
                "history_count": len(request.history),
                "attachment_count": len(request.attachments),
            }
        )
    log_lingneng_event("request_validation_failed", trace_context)


def _elapsed_ms(started_at: float) -> int:
    return max(0, int((time.monotonic() - started_at) * 1000))


def _stream_trace_context(
    trace_context: dict[str, Any],
    *,
    started_at: float,
    status: str,
    agent_step_count: int,
    citation_count: int,
    artifact_count: int,
    answer_chars: int,
    error_code: str | None = None,
    recoverable: bool | None = None,
) -> dict[str, Any]:
    return enrich_trace_context(
        trace_context,
        status=status,
        duration_ms=_elapsed_ms(started_at),
        agent_step_count=agent_step_count,
        citation_count=citation_count,
        artifact_count=artifact_count,
        answer_chars=answer_chars,
        error_code=error_code,
        recoverable=recoverable,
    )


def _mark_failed_defensively(
    run_store: LingNengRunStore,
    run_id: str,
    code: str,
    message: str,
) -> None:
    try:
        run_store.mark_failed(run_id, code, message)
    except RunStoreStateError:
        return


def _new_trace_id() -> str:
    return f"trace_{uuid.uuid4().hex}"


def _runtime_error_frame(run_id: str, request_id: str) -> str:
    return encode_sse(
        "error",
        ErrorEvent(
            run_id=run_id,
            request_id=request_id,
            code="RUNTIME_ERROR",
            message="Agent runtime failed",
            trace_id=_new_trace_id(),
            recoverable=False,
        ),
    )


def _raise_invalid_chat_request() -> NoReturn:
    raise HTTPException(status_code=422, detail="Invalid chat request")
