from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import AttachmentPayload, ChatStreamRequest
from lingneng.tools.artifacts import sanitize_strict_public_url


AttachmentProviderStatus = Literal["succeeded", "failed", "skipped", "timeout"]
AttachmentPromptStatus = Literal["empty", "succeeded", "skipped", "failed"]

_CURRENT_PROVIDER: ContextVar[AttachmentProcessingProvider | None] = ContextVar(
    "lingneng_attachment_processing_provider",
    default=None,
)
_ATTACHMENT_PROMPT_HEADING = "## LingNeng Current Request Attachments"
_IMAGE_SUFFIXES = frozenset(
    {
        ".apng",
        ".avif",
        ".bmp",
        ".gif",
        ".heic",
        ".heif",
        ".jpeg",
        ".jpg",
        ".png",
        ".svg",
        ".tif",
        ".tiff",
        ".webp",
    }
)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
_LOCAL_ROOT_FRAGMENT_RE = re.compile(
    r"(?<![A-Za-z0-9._-])[\\/]+(?:Users|home|private|tmp|var|etc|opt|root)\b"
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
    "exception",
)
_PUBLIC_WARNING_CODES = frozenset(
    {
        "ATTACHMENT_CONTEXT_TRUNCATED",
        "ATTACHMENT_FILE_TOO_LARGE",
        "ATTACHMENT_HOST_NOT_ALLOWED",
        "ATTACHMENT_IMAGE_TOO_LARGE",
        "ATTACHMENT_MAX_FILES_EXCEEDED",
        "ATTACHMENT_PROVIDER_ERROR",
        "ATTACHMENT_PROVIDER_INVALID_RESULT",
        "ATTACHMENT_PROVIDER_NOT_CONFIGURED",
        "ATTACHMENT_PROVIDER_TIMEOUT",
        "ATTACHMENT_TOTAL_BYTES_EXCEEDED",
        "ATTACHMENT_URL_INVALID",
    }
)
_PUBLIC_WARNING_MESSAGES = {
    "ATTACHMENT_CONTEXT_TRUNCATED": "Attachment context was truncated.",
    "ATTACHMENT_FILE_TOO_LARGE": "Attachment exceeds the per-file byte limit.",
    "ATTACHMENT_HOST_NOT_ALLOWED": "Attachment download host is not allowed.",
    "ATTACHMENT_IMAGE_TOO_LARGE": "Image attachment exceeds the image byte limit.",
    "ATTACHMENT_MAX_FILES_EXCEEDED": "Attachment count exceeds the request limit.",
    "ATTACHMENT_PROVIDER_ERROR": "Attachment processing provider failed.",
    "ATTACHMENT_PROVIDER_INVALID_RESULT": (
        "Attachment processing provider returned an invalid result."
    ),
    "ATTACHMENT_PROVIDER_NOT_CONFIGURED": (
        "Attachment processing provider is not configured."
    ),
    "ATTACHMENT_PROVIDER_TIMEOUT": "Attachment processing provider timed out.",
    "ATTACHMENT_TOTAL_BYTES_EXCEEDED": (
        "Attachment total size exceeds the request limit."
    ),
    "ATTACHMENT_URL_INVALID": "Attachment download URL is invalid.",
}


class AttachmentWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str | None = None
    file_id: str | None = None


class AttachmentProcessingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    user_id: str
    session_id: str
    conversation_id: str | None
    request_id: str
    employee_type: str
    attachments: list[AttachmentPayload] = Field(default_factory=list)
    timeout_seconds: float
    context_max_chars: int


class AttachmentProcessingResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: AttachmentProviderStatus = "succeeded"
    context_text: str = ""
    processed_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    selected_count: int = Field(default=0, ge=0)
    warnings: list[AttachmentWarning] = Field(default_factory=list)
    code: str | None = None
    message: str | None = None


class AttachmentPromptContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_text: str = ""
    status: AttachmentPromptStatus = "empty"
    selected_count: int = Field(default=0, ge=0)
    processed_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    warnings: list[AttachmentWarning] = Field(default_factory=list)


class AttachmentProcessingProvider(Protocol):
    def process(
        self,
        request: AttachmentProcessingRequest,
    ) -> AttachmentProcessingResult | dict[str, Any]:
        ...


@contextmanager
def attachment_processing_context(
    *,
    provider: AttachmentProcessingProvider | None = None,
) -> Iterator[None]:
    provider_token = _CURRENT_PROVIDER.set(provider)
    try:
        yield
    finally:
        _CURRENT_PROVIDER.reset(provider_token)


def build_attachment_prompt_context(
    settings: LingNengSettings,
    request: ChatStreamRequest,
) -> AttachmentPromptContext:
    attachments = list(request.attachments)
    if not attachments:
        return AttachmentPromptContext()

    if len(attachments) > settings.attachment_max_files:
        return _skipped_context(
            [
                _warning(
                    "ATTACHMENT_MAX_FILES_EXCEEDED",
                )
            ]
        )

    selected, warnings = _select_attachments(settings, attachments)
    if not selected:
        return _skipped_context(warnings)

    total_bytes = sum(_attachment_size(item) for item in selected)
    if total_bytes > settings.attachment_max_total_bytes:
        return _skipped_context(
            [
                *warnings,
                _warning(
                    "ATTACHMENT_TOTAL_BYTES_EXCEEDED",
                ),
            ],
            selected_count=len(selected),
        )

    provider = _CURRENT_PROVIDER.get()
    if provider is None:
        return _skipped_context(
            [
                *warnings,
                _warning("ATTACHMENT_PROVIDER_NOT_CONFIGURED"),
            ],
            selected_count=len(selected),
        )

    provider_request = AttachmentProcessingRequest(
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        session_id=request.session_id,
        conversation_id=request.conversation_id,
        request_id=request.request_id,
        employee_type=request.employee.employee_type.value,
        attachments=selected,
        timeout_seconds=settings.attachment_timeout_seconds,
        context_max_chars=settings.attachment_context_max_chars,
    )
    try:
        provider_result = _coerce_provider_result(provider.process(provider_request))
    except ValidationError:
        return _failed_context(
            [
                *warnings,
                _warning("ATTACHMENT_PROVIDER_INVALID_RESULT"),
            ],
            selected_count=len(selected),
            failed_count=len(selected),
        )
    except Exception:
        return _failed_context(
            [
                *warnings,
                _warning("ATTACHMENT_PROVIDER_ERROR"),
            ],
            selected_count=len(selected),
            failed_count=len(selected),
        )

    provider_warnings = _public_provider_warnings(provider_result.warnings)
    selected_count = provider_result.selected_count or len(selected)
    if _is_timeout_result(provider_result):
        return _failed_context(
            [
                *warnings,
                *provider_warnings,
                _warning("ATTACHMENT_PROVIDER_TIMEOUT"),
            ],
            selected_count=selected_count,
            processed_count=provider_result.processed_count,
            failed_count=provider_result.failed_count or len(selected),
        )
    if provider_result.status == "failed":
        return _failed_context(
            [
                *warnings,
                *provider_warnings,
                _warning(_public_failure_code(provider_result.code)),
            ],
            selected_count=selected_count,
            processed_count=provider_result.processed_count,
            failed_count=provider_result.failed_count or len(selected),
        )
    if provider_result.status == "skipped":
        return _skipped_context(
            [
                *warnings,
                *provider_warnings,
                _warning(_public_failure_code(provider_result.code)),
            ],
            selected_count=selected_count,
            processed_count=provider_result.processed_count,
            failed_count=provider_result.failed_count,
        )

    context_text, truncated = _bounded_context_text(
        provider_result.context_text,
        max_chars=settings.attachment_context_max_chars,
    )
    if truncated:
        warnings.append(_warning("ATTACHMENT_CONTEXT_TRUNCATED"))
    prompt_text = (
        f"{_ATTACHMENT_PROMPT_HEADING}\n\n{context_text}" if context_text else ""
    )
    return AttachmentPromptContext(
        prompt_text=prompt_text,
        status="succeeded",
        selected_count=selected_count,
        processed_count=provider_result.processed_count,
        failed_count=provider_result.failed_count,
        warnings=[*warnings, *provider_warnings],
    )


def _select_attachments(
    settings: LingNengSettings,
    attachments: list[AttachmentPayload],
) -> tuple[list[AttachmentPayload], list[AttachmentWarning]]:
    selected: list[AttachmentPayload] = []
    warnings: list[AttachmentWarning] = []
    allowed_hosts = _normalized_allowed_hosts(settings.attachment_allowed_hosts)
    for attachment in attachments:
        clean_url = sanitize_strict_public_url(attachment.download_url)
        if not clean_url:
            warnings.append(_warning("ATTACHMENT_URL_INVALID", attachment=attachment))
            continue
        host = _url_host(clean_url)
        if not host:
            warnings.append(_warning("ATTACHMENT_URL_INVALID", attachment=attachment))
            continue
        if allowed_hosts and host not in allowed_hosts:
            warnings.append(
                _warning("ATTACHMENT_HOST_NOT_ALLOWED", attachment=attachment)
            )
            continue

        size = _attachment_size(attachment)
        if size > settings.attachment_max_file_bytes:
            warnings.append(_warning("ATTACHMENT_FILE_TOO_LARGE", attachment=attachment))
            continue
        if _is_image_attachment(attachment) and size > settings.attachment_max_image_bytes:
            warnings.append(_warning("ATTACHMENT_IMAGE_TOO_LARGE", attachment=attachment))
            continue

        selected.append(_attachment_with_url(attachment, clean_url))
    return selected, warnings


def _coerce_provider_result(value: Any) -> AttachmentProcessingResult:
    if isinstance(value, AttachmentProcessingResult):
        return value
    return AttachmentProcessingResult.model_validate(value)


def _bounded_context_text(value: str, *, max_chars: int) -> tuple[str, bool]:
    sanitized = _sanitize_prompt_text(value)
    if max_chars <= 0:
        return "", bool(sanitized)
    if len(sanitized) <= max_chars:
        return sanitized, False
    return sanitized[:max_chars], True


def _sanitize_prompt_text(value: str) -> str:
    if not isinstance(value, str):
        return ""
    clean_text = _CONTROL_CHAR_RE.sub("", value).strip()
    lowered = clean_text.lower()
    if (
        any(part in lowered for part in _FORBIDDEN_TEXT_PARTS)
        or _looks_like_local_path(clean_text)
        or _contains_embedded_local_path(clean_text)
    ):
        return ""
    return clean_text


def _public_provider_warnings(
    warnings: list[AttachmentWarning],
) -> list[AttachmentWarning]:
    return [
        _warning(warning.code, file_id=warning.file_id)
        for warning in warnings
        if warning.code
    ]


def _failed_context(
    warnings: list[AttachmentWarning],
    *,
    selected_count: int = 0,
    processed_count: int = 0,
    failed_count: int = 0,
) -> AttachmentPromptContext:
    return AttachmentPromptContext(
        prompt_text="",
        status="failed",
        selected_count=selected_count,
        processed_count=processed_count,
        failed_count=failed_count,
        warnings=warnings,
    )


def _skipped_context(
    warnings: list[AttachmentWarning],
    *,
    selected_count: int = 0,
    processed_count: int = 0,
    failed_count: int = 0,
) -> AttachmentPromptContext:
    return AttachmentPromptContext(
        prompt_text="",
        status="skipped",
        selected_count=selected_count,
        processed_count=processed_count,
        failed_count=failed_count,
        warnings=warnings,
    )


def _is_timeout_result(result: AttachmentProcessingResult) -> bool:
    return result.status == "timeout" or result.code == "ATTACHMENT_PROVIDER_TIMEOUT"


def _public_failure_code(value: str | None) -> str:
    if value in _PUBLIC_WARNING_CODES:
        return value
    return "ATTACHMENT_PROVIDER_ERROR"


def _warning(
    code: str,
    *,
    attachment: AttachmentPayload | None = None,
    file_id: str | None = None,
) -> AttachmentWarning:
    public_code = code if code in _PUBLIC_WARNING_CODES else "ATTACHMENT_PROVIDER_ERROR"
    return AttachmentWarning(
        code=public_code,
        message=_PUBLIC_WARNING_MESSAGES.get(public_code),
        file_id=_safe_file_id(file_id or (attachment.file_id if attachment else None)),
    )


def _safe_file_id(value: str | None) -> str | None:
    if not value:
        return None
    clean = _CONTROL_CHAR_RE.sub("", value).strip()
    if not clean or _contains_embedded_local_path(clean):
        return None
    return clean[:128]


def _attachment_with_url(
    attachment: AttachmentPayload,
    clean_url: str,
) -> AttachmentPayload:
    data = attachment.model_dump()
    data["download_url"] = clean_url
    return AttachmentPayload.model_validate(data)


def _normalized_allowed_hosts(hosts: list[str]) -> set[str]:
    normalized: set[str] = set()
    for host in hosts:
        value = host.strip().lower()
        if not value:
            continue
        if "://" in value:
            parsed_host = _url_host(value)
            if parsed_host:
                normalized.add(parsed_host)
            continue
        normalized.add(value.split("/", 1)[0].split(":", 1)[0])
    return normalized


def _url_host(value: str) -> str | None:
    try:
        return urlsplit(value).hostname.lower()  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        return None


def _attachment_size(attachment: AttachmentPayload) -> int:
    if attachment.size is None:
        return 0
    return max(0, int(attachment.size))


def _is_image_attachment(attachment: AttachmentPayload) -> bool:
    mime_type = attachment.mime_type.strip().lower()
    if mime_type.startswith("image/"):
        return True
    file_name = attachment.file_name.strip().lower()
    return any(file_name.endswith(suffix) for suffix in _IMAGE_SUFFIXES)


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
