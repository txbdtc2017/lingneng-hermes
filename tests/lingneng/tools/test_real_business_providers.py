from __future__ import annotations

import json
from pathlib import Path

import httpx

from lingneng.config.settings import LingNengSettings
from lingneng.tools.providers import (
    build_lingneng_tool_providers,
    build_web_search_provider,
)
from lingneng.tools.web_search_provider import BochaWebSearchProvider


def settings(tmp_path: Path, **env_overrides: str) -> LingNengSettings:
    env = {"LINGNENG_RUNTIME_DIR": str(tmp_path)}
    env.update(env_overrides)
    return LingNengSettings.from_env(env)


def test_provider_factory_returns_none_for_incomplete_config(tmp_path):
    providers = build_lingneng_tool_providers(settings(tmp_path))

    assert providers.web_search is None
    assert providers.document_generation is None
    assert providers.image_generation is None
    assert providers.chart_visualization is None


def test_bocha_provider_sends_expected_request_and_normalizes_sources(tmp_path):
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["content_type"] = request.headers["Content-Type"]
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "code": 200,
                "data": {
                    "webPages": {
                        "value": [
                            {
                                "id": "bocha-1",
                                "name": "餐饮趋势",
                                "url": "https://example.com/trend",
                                "summary": "公开摘要",
                                "siteName": "Example",
                                "datePublished": "2026-06-11",
                            }
                        ]
                    }
                },
            },
        )

    provider = BochaWebSearchProvider(
        settings(
            tmp_path,
            LINGNENG_WEB_SEARCH_PROVIDER="bocha",
            LINGNENG_BOCHA_WEB_SEARCH_API_KEY="key",
            LINGNENG_BOCHA_WEB_SEARCH_BASE_URL="https://bocha.example",
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.search(
        provider.request_model(query="餐饮趋势", top_k=5, recency_filter="week")
    )

    assert captured["url"] == "https://bocha.example/v1/web-search"
    assert captured["authorization"] == "Bearer key"
    assert "application/json" in str(captured["content_type"])
    assert captured["body"] == {
        "query": "餐饮趋势",
        "freshness": "oneWeek",
        "summary": True,
        "count": 5,
    }
    assert result.sources == [
        {
            "id": "bocha-1",
            "title": "餐饮趋势",
            "url": "https://example.com/trend",
            "website": "Example",
            "date": "2026-06-11",
            "snippet": "公开摘要",
        }
    ]


def test_bocha_provider_accepts_official_top_level_web_pages_shape(tmp_path):
    official_payload = {
        "_type": "SearchResponse",
        "queryContext": {"originalQuery": "灵能 AI"},
        "webPages": {
            "totalEstimatedMatches": 1,
            "value": [
                {
                    "id": "official-1",
                    "name": "灵能 AI 官方搜索结果",
                    "url": "https://example.com/official",
                    "siteName": "Example",
                    "siteIcon": "https://example.com/icon.png",
                    "snippet": "网页片段",
                    "summary": "可用摘要",
                    "datePublished": "2026-06-11",
                }
            ],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json=official_payload)

    provider = BochaWebSearchProvider(
        settings(
            tmp_path,
            LINGNENG_WEB_SEARCH_PROVIDER="bocha",
            LINGNENG_BOCHA_WEB_SEARCH_API_KEY="key",
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.search(provider.request_model(query="灵能 AI", top_k=1))

    assert result.sources == [
        {
            "id": "official-1",
            "title": "灵能 AI 官方搜索结果",
            "url": "https://example.com/official",
            "website": "Example",
            "date": "2026-06-11",
            "snippet": "网页片段；可用摘要",
        }
    ]
    assert "可用摘要" in result.sources[0]["snippet"]

    from lingneng.tools.web_search import web_search_context, web_search_handler

    with web_search_context(settings(tmp_path), provider=provider):
        public_result = json.loads(web_search_handler({"query": "灵能 AI", "top_k": 1}))

    dumped = json.dumps(public_result, ensure_ascii=False)
    assert public_result["success"] is True
    assert public_result["safe_output"]["sources"][0] == result.sources[0]
    assert "_type" not in dumped
    assert "queryContext" not in dumped
    assert "totalEstimatedMatches" not in dumped
    assert "siteIcon" not in dumped


def test_bocha_provider_maps_recency_filters(tmp_path):
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content.decode()))
        return httpx.Response(
            200,
            json={"code": 200, "data": {"webPages": {"value": []}}},
        )

    provider = BochaWebSearchProvider(
        settings(
            tmp_path,
            LINGNENG_WEB_SEARCH_PROVIDER="bocha",
            LINGNENG_BOCHA_WEB_SEARCH_API_KEY="key",
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    for value in ["", "week", "month", "semiyear", "year", "other"]:
        provider.search(provider.request_model(query="q", top_k=1, recency_filter=value))

    assert [body["freshness"] for body in bodies] == [
        "noLimit",
        "oneWeek",
        "oneMonth",
        "oneYear",
        "oneYear",
        "noLimit",
    ]


def test_bocha_provider_errors_are_sanitized_by_handler(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"code": 401, "message": "bad key"})

    provider = BochaWebSearchProvider(
        settings(
            tmp_path,
            LINGNENG_WEB_SEARCH_PROVIDER="bocha",
            LINGNENG_BOCHA_WEB_SEARCH_API_KEY="secret-key",
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    from lingneng.tools.web_search import web_search_context, web_search_handler

    with web_search_context(settings(tmp_path), provider=provider):
        result = json.loads(web_search_handler({"query": "餐饮"}))

    assert result["success"] is False
    assert result["code"] == "WEB_SEARCH_PROVIDER_ERROR"
    assert "secret-key" not in json.dumps(result, ensure_ascii=False)


def test_provider_factory_builds_bocha_provider(tmp_path):
    provider = build_web_search_provider(
        settings(
            tmp_path,
            LINGNENG_WEB_SEARCH_PROVIDER="bocha",
            LINGNENG_BOCHA_WEB_SEARCH_API_KEY="key",
        )
    )

    assert provider.__class__.__name__ == "BochaWebSearchProvider"
