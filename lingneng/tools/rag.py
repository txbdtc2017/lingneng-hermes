from __future__ import annotations

import json
import math
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_events import Citation
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import ResolvedSessionKey
from lingneng.tools.artifacts import stable_percent_decode


@dataclass(frozen=True)
class RagRequestContext:
    settings: LingNengSettings
    tenant_id: str
    user_id: str
    employee_type: str
    conversation_id: str | None
    session_key: str
    request_id: str


class RagRetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    tenant_id: str
    user_id: str
    employee_type: str
    conversation_id: str | None
    session_key: str
    request_id: str
    top_k: int
    filters: dict[str, Any] = Field(default_factory=dict)


class RagRetrieveResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["hit", "empty", "failed"]
    context: str = ""
    citations: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    code: str | None = None
    message: str | None = None


class RagProvider(Protocol):
    def retrieve(self, request: RagRetrieveRequest) -> RagRetrieveResult: ...


_CURRENT_CONTEXT: ContextVar[RagRequestContext | None] = ContextVar(
    "lingneng_rag_request_context",
    default=None,
)
_CURRENT_PROVIDER: ContextVar[RagProvider | None] = ContextVar(
    "lingneng_rag_provider",
    default=None,
)
_FORBIDDEN_KEY_PARTS = (
    "api_key",
    "authorization",
    "bearer",
    "credential",
    "input",
    "password",
    "passwd",
    "query",
    "secret",
    "token",
    "traceback",
    "exception",
    "history",
    "request",
    "payload",
    "args",
)
_FORBIDDEN_TEXT_PARTS = (
    "api_key",
    "authorization",
    "bearer",
    "credential",
    "password",
    "passwd",
    "raw input",
    "raw query",
    "raw request",
    "secret",
    "token",
    "traceback",
    "exception",
    "user private input",
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
    r"(?<![A-Za-z0-9._-])[\\/]+"
    r"(?:Users|home|private|tmp|var|etc|opt|root|Volumes|Library|usr)\b",
    re.IGNORECASE,
)
_HOME_PATH_FRAGMENT_RE = re.compile(r"(?<![A-Za-z0-9._-])~[\\/]")
_PATH_TRAVERSAL_FRAGMENT_RE = re.compile(r"(?:^|[\s\\/])\.\.(?:[\\/]|$)")
_LOCAL_FILE_URL_RE = re.compile(r"(?i)\bfile://")
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
_PUBLIC_FAILURE_CODES = frozenset(
    {
        "RAG_CONTEXT_MISSING",
        "INVALID_RAG_QUERY",
        "NOT_CONFIGURED",
        "RAG_PROVIDER_ERROR",
        "RAG_PROVIDER_INVALID_RESULT",
        "RAG_PROVIDER_TIMEOUT",
    }
)
_RAG_FILTER_MAX_DEPTH = 4
_RAG_FILTER_MAX_KEYS = 32
_RAG_FILTER_MAX_LIST_ITEMS = 32
_RAG_FILTER_MAX_STRING_CHARS = 256
_RAG_FILTER_MAX_SERIALIZED_BYTES = 4096
_FILTER_DROP = object()


@dataclass(frozen=True)
class _HttpRagResponse:
    status_code: int
    content: bytes = b""
    exceeded_size: bool = False


class HttpRagProvider:
    def __init__(
        self,
        settings: LingNengSettings,
        *,
        http_client: Any | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client

    def retrieve(self, request: RagRetrieveRequest) -> RagRetrieveResult:
        try:
            response = self._post(request.model_dump())
        except httpx.TimeoutException:
            return _provider_failure("RAG_PROVIDER_TIMEOUT")
        except Exception:
            return _provider_failure("RAG_PROVIDER_ERROR")

        if response.exceeded_size:
            return _provider_failure("RAG_PROVIDER_INVALID_RESULT")
        if response.status_code < 200 or response.status_code >= 300:
            return _provider_failure("RAG_PROVIDER_ERROR")

        try:
            payload = json.loads(response.content.decode("utf-8"))
            return _coerce_rag_provider_payload(payload)
        except Exception:
            return _provider_failure("RAG_PROVIDER_INVALID_RESULT")

    def _post(self, payload: dict[str, Any]) -> _HttpRagResponse:
        if self._http_client is not None:
            return self._post_with_client(self._http_client, payload)

        with httpx.Client(
            timeout=self._settings.rag_timeout_seconds,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            return self._post_with_client(client, payload)

    def _post_with_client(
        self,
        client: Any,
        payload: dict[str, Any],
    ) -> _HttpRagResponse:
        headers = (
            {"Authorization": f"Bearer {self._settings.rag_api_key}"}
            if self._settings.rag_api_key
            else {}
        )
        with client.stream(
            "POST",
            self._settings.rag_endpoint,
            json=payload,
            headers=headers,
            timeout=self._settings.rag_timeout_seconds,
        ) as response:
            status_code = int(response.status_code)
            if status_code < 200 or status_code >= 300:
                return _HttpRagResponse(status_code=status_code)

            chunks: list[bytes] = []
            total_size = 0
            max_size = self._settings.rag_http_max_response_bytes
            chunk_size = min(65536, max_size + 1)
            for chunk in response.iter_bytes(chunk_size=chunk_size):
                next_size = total_size + len(chunk)
                if next_size > max_size:
                    return _HttpRagResponse(
                        status_code=status_code,
                        exceeded_size=True,
                    )
                chunks.append(chunk)
                total_size = next_size

            return _HttpRagResponse(
                status_code=status_code,
                content=b"".join(chunks),
            )


def _provider_failure(code: str) -> RagRetrieveResult:
    return RagRetrieveResult(
        status="failed",
        code=_public_failure_code(code, default="RAG_PROVIDER_ERROR"),
    )


def _coerce_rag_provider_payload(payload: Any) -> RagRetrieveResult:
    if isinstance(payload, dict) and "status" in payload:
        return RagRetrieveResult.model_validate(payload)
    if isinstance(payload, dict) and (
        "context" in payload or "citations" in payload or "route_debug" in payload
    ):
        if "context" in payload and not isinstance(payload.get("context"), str):
            raise ValueError("invalid RAG provider response")
        context = payload.get("context", "")
        if "citations" in payload and not isinstance(payload.get("citations"), list):
            raise ValueError("invalid RAG provider response")
        citations = payload.get("citations", [])
        status: Literal["hit", "empty"] = "hit" if context or citations else "empty"
        metadata = (
            payload.get("route_debug")
            if isinstance(payload.get("route_debug"), dict)
            else {}
        )
        return RagRetrieveResult(
            status=status,
            context=context,
            citations=citations,
            metadata=metadata,
        )
    raise ValueError("invalid RAG provider response")


def build_rag_request_context(
    *,
    settings: LingNengSettings,
    request: ChatStreamRequest,
    resolved_session: ResolvedSessionKey,
) -> RagRequestContext:
    return RagRequestContext(
        settings=settings,
        tenant_id=resolved_session.tenant_id,
        user_id=resolved_session.user_id,
        employee_type=resolved_session.employee_type,
        conversation_id=resolved_session.conversation_id,
        session_key=resolved_session.session_key,
        request_id=request.request_id,
    )


@contextmanager
def rag_request_context(
    context: RagRequestContext,
    *,
    provider: RagProvider | None = None,
) -> Iterator[None]:
    context_token = _CURRENT_CONTEXT.set(context)
    provider_token = _CURRENT_PROVIDER.set(provider)
    try:
        yield
    finally:
        _CURRENT_PROVIDER.reset(provider_token)
        _CURRENT_CONTEXT.reset(context_token)


def retrieve_rag_handler(args: dict[str, Any] | None = None, **kwargs: Any) -> str:
    del kwargs
    context = _CURRENT_CONTEXT.get()
    if context is None:
        return _json_result(_failed_result("RAG_CONTEXT_MISSING"))

    raw_args = args or {}
    query = raw_args.get("query")
    if not isinstance(query, str) or not query.strip():
        return _json_result(_failed_result("INVALID_RAG_QUERY"))

    provider = _CURRENT_PROVIDER.get()
    if provider is None:
        endpoint = context.settings.rag_endpoint.strip()
        if not endpoint:
            return _json_result(_failed_result("NOT_CONFIGURED"))
        provider = HttpRagProvider(context.settings)

    request = RagRetrieveRequest(
        query=query.strip(),
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        employee_type=context.employee_type,
        conversation_id=context.conversation_id,
        session_key=context.session_key,
        request_id=context.request_id,
        top_k=_normalize_top_k(raw_args.get("top_k"), context.settings),
        filters=_normalize_filters(raw_args.get("filters")),
    )

    try:
        result = provider.retrieve(request)
    except Exception:
        return _json_result(_failed_result("RAG_PROVIDER_ERROR"))
    if not isinstance(result, RagRetrieveResult):
        return _json_result(_failed_result("RAG_PROVIDER_INVALID_RESULT"))

    return _json_result(_normalize_provider_result(result, context.settings))


def _normalize_top_k(value: Any, settings: LingNengSettings) -> int:
    max_top_k = max(1, settings.rag_max_top_k)
    default_top_k = min(max(1, settings.rag_default_top_k), max_top_k)
    if value is None:
        return default_top_k
    try:
        top_k = int(value)
    except (TypeError, ValueError):
        return default_top_k
    return min(max(1, top_k), max_top_k)


def _normalize_filters(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized = _normalize_filter_mapping(value, depth=0)
    try:
        serialized = json.dumps(
            normalized,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        return {}
    if len(serialized.encode("utf-8")) > _RAG_FILTER_MAX_SERIALIZED_BYTES:
        return {}
    return normalized


def _normalize_filter_mapping(
    value: dict[Any, Any],
    *,
    depth: int,
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if len(normalized) >= _RAG_FILTER_MAX_KEYS:
            break
        if not isinstance(key, str):
            continue
        normalized_item = _normalize_filter_value(item, depth=depth + 1)
        if normalized_item is _FILTER_DROP:
            continue
        normalized[key[:_RAG_FILTER_MAX_STRING_CHARS]] = normalized_item
    return normalized


def _normalize_filter_value(value: Any, *, depth: int) -> Any:
    if isinstance(value, dict):
        if depth > _RAG_FILTER_MAX_DEPTH:
            return {}
        return _normalize_filter_mapping(value, depth=depth)
    if isinstance(value, list | tuple):
        if depth > _RAG_FILTER_MAX_DEPTH:
            return []
        normalized: list[Any] = []
        for item in value[:_RAG_FILTER_MAX_LIST_ITEMS]:
            normalized_item = _normalize_filter_value(item, depth=depth + 1)
            if normalized_item is not _FILTER_DROP:
                normalized.append(normalized_item)
        return normalized
    if isinstance(value, str):
        return value[:_RAG_FILTER_MAX_STRING_CHARS]
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return _FILTER_DROP
    return _FILTER_DROP


def _normalize_provider_result(
    result: RagRetrieveResult,
    settings: LingNengSettings,
) -> dict[str, Any]:
    context = _sanitize_public_text(result.context or "")
    if len(context) > settings.rag_context_max_chars:
        context = context[: settings.rag_context_max_chars]
    citations = _sanitize_citations(result.citations)
    metadata = _sanitize_metadata(result.metadata)
    metadata["selected_count"] = len(citations)
    metadata["citation_count"] = len(citations)

    if result.status == "failed":
        code = _public_failure_code(result.code, default="RAG_PROVIDER_ERROR")
        return _failed_result(code, context=context, metadata=metadata)

    return {
        "success": True,
        "tool_name": "retrieve_rag",
        "status": result.status,
        "context": context,
        "citations": citations,
        "metadata": metadata,
    }


def _failed_result(
    code: str,
    *,
    context: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "tool_name": "retrieve_rag",
        "status": "failed",
        "code": code,
        "message": _public_error_message(code),
        "context": context,
        "citations": [],
        "metadata": metadata or {"selected_count": 0, "citation_count": 0},
    }


def _public_error_message(code: str) -> str:
    messages = {
        "RAG_CONTEXT_MISSING": "LingNeng RAG request context is missing.",
        "INVALID_RAG_QUERY": "LingNeng RAG query is invalid.",
        "NOT_CONFIGURED": "LingNeng RAG provider is not configured.",
        "RAG_PROVIDER_ERROR": "LingNeng RAG provider failed.",
        "RAG_PROVIDER_TIMEOUT": "LingNeng RAG provider timed out.",
    }
    return messages.get(code, "LingNeng RAG retrieval failed.")


def _public_failure_code(value: str | None, *, default: str) -> str:
    if value in _PUBLIC_FAILURE_CODES:
        return value
    return default


def _sanitize_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(citations, list):
        return []
    sanitized: list[dict[str, Any]] = []
    for item in citations:
        if not isinstance(item, dict):
            continue
        citation: dict[str, Any] = {}
        for key in _PUBLIC_CITATION_FIELDS:
            if key in item:
                citation[key] = _sanitize_public_value(item[key])
        try:
            sanitized.append(Citation.model_validate(citation).model_dump(mode="json"))
        except ValidationError:
            continue
    return sanitized


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_public_value(metadata)
    if not isinstance(sanitized, dict):
        return {}
    return sanitized


def _sanitize_public_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _sanitize_public_value(item)
            for key, item in value.items()
            if not _is_forbidden_key(key)
        }
    if isinstance(value, list | tuple):
        return [_sanitize_public_value(item) for item in value]
    if isinstance(value, str):
        return _sanitize_public_text(value)
    if value is None or isinstance(value, bool | int | float):
        return value
    return None


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
        or _HOME_PATH_FRAGMENT_RE.search(value) is not None
        or _PATH_TRAVERSAL_FRAGMENT_RE.search(value) is not None
        or _LOCAL_FILE_URL_RE.search(value) is not None
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
            _is_forbidden_key(key) or _contains_forbidden_payload_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_payload_key(item) for item in value)
    return False


def _is_forbidden_key(value: object) -> bool:
    lowered = str(value).lower()
    return any(part in lowered for part in _FORBIDDEN_KEY_PARTS)


def _json_result(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False)
