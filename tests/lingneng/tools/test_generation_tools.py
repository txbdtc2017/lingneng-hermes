from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import model_tools
from lingneng.config.settings import LingNengSettings
from lingneng.tools.chart_visualization import (
    ChartVisualizationResult,
    chart_visualization_context,
    chart_visualization_handler,
)
from lingneng.tools.document_generation import (
    DocumentGenerationResult,
    document_generation_context,
    document_generation_handler,
)
from lingneng.tools.image_generation import (
    ImageGenerationResult,
    image_generation_context,
    image_generation_handler,
)
from lingneng.tools.web_search import (
    WebSearchResult,
    lingneng_tool_context,
    web_search_context,
    web_search_handler,
)
from model_tools import get_tool_definitions
from tools.registry import registry


DOC_ARTIFACT = {
    "artifact_id": "artifact-doc-1",
    "artifact_type": "document",
    "source": "document_generation",
    "file_name": "report.pdf",
    "mime_type": "application/pdf",
    "url": "https://files.example.test/report.pdf",
    "object_key": "external/java-agent-file/artifact-doc-1",
    "format": "pdf",
    "target_format": "pdf",
    "conversion_required": False,
    "conversion_owner": None,
}

IMAGE_ARTIFACT = {
    "artifact_id": "artifact-img-1",
    "artifact_type": "image",
    "source": "image_generation",
    "file_name": "image.png",
    "mime_type": "image/png",
    "url": "https://files.example.test/image.png",
    "object_key": "external/java-agent-file/artifact-img-1",
    "format": "png",
    "target_format": "png",
    "conversion_required": False,
    "conversion_owner": None,
}

CHART_ARTIFACT_WRONG_SOURCE = {
    "artifact_id": "artifact-chart-1",
    "artifact_type": "document",
    "source": "image_generation",
    "file_name": "chart.png",
    "mime_type": "image/png",
    "url": "https://files.example.test/chart.png",
    "object_key": "external/java-agent-file/artifact-chart-1",
    "format": "png",
    "target_format": "png",
    "conversion_required": False,
    "conversion_owner": None,
}


def settings(tmp_path: Path) -> LingNengSettings:
    return LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_DOCUMENT_MAX_CONTENT_CHARS": "1000",
            "LINGNENG_IMAGE_MAX_COUNT": "2",
            "LINGNENG_WEB_SEARCH_DEFAULT_TOP_K": "2",
            "LINGNENG_WEB_SEARCH_MAX_TOP_K": "3",
        }
    )


def allowlist_settings(tmp_path: Path) -> LingNengSettings:
    return LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_DOCUMENT_MAX_CONTENT_CHARS": "1000",
            "LINGNENG_IMAGE_MAX_COUNT": "2",
            "LINGNENG_WEB_SEARCH_DEFAULT_TOP_K": "2",
            "LINGNENG_WEB_SEARCH_MAX_TOP_K": "3",
            "LINGNENG_ARTIFACT_URL_ALLOWED_HOSTS": "files.example.test",
        }
    )


def small_output_settings(tmp_path: Path) -> LingNengSettings:
    return LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_DOCUMENT_MAX_CONTENT_CHARS": "1000",
            "LINGNENG_IMAGE_MAX_COUNT": "2",
            "LINGNENG_TOOL_RESULT_MAX_CHARS": "1000",
            "LINGNENG_WEB_SEARCH_DEFAULT_TOP_K": "3",
            "LINGNENG_WEB_SEARCH_MAX_TOP_K": "5",
        }
    )


def _percent_encode(value: str, rounds: int) -> str:
    encoded = value
    for _ in range(rounds):
        encoded = quote(encoded, safe="")
    return encoded


class FakeDocumentProvider:
    def __init__(self, artifacts: list[dict[str, Any]] | None = None) -> None:
        self.request: Any = None
        self.artifacts = artifacts if artifacts is not None else [DOC_ARTIFACT]

    def generate(self, request: Any) -> DocumentGenerationResult:
        self.request = request
        return DocumentGenerationResult(
            summary="PDF 文档生成完成",
            artifacts=self.artifacts,
            safe_output={"provider_job_id": "job-doc-1"},
            metadata={"template": "default"},
        )


class FakeImageProvider:
    def __init__(self, artifacts: list[dict[str, Any]] | None = None) -> None:
        self.request: Any = None
        self.artifacts = artifacts if artifacts is not None else [IMAGE_ARTIFACT]

    def generate(self, request: Any) -> ImageGenerationResult:
        self.request = request
        return ImageGenerationResult(
            summary="图片生成完成",
            artifacts=self.artifacts,
            safe_output={"provider_job_id": "job-image-1"},
        )


class FakeChartProvider:
    def __init__(self, artifacts: list[dict[str, Any]] | None = None) -> None:
        self.request: Any = None
        self.artifacts = (
            artifacts if artifacts is not None else [CHART_ARTIFACT_WRONG_SOURCE]
        )

    def generate(self, request: Any) -> ChartVisualizationResult:
        self.request = request
        return ChartVisualizationResult(
            summary="图表生成完成",
            artifacts=self.artifacts,
            metadata={"secret_token": "must-not-leak", "chart_rows": 2},
        )


class FakeWebSearchProvider:
    def __init__(self) -> None:
        self.request: Any = None

    def search(self, request: Any) -> WebSearchResult:
        self.request = request
        return WebSearchResult(
            summary="搜索完成",
            sources=[
                {
                    "id": "src-1",
                    "title": "Result A",
                    "url": "https://example.com/a",
                    "website": "example.com",
                    "date": "2026-06-06",
                    "snippet": "Public snippet",
                    "api_key": "must-not-leak",
                },
                {
                    "id": "src-credential",
                    "title": "Credential URL",
                    "url": "https://user:pass@example.com/secret",
                    "website": "example.com",
                    "snippet": "drop",
                },
                {
                    "id": "src-ftp",
                    "title": "FTP URL",
                    "url": "ftp://example.com/file",
                    "website": "example.com",
                    "snippet": "drop",
                },
                {
                    "id": "src-whitespace",
                    "title": "Whitespace Authority",
                    "url": "https://exa mple.com/file",
                    "website": "exa mple.com",
                    "snippet": "drop",
                },
                {
                    "id": "src-control",
                    "title": "Control URL",
                    "url": "https://bad.example.com\x00/file",
                    "website": "bad.example.com",
                    "snippet": "drop",
                },
                {
                    "id": "src-2",
                    "title": "Result B",
                    "url": "http://example.org/b",
                    "website": "example.org",
                    "date": None,
                    "snippet": "Another public snippet",
                    "metadata": {"token": "must-not-leak"},
                },
            ],
            metadata={"raw_payload": "must-not-leak", "source_count": 6},
        )


class ExplodingProvider:
    def generate(self, request: Any) -> Any:
        del request
        raise RuntimeError("traceback secret-token /Users/rotas/private")

    def search(self, request: Any) -> Any:
        del request
        raise RuntimeError("traceback secret-token /Users/rotas/private")


class UnsafeWebSearchUrlProvider:
    def search(self, request: Any) -> WebSearchResult:
        del request
        return WebSearchResult(
            summary="搜索完成",
            sources=[
                {
                    "id": "local-query",
                    "title": "Local Query",
                    "url": "https://example.com/page?file=/Users/rotas/secret.pdf",
                    "website": "example.com",
                    "snippet": "drop",
                },
                {
                    "id": "credential-redirect",
                    "title": "Credential Redirect",
                    "url": "https://example.com/page?redirect=https://user:pass@internal.example/secret",
                    "website": "example.com",
                    "snippet": "drop",
                },
                {
                    "id": "encoded-local-path",
                    "title": "Encoded Local Path",
                    "url": "https://example.com/files/%2FUsers%2Frotas%2Fsecret.pdf",
                    "website": "example.com",
                    "snippet": "drop",
                },
                {
                    "id": "path-traversal",
                    "title": "Traversal",
                    "url": "https://example.com/files/../secret.pdf",
                    "website": "example.com",
                    "snippet": "drop",
                },
                {
                    "id": "multi-encoded-traversal",
                    "title": "Multi Encoded",
                    "url": f"https://example.com/files/{_percent_encode('../secret.pdf', 6)}",
                    "website": "example.com",
                    "snippet": "drop",
                },
                {
                    "id": "encoded-authority-space",
                    "title": "Encoded Authority Space",
                    "url": "https://exa%20mple.com/file",
                    "website": "exa mple.com",
                    "snippet": "drop",
                },
                {
                    "id": "encoded-localhost",
                    "title": "Encoded Localhost",
                    "url": "https://local%68ost/file",
                    "website": "localhost",
                    "snippet": "drop",
                },
                {
                    "id": "safe",
                    "title": "Safe",
                    "url": "https://example.com/safe?download=1",
                    "website": "example.com",
                    "snippet": "keep",
                },
            ],
        )


class OversizedDocumentProvider:
    def generate(self, request: Any) -> DocumentGenerationResult:
        del request
        return DocumentGenerationResult(
            summary="PDF 文档生成完成",
            artifacts=[DOC_ARTIFACT],
            safe_output=_oversized_public_payload(),
            metadata=_oversized_public_payload(),
        )


class ManyArtifactsDocumentProvider:
    def generate(self, request: Any) -> DocumentGenerationResult:
        del request
        artifacts = [
            {
                **DOC_ARTIFACT,
                "artifact_id": f"artifact-doc-{index}",
                "object_key": f"external/java-agent-file/artifact-doc-{index}",
            }
            for index in range(200)
        ]
        return DocumentGenerationResult(summary="ok", artifacts=artifacts)


class OversizedImageProvider:
    def generate(self, request: Any) -> ImageGenerationResult:
        del request
        return ImageGenerationResult(
            summary="图片生成完成",
            artifacts=[IMAGE_ARTIFACT],
            safe_output=_oversized_public_payload(),
            metadata=_oversized_public_payload(),
        )


class OversizedChartProvider:
    def generate(self, request: Any) -> ChartVisualizationResult:
        del request
        return ChartVisualizationResult(
            summary="图表生成完成",
            artifacts=[CHART_ARTIFACT_WRONG_SOURCE],
            safe_output=_oversized_public_payload(),
            metadata=_oversized_public_payload(),
        )


class OversizedWebSearchProvider:
    def search(self, request: Any) -> WebSearchResult:
        del request
        return WebSearchResult(
            summary="搜索完成",
            sources=[
                {
                    "id": "safe",
                    "title": "Safe",
                    "url": "https://example.com/safe",
                    "website": "example.com",
                    "snippet": "keep",
                }
            ],
            safe_output=_oversized_public_payload(),
            metadata=_oversized_public_payload(),
        )


class EncodedPublicPayloadDocumentProvider:
    def generate(self, request: Any) -> DocumentGenerationResult:
        del request
        return DocumentGenerationResult(
            summary="PDF 文档生成完成",
            artifacts=[DOC_ARTIFACT],
            safe_output={
                "note": "api%5Fkey%3Dabc123",
                "path": "%2FUsers%2Frotas%2Fsecret.pdf",
            },
            metadata={"auth": "Bearer%20abc123"},
        )


class EncodedWebSearchTextProvider:
    def search(self, request: Any) -> WebSearchResult:
        del request
        return WebSearchResult(
            summary="搜索完成",
            sources=[
                {
                    "id": "encoded-text",
                    "title": "api%5Fkey%3Dabc123",
                    "url": "https://example.com/safe",
                    "website": "example.com",
                    "date": "2026-06-06",
                    "snippet": "Bearer%20abc123 %2FUsers%2Frotas%2Fsecret.pdf",
                }
            ],
        )


def _oversized_public_payload() -> dict[str, Any]:
    huge = "OVERSIZED_RAW_CONTENT" * 500
    return {
        "huge": huge,
        "items": [{"text": huge, "index": index} for index in range(100)],
        "nested": {"huge": huge, "values": [huge for _ in range(100)]},
    }


def test_document_generation_returns_artifact_metadata_and_bounded_request(tmp_path):
    provider = FakeDocumentProvider()
    content = "正文" + ("A" * 1200)

    with document_generation_context(settings(tmp_path), provider=provider):
        result = json.loads(
            document_generation_handler(
                {
                    "title": "报告",
                    "instruction": "生成 PDF",
                    "content": content,
                    "format": "pdf",
                }
            )
        )

    assert result["success"] is True
    assert result["status"] == "succeeded"
    assert result["tool_name"] == "document_generation"
    assert result["artifacts"][0]["artifact_id"] == "artifact-doc-1"
    assert provider.request.title == "报告"
    assert len(provider.request.content) == settings(tmp_path).document_max_content_chars
    assert result["safe_output"]["artifact_count"] == 1
    safe_dump = json.dumps(result["safe_output"], ensure_ascii=False)
    assert content not in safe_dump
    assert "正文" not in safe_dump


def test_document_generation_enforces_artifact_url_allowlist(tmp_path):
    provider = FakeDocumentProvider(
        artifacts=[{**DOC_ARTIFACT, "url": "https://evil.example.test/report.pdf"}]
    )

    with document_generation_context(allowlist_settings(tmp_path), provider=provider):
        result = json.loads(
            document_generation_handler({"instruction": "生成 PDF", "content": "正文"})
        )

    assert result["success"] is False
    assert result["code"] == "DOCUMENT_GENERATION_NO_VALID_ARTIFACTS"
    assert result["artifacts"] == []


def test_document_generation_accepts_allowed_artifact_host(tmp_path):
    provider = FakeDocumentProvider()

    with document_generation_context(allowlist_settings(tmp_path), provider=provider):
        result = json.loads(
            document_generation_handler({"instruction": "生成 PDF", "content": "正文"})
        )

    assert result["success"] is True
    assert result["artifacts"][0]["url"] == "https://files.example.test/report.pdf"


def test_image_generation_clamps_count_to_settings(tmp_path):
    provider = FakeImageProvider()

    with image_generation_context(settings(tmp_path), provider=provider):
        result = json.loads(
            image_generation_handler(
                {
                    "prompt": "生成产品图",
                    "count": 99,
                    "size": "1024x1024",
                    "quality": "high",
                    "style": "realistic",
                }
            )
        )

    assert result["success"] is True
    assert provider.request.count == settings(tmp_path).image_max_count
    assert result["safe_output"]["requested_count"] == settings(tmp_path).image_max_count


def test_image_generation_enforces_artifact_url_allowlist(tmp_path):
    provider = FakeImageProvider(
        artifacts=[{**IMAGE_ARTIFACT, "url": "https://evil.example.test/image.png"}]
    )

    with image_generation_context(allowlist_settings(tmp_path), provider=provider):
        result = json.loads(image_generation_handler({"prompt": "生成配图"}))

    assert result["success"] is False
    assert result["code"] == "IMAGE_GENERATION_NO_VALID_ARTIFACTS"
    assert result["artifacts"] == []


def test_image_generation_partial_success_returns_valid_artifacts(tmp_path):
    invalid_artifact = {**IMAGE_ARTIFACT, "url": "file:///Users/rotas/private.png"}
    provider = FakeImageProvider(artifacts=[invalid_artifact, IMAGE_ARTIFACT])

    with image_generation_context(settings(tmp_path), provider=provider):
        result = json.loads(
            image_generation_handler({"prompt": "生成配图", "count": 2})
        )

    assert result["success"] is True
    assert result["status"] == "succeeded"
    assert [artifact["artifact_id"] for artifact in result["artifacts"]] == [
        "artifact-img-1"
    ]


def test_chart_visualization_returns_image_artifact_with_chart_source(tmp_path):
    provider = FakeChartProvider()

    with chart_visualization_context(settings(tmp_path), provider=provider):
        result = json.loads(
            chart_visualization_handler(
                {
                    "instruction": "生成趋势图",
                    "title": "收入趋势",
                    "chart_type": "line",
                    "data": {
                        "rows": [
                            {"month": "Jan", "revenue": 10},
                            {"month": "Feb", "revenue": 20},
                        ],
                        "secret_token": "must-not-leak",
                    },
                }
            )
        )

    assert result["success"] is True
    assert result["artifacts"][0]["artifact_type"] == "image"
    assert result["artifacts"][0]["source"] == "chart_visualization"
    dumped = json.dumps(result, ensure_ascii=False)
    assert "secret_token" not in dumped
    assert "must-not-leak" not in dumped


def test_chart_visualization_enforces_artifact_url_allowlist(tmp_path):
    provider = FakeChartProvider(
        artifacts=[
            {
                **CHART_ARTIFACT_WRONG_SOURCE,
                "url": "https://evil.example.test/chart.png",
            }
        ]
    )

    with chart_visualization_context(allowlist_settings(tmp_path), provider=provider):
        result = json.loads(chart_visualization_handler({"instruction": "生成趋势图"}))

    assert result["success"] is False
    assert result["code"] == "CHART_VISUALIZATION_NO_VALID_ARTIFACTS"
    assert result["artifacts"] == []


def test_web_search_clamps_top_k_and_returns_public_sources_only(tmp_path):
    provider = FakeWebSearchProvider()

    with web_search_context(settings(tmp_path), provider=provider):
        result = json.loads(
            web_search_handler(
                {
                    "query": "灵能 AI 最新信息",
                    "top_k": 99,
                    "recency_filter": "week",
                    "site_filter": "example.com",
                }
            )
        )

    assert result["success"] is True
    assert result["tool_name"] == "web_search"
    assert result["artifacts"] == []
    assert provider.request.top_k == settings(tmp_path).web_search_max_top_k
    assert result["safe_output"]["top_k"] == settings(tmp_path).web_search_max_top_k
    sources = result["safe_output"]["sources"]
    assert [source["url"] for source in sources] == [
        "https://example.com/a",
        "http://example.org/b",
    ]
    assert set(sources[0]) == {"id", "title", "url", "website", "date", "snippet"}
    dumped = json.dumps(result, ensure_ascii=False).lower()
    assert "user:pass" not in dumped
    assert "ftp://" not in dumped
    assert "exa mple.com" not in dumped
    assert "\\u0000" not in dumped
    assert "api_key" not in dumped
    assert "token" not in dumped
    assert "raw_payload" not in dumped


def test_generation_public_output_percent_decodes_before_secret_checks(tmp_path):
    with document_generation_context(
        settings(tmp_path),
        provider=EncodedPublicPayloadDocumentProvider(),
    ):
        result = json.loads(document_generation_handler({"instruction": "生成报告"}))

    dumped = json.dumps(result, ensure_ascii=False).lower()
    assert result["success"] is True
    assert "api%5fkey" not in dumped
    assert "bearer%20" not in dumped
    assert "%2fusers%2frotas" not in dumped
    assert "abc123" not in dumped
    assert "/users/rotas" not in dumped


def test_web_search_source_text_percent_decodes_before_secret_checks(tmp_path):
    with web_search_context(settings(tmp_path), provider=EncodedWebSearchTextProvider()):
        result = json.loads(web_search_handler({"query": "搜索"}))

    dumped = json.dumps(result, ensure_ascii=False).lower()
    assert result["success"] is True
    assert len(result["safe_output"]["sources"]) == 1
    assert "api%5fkey" not in dumped
    assert "bearer%20" not in dumped
    assert "%2fusers%2frotas" not in dumped
    assert "abc123" not in dumped
    assert "/users/rotas" not in dumped


def test_web_search_rejects_decoded_local_path_and_redirect_credential_urls(
    tmp_path,
):
    with web_search_context(settings(tmp_path), provider=UnsafeWebSearchUrlProvider()):
        result = json.loads(web_search_handler({"query": "搜索", "top_k": 10}))

    assert result["success"] is True
    sources = result["safe_output"]["sources"]
    assert [source["url"] for source in sources] == [
        "https://example.com/safe?download=1"
    ]
    dumped = json.dumps(result, ensure_ascii=False).lower()
    assert "/users/rotas" not in dumped
    assert "%2fusers" not in dumped
    assert "../" not in dumped
    assert "user:pass" not in dumped
    assert "internal.example" not in dumped


def test_generation_tool_results_are_bounded_by_public_budget(tmp_path):
    cfg = small_output_settings(tmp_path)
    checks = [
        (
            document_generation_context,
            document_generation_handler,
            OversizedDocumentProvider(),
            {"instruction": "生成报告", "content": "正文"},
            "document_generation",
        ),
        (
            image_generation_context,
            image_generation_handler,
            OversizedImageProvider(),
            {"prompt": "生成图片"},
            "image_generation",
        ),
        (
            chart_visualization_context,
            chart_visualization_handler,
            OversizedChartProvider(),
            {"instruction": "生成图表"},
            "chart_visualization",
        ),
        (
            web_search_context,
            web_search_handler,
            OversizedWebSearchProvider(),
            {"query": "搜索"},
            "web_search",
        ),
    ]

    for context, handler, provider, args, tool_name in checks:
        with context(cfg, provider=provider):
            raw_result = handler(args)
        result = json.loads(raw_result)

        assert len(raw_result) <= cfg.tool_result_max_chars
        assert result["success"] is True
        assert result["tool_name"] == tool_name
        assert result["status"] == "succeeded"
        assert result["summary"]
        assert "artifacts" in result
        assert "code" in result
        assert "message" in result
        dumped = json.dumps(result, ensure_ascii=False)
        assert "OVERSIZED_RAW_CONTENT" not in dumped
        assert (
            result["metadata"].get("truncated") is True
            or result["safe_output"].get("truncated") is True
        )


def test_generation_tool_result_truncates_many_valid_artifacts(tmp_path):
    cfg = small_output_settings(tmp_path)

    with document_generation_context(
        cfg,
        provider=ManyArtifactsDocumentProvider(),
    ):
        raw_result = document_generation_handler({"instruction": "x"})
    result = json.loads(raw_result)

    assert len(raw_result) <= cfg.tool_result_max_chars
    assert result["success"] is True
    assert result["tool_name"] == "document_generation"
    assert result["artifacts"]
    assert len(result["artifacts"]) < 200
    assert result["metadata"]["truncated"] is True
    assert result["metadata"]["artifact_omitted_count"] > 0
    assert result["metadata"]["artifact_total_count"] == 200


def test_provider_exceptions_return_safe_public_failures(tmp_path):
    provider = ExplodingProvider()
    checks = [
        (
            document_generation_context,
            document_generation_handler,
            {"instruction": "生成报告"},
            "DOCUMENT_GENERATION_PROVIDER_ERROR",
        ),
        (
            image_generation_context,
            image_generation_handler,
            {"prompt": "生成图片"},
            "IMAGE_GENERATION_PROVIDER_ERROR",
        ),
        (
            chart_visualization_context,
            chart_visualization_handler,
            {"instruction": "生成图表"},
            "CHART_VISUALIZATION_PROVIDER_ERROR",
        ),
        (
            web_search_context,
            web_search_handler,
            {"query": "搜索"},
            "WEB_SEARCH_PROVIDER_ERROR",
        ),
    ]

    for context, handler, args, code in checks:
        with context(settings(tmp_path), provider=provider):
            result = json.loads(handler(args))

        assert result["success"] is False
        assert result["status"] == "failed"
        assert result["code"] == code
        assert result["artifacts"] == []
        dumped = json.dumps(result, ensure_ascii=False).lower()
        assert "traceback" not in dumped
        assert "secret-token" not in dumped
        assert "/users/rotas" not in dumped


def test_missing_providers_return_real_not_configured_results(tmp_path):
    checks = [
        (document_generation_context, document_generation_handler, "document_generation"),
        (image_generation_context, image_generation_handler, "image_generation"),
        (chart_visualization_context, chart_visualization_handler, "chart_visualization"),
        (web_search_context, web_search_handler, "web_search"),
    ]

    for context, handler, tool_name in checks:
        with context(settings(tmp_path), provider=None):
            result = json.loads(handler({"query": "hello", "prompt": "hello"}))

        assert result["success"] is False
        assert result["status"] == "skipped"
        assert result["code"] == "NOT_CONFIGURED"
        assert result["tool_name"] == tool_name
        assert result["artifacts"] == []
        assert result.get("phase") != "phase_3_stub"


def test_registry_dispatch_web_search_uses_lingneng_controlled_handler(tmp_path):
    provider = FakeWebSearchProvider()

    import lingneng.tools.toolset  # noqa: F401

    with web_search_context(settings(tmp_path), provider=provider):
        definitions = get_tool_definitions(
            enabled_toolsets=["lingneng"],
            disabled_toolsets=["kanban"],
            quiet_mode=True,
        )
        schema = next(
            item["function"]
            for item in definitions
            if item["function"]["name"] == "web_search"
        )
        result = json.loads(registry.dispatch("web_search", {"query": "搜索"}))

    assert set(schema["parameters"]["properties"]) == {
        "query",
        "top_k",
        "recency_filter",
        "site_filter",
    }
    assert result["tool_name"] == "web_search"
    assert provider.request.query == "搜索"


def test_lingneng_web_search_does_not_override_hermes_web_search():
    repo_root = Path(__file__).resolve().parents[3]
    code = (
        "import tools.web_tools\n"
        "from model_tools import get_tool_definitions\n"
        "from tools.registry import registry\n"
        "assert registry.get_entry('web_search').toolset == 'web'\n"
        "import lingneng.tools.toolset\n"
        "entry = registry.get_entry('web_search')\n"
        "assert entry.toolset == 'web'\n"
        "assert entry.handler.__module__ == 'tools.web_tools'\n"
        "entry.check_fn = lambda: True\n"
        "import model_tools\n"
        "model_tools._clear_tool_defs_cache()\n"
        "defs = get_tool_definitions(enabled_toolsets=['web'], disabled_toolsets=['kanban'], quiet_mode=True)\n"
        "schema = [item['function'] for item in defs if item['function']['name'] == 'web_search'][0]\n"
        "props = set(schema['parameters']['properties'])\n"
        "assert 'limit' in props\n"
        "assert props.isdisjoint({'top_k', 'recency_filter', 'site_filter'})\n"
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr


def test_lingneng_web_search_schema_context_does_not_pollute_hermes_web_schema(
    tmp_path,
    monkeypatch,
):
    import lingneng.tools.toolset  # noqa: F401
    entry = registry.get_entry("web_search")
    assert entry is not None
    original_check_fn = entry.check_fn
    monkeypatch.setattr(entry, "check_fn", lambda: True)
    model_tools._clear_tool_defs_cache()

    try:
        with lingneng_tool_context(settings(tmp_path)):
            lingneng_defs = get_tool_definitions(
                enabled_toolsets=["lingneng"],
                disabled_toolsets=["kanban"],
                quiet_mode=True,
            )
            lingneng_schema = next(
                item["function"]
                for item in lingneng_defs
                if item["function"]["name"] == "web_search"
            )

        web_defs = get_tool_definitions(
            enabled_toolsets=["web"],
            disabled_toolsets=["kanban"],
            quiet_mode=True,
        )
        web_schema = next(
            item["function"]
            for item in web_defs
            if item["function"]["name"] == "web_search"
        )
    finally:
        monkeypatch.setattr(entry, "check_fn", original_check_fn)
        model_tools._clear_tool_defs_cache()

    assert "top_k" in lingneng_schema["parameters"]["properties"]
    assert "limit" in web_schema["parameters"]["properties"]
    assert "top_k" not in web_schema["parameters"]["properties"]
