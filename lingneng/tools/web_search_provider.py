from __future__ import annotations

from typing import Any

import httpx

from lingneng.config.settings import LingNengSettings
from lingneng.tools.web_search import WebSearchRequest, WebSearchResult


_FRESHNESS_BY_RECENCY = {
    "week": "oneWeek",
    "month": "oneMonth",
    "semiyear": "oneYear",
    "year": "oneYear",
}


class BochaWebSearchProviderError(RuntimeError):
    """Internal-only Bocha provider failure."""


class BochaWebSearchProvider:
    request_model = WebSearchRequest

    def __init__(
        self,
        settings: LingNengSettings,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = settings.bocha_web_search_api_key
        self.base_url = settings.bocha_web_search_base_url.rstrip("/")
        self.timeout_seconds = settings.bocha_web_search_timeout_seconds
        self._http_client = http_client

    def search(self, request: WebSearchRequest) -> WebSearchResult:
        body = {
            "query": request.query,
            "freshness": _map_freshness(request.recency_filter),
            "summary": True,
            "count": request.top_k,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = self._post(body=body, headers=headers)
            response.raise_for_status()
            payload = response.json()
            if _is_error_payload(payload):
                raise BochaWebSearchProviderError("bocha web search failed")
        except BochaWebSearchProviderError:
            raise
        except Exception as exc:
            raise BochaWebSearchProviderError("bocha web search failed") from exc

        return WebSearchResult(
            summary="联网搜索完成",
            sources=_sources_from_payload(payload),
            metadata={"provider": "bocha"},
        )

    def _post(self, *, body: dict[str, Any], headers: dict[str, str]) -> httpx.Response:
        url = f"{self.base_url}/v1/web-search"
        if self._http_client is not None:
            return self._http_client.post(
                url,
                headers=headers,
                json=body,
                timeout=self.timeout_seconds,
            )
        with httpx.Client(timeout=self.timeout_seconds, trust_env=False) as client:
            return client.post(url, headers=headers, json=body)


def _map_freshness(recency_filter: str | None) -> str:
    if not recency_filter:
        return "noLimit"
    return _FRESHNESS_BY_RECENCY.get(recency_filter, "noLimit")


def _is_error_payload(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    code = payload.get("code")
    return code not in {None, 0, 200, "0", "200"}


def _sources_from_payload(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    candidates = _nested(payload, ["webPages", "value"])
    if not isinstance(candidates, list):
        candidates = _nested(payload, ["data", "webPages", "value"])
    if not isinstance(candidates, list):
        candidates = _nested(payload, ["data", "web_pages", "value"])
    if not isinstance(candidates, list):
        candidates = _nested(payload, ["references"])
    if not isinstance(candidates, list):
        candidates = []

    sources: list[dict[str, Any]] = []
    for index, item in enumerate(candidates, start=1):
        if not isinstance(item, dict):
            continue
        sources.append(
            {
                "id": item.get("id") or item.get("source_id") or f"bocha-{index}",
                "title": item.get("title") or item.get("name") or "",
                "url": item.get("url") or "",
                "website": item.get("website") or item.get("siteName") or "",
                "date": item.get("date") or item.get("datePublished"),
                "snippet": _snippet_from_item(item),
            }
        )
    return sources


def _snippet_from_item(item: dict[str, Any]) -> str:
    snippet = _text_value(item.get("snippet"))
    summary = _text_value(item.get("summary"))
    if snippet and summary and summary not in snippet:
        return f"{snippet}；{summary}"
    return snippet or summary


def _text_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _nested(payload: dict[str, Any], path: list[str]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
