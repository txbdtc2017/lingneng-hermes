from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

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


def test_provider_factory_fail_closes_single_provider_build_failure(
    tmp_path,
    monkeypatch,
    caplog,
):
    from lingneng.tools.image_provider import RedisAigcResultStore

    def fail_from_settings(cls, settings):
        del cls, settings
        raise ValueError(
            "redis://:redis-secret@redis.example/0 token=secret-token"
        )

    monkeypatch.setattr(
        RedisAigcResultStore,
        "from_settings",
        classmethod(fail_from_settings),
    )

    with caplog.at_level("WARNING", logger="lingneng.tools.providers"):
        providers = build_lingneng_tool_providers(
            settings(
                tmp_path,
                LINGNENG_WEB_SEARCH_PROVIDER="bocha",
                LINGNENG_BOCHA_WEB_SEARCH_API_KEY="bocha-secret",
                LINGNENG_DOCUMENT_PROVIDER="java_file",
                LINGNENG_JAVA_AGENT_FILE_BASE_URL="https://java.example.test",
                LINGNENG_JAVA_INTERNAL_KEY="java-secret",
                LINGNENG_IMAGE_PROVIDER="aigc",
                LINGNENG_AIGC_IMAGE_BASE_URL="https://aigc.example.test",
                LINGNENG_AIGC_RESULT_STORE="redis",
                LINGNENG_AIGC_REDIS_URL="redis://:redis-secret@redis.example/0",
            )
        )

    assert providers.web_search.__class__.__name__ == "BochaWebSearchProvider"
    assert providers.document_generation.__class__.__name__ == "JavaFileDocumentProvider"
    assert providers.image_generation is None
    assert providers.chart_visualization is None
    assert "image_generation" in caplog.text
    dumped_logs = caplog.text
    assert "redis-secret" not in dumped_logs
    assert "secret-token" not in dumped_logs
    assert "bocha-secret" not in dumped_logs
    assert "java-secret" not in dumped_logs
    assert "redis://" not in dumped_logs


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


def test_aigc_image_client_submits_expected_payload(tmp_path):
    del tmp_path
    from lingneng.tools.image_provider import AigcImageClient

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={"code": 200, "msg": "ok", "data": {"taskId": "task-img-1"}},
        )

    client = AigcImageClient(
        base_url="https://aigc.example",
        env="DEV",
        timeout_seconds=3,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    task_id = client.submit_text_to_image(
        prompt="火锅店海报",
        size="1024x1024",
        quality="standard",
    )

    assert task_id == "task-img-1"
    assert captured["url"] == "https://aigc.example/api/aigc/image/text2img"
    assert captured["body"] == {
        "prompt": "火锅店海报",
        "size": "1024x1024",
        "quality": "standard",
        "env": "DEV",
    }


def test_aigc_image_client_accepts_full_endpoint_url(tmp_path):
    del tmp_path
    from lingneng.tools.image_provider import AigcImageClient

    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, json={"code": 200, "data": {"task_id": "task-img-1"}})

    client = AigcImageClient(
        base_url="https://aigc.example/api/aigc/image/text2img",
        env="DEV",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    client.submit_text_to_image(prompt="海报", size="1024x1024", quality="standard")

    assert urls == ["https://aigc.example/api/aigc/image/text2img"]


def test_aigc_image_provider_returns_partial_success_artifacts(tmp_path):
    from lingneng.tools.image_generation import ImageGenerationRequest
    from lingneng.tools.image_provider import (
        AigcImageGenerationProvider,
        AigcImageProviderError,
        AigcMaterialTaskResult,
    )

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, str]] = []
            self.task_ids = ["task-ok", "task-error"]

        def submit_text_to_image(self, *, prompt: str, size: str, quality: str) -> str:
            self.calls.append({"prompt": prompt, "size": size, "quality": quality})
            return self.task_ids.pop(0)

    class FakeStore:
        def wait(
            self,
            task_id: str,
            *,
            timeout_seconds: float,
            poll_interval_seconds: float,
        ) -> AigcMaterialTaskResult:
            del timeout_seconds, poll_interval_seconds
            if task_id == "task-ok":
                return AigcMaterialTaskResult(
                    task_id=task_id,
                    status="success",
                    task_type="IMAGE",
                    material_urls=["https://files.example/generated.png"],
                )
            raise AigcImageProviderError("aigc task failed")

    fake_client = FakeClient()
    provider = AigcImageGenerationProvider(
        settings(tmp_path),
        client=fake_client,
        result_store=FakeStore(),
    )

    result = provider.generate(
        ImageGenerationRequest(prompt="海报", count=2, size="", quality="", style="")
    )

    assert fake_client.calls == [
        {"prompt": "海报", "size": "1024x1024", "quality": "standard"},
        {"prompt": "海报", "size": "1024x1024", "quality": "standard"},
    ]
    assert result.artifacts[0]["artifact_type"] == "image"
    assert result.artifacts[0]["source"] == "image_generation"
    assert result.artifacts[0]["object_key"] == "external/aigc-image/task-ok/1"
    assert result.safe_output["requested_count"] == 2
    assert result.safe_output["succeeded_count"] == 1
    assert result.safe_output["failed_count"] == 1


def test_redis_aigc_result_store_from_settings_sets_socket_timeouts(
    tmp_path,
    monkeypatch,
):
    import redis

    from lingneng.tools.image_provider import RedisAigcResultStore

    captured: dict[str, object] = {}
    redis_client = object()

    def fake_from_url(cls, url: str, **kwargs):
        del cls
        captured["url"] = url
        captured["kwargs"] = kwargs
        return redis_client

    monkeypatch.setattr(redis.Redis, "from_url", classmethod(fake_from_url))

    store = RedisAigcResultStore.from_settings(
        settings(
            tmp_path,
            LINGNENG_AIGC_REDIS_URL="redis://redis.example/0",
            LINGNENG_AIGC_REDIS_KEY_PREFIX="biz",
            LINGNENG_AIGC_RESULT_POLL_INTERVAL_SECONDS="2.0",
            LINGNENG_AIGC_RESULT_WAIT_TIMEOUT_SECONDS="10.0",
        )
    )

    assert store.redis_client is redis_client
    assert captured["url"] == "redis://redis.example/0"
    assert captured["kwargs"] == {
        "decode_responses": True,
        "socket_connect_timeout": 2.0,
        "socket_timeout": 2.0,
    }


def test_redis_aigc_result_store_rejects_malformed_json():
    from lingneng.tools.image_provider import (
        AigcImageProviderError,
        RedisAigcResultStore,
    )

    class FakeRedis:
        def get(self, key: str) -> str:
            assert key == "prefix:aigc:image_task:task-bad"
            return "{not-json"

    store = RedisAigcResultStore(redis_client=FakeRedis(), key_prefix="prefix")

    with pytest.raises(AigcImageProviderError):
        store.get("task-bad")


def test_redis_aigc_result_store_pending_result_times_out(monkeypatch):
    from lingneng.tools import image_provider
    from lingneng.tools.image_provider import (
        AigcImageProviderError,
        RedisAigcResultStore,
    )

    class FakeRedis:
        def get(self, key: str) -> str:
            del key
            return json.dumps(
                {
                    "task_id": "task-pending",
                    "status": "pending",
                    "task_type": "IMAGE",
                    "material_urls": [],
                }
            )

    sleeps: list[float] = []
    monotonic_values = iter([0.0, 0.0, 0.2])
    monkeypatch.setattr(image_provider.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(image_provider.time, "sleep", lambda seconds: sleeps.append(seconds))
    store = RedisAigcResultStore(redis_client=FakeRedis(), key_prefix="prefix")

    with pytest.raises(AigcImageProviderError):
        store.wait(
            "task-pending",
            timeout_seconds=0.1,
            poll_interval_seconds=0.5,
        )

    assert sleeps == [0.1]


def test_image_generation_handler_sanitizes_aigc_provider_errors(tmp_path):
    from lingneng.tools.image_generation import (
        image_generation_context,
        image_generation_handler,
    )
    from lingneng.tools.image_provider import AigcImageProviderError

    class LeakyProvider:
        def generate(self, request):
            del request
            raise AigcImageProviderError(
                "secret-token traceback /Users/rotas/private.png"
            )

    with image_generation_context(settings(tmp_path), provider=LeakyProvider()):
        result = json.loads(image_generation_handler({"prompt": "生成海报"}))

    dumped = json.dumps(result, ensure_ascii=False)
    assert result["success"] is False
    assert result["code"] == "IMAGE_GENERATION_PROVIDER_ERROR"
    assert "secret-token" not in dumped
    assert "traceback" not in dumped
    assert "/Users/rotas" not in dumped


def test_aigc_image_provider_does_not_swallow_non_provider_exceptions(tmp_path):
    from lingneng.tools.image_generation import (
        image_generation_context,
        image_generation_handler,
    )
    from lingneng.tools.image_provider import (
        AigcImageGenerationProvider,
        AigcMaterialTaskResult,
    )

    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        def submit_text_to_image(self, *, prompt: str, size: str, quality: str) -> str:
            del prompt, size, quality
            self.calls += 1
            if self.calls == 1:
                return "task-ok"
            raise RuntimeError("programmer bug secret-token")

    class FakeStore:
        def wait(
            self,
            task_id: str,
            *,
            timeout_seconds: float,
            poll_interval_seconds: float,
        ) -> AigcMaterialTaskResult:
            del timeout_seconds, poll_interval_seconds
            return AigcMaterialTaskResult(
                task_id=task_id,
                status="success",
                task_type="IMAGE",
                material_urls=["https://files.example/generated.png"],
            )

    provider = AigcImageGenerationProvider(
        settings(tmp_path),
        client=FakeClient(),
        result_store=FakeStore(),
    )

    with image_generation_context(settings(tmp_path), provider=provider):
        result = json.loads(
            image_generation_handler({"prompt": "生成海报", "count": 2})
        )

    dumped = json.dumps(result, ensure_ascii=False)
    assert result["success"] is False
    assert result["code"] == "IMAGE_GENERATION_PROVIDER_ERROR"
    assert result["artifacts"] == []
    assert "programmer bug" not in dumped
    assert "secret-token" not in dumped


def test_chart_provider_delegates_to_image_provider_and_rewrites_source(tmp_path):
    from lingneng.tools.chart_provider import ChartImageGenerationProvider
    from lingneng.tools.chart_visualization import ChartVisualizationRequest

    class FakeImageProvider:
        def __init__(self) -> None:
            self.request = None

        def generate(self, request):
            self.request = request
            return {
                "summary": "图片生成完成",
                "safe_output": {
                    "requested_count": 1,
                    "succeeded_count": 1,
                    "failed_count": 0,
                },
                "artifacts": [
                    {
                        "artifact_id": "artifact-img-1",
                        "artifact_type": "image",
                        "source": "image_generation",
                        "file_name": "generated-image-1.png",
                        "mime_type": "image/png",
                        "url": "https://files.example/chart.png",
                        "object_key": "external/aigc-image/task-chart/1",
                        "format": "png",
                        "target_format": "png",
                        "conversion_required": False,
                        "conversion_owner": None,
                    }
                ],
            }

    image_provider = FakeImageProvider()
    cfg = settings(tmp_path)
    provider = ChartImageGenerationProvider(settings=cfg, image_provider=image_provider)

    result = provider.generate(
        ChartVisualizationRequest(
            instruction="生成趋势图",
            title="收入趋势",
            chart_type="line",
            data_summary="Jan=10, Feb=20",
        )
    )

    assert "收入趋势" in image_provider.request.prompt
    assert "line" in image_provider.request.prompt
    assert result.artifacts[0]["source"] == "chart_visualization"
    assert result.artifacts[0]["file_name"] == "收入趋势-1.png"
    assert result.safe_output["chart_type"] == "line"
