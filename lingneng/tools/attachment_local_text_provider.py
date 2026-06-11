from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import AttachmentPayload
from lingneng.tools.artifacts import stable_percent_decode
from lingneng.tools.attachments import (
    AttachmentProcessingRequest,
    AttachmentProcessingResult,
    AttachmentWarning,
)


_SUPPORTED_SUFFIXES = frozenset({".txt", ".md", ".markdown", ".csv"})
_SUPPORTED_MIME_TYPES = frozenset({"text/plain", "text/markdown", "text/csv"})
_CSV_SUFFIXES = frozenset({".csv"})
_CSV_MIME_TYPES = frozenset({"text/csv"})
_ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_CJK_CHAR_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
_LOCAL_ROOT_FRAGMENT_RE = re.compile(
    r"(?<![A-Za-z0-9._-])[\\/]+(?:Users|home|private|tmp|var|etc|opt|root)\b"
)
_FORBIDDEN_TEXT_PARTS = (
    "api_key",
    "authorization",
    "awsaccesskeyid",
    "bearer ",
    "credential",
    "password",
    "passwd",
    "raw payload",
    "raw request",
    "secret",
    "signed url",
    "signature=",
    "token:",
    "token=",
    "traceback",
    "exception",
    "x-amz-credential",
    "x-amz-security-token",
    "x-amz-signature",
    "x-oss-signature",
)
_PUBLIC_FAILURE_CODES = frozenset(
    {
        "ATTACHMENT_CONTEXT_TRUNCATED",
        "ATTACHMENT_FILE_TOO_LARGE",
        "ATTACHMENT_PROVIDER_ERROR",
        "ATTACHMENT_PROVIDER_INVALID_RESULT",
        "ATTACHMENT_PROVIDER_NOT_CONFIGURED",
        "ATTACHMENT_PROVIDER_TIMEOUT",
        "ATTACHMENT_URL_INVALID",
    }
)


class LocalTextAttachmentProcessingProviderError(Exception):
    """Internal marker carrying only public attachment warning codes."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class _ProcessedAttachment:
    section: str
    truncated: bool = False


class LocalTextAttachmentProcessingProvider:
    def __init__(
        self,
        settings: LingNengSettings,
        *,
        http_client: Any | None = None,
    ) -> None:
        self.settings = settings
        self._http_client = http_client

    def process(
        self,
        request: AttachmentProcessingRequest,
    ) -> AttachmentProcessingResult:
        supported = [
            attachment
            for attachment in request.attachments
            if _is_supported_attachment(attachment)
        ]
        unsupported_count = len(request.attachments) - len(supported)
        warnings: list[AttachmentWarning] = []
        if unsupported_count:
            warnings.append(_warning("ATTACHMENT_PROVIDER_NOT_CONFIGURED"))
        if not supported:
            return AttachmentProcessingResult(
                status="skipped",
                context_text="",
                processed_count=0,
                failed_count=unsupported_count,
                selected_count=0,
                warnings=warnings or [_warning("ATTACHMENT_PROVIDER_NOT_CONFIGURED")],
                code="ATTACHMENT_PROVIDER_NOT_CONFIGURED",
            )

        sections: list[str] = []
        processed_count = 0
        failed_count = unsupported_count
        failure_code: str | None = None
        for attachment in supported:
            try:
                processed = self._process_attachment(attachment, request)
            except LocalTextAttachmentProcessingProviderError as exc:
                failed_count += 1
                public_code = _public_failure_code(exc.code)
                failure_code = failure_code or public_code
                warnings.append(_warning(public_code))
                continue
            except Exception:
                failed_count += 1
                public_code = "ATTACHMENT_PROVIDER_ERROR"
                failure_code = failure_code or public_code
                warnings.append(_warning(public_code))
                continue
            sections.append(processed.section)
            processed_count += 1
            if processed.truncated:
                warnings.append(_warning("ATTACHMENT_CONTEXT_TRUNCATED"))

        if not sections:
            code = failure_code or "ATTACHMENT_PROVIDER_ERROR"
            return AttachmentProcessingResult(
                status="failed",
                context_text="",
                processed_count=processed_count,
                failed_count=failed_count,
                selected_count=0,
                warnings=warnings or [_warning(code)],
                code=code,
            )

        return AttachmentProcessingResult(
            status="succeeded",
            context_text="\n\n".join(sections),
            processed_count=processed_count,
            failed_count=failed_count,
            selected_count=len(sections),
            warnings=warnings,
        )

    def _process_attachment(
        self,
        attachment: AttachmentPayload,
        request: AttachmentProcessingRequest,
    ) -> _ProcessedAttachment:
        body = self._download(attachment, request)
        decoded = body.decode("utf-8-sig", errors="replace")
        max_chars = max(1, int(self.settings.attachment_local_text_max_chars_per_file))
        text = _format_csv(decoded, max_chars=max_chars) if _is_csv(attachment) else decoded
        text, truncated = _bound_text(text, max_chars=max_chars)
        selected_chunks = _select_chunks(
            _chunks(
                text,
                chunk_size=int(self.settings.attachment_chunk_size),
                overlap=int(self.settings.attachment_chunk_overlap),
            ),
            query=request.query,
            limit=int(self.settings.attachment_selected_chunk_limit),
        )
        bullets = [_snippet(chunk) for chunk in selected_chunks]
        bullets = [bullet for bullet in bullets if bullet]
        if not bullets:
            raise LocalTextAttachmentProcessingProviderError(
                "ATTACHMENT_PROVIDER_INVALID_RESULT"
            )
        return _ProcessedAttachment(
            section=_format_section(attachment, bullets),
            truncated=truncated,
        )

    def _download(
        self,
        attachment: AttachmentPayload,
        request: AttachmentProcessingRequest,
    ) -> bytes:
        url = attachment.download_url.strip()
        if not _is_http_url(url):
            raise LocalTextAttachmentProcessingProviderError("ATTACHMENT_URL_INVALID")
        timeout_seconds = max(0.1, float(request.timeout_seconds))
        max_bytes = max(1, int(self.settings.attachment_local_text_max_bytes))
        if self._http_client is not None:
            return self._stream_get(
                self._http_client,
                url=url,
                timeout_seconds=timeout_seconds,
                max_bytes=max_bytes,
            )
        with httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            return self._stream_get(
                client,
                url=url,
                timeout_seconds=timeout_seconds,
                max_bytes=max_bytes,
            )

    def _stream_get(
        self,
        client: Any,
        *,
        url: str,
        timeout_seconds: float,
        max_bytes: int,
    ) -> bytes:
        try:
            with client.stream("GET", url, timeout=timeout_seconds) as response:
                status_code = int(response.status_code)
                if status_code < 200 or status_code >= 300:
                    raise LocalTextAttachmentProcessingProviderError(
                        "ATTACHMENT_PROVIDER_ERROR"
                    )
                content_length = _content_length(response)
                if content_length is not None and content_length > max_bytes:
                    raise LocalTextAttachmentProcessingProviderError(
                        "ATTACHMENT_FILE_TOO_LARGE"
                    )

                chunks: list[bytes] = []
                total_bytes = 0
                chunk_size = min(65536, max_bytes + 1)
                for chunk in response.iter_bytes(chunk_size=chunk_size):
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise LocalTextAttachmentProcessingProviderError(
                            "ATTACHMENT_FILE_TOO_LARGE"
                        )
                    chunks.append(chunk)
                return b"".join(chunks)
        except LocalTextAttachmentProcessingProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise LocalTextAttachmentProcessingProviderError(
                "ATTACHMENT_PROVIDER_TIMEOUT"
            ) from exc
        except Exception as exc:
            raise LocalTextAttachmentProcessingProviderError(
                "ATTACHMENT_PROVIDER_ERROR"
            ) from exc


def _is_supported_attachment(attachment: AttachmentPayload) -> bool:
    return (
        _file_suffix(attachment.file_name) in _SUPPORTED_SUFFIXES
        or _mime_type(attachment.mime_type) in _SUPPORTED_MIME_TYPES
    )


def _is_csv(attachment: AttachmentPayload) -> bool:
    return (
        _file_suffix(attachment.file_name) in _CSV_SUFFIXES
        or _mime_type(attachment.mime_type) in _CSV_MIME_TYPES
    )


def _file_suffix(file_name: str) -> str:
    clean = _CONTROL_CHAR_RE.sub("", file_name).strip().lower()
    if "." not in clean:
        return ""
    return "." + clean.rsplit(".", 1)[-1]


def _mime_type(mime_type: str) -> str:
    return mime_type.split(";", 1)[0].strip().lower()


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _content_length(response: Any) -> int | None:
    raw_value = getattr(response, "headers", {}).get("content-length")
    if raw_value in (None, ""):
        return None
    try:
        value = int(str(raw_value).strip())
    except ValueError as exc:
        raise LocalTextAttachmentProcessingProviderError(
            "ATTACHMENT_PROVIDER_INVALID_RESULT"
        ) from exc
    if value < 0:
        raise LocalTextAttachmentProcessingProviderError(
            "ATTACHMENT_PROVIDER_INVALID_RESULT"
        )
    return value


def _format_csv(text: str, *, max_chars: int) -> str:
    rows: list[str] = []
    total_chars = 0
    for row in csv.reader(io.StringIO(text)):
        cells = [_clean_cell(cell) for cell in row]
        if not any(cells):
            continue
        line = " | ".join(cells)
        next_total = total_chars + len(line) + (1 if rows else 0)
        if next_total > max_chars:
            break
        rows.append(line)
        total_chars = next_total
    return "\n".join(rows)


def _clean_cell(value: str) -> str:
    return " ".join(_CONTROL_CHAR_RE.sub("", value).strip().split())


def _bound_text(text: str, *, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _chunks(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    chunks = []
    start = 0
    safe_overlap = min(max(overlap, 0), max(0, chunk_size - 1))
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(end - safe_overlap, start + 1)
    return chunks


def _select_chunks(chunks: list[str], *, query: str, limit: int) -> list[str]:
    if limit <= 0:
        return []
    query_terms = _lexical_terms(query)
    if not query_terms:
        return chunks[:limit]

    scored = [
        (len(query_terms.intersection(_lexical_terms(chunk))), index, chunk)
        for index, chunk in enumerate(chunks)
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [chunk for _score, _index, chunk in scored[:limit]]


def _lexical_terms(value: str) -> set[str]:
    lowered = value.lower()
    return set(_ASCII_TOKEN_RE.findall(lowered)).union(_CJK_CHAR_RE.findall(lowered))


def _format_section(attachment: AttachmentPayload, bullets: list[str]) -> str:
    bullet_text = "\n".join(f"- {bullet}" for bullet in bullets)
    return (
        f"### {_safe_display_name(attachment.file_name)}\n"
        f"类型: {_safe_mime_display(attachment.mime_type)}\n"
        "内容摘要/片段:\n"
        f"{bullet_text}"
    )


def _snippet(value: str) -> str:
    clean = _safe_public_text(value)
    return " ".join(clean.split())


def _safe_display_name(value: str) -> str:
    clean = _safe_public_text(value)
    if not clean:
        return "attachment"
    return clean[:160]


def _safe_mime_display(value: str) -> str:
    clean = _safe_public_text(_mime_type(value))
    if not clean:
        return "application/octet-stream"
    return clean[:100]


def _safe_public_text(value: str) -> str:
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
        any(part in lowered for part in _FORBIDDEN_TEXT_PARTS)
        or value.startswith(("/", "\\", "~"))
        or "file://" in lowered
        or "local://" in lowered
        or _LOCAL_ROOT_FRAGMENT_RE.search(value) is not None
        or _WINDOWS_ABSOLUTE_PATH_RE.search(value) is not None
    )


def _public_failure_code(value: str | None) -> str:
    if value in _PUBLIC_FAILURE_CODES:
        return value
    return "ATTACHMENT_PROVIDER_ERROR"


def _warning(code: str) -> AttachmentWarning:
    return AttachmentWarning(code=_public_failure_code(code))
