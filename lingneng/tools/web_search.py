from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from lingneng.config.settings import LingNengSettings
from lingneng.tools.artifacts import sanitize_strict_public_url
from lingneng.tools.document_generation import (
    _bounded_text,
    _coerce_result,
    _json_result,
    _public_result,
    _sanitize_public_text,
    _sanitize_public_value,
    _text_arg,
)


_CURRENT_SETTINGS: ContextVar[LingNengSettings | None] = ContextVar(
    "lingneng_web_search_settings",
    default=None,
)
_CURRENT_PROVIDER: ContextVar[WebSearchProvider | None] = ContextVar(
    "lingneng_web_search_provider",
    default=None,
)
_LINGNENG_TOOL_CONTEXT_ACTIVE: ContextVar[bool] = ContextVar(
    "lingneng_tool_context_active",
    default=False,
)
class WebSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    top_k: int
    recency_filter: str = ""
    site_filter: str = ""


class WebSearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = ""
    sources: list[dict[str, Any]] = Field(default_factory=list)
    safe_output: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    code: str | None = None
    message: str | None = None


class WebSearchProvider(Protocol):
    def search(self, request: WebSearchRequest) -> WebSearchResult: ...


@contextmanager
def web_search_context(
    settings: LingNengSettings,
    *,
    provider: WebSearchProvider | None = None,
) -> Iterator[None]:
    settings_token = _CURRENT_SETTINGS.set(settings)
    provider_token = _CURRENT_PROVIDER.set(provider)
    context_token = _LINGNENG_TOOL_CONTEXT_ACTIVE.set(True)
    _clear_tool_definition_cache()
    try:
        yield
    finally:
        _LINGNENG_TOOL_CONTEXT_ACTIVE.reset(context_token)
        _CURRENT_PROVIDER.reset(provider_token)
        _CURRENT_SETTINGS.reset(settings_token)
        _clear_tool_definition_cache()


@contextmanager
def lingneng_tool_context(settings: LingNengSettings) -> Iterator[None]:
    settings_token = _CURRENT_SETTINGS.set(settings)
    context_token = _LINGNENG_TOOL_CONTEXT_ACTIVE.set(True)
    _clear_tool_definition_cache()
    try:
        yield
    finally:
        _LINGNENG_TOOL_CONTEXT_ACTIVE.reset(context_token)
        _CURRENT_SETTINGS.reset(settings_token)
        _clear_tool_definition_cache()


def is_lingneng_tool_context_active() -> bool:
    return _LINGNENG_TOOL_CONTEXT_ACTIVE.get()


def web_search_handler(args: dict[str, Any] | None = None, **kwargs: Any) -> str:
    del kwargs
    settings = _settings()
    provider = _CURRENT_PROVIDER.get()
    if provider is None:
        return _json_result(
            _public_result(
                tool_name="web_search",
                success=False,
                status="skipped",
                summary="Web search provider is not configured.",
                code="NOT_CONFIGURED",
            ),
            settings=settings,
        )

    request = _build_search_request(args or {}, settings)
    try:
        result = _coerce_result(provider.search(request), WebSearchResult)
    except Exception:
        return _json_result(
            _public_result(
                tool_name="web_search",
                success=False,
                status="failed",
                summary="Web search provider failed.",
                code="WEB_SEARCH_PROVIDER_ERROR",
            ),
            settings=settings,
        )

    sources = _public_sources(result.sources, limit=request.top_k)
    return _json_result(
        _public_result(
            tool_name="web_search",
            success=True,
            status="succeeded",
            summary=result.summary or "Web search completed.",
            safe_output={
                **result.safe_output,
                "top_k": request.top_k,
                "source_count": len(sources),
                "sources": sources,
            },
            artifacts=[],
            metadata={
                **result.metadata,
                "source_count": len(sources),
            },
        ),
        settings=settings,
    )


def _settings() -> LingNengSettings:
    return _CURRENT_SETTINGS.get() or LingNengSettings.from_env()


def _clear_tool_definition_cache() -> None:
    try:
        from model_tools import _clear_tool_defs_cache
    except ImportError:
        return
    _clear_tool_defs_cache()


def _build_search_request(
    raw_args: dict[str, Any],
    settings: LingNengSettings,
) -> WebSearchRequest:
    return WebSearchRequest(
        query=_bounded_text(_text_arg(raw_args.get("query")), max_chars=1000),
        top_k=_normalize_top_k(raw_args.get("top_k"), settings),
        recency_filter=_bounded_text(
            _text_arg(raw_args.get("recency_filter")),
            max_chars=100,
        ),
        site_filter=_bounded_text(_text_arg(raw_args.get("site_filter")), max_chars=200),
    )


def _normalize_top_k(value: Any, settings: LingNengSettings) -> int:
    max_top_k = max(1, settings.web_search_max_top_k)
    default_top_k = min(max(1, settings.web_search_default_top_k), max_top_k)
    if value is None:
        return default_top_k
    try:
        top_k = int(value)
    except (TypeError, ValueError):
        return default_top_k
    return min(max(1, top_k), max_top_k)


def _public_sources(
    sources: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, str | None]]:
    public_sources: list[dict[str, str | None]] = []
    for source in sources:
        if len(public_sources) >= limit:
            break
        if not isinstance(source, dict):
            continue
        clean_url = _normalize_public_url(source.get("url"))
        if not clean_url:
            continue
        parts = urlsplit(clean_url)
        source_id = _sanitize_source_text(
            source.get("id") or source.get("source_id") or f"source-{len(public_sources) + 1}",
            max_chars=100,
        )
        title = _sanitize_source_text(source.get("title"), max_chars=200)
        snippet = _sanitize_source_text(source.get("snippet"), max_chars=800)
        website = _sanitize_source_text(source.get("website"), max_chars=200)
        date = _sanitize_source_text(source.get("date"), max_chars=50)
        public_sources.append(
            {
                "id": source_id or f"source-{len(public_sources) + 1}",
                "title": title,
                "url": clean_url,
                "website": website or parts.hostname or "",
                "date": date or None,
                "snippet": snippet,
            }
        )
    return public_sources


def _normalize_public_url(value: Any) -> str | None:
    return sanitize_strict_public_url(value)


def _sanitize_source_text(value: Any, *, max_chars: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    sanitized = _sanitize_public_text(value, max_chars=max_chars)
    if not isinstance(_sanitize_public_value(sanitized), str):
        return ""
    return sanitized
