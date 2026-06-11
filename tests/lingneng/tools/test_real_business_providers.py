from __future__ import annotations

import json
from pathlib import Path

import httpx

from lingneng.config.settings import LingNengSettings
from lingneng.tools.document_generation import DocumentGenerationRequest
from lingneng.tools.document_provider import (
    JavaAgentFileClient,
    JavaFileDocumentProvider,
    build_document_source_markdown,
    safe_document_source_file_name,
    safe_pdf_file_name,
)
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


def test_document_source_helpers_match_lingneng_business_behavior():
    assert (
        build_document_source_markdown(
            title="门店报告",
            document_content="## 结论\n\n正文",
        )
        == "# 门店报告\n\n## 结论\n\n正文\n"
    )
    assert (
        build_document_source_markdown(
            title="门店报告",
            document_content="```markdown\n# 自定义标题\n\n正文\n```",
        )
        == "# 自定义标题\n\n正文\n"
    )
    assert safe_document_source_file_name("../门店/报告") == "报告.md"
    assert safe_document_source_file_name("   ") == "生成文档.md"
    assert safe_pdf_file_name("..\\secret") == "secret.pdf"


def test_java_agent_file_client_uploads_markdown_as_pdf(tmp_path):
    del tmp_path
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["internal_key"] = request.headers["X-Internal-Key"]
        captured["request_id"] = request.headers["X-Request-Id"]
        captured["body"] = request.content.decode("utf-8")
        return httpx.Response(
            200,
            json={"code": 0, "data": "https://files.example/doc.pdf"},
        )

    client = JavaAgentFileClient(
        base_url="https://java.example",
        upload_path="upload",
        internal_key="java-secret",
        timeout_seconds=3,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    url = client.upload_markdown_as_pdf(
        file_name="报告.md",
        markdown="# 报告",
        request_id="req-1",
    )

    assert url == "https://files.example/doc.pdf"
    assert captured["url"] == "https://java.example/upload"
    assert captured["internal_key"] == "java-secret"
    assert captured["request_id"] == "req-1"
    assert "fileFormat" in str(captured["body"])
    assert "报告.md" in str(captured["body"])


def test_java_file_document_provider_returns_external_document_artifact(tmp_path):
    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def upload_markdown_as_pdf(
            self,
            *,
            file_name: str,
            markdown: str,
            request_id: str | None = None,
        ) -> str:
            self.calls.append(
                {"file_name": file_name, "markdown": markdown, "request_id": request_id}
            )
            return "https://files.example/report.pdf"

    fake_client = FakeClient()
    provider = JavaFileDocumentProvider(
        settings(tmp_path),
        java_file_client=fake_client,
    )

    result = provider.generate(
        DocumentGenerationRequest(
            title="经营分析",
            instruction="生成 PDF",
            content="## 核心结论\n\n正文",
            target_format="pdf",
            original_content_length=10,
        )
    )

    assert result.summary == "PDF 文档生成完成"
    assert fake_client.calls[0]["file_name"] == "经营分析.md"
    assert str(fake_client.calls[0]["markdown"]).startswith("# 经营分析")
    artifact = result.artifacts[0]
    assert artifact["artifact_type"] == "document"
    assert artifact["source"] == "document_generation"
    assert artifact["file_name"] == "经营分析.pdf"
    assert artifact["mime_type"] == "application/pdf"
    assert artifact["object_key"].startswith("external/java-agent-file/")
    assert artifact["conversion_required"] is False
    assert result.safe_output["source_content_sha256"]
    assert "正文" not in json.dumps(result.safe_output, ensure_ascii=False)


def test_document_generation_handler_accepts_legacy_content_aliases(tmp_path):
    class CapturingProvider:
        def __init__(self) -> None:
            self.request = None

        def generate(self, request):
            self.request = request
            return {
                "summary": "ok",
                "artifacts": [
                    {
                        "artifact_id": "artifact-doc-1",
                        "artifact_type": "document",
                        "source": "document_generation",
                        "file_name": "report.pdf",
                        "mime_type": "application/pdf",
                        "url": "https://files.example/report.pdf",
                        "object_key": "external/java-agent-file/artifact-doc-1",
                        "format": "pdf",
                        "target_format": "pdf",
                        "conversion_required": False,
                        "conversion_owner": None,
                    }
                ],
            }

    from lingneng.tools.document_generation import (
        document_generation_context,
        document_generation_handler,
    )

    cases = [
        ({"title": "报告", "document_content": "完整正文"}, "完整正文"),
        ({"title": "报告", "content": "content 正文"}, "content 正文"),
        ({"title": "报告", "markdown": "markdown 正文"}, "markdown 正文"),
        ({"title": "报告", "content_brief": "brief 正文"}, "brief 正文"),
        (
            {
                "title": "报告",
                "document_content": " ",
                "content": "",
                "markdown": "markdown 优先",
                "content_brief": "brief 兜底",
            },
            "markdown 优先",
        ),
        (
            {
                "title": "报告",
                "content": "content 优先",
                "markdown": "markdown 次级",
            },
            "content 优先",
        ),
    ]

    for raw_args, expected_content in cases:
        provider = CapturingProvider()
        with document_generation_context(settings(tmp_path), provider=provider):
            result = json.loads(document_generation_handler(raw_args))

        assert result["success"] is True
        assert provider.request.content == expected_content
