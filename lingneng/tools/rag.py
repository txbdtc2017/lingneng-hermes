from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import ResolvedSessionKey


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
        context = payload.get("context") if isinstance(payload.get("context"), str) else ""
        citations = (
            payload.get("citations") if isinstance(payload.get("citations"), list) else []
        )
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
    return dict(value)


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
    sanitized = _sanitize_public_value(citations)
    if not isinstance(sanitized, list):
        return []
    return [item for item in sanitized if isinstance(item, dict)]


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
    lowered = value.lower()
    if any(part in lowered for part in _FORBIDDEN_TEXT_PARTS):
        return ""
    return value


def _is_forbidden_key(value: object) -> bool:
    lowered = str(value).lower()
    return any(part in lowered for part in _FORBIDDEN_KEY_PARTS)


def _json_result(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False)
