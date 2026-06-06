from __future__ import annotations

import json
import logging as py_logging
import math
import os
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import ResolvedSessionKey


LOGGER_NAME = "lingneng.observability"
LOGGER = py_logging.getLogger(LOGGER_NAME)

TRACE_ALLOWED_KEYS = frozenset(
    {
        "event_name",
        "request_id",
        "run_id",
        "tenant_id",
        "user_id",
        "conversation_id",
        "session_key",
        "employee_id",
        "employee_type",
        "status",
        "duration_ms",
        "agent_mode",
        "history_count",
        "attachment_count",
        "agent_step_count",
        "citation_count",
        "artifact_count",
        "answer_chars",
        "active_hermes_session_id",
        "compression_root_session_id",
        "compression_active_session_id",
        "compression_used",
        "tool_name",
        "error_code",
        "recoverable",
        "deploy_env",
        "deploy_image_ref",
        "deploy_git_sha",
        "deploy_build_id",
    }
)
TRACE_SUMMARY_ALLOWED_KEYS = frozenset(
    {
        "event_name",
        "request_id",
        "run_id",
        "tenant_id",
        "user_id",
        "conversation_id",
        "session_key",
        "employee_id",
        "employee_type",
        "active_hermes_session_id",
        "status",
        "duration_ms",
        "agent_mode",
        "history_count",
        "attachment_count",
        "agent_step_count",
        "citation_count",
        "artifact_count",
        "answer_chars",
        "compression_used",
        "compression_root_session_id",
        "compression_active_session_id",
        "deploy_env",
        "deploy_image_ref",
        "deploy_git_sha",
        "deploy_build_id",
    }
)
_DEPLOY_ENV_KEYS = {
    "LINGNENG_DEPLOY_ENV": "deploy_env",
    "LINGNENG_IMAGE_REF": "deploy_image_ref",
    "LINGNENG_GIT_SHA": "deploy_git_sha",
    "LINGNENG_BUILD_ID": "deploy_build_id",
}
_SECRET_MARKER_RE = re.compile(
    r"(api[_-]?key|authorization|bearer\s+\S+|password|passwd|secret|token|"
    r"x-amz|signature)",
    re.IGNORECASE,
)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(api[_-]?key|authorization|password|passwd|secret|token|signature)\s*[:=]",
    re.IGNORECASE,
)
_LOCAL_PATH_RE = re.compile(
    r"(^|[\s:=])("
    r"/Users/|/home/|/private/|/tmp/|/var/|/etc/|/root/|"
    r"[A-Za-z]:[\\/]"
    r")"
)
_DROP = object()
_MAX_SAFE_STRING_LENGTH = 512


def deploy_metadata_from_env(
    env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = os.environ if env is None else env
    metadata: dict[str, str] = {}
    for env_key, trace_key in _DEPLOY_ENV_KEYS.items():
        value = _sanitize_trace_value(source.get(env_key))
        if isinstance(value, str):
            metadata[trace_key] = value
    return metadata


def build_trace_context(
    request: ChatStreamRequest,
    resolved: ResolvedSessionKey,
    *,
    run_id: str,
    agent_mode: str | None = None,
    status: str | None = None,
    duration_ms: int | None = None,
    active_hermes_session_id: str | None = None,
    agent_step_count: int | None = None,
    citation_count: int | None = None,
    artifact_count: int | None = None,
    answer_chars: int | None = None,
    error_code: str | None = None,
    recoverable: bool | None = None,
) -> dict[str, Any]:
    active_session_id = active_hermes_session_id or resolved.session_key
    context: dict[str, Any] = {
        "request_id": request.request_id,
        "run_id": run_id,
        "tenant_id": resolved.tenant_id,
        "user_id": resolved.user_id,
        "conversation_id": resolved.conversation_id,
        "session_key": resolved.session_key,
        "employee_id": resolved.employee_id,
        "employee_type": resolved.employee_type,
        "status": status,
        "duration_ms": duration_ms,
        "agent_mode": agent_mode,
        "history_count": resolved.history_message_count,
        "attachment_count": len(request.attachments),
        "agent_step_count": agent_step_count,
        "citation_count": citation_count,
        "artifact_count": artifact_count,
        "answer_chars": answer_chars,
        "active_hermes_session_id": active_session_id,
        "compression_root_session_id": resolved.session_key,
        "compression_active_session_id": active_session_id,
        "compression_used": active_session_id != resolved.session_key,
        "error_code": error_code,
        "recoverable": recoverable,
        **deploy_metadata_from_env(),
    }
    return sanitize_trace_payload(context)


def enrich_trace_context(
    trace_context: Mapping[str, Any],
    **updates: Any,
) -> dict[str, Any]:
    return sanitize_trace_payload({**trace_context, **updates})


def build_trace_summary(trace_context: Mapping[str, Any]) -> dict[str, Any]:
    return sanitize_trace_payload(
        {**trace_context, "event_name": "final"},
        allowed_keys=TRACE_SUMMARY_ALLOWED_KEYS,
    )


def log_lingneng_event(
    event_name: str,
    trace_context: Mapping[str, Any],
    logger: py_logging.Logger | None = None,
) -> dict[str, Any]:
    payload = sanitize_trace_payload({**trace_context, "event_name": event_name})
    resolved_logger = logger or LOGGER
    message = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    resolved_logger.info(
        message,
        extra={
            "event_name": payload.get("event_name", event_name),
            "trace_payload": payload,
        },
    )
    return payload


def sanitize_trace_payload(
    payload: Mapping[str, Any],
    *,
    allowed_keys: frozenset[str] = TRACE_ALLOWED_KEYS,
) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in allowed_keys:
            continue
        clean_value = _sanitize_trace_value(value)
        if clean_value is _DROP:
            continue
        sanitized[key] = clean_value
    return sanitized


def _sanitize_trace_value(value: Any) -> Any:
    if value is None:
        return _DROP
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return _DROP
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or _is_suspicious_string(stripped):
            return _DROP
        return stripped[:_MAX_SAFE_STRING_LENGTH]
    if isinstance(value, Mapping | list | tuple | set):
        return _DROP
    return _DROP


def _is_suspicious_string(value: str) -> bool:
    if _SECRET_MARKER_RE.search(value) or _SECRET_ASSIGNMENT_RE.search(value):
        return True
    if _LOCAL_PATH_RE.search(value):
        return True
    try:
        parts = urlsplit(value)
    except ValueError:
        return True
    if parts.scheme.lower() in {"http", "https"} and parts.query:
        return _SECRET_MARKER_RE.search(parts.query) is not None
    return False
