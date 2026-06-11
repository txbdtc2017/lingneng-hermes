from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lingneng.config.settings import LingNengSettings
from lingneng.tools.document_generation import (
    DocumentGenerationResult,
    document_generation_context,
    document_generation_handler,
)
from lingneng.tools.limits import tool_run_guard_context
from tests.lingneng.tools.test_generation_tools import DOC_ARTIFACT


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
    from lingneng.tools.web_search import (
        WebSearchResult,
        web_search_context,
        web_search_handler,
    )

    class Provider:
        def __init__(self) -> None:
            self.calls = 0

        def search(self, request: Any) -> WebSearchResult:
            del request
            self.calls += 1
            return WebSearchResult(
                summary="ok",
                sources=[{"id": "s1", "title": "A", "url": "https://example.com/a"}],
            )

    cfg = settings(
        tmp_path,
        LINGNENG_DUPLICATE_ARTIFACT_GUARD_ENABLED="false",
        LINGNENG_WEB_SEARCH_MAX_CALLS_PER_RUN="1",
    )
    provider = Provider()

    with tool_run_guard_context(cfg), web_search_context(cfg, provider=provider):
        first = json.loads(web_search_handler({"query": "A"}))
        second = json.loads(web_search_handler({"query": "B"}))

    assert first["success"] is True
    assert second["code"] == "TOOL_CALL_LIMIT_EXCEEDED"
    assert provider.calls == 1
