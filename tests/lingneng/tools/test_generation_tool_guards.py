from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lingneng.config.settings import LingNengSettings
from lingneng.tools.chart_visualization import (
    ChartVisualizationResult,
    _build_chart_request,
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
from lingneng.tools.limits import tool_run_guard_context
from lingneng.tools.web_search import (
    WebSearchResult,
    web_search_context,
    web_search_handler,
)
from tests.lingneng.tools.test_generation_tools import (
    CHART_ARTIFACT_WRONG_SOURCE,
    DOC_ARTIFACT,
    IMAGE_ARTIFACT,
)


def settings(tmp_path: Path, **overrides: str) -> LingNengSettings:
    env = {
        "LINGNENG_RUNTIME_DIR": str(tmp_path),
        "LINGNENG_TOOL_ARTIFACT_MAX_CALLS_PER_RUN": "1",
        "LINGNENG_WEB_SEARCH_MAX_CALLS_PER_RUN": "1",
    }
    env.update(overrides)
    return LingNengSettings.from_env(env)


class CountingDocumentProvider:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, request: Any) -> DocumentGenerationResult:
        del request
        self.calls += 1
        return DocumentGenerationResult(summary="ok", artifacts=[DOC_ARTIFACT])


class CountingImageProvider:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, request: Any) -> ImageGenerationResult:
        del request
        self.calls += 1
        return ImageGenerationResult(summary="ok", artifacts=[IMAGE_ARTIFACT])


class CountingChartProvider:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, request: Any) -> ChartVisualizationResult:
        del request
        self.calls += 1
        return ChartVisualizationResult(
            summary="ok",
            artifacts=[CHART_ARTIFACT_WRONG_SOURCE],
        )


class CountingWebSearchProvider:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, request: Any) -> WebSearchResult:
        del request
        self.calls += 1
        return WebSearchResult(
            summary="ok",
            sources=[{"id": "s1", "title": "A", "url": "https://example.com/a"}],
        )


def test_duplicate_document_generation_is_suppressed_within_run(tmp_path: Path) -> None:
    cfg = settings(tmp_path)
    provider = CountingDocumentProvider()

    with tool_run_guard_context(cfg), document_generation_context(cfg, provider=provider):
        first = json.loads(
            document_generation_handler({"title": "报告", "content": "正文"})
        )
        second = json.loads(
            document_generation_handler({"title": "报告", "content": "正文"})
        )

    assert first["success"] is True
    assert second["success"] is False
    assert second["status"] == "skipped"
    assert second["code"] == "DUPLICATE_TOOL_CALL_SUPPRESSED"
    assert provider.calls == 1


def test_document_signature_uses_handler_content_alias_order(tmp_path: Path) -> None:
    cfg = settings(tmp_path, LINGNENG_TOOL_ARTIFACT_MAX_CALLS_PER_RUN="3")
    provider = CountingDocumentProvider()

    with tool_run_guard_context(cfg), document_generation_context(cfg, provider=provider):
        first = json.loads(
            document_generation_handler(
                {"title": "报告", "content": "正文", "document_content": "版本 A"}
            )
        )
        second = json.loads(
            document_generation_handler(
                {"title": "报告", "content": "正文", "document_content": "版本 B"}
            )
        )

    assert first["success"] is True
    assert second["success"] is True
    assert provider.calls == 2


def test_document_signature_normalizes_default_pdf_format(tmp_path: Path) -> None:
    cfg = settings(tmp_path, LINGNENG_TOOL_ARTIFACT_MAX_CALLS_PER_RUN="3")
    provider = CountingDocumentProvider()

    with tool_run_guard_context(cfg), document_generation_context(cfg, provider=provider):
        first = json.loads(
            document_generation_handler({"title": "报告", "content": "正文"})
        )
        second = json.loads(
            document_generation_handler(
                {
                    "title": "报告",
                    "content": "正文",
                    "format": "pdf",
                    "target_format": "pdf",
                }
            )
        )

    assert first["success"] is True
    assert second["code"] == "DUPLICATE_TOOL_CALL_SUPPRESSED"
    assert provider.calls == 1


def test_call_limit_is_enforced_when_duplicate_guard_disabled(tmp_path: Path) -> None:
    cfg = settings(tmp_path, LINGNENG_DUPLICATE_ARTIFACT_GUARD_ENABLED="false")
    provider = CountingDocumentProvider()

    with tool_run_guard_context(cfg), document_generation_context(cfg, provider=provider):
        first = json.loads(
            document_generation_handler({"title": "A", "content": "正文 A"})
        )
        second = json.loads(
            document_generation_handler({"title": "B", "content": "正文 B"})
        )

    assert first["success"] is True
    assert second["code"] == "TOOL_CALL_LIMIT_EXCEEDED"
    assert second["metadata"]["limit"] == 1
    assert provider.calls == 1


def test_limit_exceeded_does_not_record_duplicate_signature(tmp_path: Path) -> None:
    cfg = settings(tmp_path)
    provider = CountingDocumentProvider()

    with tool_run_guard_context(cfg), document_generation_context(cfg, provider=provider):
        first = json.loads(
            document_generation_handler({"title": "A", "content": "正文 A"})
        )
        second = json.loads(
            document_generation_handler({"title": "B", "content": "正文 B"})
        )
        third = json.loads(
            document_generation_handler({"title": "B", "content": "正文 B"})
        )

    assert first["success"] is True
    assert second["code"] == "TOOL_CALL_LIMIT_EXCEEDED"
    assert third["code"] == "TOOL_CALL_LIMIT_EXCEEDED"
    assert provider.calls == 1


def test_guard_context_is_run_scoped(tmp_path: Path) -> None:
    cfg = settings(tmp_path)
    provider = CountingDocumentProvider()

    with tool_run_guard_context(cfg), document_generation_context(cfg, provider=provider):
        assert json.loads(
            document_generation_handler({"title": "报告", "content": "正文"})
        )["success"] is True

    with tool_run_guard_context(cfg), document_generation_context(cfg, provider=provider):
        assert json.loads(
            document_generation_handler({"title": "报告", "content": "正文"})
        )["success"] is True

    assert provider.calls == 2


def test_missing_provider_is_not_rewritten_by_guard(tmp_path: Path) -> None:
    cfg = settings(tmp_path)

    with tool_run_guard_context(cfg), document_generation_context(cfg, provider=None):
        result = json.loads(
            document_generation_handler({"title": "报告", "content": "正文"})
        )

    assert result["code"] == "NOT_CONFIGURED"


def test_web_search_limit_uses_web_search_limit(tmp_path: Path) -> None:
    cfg = settings(
        tmp_path,
        LINGNENG_DUPLICATE_ARTIFACT_GUARD_ENABLED="false",
        LINGNENG_WEB_SEARCH_MAX_CALLS_PER_RUN="1",
    )
    provider = CountingWebSearchProvider()

    with tool_run_guard_context(cfg), web_search_context(cfg, provider=provider):
        first = json.loads(web_search_handler({"query": "A"}))
        second = json.loads(web_search_handler({"query": "B"}))

    assert first["success"] is True
    assert second["code"] == "TOOL_CALL_LIMIT_EXCEEDED"
    assert provider.calls == 1


def test_image_signature_normalizes_default_and_clamped_count(tmp_path: Path) -> None:
    cfg = settings(
        tmp_path,
        LINGNENG_TOOL_ARTIFACT_MAX_CALLS_PER_RUN="3",
        LINGNENG_IMAGE_MAX_COUNT="2",
    )
    provider = CountingImageProvider()

    with tool_run_guard_context(cfg), image_generation_context(cfg, provider=provider):
        first = json.loads(image_generation_handler({"prompt": "生成配图"}))
        second = json.loads(image_generation_handler({"prompt": "生成配图", "count": 1}))
        third = json.loads(image_generation_handler({"prompt": "生成配图", "count": 99}))
        fourth = json.loads(image_generation_handler({"prompt": "生成配图", "count": 2}))

    assert first["success"] is True
    assert second["code"] == "DUPLICATE_TOOL_CALL_SUPPRESSED"
    assert third["success"] is True
    assert fourth["code"] == "DUPLICATE_TOOL_CALL_SUPPRESSED"
    assert provider.calls == 2


def test_chart_signature_uses_normalized_sanitized_request(tmp_path: Path) -> None:
    cfg = settings(tmp_path, LINGNENG_TOOL_ARTIFACT_MAX_CALLS_PER_RUN="3")
    provider = CountingChartProvider()
    first_args = {
        "instruction": "生成趋势图",
        "title": "收入趋势",
        "chart_type": "line",
        "data": {
            "rows": [
                {"month": "Jan", "revenue": 10},
                {"month": "Feb", "revenue": 20},
            ],
            "secret_token": "drop-a",
        },
    }
    second_args = {
        **first_args,
        "data": {
            "rows": [
                {"month": "Jan", "revenue": 10},
                {"month": "Feb", "revenue": 20},
            ],
            "secret_token": "drop-b",
        },
    }

    assert _build_chart_request(first_args) == _build_chart_request(second_args)

    with tool_run_guard_context(cfg), chart_visualization_context(cfg, provider=provider):
        first = json.loads(chart_visualization_handler(first_args))
        second = json.loads(chart_visualization_handler(second_args))

    assert first["success"] is True
    assert second["code"] == "DUPLICATE_TOOL_CALL_SUPPRESSED"
    assert provider.calls == 1


def test_web_search_signature_normalizes_default_and_clamped_top_k(
    tmp_path: Path,
) -> None:
    cfg = settings(
        tmp_path,
        LINGNENG_WEB_SEARCH_MAX_CALLS_PER_RUN="4",
        LINGNENG_WEB_SEARCH_DEFAULT_TOP_K="3",
        LINGNENG_WEB_SEARCH_MAX_TOP_K="3",
    )
    provider = CountingWebSearchProvider()

    with tool_run_guard_context(cfg), web_search_context(cfg, provider=provider):
        first = json.loads(web_search_handler({"query": "A"}))
        second = json.loads(web_search_handler({"query": "A", "top_k": 3}))
        third = json.loads(web_search_handler({"query": "B", "top_k": 99}))
        fourth = json.loads(web_search_handler({"query": "B", "top_k": 3}))

    assert first["success"] is True
    assert second["code"] == "DUPLICATE_TOOL_CALL_SUPPRESSED"
    assert third["success"] is True
    assert fourth["code"] == "DUPLICATE_TOOL_CALL_SUPPRESSED"
    assert provider.calls == 2
