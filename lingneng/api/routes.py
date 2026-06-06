from __future__ import annotations

from json import JSONDecodeError
import uuid
from collections.abc import AsyncIterator
from typing import NoReturn

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from lingneng.api.auth import ensure_chat_configuration_ready, verify_internal_key
from lingneng.api.sse import encode_sse, with_heartbeats
from lingneng.config.settings import LingNengSettings
from lingneng.runtime.agent_adapter import AgentRunAdapter
from lingneng.schemas.chat_events import (
    AnswerDeltaEvent,
    ErrorEvent,
    FinalEvent,
    RunStartedEvent,
)
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import ResolvedSessionKey, resolve_session_key
from lingneng.session.run_store import LingNengRunStore, RunStatus, RunStoreStateError


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
        ensure_chat_configuration_ready(settings)
        verify_internal_key(settings, x_internal_key)

        request = await _parse_chat_request(raw_request)
        resolved = _resolve_chat_session_key(request)
        reservation = run_store.reserve_run(resolved.session_key, request.request_id)

        if not reservation.created:
            stream = _duplicate_stream(
                reservation.record.run_id,
                request.request_id,
                reservation.record.status,
            )
        else:
            stream = _adapter_stream(
                adapter,
                run_store,
                request,
                resolved,
                reservation.record.run_id,
            )

        return StreamingResponse(
            with_heartbeats(stream, settings.heartbeat_interval_seconds),
            media_type="text/event-stream",
        )


async def _duplicate_stream(
    run_id: str,
    request_id: str,
    status: RunStatus,
) -> AsyncIterator[str]:
    if status is RunStatus.RUNNING:
        code = "REQUEST_ALREADY_RUNNING"
        message = "Request is already running"
    else:
        code = "REQUEST_ALREADY_COMPLETED"
        message = "Request is already completed"

    yield encode_sse(
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
) -> AsyncIterator[str]:
    current_run_id = run_id
    terminal_recorded = False
    try:
        async for event in adapter.stream(request, resolved, run_id):
            if hasattr(event, "run_id"):
                current_run_id = event.run_id

            if isinstance(event, FinalEvent):
                run_store.mark_succeeded(
                    event.run_id,
                    answer=event.answer,
                    artifacts=event.artifacts,
                )
                terminal_recorded = True
                yield encode_sse("final", event)
                return

            if isinstance(event, ErrorEvent):
                _mark_failed_defensively(
                    run_store,
                    event.run_id,
                    event.code,
                    event.message,
                )
                terminal_recorded = True
                yield encode_sse("error", event)
                return

            yield encode_sse(_event_name(event), event)

        _mark_failed_defensively(
            run_store,
            current_run_id,
            "RUNTIME_ERROR",
            "Agent runtime failed",
        )
        terminal_recorded = True
        yield _runtime_error_frame(current_run_id, request.request_id)
    except Exception:
        _mark_failed_defensively(
            run_store,
            current_run_id,
            "RUNTIME_ERROR",
            "Agent runtime failed",
        )
        terminal_recorded = True
        yield _runtime_error_frame(current_run_id, request.request_id)
    finally:
        if not terminal_recorded:
            _mark_failed_defensively(
                run_store,
                current_run_id,
                "CLIENT_STREAM_CANCELLED",
                "Client disconnected before stream completed",
            )


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
    event: RunStartedEvent | AnswerDeltaEvent | FinalEvent | ErrorEvent,
) -> str:
    if isinstance(event, RunStartedEvent):
        return "run_started"
    if isinstance(event, AnswerDeltaEvent):
        return "answer_delta"
    if isinstance(event, FinalEvent):
        return "final"
    if isinstance(event, ErrorEvent):
        return "error"
    _unsupported_event(event)


def _unsupported_event(event: object) -> NoReturn:
    raise ValueError(f"Unsupported LingNeng event model: {event.__class__.__name__}")


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
