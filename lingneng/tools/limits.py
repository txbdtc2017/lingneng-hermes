from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from lingneng.config.settings import LingNengSettings
from lingneng.tools.document_generation import _json_result, _public_result


_CURRENT_GUARD: ContextVar[ToolRunGuard | None] = ContextVar(
    "lingneng_tool_run_guard",
    default=None,
)
_ARTIFACT_TOOLS = {
    "document_generation",
    "image_generation",
    "chart_visualization",
}
_LIMIT_CODE = "TOOL_CALL_LIMIT_EXCEEDED"
_DUPLICATE_CODE = "DUPLICATE_TOOL_CALL_SUPPRESSED"


@dataclass
class ToolRunGuard:
    settings: LingNengSettings
    counts: dict[str, int] = field(default_factory=dict)
    signatures: set[tuple[str, str]] = field(default_factory=set)

    def check(self, tool_name: str, args: dict[str, Any]) -> str | None:
        signature = _signature(tool_name, args, self.settings)
        key = (tool_name, signature)
        if self.settings.duplicate_artifact_guard_enabled:
            if key in self.signatures:
                return _DUPLICATE_CODE

        limit = _limit_for(tool_name, self.settings)
        next_count = self.counts.get(tool_name, 0) + 1
        if next_count > limit:
            return _LIMIT_CODE

        if self.settings.duplicate_artifact_guard_enabled:
            self.signatures.add(key)
        self.counts[tool_name] = next_count
        return None


@contextmanager
def tool_run_guard_context(settings: LingNengSettings) -> Iterator[ToolRunGuard]:
    guard = ToolRunGuard(settings=settings)
    token = _CURRENT_GUARD.set(guard)
    try:
        yield guard
    finally:
        _CURRENT_GUARD.reset(token)


def guarded_tool_skip_result(
    tool_name: str,
    args: dict[str, Any],
    settings: LingNengSettings,
) -> str | None:
    guard = _CURRENT_GUARD.get()
    if guard is None:
        return None

    code = guard.check(tool_name, args)
    if code is None:
        return None

    duplicate = code == _DUPLICATE_CODE
    return _json_result(
        _public_result(
            tool_name=tool_name,
            success=False,
            status="skipped",
            summary="Tool call was skipped by LingNeng run guard.",
            safe_output={
                "reason": "duplicate_suppressed" if duplicate else "limit_exceeded"
            },
            artifacts=[],
            metadata={
                "limit": _limit_for(tool_name, guard.settings),
                "duplicate_suppressed": duplicate,
            },
            code=code,
            message=_message(tool_name, code),
        ),
        settings=settings,
    )


def _limit_for(tool_name: str, settings: LingNengSettings) -> int:
    if tool_name == "web_search":
        return settings.web_search_max_calls_per_run
    if tool_name in _ARTIFACT_TOOLS:
        return settings.tool_artifact_max_calls_per_run
    return settings.tool_artifact_max_calls_per_run


def _message(tool_name: str, code: str) -> str:
    if code == _LIMIT_CODE:
        return f"LingNeng {tool_name} call limit was reached for this run."
    if code == _DUPLICATE_CODE:
        return f"LingNeng duplicate {tool_name} call was suppressed for this run."
    return f"LingNeng {tool_name} call was skipped for this run."


def _signature(
    tool_name: str,
    args: dict[str, Any],
    settings: LingNengSettings,
) -> str:
    if tool_name == "document_generation":
        payload = _document_signature_payload(args, settings)
    elif tool_name == "image_generation":
        payload = _image_signature_payload(args, settings)
    elif tool_name == "chart_visualization":
        payload = _chart_signature_payload(args)
    elif tool_name == "web_search":
        payload = _web_search_signature_payload(args, settings)
    else:
        payload = _stable_json_hash(args)
    return _stable_json_hash(payload)


def _document_signature_payload(
    args: dict[str, Any],
    settings: LingNengSettings,
) -> dict[str, Any]:
    from lingneng.tools.document_generation import _build_document_request

    request = _build_document_request(args, settings)
    return {
        "title": request.title,
        "instruction": request.instruction,
        "format": request.format,
        "target_format": request.target_format,
        "content_sha256": _sha256_text(request.content),
    }


def _image_signature_payload(
    args: dict[str, Any],
    settings: LingNengSettings,
) -> dict[str, Any]:
    from lingneng.tools.document_generation import _bounded_text, _text_arg
    from lingneng.tools.image_generation import _normalize_count

    return {
        "prompt_sha256": _sha256_text(
            _bounded_text(_text_arg(args.get("prompt")), max_chars=4000)
        ),
        "count": _normalize_count(args.get("count"), settings),
        "size": _bounded_text(_text_arg(args.get("size")), max_chars=40),
        "quality": _bounded_text(_text_arg(args.get("quality")), max_chars=40),
        "style": _bounded_text(_text_arg(args.get("style")), max_chars=100),
    }


def _chart_signature_payload(args: dict[str, Any]) -> dict[str, Any]:
    from lingneng.tools.chart_visualization import _build_chart_request

    request = _build_chart_request(args)
    return {
        "instruction_sha256": _sha256_text(request.instruction),
        "title": request.title,
        "chart_type": request.chart_type,
        "data_summary_sha256": _sha256_text(request.data_summary),
        "data_sha256": _stable_json_hash(request.data),
    }


def _web_search_signature_payload(
    args: dict[str, Any],
    settings: LingNengSettings,
) -> dict[str, Any]:
    from lingneng.tools.web_search import _build_search_request

    request = _build_search_request(args, settings)
    return {
        "query_sha256": _sha256_text(request.query),
        "top_k": request.top_k,
        "recency_filter": request.recency_filter,
        "site_filter": request.site_filter,
    }


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _stable_scalar(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return _stable_json_hash(value)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_json_hash(value: Any) -> str:
    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    except (TypeError, ValueError):
        serialized = repr(type(value).__name__)
    return _sha256_text(serialized)
