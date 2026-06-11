from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import ValidationError

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_events import (
    AgentStepEvent,
    AnswerDeltaEvent,
    ArtifactCreatedEvent,
    Citation,
    CitationDeltaEvent,
    FinalEvent,
    RagContextEvent,
    RunStartedEvent,
    RouteConfirmRequiredEvent,
    RouteResultEvent,
    RouteSuggestionEvent,
)
from lingneng.tools.artifacts import (
    artifact_from_public_dict,
    dedupe_artifacts as _dedupe_artifacts,
    stable_percent_decode,
)


RagBridgeEvent = CitationDeltaEvent | RagContextEvent
RouteBridgeEvent = (
    RouteResultEvent | RouteSuggestionEvent | RouteConfirmRequiredEvent
)
_RAG_TOOL_NAME = "retrieve_rag"
_ROUTE_TOOL_NAME = "employee_handoff"
_ARTIFACT_TOOL_NAMES = {
    "document_generation",
    "image_generation",
    "chart_visualization",
}
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
_PUBLIC_CITATION_FIELDS = frozenset(
    {
        "document_id",
        "source_file_id",
        "source_file_name",
        "page_no",
        "section_title",
        "chunk_id",
        "score",
    }
)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
_LOCAL_ROOT_FRAGMENT_RE = re.compile(
    r"(?<![A-Za-z0-9._-])[\\/]+(?:Users|home|private|tmp|var|etc|opt|root)\b"
)
_CREDENTIAL_VALUE_RE = re.compile(
    r"(?i)"
    r"(api[_-]?key|authorization|bearer|credential|password|passwd|secret|signature|token)"
    r"\s*[:=]\s*\S+|bearer\s+\S+"
)
_RAW_PAYLOAD_VALUE_RE = re.compile(
    r"(?i)\b(?:raw\s+)?(?:request|query|input|payload|args|history)\b\s*[:=]\s*\S+"
)
_SECRET_TOKEN_FRAGMENT_RE = re.compile(r"(?i)\b(?:secret|token|credential)[_-][A-Za-z0-9]")
_URL_CREDENTIALS_FRAGMENT_RE = re.compile(r"://[^/?#\s:@]+:[^/?#\s:@]+@")


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
        context_text = _rag_context_text(payload)
        events.append(
            RagContextEvent(
                context=context_text,
                citations=valid_citations,
                status=_rag_status(payload, valid_citations, context_text),
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


def artifact_events_from_tool_result(
    *,
    tool_name: str,
    result: Any,
    settings: LingNengSettings | None = None,
) -> tuple[list[ArtifactCreatedEvent], list[dict[str, Any]]]:
    if not is_artifact_producing_tool(tool_name):
        return [], []

    payload = _parse_tool_result(result)
    if payload is None:
        return [], []

    payload_tool_name = payload.get("tool_name")
    if payload_tool_name is not None and payload_tool_name != tool_name:
        return [], []

    artifacts = _valid_artifact_dicts(payload.get("artifacts"), settings=settings)
    events = [
        ArtifactCreatedEvent.model_validate(artifact)
        for artifact in artifacts
    ]
    return events, artifacts


def route_events_from_tool_result(
    *,
    tool_name: str,
    result: Any,
) -> tuple[list[RouteBridgeEvent], dict[str, Any] | None]:
    if tool_name != _ROUTE_TOOL_NAME:
        return [], None

    payload = _parse_tool_result(result)
    if payload is None:
        return [], None
    if payload.get("success") is not True:
        return [], None

    route_event_type = payload.get("route_event_type")
    route = payload.get("route")
    if not isinstance(route_event_type, str) or not isinstance(route, dict):
        return [], None

    event_model = _route_event_model(route_event_type)
    if event_model is None:
        return [], None

    try:
        event = event_model.model_validate(route)
    except ValidationError:
        return [], None

    return [event], _route_trace_summary(route_event_type, payload, route)


def is_artifact_producing_tool(tool_name: str) -> bool:
    return tool_name in _ARTIFACT_TOOL_NAMES


def dedupe_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _dedupe_artifacts(artifacts)


def final_answer(
    run_id: str,
    answer: str,
    citations: list[dict[str, Any]] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    settings: LingNengSettings | None = None,
    trace_summary: dict[str, Any] | None = None,
) -> FinalEvent:
    return FinalEvent.model_validate(
        {
            "run_id": run_id,
            "status": "succeeded",
            "answer": answer,
            "citations": citations or [],
            "artifacts": _valid_artifact_dicts(artifacts or [], settings=settings),
            "trace_summary": trace_summary or {},
        }
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
        if not isinstance(item, dict):
            continue
        citation = {
            key: _sanitize_public_value(item[key])
            for key in _PUBLIC_CITATION_FIELDS
            if key in item
        }
        try:
            citations.append(Citation.model_validate(citation))
        except ValidationError:
            continue
    return citations


def _valid_artifact_dicts(
    value: Any,
    *,
    settings: LingNengSettings | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    artifacts: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            if hasattr(item, "model_dump"):
                item = item.model_dump(mode="json")
            else:
                continue
        try:
            artifact = artifact_from_public_dict(item, settings=settings)
        except (TypeError, ValueError, ValidationError):
            continue
        artifacts.append(artifact.model_dump(mode="json"))
    return _dedupe_artifacts(artifacts)


def _rag_status(
    payload: dict[str, Any],
    citations: list[Citation],
    context_text: str,
) -> Literal["hit", "empty", "failed"]:
    if _is_failure_result(payload):
        return "failed"
    value = payload.get("status")
    if value == "empty":
        return "empty"
    if value == "hit":
        return "hit" if citations or context_text else "empty"
    return "hit" if citations or context_text else "empty"


def _rag_context_text(payload: dict[str, Any]) -> str:
    context = payload.get("context")
    if isinstance(context, str):
        public_context = _sanitize_public_text(context)
        if public_context or not _is_failure_result(payload):
            return public_context
    message = payload.get("message")
    if _is_failure_result(payload) and isinstance(message, str):
        return _sanitize_public_text(message)
    return ""


def _rag_metadata(value: Any) -> dict[str, Any]:
    sanitized = _sanitize_public_value(value)
    return sanitized if isinstance(sanitized, dict) else {}


def _is_public_text(value: str) -> bool:
    return bool(_sanitize_public_text(value))


def _is_failure_result(payload: dict[str, Any]) -> bool:
    return (
        payload.get("status") == "failed"
        or payload.get("success") is False
        or bool(payload.get("code"))
    )


def _route_event_model(
    route_event_type: str,
) -> type[RouteBridgeEvent] | None:
    if route_event_type == "route_result":
        return RouteResultEvent
    if route_event_type == "route_suggestion":
        return RouteSuggestionEvent
    if route_event_type == "route_confirm_required":
        return RouteConfirmRequiredEvent
    return None


def _route_trace_summary(
    route_event_type: str,
    payload: dict[str, Any],
    route: dict[str, Any],
) -> dict[str, Any]:
    return {
        "route_event_type": route_event_type,
        "terminal": bool(payload.get("terminal")),
        "target_employee_type": route.get("target_employee_type"),
        "current_employee_type": route.get("current_employee_type"),
        "confidence": route.get("confidence"),
    }


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
        return _sanitize_public_text(value)
    if value is None or isinstance(value, bool | int | float):
        return value
    return None


def _is_public_metadata_key(value: str) -> bool:
    lowered = value.lower()
    return not any(part in lowered for part in _METADATA_KEY_BLOCKLIST)


def _is_public_metadata_text(value: str) -> bool:
    return bool(_sanitize_public_text(value))


def _sanitize_public_text(value: str) -> str:
    clean = _CONTROL_CHAR_RE.sub("", value).strip()
    decoded, decode_stable = stable_percent_decode(clean)
    if (
        not decode_stable
        or _has_forbidden_public_text(clean)
        or _has_forbidden_public_text(decoded)
    ):
        return ""
    return clean


def _has_forbidden_public_text(value: str) -> bool:
    lowered = value.lower()
    return (
        _CREDENTIAL_VALUE_RE.search(value) is not None
        or _RAW_PAYLOAD_VALUE_RE.search(value) is not None
        or _has_raw_payload_json_shape(value)
        or _SECRET_TOKEN_FRAGMENT_RE.search(value) is not None
        or _WINDOWS_ABSOLUTE_PATH_RE.search(value) is not None
        or _LOCAL_ROOT_FRAGMENT_RE.search(value) is not None
        or _URL_CREDENTIALS_FRAGMENT_RE.search(value) is not None
        or "x-amz-signature" in lowered
        or "traceback" in lowered
        or "user private input" in lowered
    )


def _has_raw_payload_json_shape(value: str) -> bool:
    stripped = value.strip()
    if not (
        (stripped.startswith("{") and stripped.endswith("}"))
        or (stripped.startswith("[") and stripped.endswith("]"))
    ):
        return False
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return False
    return _contains_forbidden_payload_key(parsed)


def _contains_forbidden_payload_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            _is_public_metadata_key(str(key)) is False
            or _contains_forbidden_payload_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_payload_key(item) for item in value)
    return False
