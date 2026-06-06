from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from lingneng.schemas.chat_events import (
    AgentStepEvent,
    AnswerDeltaEvent,
    Citation,
    CitationDeltaEvent,
    FinalEvent,
    RagContextEvent,
    RunStartedEvent,
)


RagBridgeEvent = CitationDeltaEvent | RagContextEvent
_RAG_TOOL_NAME = "retrieve_rag"
_PUBLIC_CONTEXT_TEXT_BLOCKLIST = (
    "api_key",
    "secret",
    "token",
    "authorization",
    "bearer",
    "traceback",
    "exception",
)
_METADATA_KEY_BLOCKLIST = (
    *_PUBLIC_CONTEXT_TEXT_BLOCKLIST,
    "request",
    "payload",
    "query",
    "args",
    "history",
    "input",
)
_METADATA_TEXT_BLOCKLIST = (
    *_PUBLIC_CONTEXT_TEXT_BLOCKLIST,
    "request",
    "payload",
    "query",
    "args",
    "history",
    "input",
)


def _tool_step_id(sequence: int) -> str:
    return f"tool-{sequence}"


def _public_tool_name(tool_name: str) -> str:
    safe = "".join(
        ch for ch in tool_name if ch.isascii() and (ch.isalnum() or ch in {"_", "-", "."})
    )
    return (safe or "tool")[:64]


def run_started(run_id: str, request_id: str) -> RunStartedEvent:
    return RunStartedEvent(run_id=run_id, request_id=request_id)


def answer_delta(text: str, sequence: int) -> AnswerDeltaEvent:
    return AnswerDeltaEvent(text=text, sequence=sequence)


def agent_step_started(
    sequence: int,
    tool_name: str,
    preview: str | None = None,
) -> AgentStepEvent:
    safe_name = _public_tool_name(tool_name)
    return AgentStepEvent(
        sequence=sequence,
        step_id=_tool_step_id(sequence),
        phase="tool",
        status="started",
        title=safe_name,
        short_text=f"Starting {safe_name}.",
        summary="Tool input received." if preview else None,
        refs=[],
    )


def agent_step_completed(
    sequence: int,
    tool_name: str,
    duration: float | None = None,
    is_error: bool = False,
    result: Any = None,
) -> AgentStepEvent:
    safe_name = _public_tool_name(tool_name)
    if is_error:
        return AgentStepEvent(
            sequence=sequence,
            step_id=_tool_step_id(sequence),
            phase="tool",
            status="failed",
            title=safe_name,
            short_text=f"{safe_name} failed.",
            summary="Tool failed with a public error summary.",
            refs=[],
        )

    summary = f"Duration: {duration:.2f}s" if duration is not None else None
    return AgentStepEvent(
        sequence=sequence,
        step_id=_tool_step_id(sequence),
        phase="tool",
        status="succeeded",
        title=safe_name,
        short_text=f"Completed {safe_name}.",
        summary=summary,
        refs=[],
    )


def agent_step_skipped(
    sequence: int,
    tool_name: str,
    reason: str | None = None,
) -> AgentStepEvent:
    safe_name = _public_tool_name(tool_name)
    return AgentStepEvent(
        sequence=sequence,
        step_id=_tool_step_id(sequence),
        phase="tool",
        status="skipped",
        title=safe_name,
        short_text=f"Skipped {safe_name}.",
        summary="Tool was skipped." if reason else None,
        refs=[],
    )


def rag_events_from_tool_result(
    *,
    tool_name: str,
    result: Any,
    include_citations: bool,
    include_rag_context: bool,
) -> tuple[list[RagBridgeEvent], list[dict[str, Any]]]:
    if tool_name != _RAG_TOOL_NAME:
        return [], []

    payload = _parse_tool_result(result)
    if payload is None:
        return [], []
    if not _is_rag_result_payload(payload):
        return [], []

    valid_citations = _valid_citations(payload.get("citations"))
    events: list[RagBridgeEvent] = []
    if include_citations:
        events.extend(
            CitationDeltaEvent.model_validate(citation.model_dump())
            for citation in valid_citations
        )

    if include_rag_context:
        events.append(
            RagContextEvent(
                context=_rag_context_text(payload),
                citations=valid_citations,
                status=_rag_status(payload, valid_citations),
                metadata=_rag_metadata(payload.get("metadata")),
            )
        )

    citations = [citation.model_dump(mode="json") for citation in valid_citations]
    return events, citations if include_citations else []


def dedupe_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for citation in citations:
        chunk_id = citation.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id:
            continue
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        deduped.append(citation)
    return deduped


def final_answer(
    run_id: str,
    answer: str,
    citations: list[dict[str, Any]] | None = None,
) -> FinalEvent:
    return FinalEvent(
        run_id=run_id,
        status="succeeded",
        answer=answer,
        citations=citations or [],
    )


def _parse_tool_result(result: Any) -> dict[str, Any] | None:
    if isinstance(result, dict):
        return result
    if not isinstance(result, str):
        return None
    try:
        parsed = json.loads(result)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _is_rag_result_payload(payload: dict[str, Any]) -> bool:
    payload_tool_name = payload.get("tool_name")
    if payload_tool_name is not None and payload_tool_name != _RAG_TOOL_NAME:
        return False
    return any(
        key in payload
        for key in (
            "status",
            "context",
            "citations",
            "metadata",
            "code",
            "message",
        )
    )


def _valid_citations(value: Any) -> list[Citation]:
    if not isinstance(value, list):
        return []
    citations: list[Citation] = []
    for item in value:
        try:
            citations.append(Citation.model_validate(item))
        except ValidationError:
            continue
    return citations


def _rag_status(payload: dict[str, Any], citations: list[Citation]) -> str:
    if _is_failure_result(payload):
        return "failed"
    value = payload.get("status")
    if value in {"hit", "empty", "failed"}:
        return value
    return "hit" if citations else "empty"


def _rag_context_text(payload: dict[str, Any]) -> str:
    context = payload.get("context")
    if isinstance(context, str) and _is_public_text(context):
        return context
    message = payload.get("message")
    if _is_failure_result(payload) and isinstance(message, str):
        return message if _is_public_text(message) else ""
    return ""


def _rag_metadata(value: Any) -> dict[str, Any]:
    sanitized = _sanitize_public_value(value)
    return sanitized if isinstance(sanitized, dict) else {}


def _is_public_text(value: str) -> bool:
    lowered = value.lower()
    return not any(part in lowered for part in _PUBLIC_CONTEXT_TEXT_BLOCKLIST)


def _is_failure_result(payload: dict[str, Any]) -> bool:
    return (
        payload.get("status") == "failed"
        or payload.get("success") is False
        or bool(payload.get("code"))
    )


def _sanitize_public_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _sanitize_public_value(item)
            for key, item in value.items()
            if _is_public_metadata_key(str(key))
        }
    if isinstance(value, list | tuple):
        return [_sanitize_public_value(item) for item in value]
    if isinstance(value, str):
        return value if _is_public_metadata_text(value) else ""
    if value is None or isinstance(value, bool | int | float):
        return value
    return None


def _is_public_metadata_key(value: str) -> bool:
    lowered = value.lower()
    return not any(part in lowered for part in _METADATA_KEY_BLOCKLIST)


def _is_public_metadata_text(value: str) -> bool:
    lowered = value.lower()
    return not any(part in lowered for part in _METADATA_TEXT_BLOCKLIST)
