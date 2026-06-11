from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from lingneng.config.settings import LingNengSettings
from lingneng.tools.document_generation import (
    DocumentGenerationRequest,
    DocumentGenerationResult,
)


_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_DANGEROUS_QUOTE_RE = re.compile(r"[\"'`“”‘’]")
_H1_RE = re.compile(r"^\s*#(?!#)\s+\S", re.MULTILINE)
_MARKDOWN_FENCE_RE = re.compile(
    r"^```(?:markdown|md)?[ \t]*\r?\n(?P<body>.*?)(?:\r?\n)?```[ \t]*$",
    re.IGNORECASE | re.DOTALL,
)
_KNOWN_DOCUMENT_SUFFIXES = (".markdown", ".md", ".pdf", ".docx", ".doc")


class JavaAgentFileProviderError(RuntimeError):
    """Internal-only Java file provider failure."""


class JavaAgentFileClient:
    def __init__(
        self,
        *,
        base_url: str,
        upload_path: str,
        internal_key: str,
        timeout_seconds: float,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.upload_path = _normalize_upload_path(upload_path)
        self.internal_key = internal_key
        self.timeout_seconds = timeout_seconds
        self._http_client = http_client

    def upload_markdown_as_pdf(
        self,
        file_name: str,
        markdown: str,
        request_id: str | None = None,
    ) -> str:
        headers = {"X-Internal-Key": self.internal_key}
        if request_id:
            headers["X-Request-Id"] = request_id
        files = {
            "file": (
                file_name,
                markdown.encode("utf-8"),
                "text/markdown",
            )
        }
        try:
            response = self._post(
                headers=headers,
                data={"fileFormat": "pdf"},
                files=files,
            )
            response.raise_for_status()
            url = _extract_upload_url(response.json())
        except JavaAgentFileProviderError:
            raise
        except Exception as exc:
            raise JavaAgentFileProviderError("java file upload failed") from exc
        if not url:
            raise JavaAgentFileProviderError("java file upload failed")
        return url

    def _post(
        self,
        *,
        headers: dict[str, str],
        data: dict[str, str],
        files: dict[str, tuple[str, bytes, str]],
    ) -> httpx.Response:
        url = f"{self.base_url}{self.upload_path}"
        if self._http_client is not None:
            return self._http_client.post(
                url,
                headers=headers,
                data=data,
                files=files,
                timeout=self.timeout_seconds,
            )
        with httpx.Client(timeout=self.timeout_seconds, trust_env=False) as client:
            return client.post(url, headers=headers, data=data, files=files)


class JavaFileDocumentProvider:
    def __init__(
        self,
        settings: LingNengSettings,
        *,
        java_file_client: JavaAgentFileClient | None = None,
    ) -> None:
        self.settings = settings
        self.java_file_client = java_file_client or JavaAgentFileClient(
            base_url=settings.java_agent_file_base_url,
            upload_path=settings.java_agent_file_upload_path,
            internal_key=settings.java_internal_key,
            timeout_seconds=settings.java_agent_file_upload_timeout_seconds,
        )

    @classmethod
    def from_settings(cls, settings: LingNengSettings) -> "JavaFileDocumentProvider":
        return cls(
            settings,
            java_file_client=JavaAgentFileClient(
                base_url=settings.java_agent_file_base_url,
                upload_path=settings.java_agent_file_upload_path,
                internal_key=settings.java_internal_key,
                timeout_seconds=settings.java_agent_file_upload_timeout_seconds,
            ),
        )

    def generate(self, request: DocumentGenerationRequest) -> DocumentGenerationResult:
        source_file_name = safe_document_source_file_name(request.title)
        source_markdown = build_document_source_markdown(
            title=request.title,
            document_content=request.content,
        )
        public_url = self.java_file_client.upload_markdown_as_pdf(
            file_name=source_file_name,
            markdown=source_markdown,
        )
        artifact = create_external_document_artifact(
            file_name=safe_pdf_file_name(request.title),
            url=public_url,
        )
        safe_output = {
            **document_source_debug_summary(
                source_file_name=source_file_name,
                source_content=source_markdown,
            ),
            "artifact_count": 1,
        }
        return DocumentGenerationResult(
            summary="PDF 文档生成完成",
            artifacts=[artifact],
            safe_output=safe_output,
            metadata={"provider": "java_file", "artifact_count": 1},
        )


def build_document_source_markdown(*, title: str, document_content: str) -> str:
    body = _unwrap_markdown_fence(document_content.strip())
    if not _has_h1(body):
        safe_title = safe_document_title(title)
        body = f"# {safe_title}\n\n{body}" if body else f"# {safe_title}"
    return body.rstrip() + "\n"


def safe_document_title(value: str) -> str:
    title = _safe_name_segment(value)
    title = _strip_known_document_suffix(title)
    return title or "生成文档"


def safe_document_source_file_name(value: str) -> str:
    return _safe_file_name(
        value,
        extension=".md",
        default_file_name="生成文档.md",
    )


def safe_pdf_file_name(value: str) -> str:
    return _safe_file_name(
        value,
        extension=".pdf",
        default_file_name="生成文档.pdf",
    )


def document_source_debug_summary(
    *,
    source_file_name: str,
    source_content: str,
) -> dict[str, Any]:
    return {
        "source_format": "markdown",
        "source_file_name": source_file_name,
        "source_content_length": len(source_content),
        "source_content_sha256": hashlib.sha256(
            source_content.encode("utf-8")
        ).hexdigest(),
    }


def create_external_document_artifact(*, file_name: str, url: str) -> dict[str, Any]:
    artifact_id = f"artifact_{uuid4().hex}"
    return {
        "artifact_id": artifact_id,
        "artifact_type": "document",
        "source": "document_generation",
        "file_name": safe_pdf_file_name(file_name),
        "mime_type": "application/pdf",
        "url": url,
        "object_key": f"external/java-agent-file/{artifact_id}",
        "format": "pdf",
        "target_format": "pdf",
        "conversion_required": False,
        "conversion_owner": None,
    }


def _normalize_upload_path(value: str) -> str:
    path = value.strip()
    if not path:
        return "/"
    if not path.startswith("/"):
        return f"/{path}"
    return path


def _extract_upload_url(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    candidates = [
        data if isinstance(data, str) else None,
        data.get("url") if isinstance(data, dict) else None,
        data.get("download_url") if isinstance(data, dict) else None,
        payload.get("url"),
        payload.get("download_url"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and _is_http_url(candidate):
            return candidate.strip()
    return None


def _is_http_url(value: str) -> bool:
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return False
    return parts.scheme.lower() in {"http", "https"} and bool(parts.netloc)


def _unwrap_markdown_fence(value: str) -> str:
    match = _MARKDOWN_FENCE_RE.match(value)
    if match is None:
        return value
    return match.group("body").strip()


def _has_h1(value: str) -> bool:
    return _H1_RE.search(value) is not None


def _safe_file_name(
    value: str,
    *,
    extension: str,
    default_file_name: str,
) -> str:
    stem = _strip_known_document_suffix(_safe_name_segment(value))
    if not stem:
        return default_file_name
    return f"{stem}{extension}"


def _safe_name_segment(value: str) -> str:
    if value is None:
        return ""
    segment = PurePosixPath(str(value).replace("\\", "/")).name
    segment = _CONTROL_CHAR_RE.sub("", segment)
    segment = _DANGEROUS_QUOTE_RE.sub("", segment)
    return segment.strip(" .")


def _strip_known_document_suffix(value: str) -> str:
    lowered = value.lower()
    for suffix in _KNOWN_DOCUMENT_SUFFIXES:
        if lowered.endswith(suffix):
            return value[: -len(suffix)].strip(" .")
    return value
