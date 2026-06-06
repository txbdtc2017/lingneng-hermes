from __future__ import annotations

import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lingneng.config.settings import LingNengSettings
from lingneng.tools.artifacts import artifact_from_public_dict, dedupe_artifacts


ToolStatus = Literal["succeeded", "failed", "skipped"]

_CURRENT_SETTINGS: ContextVar[LingNengSettings | None] = ContextVar(
    "lingneng_document_generation_settings",
    default=None,
)
_CURRENT_PROVIDER: ContextVar[DocumentGenerationProvider | None] = ContextVar(
    "lingneng_document_generation_provider",
    default=None,
)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
_LOCAL_ROOT_FRAGMENT_RE = re.compile(
    r"(?<![A-Za-z0-9._-])[\\/]+(?:Users|home|private|tmp|var|etc|opt|root)\b"
)
_FORBIDDEN_KEY_EXACT = (
    "args",
    "body",
    "content",
    "document_body",
    "full_body",
    "full_content",
    "history",
    "input",
    "payload",
    "raw_body",
    "raw_content",
    "request",
)
_FORBIDDEN_KEY_PARTS = (
    "api_key",
    "authorization",
    "bearer",
    "credential",
    "exception",
    "password",
    "passwd",
    "raw_payload",
    "raw_request",
    "request_payload",
    "secret",
    "signed",
    "token",
    "traceback",
)
_FORBIDDEN_TEXT_PARTS = (
    "api_key",
    "authorization",
    "bearer ",
    "credential",
    "password",
    "passwd",
    "raw payload",
    "raw request",
    "secret",
    "signed url",
    "token",
    "traceback",
)
_PUBLIC_MESSAGE_BY_CODE = {
    "NOT_CONFIGURED": "LingNeng generation provider is not configured.",
    "DOCUMENT_GENERATION_PROVIDER_ERROR": "LingNeng document generation provider failed.",
    "DOCUMENT_GENERATION_NO_VALID_ARTIFACTS": (
        "LingNeng document generation returned no valid public artifacts."
    ),
    "IMAGE_GENERATION_PROVIDER_ERROR": "LingNeng image generation provider failed.",
    "IMAGE_GENERATION_NO_VALID_ARTIFACTS": (
        "LingNeng image generation returned no valid public artifacts."
    ),
    "CHART_VISUALIZATION_PROVIDER_ERROR": (
        "LingNeng chart visualization provider failed."
    ),
    "CHART_VISUALIZATION_NO_VALID_ARTIFACTS": (
        "LingNeng chart visualization returned no valid public artifacts."
    ),
    "WEB_SEARCH_PROVIDER_ERROR": "LingNeng web search provider failed.",
}
_MAX_PUBLIC_DEPTH = 4
_MAX_PUBLIC_ITEMS = 20


class DocumentGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = ""
    instruction: str = ""
    content: str = ""
    format: str = "pdf"
    target_format: str = "pdf"
    original_content_length: int = 0
    content_truncated: bool = False


class DocumentGenerationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = ""
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    safe_output: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    code: str | None = None
    message: str | None = None


class DocumentGenerationProvider(Protocol):
    def generate(self, request: DocumentGenerationRequest) -> DocumentGenerationResult: ...


@contextmanager
def document_generation_context(
    settings: LingNengSettings,
    *,
    provider: DocumentGenerationProvider | None = None,
) -> Iterator[None]:
    settings_token = _CURRENT_SETTINGS.set(settings)
    provider_token = _CURRENT_PROVIDER.set(provider)
    try:
        yield
    finally:
        _CURRENT_PROVIDER.reset(provider_token)
        _CURRENT_SETTINGS.reset(settings_token)


def document_generation_handler(args: dict[str, Any] | None = None, **kwargs: Any) -> str:
    del kwargs
    settings = _settings()
    provider = _CURRENT_PROVIDER.get()
    if provider is None:
        return _json_result(
            _public_result(
                tool_name="document_generation",
                success=False,
                status="skipped",
                summary="Document generation provider is not configured.",
                code="NOT_CONFIGURED",
            ),
            settings=settings,
        )

    raw_args = args or {}
    request = _build_document_request(raw_args, settings)
    try:
        result = _coerce_result(provider.generate(request), DocumentGenerationResult)
    except Exception:
        return _json_result(
            _public_result(
                tool_name="document_generation",
                success=False,
                status="failed",
                summary="Document generation provider failed.",
                code="DOCUMENT_GENERATION_PROVIDER_ERROR",
            ),
            settings=settings,
        )

    artifacts = _valid_artifact_dicts(result.artifacts)
    if not artifacts:
        return _json_result(
            _public_result(
                tool_name="document_generation",
                success=False,
                status="failed",
                summary="Document generation returned no valid artifacts.",
                code="DOCUMENT_GENERATION_NO_VALID_ARTIFACTS",
            ),
            settings=settings,
        )

    safe_output = {
        **result.safe_output,
        "title": request.title,
        "format": request.target_format or request.format,
        "content_length": request.original_content_length,
        "bounded_content_length": len(request.content),
        "content_truncated": request.content_truncated,
        "artifact_count": len(artifacts),
    }
    metadata = {**result.metadata, "artifact_count": len(artifacts)}
    return _json_result(
        _public_result(
            tool_name="document_generation",
            success=True,
            status="succeeded",
            summary=result.summary or "Document generation completed.",
            safe_output=safe_output,
            artifacts=artifacts,
            metadata=metadata,
        ),
        settings=settings,
    )


def _build_document_request(
    raw_args: dict[str, Any],
    settings: LingNengSettings,
) -> DocumentGenerationRequest:
    raw_content = _text_arg(raw_args.get("content"))
    bounded_content = _bounded_text(
        raw_content,
        max_chars=settings.document_max_content_chars,
    )
    output_format = _bounded_text(
        _text_arg(raw_args.get("target_format") or raw_args.get("format") or "pdf"),
        max_chars=40,
    )
    if not output_format:
        output_format = "pdf"
    return DocumentGenerationRequest(
        title=_bounded_text(_text_arg(raw_args.get("title")), max_chars=200),
        instruction=_bounded_text(
            _text_arg(raw_args.get("instruction")),
            max_chars=4000,
        ),
        content=bounded_content,
        format=_bounded_text(
            _text_arg(raw_args.get("format") or output_format),
            max_chars=40,
        )
        or output_format,
        target_format=output_format,
        original_content_length=len(raw_content),
        content_truncated=len(raw_content) > len(bounded_content),
    )


def _settings() -> LingNengSettings:
    return _CURRENT_SETTINGS.get() or LingNengSettings.from_env()


def _text_arg(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _bounded_text(value: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    return _strip_control_chars(value).strip()[:max_chars]


def _coerce_result(value: Any, model: type[BaseModel]) -> Any:
    if isinstance(value, model):
        return value
    return model.model_validate(value)


def _valid_artifact_dicts(
    value: list[Any],
    *,
    overrides: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        candidate = dict(item)
        if overrides:
            candidate.update(overrides)
        try:
            artifact = artifact_from_public_dict(candidate)
        except ValidationError:
            continue
        artifacts.append(artifact.model_dump(mode="json"))
    return dedupe_artifacts(artifacts)


def _public_result(
    *,
    tool_name: str,
    success: bool,
    status: ToolStatus,
    summary: str,
    safe_output: dict[str, Any] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    code: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    public_summary = _sanitize_public_text(summary, max_chars=500)
    public_code = _sanitize_public_text(code or "", max_chars=100) or None
    public_message = (
        _sanitize_public_text(message, max_chars=500)
        if message
        else _public_message(public_code, tool_name)
    )
    public_artifacts = list(artifacts or [])
    metadata_value = _sanitize_mapping(metadata or {})
    total_artifacts = len(public_artifacts)
    if total_artifacts > _MAX_PUBLIC_ITEMS:
        public_artifacts = public_artifacts[:_MAX_PUBLIC_ITEMS]
        _mark_artifacts_truncated(
            metadata_value,
            total_count=total_artifacts,
            kept_count=len(public_artifacts),
        )
    return {
        "success": success,
        "tool_name": tool_name,
        "status": status,
        "summary": public_summary,
        "safe_output": _sanitize_mapping(safe_output or {}),
        "artifacts": public_artifacts,
        "metadata": metadata_value,
        "code": public_code,
        "message": public_message,
    }


def _public_message(code: str | None, tool_name: str) -> str | None:
    if code is None:
        return None
    return _PUBLIC_MESSAGE_BY_CODE.get(code, f"LingNeng {tool_name} failed safely.")


def _sanitize_mapping(value: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_public_value(value)
    if not isinstance(sanitized, dict):
        return {}
    return sanitized


def _sanitize_public_value(value: Any) -> Any:
    return _sanitize_public_value_at_depth(value, depth=0)


def _sanitize_public_value_at_depth(value: Any, *, depth: int) -> Any:
    if depth >= _MAX_PUBLIC_DEPTH:
        return {"truncated": True, "reason": "max_depth"}
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        omitted_count = 0
        items = list(value.items())
        for index, (key, item) in enumerate(items[:_MAX_PUBLIC_ITEMS]):
            if _is_forbidden_key(key):
                omitted_count += 1
                continue
            sanitized[str(key)] = _sanitize_public_value_at_depth(
                item,
                depth=depth + 1,
            )
        omitted_count += max(0, len(items) - _MAX_PUBLIC_ITEMS)
        if omitted_count:
            sanitized["truncated"] = True
            sanitized["omitted_count"] = omitted_count
        return sanitized
    if isinstance(value, list | tuple):
        sanitized_list = [
            _sanitize_public_value_at_depth(item, depth=depth + 1)
            for item in list(value)[:_MAX_PUBLIC_ITEMS]
        ]
        omitted_count = max(0, len(value) - _MAX_PUBLIC_ITEMS)
        if omitted_count:
            sanitized_list.append(
                {"truncated": True, "omitted_count": omitted_count}
            )
        return sanitized_list
    if isinstance(value, str):
        return _sanitize_public_text(value, max_chars=1000)
    if value is None or isinstance(value, bool | int | float):
        return value
    return None


def _sanitize_public_text(value: str, *, max_chars: int) -> str:
    clean_text = _strip_control_chars(value).strip()
    lowered = clean_text.lower()
    if (
        any(part in lowered for part in _FORBIDDEN_TEXT_PARTS)
        or _looks_like_local_path(clean_text)
        or _contains_embedded_local_path(clean_text)
    ):
        return ""
    return clean_text[:max_chars]


def _strip_control_chars(value: str) -> str:
    return _CONTROL_CHAR_RE.sub("", value)


def _is_forbidden_key(value: object) -> bool:
    lowered = str(value).lower()
    return lowered in _FORBIDDEN_KEY_EXACT or any(
        part in lowered for part in _FORBIDDEN_KEY_PARTS
    )


def _looks_like_local_path(value: str) -> bool:
    lowered = value.lower()
    return (
        lowered.startswith(("file://", "local://"))
        or value.startswith(("/", "\\", "~"))
        or _WINDOWS_ABSOLUTE_PATH_RE.search(value) is not None
    )


def _contains_embedded_local_path(value: str) -> bool:
    lowered = value.lower()
    return (
        "file://" in lowered
        or "local://" in lowered
        or _LOCAL_ROOT_FRAGMENT_RE.search(value) is not None
        or _WINDOWS_ABSOLUTE_PATH_RE.search(value) is not None
    )


def _json_result(
    value: dict[str, Any],
    *,
    settings: LingNengSettings | None = None,
) -> str:
    if settings is None:
        return json.dumps(value, ensure_ascii=False)

    max_chars = max(500, settings.tool_result_max_chars)
    serialized = json.dumps(value, ensure_ascii=False)
    if len(serialized) <= max_chars:
        return serialized

    bounded = dict(value)
    safe_output = bounded.get("safe_output")
    metadata = bounded.get("metadata")
    omitted_count = _count_public_items(safe_output) + _count_public_items(metadata)
    bounded["safe_output"] = {
        "truncated": True,
        "omitted_count": _count_public_items(safe_output),
    }
    bounded["metadata"] = {
        "truncated": True,
        "omitted_count": omitted_count,
        "tool_result_max_chars": max_chars,
    }
    artifacts = list(bounded.get("artifacts") or [])
    original_artifact_total = _artifact_total_count(value.get("metadata"), artifacts)
    while True:
        serialized = json.dumps(bounded, ensure_ascii=False)
        if len(serialized) <= max_chars or not artifacts:
            return serialized
        artifacts = artifacts[:-1]
        bounded["artifacts"] = artifacts
        _mark_artifacts_truncated(
            bounded["metadata"],
            total_count=original_artifact_total,
            kept_count=len(artifacts),
        )


def _mark_artifacts_truncated(
    metadata: dict[str, Any],
    *,
    total_count: int,
    kept_count: int,
) -> None:
    omitted_count = max(0, total_count - kept_count)
    if not omitted_count:
        return
    metadata["truncated"] = True
    metadata["artifact_total_count"] = total_count
    metadata["artifact_omitted_count"] = omitted_count
    metadata["artifact_kept_count"] = kept_count


def _artifact_total_count(metadata: Any, artifacts: list[Any]) -> int:
    if isinstance(metadata, dict):
        value = metadata.get("artifact_total_count")
        if isinstance(value, int) and value >= len(artifacts):
            return value
    return len(artifacts)


def _count_public_items(value: Any) -> int:
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, list | tuple):
        return len(value)
    if value:
        return 1
    return 0
