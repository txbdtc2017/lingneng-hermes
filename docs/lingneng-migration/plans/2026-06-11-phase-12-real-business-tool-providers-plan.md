# Phase 12 Real Business Tool Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire configured LingNeng business providers for web search, document generation, image generation, chart visualization, artifact output, and run-scoped expensive-tool guards into the Hermes LingNeng toolset.

**Architecture:** Keep the existing Phase 5 tool handlers and public envelopes. Add focused provider modules under `lingneng/tools/`, a provider factory that returns configured providers or `None`, deterministic run-scoped guard context, and runtime wiring in `HermesAgentRunAdapter`. Tests use mock HTTP transports and fake result stores; live services remain opt-in and are not required by CI.

**Tech Stack:** Python 3.11-3.13, Pydantic v2, httpx, redis 5.3.1, Hermes tool registry/context overrides, FastAPI/SSE contract tests, pytest, uv, ruff.

---

## Approved Spec

This plan implements:

```text
docs/lingneng-migration/specs/2026-06-11-phase-12-real-business-tool-providers-spec.md
```

Required context was reloaded before writing this plan:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-11-lingneng-business-capability-hermes-migration-spec.md`
- `docs/lingneng-migration/specs/2026-06-11-phase-12-real-business-tool-providers-spec.md`

## Execution Gate

No additional user confirmation is required before execution if these accepted
decisions remain true:

- Use old LingNengAI only as a behavior reference; do not import old `app.*`
  modules at runtime.
- Configure real providers through `LingNengSettings`; incomplete config returns
  `NOT_CONFIGURED`.
- Add `redis==5.3.1`, matching the old LingNengAI lockfile version, because
  AIGC image generation needs Redis-backed task result polling to return image
  artifacts.
- Keep live Bocha, Java file, AIGC, and Redis integration tests skipped unless
  explicitly enabled later.
- Do not include Phase 13 attachments, Phase 14 RAG hardening, Phase 15 training
  ingestion, deployment, or CI/CD.

If any of those changes, update the spec and this plan before code execution.

## Scope

Implement:

- provider and guard settings
- secret-safe ready summary booleans
- provider factory
- Bocha-compatible web search provider
- Java file/PDF document provider
- AIGC image provider with Redis result polling
- chart provider backed by image generation
- request/run-scoped call limits and duplicate suppression
- Hermes adapter context wiring
- deterministic provider, guard, runtime, and SSE contract tests

Do not implement:

- attachment parser/OCR/vision providers
- full RAG query hardening or training ingestion
- Java code changes
- old LingNengAI imports
- local PDF rendering fallback
- live service tests enabled by default
- new router graph or LLM-based tool admission classifier

## File Map

Create:

- `lingneng/tools/providers.py`
  - `LingNengToolProviders` container and `build_lingneng_tool_providers()`.
- `lingneng/tools/web_search_provider.py`
  - Bocha-compatible sync provider and response normalizer.
- `lingneng/tools/document_provider.py`
  - Java file client, document source helpers, external document artifact helper,
    and `JavaFileDocumentProvider`.
- `lingneng/tools/image_provider.py`
  - AIGC request/result models, sync AIGC client, Redis result store, image
    artifact helper, and `AigcImageGenerationProvider`.
- `lingneng/tools/chart_provider.py`
  - chart provider that delegates to `ImageGenerationProvider` and rewrites
    artifact metadata.
- `lingneng/tools/limits.py`
  - `ToolRunGuard`, `tool_run_guard_context()`, duplicate signatures, and safe
    skip envelopes.
- `tests/lingneng/tools/test_real_business_providers.py`
- `tests/lingneng/tools/test_generation_tool_guards.py`

Modify:

- `pyproject.toml`
  - add `redis==5.3.1`.
- `uv.lock`
  - regenerate with `uv lock`.
- `lingneng/config/settings.py`
  - add provider/guard settings and ready-summary booleans.
- `lingneng/tools/document_generation.py`
  - content aliases and guard hook.
- `lingneng/tools/image_generation.py`
  - guard hook.
- `lingneng/tools/chart_visualization.py`
  - guard hook.
- `lingneng/tools/web_search.py`
  - guard hook.
- `lingneng/runtime/hermes_adapter.py`
  - provider factory and provider/guard contexts around the Hermes run.
- `tests/lingneng/config/test_settings.py`
- `tests/lingneng/runtime/test_hermes_adapter_config.py`
- `tests/lingneng/contract/test_artifact_chat_stream.py`

Avoid modifying:

- `run_agent.py`
- `model_tools.py`
- `toolsets.py`
- gateway platform adapters
- old `/Users/rotas/Documents/work/hailun/LingNengAI` files

## Task 12.1: Add Provider Settings, Redis Dependency, And Provider Factory Skeleton

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `lingneng/config/settings.py`
- Create: `lingneng/tools/providers.py`
- Modify: `tests/lingneng/config/test_settings.py`
- Test: `tests/lingneng/tools/test_real_business_providers.py`

- [ ] **Step 1: Write failing settings tests**

Append to `tests/lingneng/config/test_settings.py`:

```python
def test_phase_12_provider_settings_defaults(tmp_path):
    settings = LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})

    assert settings.web_search_provider == ""
    assert settings.bocha_web_search_api_key == ""
    assert settings.bocha_web_search_base_url == "https://api.bochaai.com"
    assert settings.bocha_web_search_timeout_seconds == 30.0
    assert settings.document_provider == ""
    assert settings.java_agent_file_base_url == ""
    assert settings.java_agent_file_upload_path == "/ai/internal/agent-file/upload"
    assert settings.java_internal_key == ""
    assert settings.java_agent_file_upload_timeout_seconds == 120.0
    assert settings.image_provider == ""
    assert settings.aigc_image_base_url == ""
    assert settings.aigc_image_timeout_seconds == 30.0
    assert settings.aigc_result_store == ""
    assert settings.aigc_redis_url == ""
    assert settings.aigc_redis_key_prefix == "lingneng-agent"
    assert settings.aigc_result_ttl_seconds == 7200
    assert settings.aigc_result_wait_timeout_seconds == 300.0
    assert settings.aigc_result_poll_interval_seconds == 1.0
    assert settings.tool_artifact_max_calls_per_run == 3
    assert settings.web_search_max_calls_per_run == 12
    assert settings.duplicate_artifact_guard_enabled is True

    summary = settings.ready_summary()
    assert summary["web_search_configured"] is False
    assert summary["document_provider_configured"] is False
    assert summary["image_provider_configured"] is False
    assert summary["aigc_result_store_configured"] is False


def test_phase_12_provider_settings_from_env_are_secret_safe(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_WEB_SEARCH_PROVIDER": "bocha",
            "LINGNENG_BOCHA_WEB_SEARCH_API_KEY": "bocha-secret",
            "LINGNENG_BOCHA_WEB_SEARCH_BASE_URL": "https://bocha.example",
            "LINGNENG_BOCHA_WEB_SEARCH_TIMEOUT_SECONDS": "5.5",
            "LINGNENG_DOCUMENT_PROVIDER": "java_file",
            "LINGNENG_JAVA_AGENT_FILE_BASE_URL": "https://java-file.example",
            "LINGNENG_JAVA_AGENT_FILE_UPLOAD_PATH": "upload",
            "LINGNENG_JAVA_INTERNAL_KEY": "java-secret",
            "LINGNENG_JAVA_AGENT_FILE_UPLOAD_TIMEOUT_SECONDS": "33",
            "LINGNENG_IMAGE_PROVIDER": "aigc",
            "LINGNENG_AIGC_IMAGE_BASE_URL": "https://aigc.example",
            "LINGNENG_AIGC_IMAGE_TIMEOUT_SECONDS": "44",
            "LINGNENG_AIGC_RESULT_STORE": "redis",
            "LINGNENG_AIGC_REDIS_URL": "redis://:redis-secret@localhost:6379/0",
            "LINGNENG_AIGC_REDIS_KEY_PREFIX": "ln:test",
            "LINGNENG_AIGC_RESULT_TTL_SECONDS": "60",
            "LINGNENG_AIGC_RESULT_WAIT_TIMEOUT_SECONDS": "8",
            "LINGNENG_AIGC_RESULT_POLL_INTERVAL_SECONDS": "0.2",
            "LINGNENG_TOOL_ARTIFACT_MAX_CALLS_PER_RUN": "2",
            "LINGNENG_WEB_SEARCH_MAX_CALLS_PER_RUN": "4",
            "LINGNENG_DUPLICATE_ARTIFACT_GUARD_ENABLED": "false",
        }
    )

    assert settings.java_agent_file_upload_path == "/upload"
    assert settings.web_search_configured is True
    assert settings.document_provider_configured is True
    assert settings.image_provider_configured is True
    assert settings.aigc_result_store_configured is True
    assert settings.duplicate_artifact_guard_enabled is False

    dumped = repr(settings.ready_summary())
    assert "bocha-secret" not in dumped
    assert "java-secret" not in dumped
    assert "redis-secret" not in dumped
```

- [ ] **Step 2: Write failing provider factory tests**

Create `tests/lingneng/tools/test_real_business_providers.py` with this initial
content:

```python
from __future__ import annotations

from pathlib import Path

from lingneng.config.settings import LingNengSettings
from lingneng.tools.providers import build_lingneng_tool_providers


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
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/config/test_settings.py::test_phase_12_provider_settings_defaults \
  tests/lingneng/config/test_settings.py::test_phase_12_provider_settings_from_env_are_secret_safe \
  tests/lingneng/tools/test_real_business_providers.py::test_provider_factory_returns_none_for_incomplete_config \
  -q
```

Expected: fail because settings and provider factory do not exist yet.

- [ ] **Step 4: Add Redis dependency**

In `pyproject.toml`, add an exact-pinned core dependency near `httpx`:

```toml
  "redis==5.3.1",
```

Run:

```bash
uv lock
```

Expected: `uv.lock` includes `redis` 5.3.1. This package is needed because the
AIGC provider must poll the old LingNengAI Redis result key shape to return
actual image artifact URLs.

- [ ] **Step 5: Add provider settings**

In `lingneng/config/settings.py`, add fields to `LingNengSettings`:

```python
    web_search_provider: str = ""
    bocha_web_search_api_key: str = Field(default="", repr=False)
    bocha_web_search_base_url: str = "https://api.bochaai.com"
    bocha_web_search_timeout_seconds: float = Field(default=30.0, ge=0.1)
    document_provider: str = ""
    java_agent_file_base_url: str = ""
    java_agent_file_upload_path: str = "/ai/internal/agent-file/upload"
    java_internal_key: str = Field(default="", repr=False)
    java_agent_file_upload_timeout_seconds: float = Field(default=120.0, ge=0.1)
    image_provider: str = ""
    aigc_image_base_url: str = ""
    aigc_image_timeout_seconds: float = Field(default=30.0, ge=0.1)
    aigc_result_store: str = ""
    aigc_redis_url: str = Field(default="", repr=False)
    aigc_redis_key_prefix: str = "lingneng-agent"
    aigc_result_ttl_seconds: int = Field(default=7200, ge=1)
    aigc_result_wait_timeout_seconds: float = Field(default=300.0, ge=0.1)
    aigc_result_poll_interval_seconds: float = Field(default=1.0, ge=0.01)
    tool_artifact_max_calls_per_run: int = Field(default=3, ge=1)
    web_search_max_calls_per_run: int = Field(default=12, ge=1)
    duplicate_artifact_guard_enabled: bool = True
```

Add env parsing in `from_env()` using the documented `LINGNENG_*` keys.
Normalize `java_agent_file_upload_path` to start with `/` either in a
`model_validator` or helper.

Add properties:

```python
    @property
    def web_search_configured(self) -> bool:
        return (
            self.web_search_provider.strip().lower() == "bocha"
            and bool(self.bocha_web_search_api_key.strip())
        )

    @property
    def document_provider_configured(self) -> bool:
        return (
            self.document_provider.strip().lower() == "java_file"
            and bool(self.java_agent_file_base_url.strip())
            and bool(self.java_internal_key.strip())
        )

    @property
    def image_provider_configured(self) -> bool:
        return (
            self.image_provider.strip().lower() == "aigc"
            and bool(self.aigc_image_base_url.strip())
            and self.aigc_result_store.strip().lower() == "redis"
            and bool(self.aigc_redis_url.strip())
        )

    @property
    def aigc_result_store_configured(self) -> bool:
        return (
            self.aigc_result_store.strip().lower() == "redis"
            and bool(self.aigc_redis_url.strip())
        )
```

Extend `ready_summary()` with only booleans:

```python
            "web_search_configured": self.web_search_configured,
            "document_provider_configured": self.document_provider_configured,
            "image_provider_configured": self.image_provider_configured,
            "aigc_result_store_configured": self.aigc_result_store_configured,
```

- [ ] **Step 6: Add provider factory skeleton**

Create `lingneng/tools/providers.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from lingneng.config.settings import LingNengSettings
from lingneng.tools.chart_visualization import ChartVisualizationProvider
from lingneng.tools.document_generation import DocumentGenerationProvider
from lingneng.tools.image_generation import ImageGenerationProvider
from lingneng.tools.web_search import WebSearchProvider


@dataclass(frozen=True)
class LingNengToolProviders:
    web_search: WebSearchProvider | None = None
    document_generation: DocumentGenerationProvider | None = None
    image_generation: ImageGenerationProvider | None = None
    chart_visualization: ChartVisualizationProvider | None = None


def build_lingneng_tool_providers(settings: LingNengSettings) -> LingNengToolProviders:
    image_provider = build_image_generation_provider(settings)
    return LingNengToolProviders(
        web_search=build_web_search_provider(settings),
        document_generation=build_document_generation_provider(settings),
        image_generation=image_provider,
        chart_visualization=build_chart_visualization_provider(
            settings,
            image_provider=image_provider,
        ),
    )


def build_web_search_provider(settings: LingNengSettings) -> WebSearchProvider | None:
    if settings.web_search_provider.strip().lower() != "bocha":
        return None
    if not settings.bocha_web_search_api_key.strip():
        return None
    try:
        from lingneng.tools.web_search_provider import BochaWebSearchProvider
    except Exception:
        return None
    return BochaWebSearchProvider(settings)


def build_document_generation_provider(
    settings: LingNengSettings,
) -> DocumentGenerationProvider | None:
    if settings.document_provider.strip().lower() != "java_file":
        return None
    if not settings.document_provider_configured:
        return None
    try:
        from lingneng.tools.document_provider import JavaFileDocumentProvider
    except Exception:
        return None
    return JavaFileDocumentProvider.from_settings(settings)


def build_image_generation_provider(
    settings: LingNengSettings,
) -> ImageGenerationProvider | None:
    if not settings.image_provider_configured:
        return None
    try:
        from lingneng.tools.image_provider import AigcImageGenerationProvider
    except Exception:
        return None
    return AigcImageGenerationProvider.from_settings(settings)


def build_chart_visualization_provider(
    settings: LingNengSettings,
    *,
    image_provider: ImageGenerationProvider | None = None,
) -> ChartVisualizationProvider | None:
    if image_provider is None:
        return None
    try:
        from lingneng.tools.chart_provider import ChartImageGenerationProvider
    except Exception:
        return None
    return ChartImageGenerationProvider(settings=settings, image_provider=image_provider)
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/config/test_settings.py::test_phase_12_provider_settings_defaults \
  tests/lingneng/config/test_settings.py::test_phase_12_provider_settings_from_env_are_secret_safe \
  tests/lingneng/tools/test_real_business_providers.py::test_provider_factory_returns_none_for_incomplete_config \
  -q
```

Expected: pass.

- [ ] **Step 8: Regression check**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/config/test_settings.py tests/lingneng/tools/test_generation_tools.py -q
```

Expected: pass.

- [ ] **Step 9: Commit and push**

```bash
git add pyproject.toml uv.lock lingneng/config/settings.py lingneng/tools/providers.py tests/lingneng/config/test_settings.py tests/lingneng/tools/test_real_business_providers.py
git commit -m "feat: 增加业务工具提供方配置"
git push origin dev
```

## Task 12.2: Implement Bocha-Compatible Web Search Provider

**Files:**
- Create: `lingneng/tools/web_search_provider.py`
- Modify: `lingneng/tools/providers.py`
- Modify: `tests/lingneng/tools/test_real_business_providers.py`

- [ ] **Step 1: Add failing Bocha provider tests**

Append to `tests/lingneng/tools/test_real_business_providers.py`:

```python
import json

import httpx

from lingneng.tools.providers import build_web_search_provider
from lingneng.tools.web_search_provider import BochaWebSearchProvider


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


def test_bocha_provider_maps_recency_filters(tmp_path):
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content.decode()))
        return httpx.Response(200, json={"code": 200, "data": {"webPages": {"value": []}}})

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
```

If direct constructor tests need the request model, expose this class attribute
in the implementation:

```python
request_model = WebSearchRequest
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_real_business_providers.py -q
```

Expected: fail because `web_search_provider.py` is missing.

- [ ] **Step 3: Implement provider**

Create `lingneng/tools/web_search_provider.py`:

```python
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
        response = self._post(body=body, headers=headers)
        response.raise_for_status()
        payload = response.json()
        if _is_error_payload(payload):
            raise RuntimeError("bocha web search failed")
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
                "snippet": item.get("snippet") or item.get("summary") or "",
            }
        )
    return sources


def _nested(payload: dict[str, Any], path: list[str]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_real_business_providers.py tests/lingneng/tools/test_generation_tools.py::test_web_search_clamps_top_k_and_returns_public_sources_only -q
```

Expected: pass.

- [ ] **Step 5: Run isolation regression**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/tools/test_generation_tools.py::test_lingneng_web_search_does_not_override_hermes_web_search \
  tests/lingneng/tools/test_generation_tools.py::test_lingneng_web_search_schema_context_does_not_pollute_hermes_web_schema \
  -q
```

Expected: pass.

- [ ] **Step 6: Commit and push**

```bash
git add lingneng/tools/web_search_provider.py lingneng/tools/providers.py tests/lingneng/tools/test_real_business_providers.py
git commit -m "feat: 接入 Bocha 联网搜索提供方"
git push origin dev
```

## Task 12.3: Implement Java File Document Provider

**Files:**
- Create: `lingneng/tools/document_provider.py`
- Modify: `lingneng/tools/document_generation.py`
- Modify: `lingneng/tools/providers.py`
- Modify: `tests/lingneng/tools/test_real_business_providers.py`
- Modify: `tests/lingneng/tools/test_generation_tools.py`

- [ ] **Step 1: Add failing document provider tests**

Append to `tests/lingneng/tools/test_real_business_providers.py`:

```python
from lingneng.tools.document_provider import (
    JavaAgentFileClient,
    JavaFileDocumentProvider,
    build_document_source_markdown,
    safe_document_source_file_name,
    safe_pdf_file_name,
)
from lingneng.tools.document_generation import DocumentGenerationRequest


def test_document_source_helpers_match_lingneng_business_behavior():
    assert build_document_source_markdown(
        title="门店报告",
        document_content="## 结论\n\n正文",
    ) == "# 门店报告\n\n## 结论\n\n正文\n"
    assert build_document_source_markdown(
        title="门店报告",
        document_content="```markdown\n# 自定义标题\n\n正文\n```",
    ) == "# 自定义标题\n\n正文\n"
    assert safe_document_source_file_name("../门店/报告") == "报告.md"
    assert safe_document_source_file_name("   ") == "生成文档.md"
    assert safe_pdf_file_name("..\\secret") == "secret.pdf"


def test_java_agent_file_client_uploads_markdown_as_pdf(tmp_path):
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["internal_key"] = request.headers["X-Internal-Key"]
        captured["request_id"] = request.headers["X-Request-Id"]
        body = request.content.decode("latin1")
        captured["body"] = body
        return httpx.Response(200, json={"code": 0, "data": "https://files.example/doc.pdf"})

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
        def __init__(self):
            self.calls = []

        def upload_markdown_as_pdf(self, *, file_name, markdown, request_id=None):
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
    assert fake_client.calls[0]["markdown"].startswith("# 经营分析")
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
        def __init__(self):
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

    provider = CapturingProvider()
    from lingneng.tools.document_generation import document_generation_context, document_generation_handler

    with document_generation_context(settings(tmp_path), provider=provider):
        result = json.loads(
            document_generation_handler({"title": "报告", "document_content": "完整正文"})
        )

    assert result["success"] is True
    assert provider.request.content == "完整正文"
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_real_business_providers.py::test_document_source_helpers_match_lingneng_business_behavior tests/lingneng/tools/test_real_business_providers.py::test_java_agent_file_client_uploads_markdown_as_pdf tests/lingneng/tools/test_real_business_providers.py::test_java_file_document_provider_returns_external_document_artifact tests/lingneng/tools/test_real_business_providers.py::test_document_generation_handler_accepts_legacy_content_aliases -q
```

Expected: fail because document provider/helpers are missing.

- [ ] **Step 3: Implement document provider**

Create `lingneng/tools/document_provider.py` with:

- `JavaAgentFileClient`
  - sync `upload_markdown_as_pdf(file_name, markdown, request_id=None)`.
  - multipart form fields: `data={"fileFormat": "pdf"}` and
    `files={"file": (file_name, markdown.encode("utf-8"), "text/markdown")}`.
  - headers: `X-Internal-Key`, and `X-Request-Id` when present.
  - response URL extraction in this order:
    `data` string, `data.url`, `data.download_url`, `url`, `download_url`.
  - reject non-HTTP(S) or missing URL by raising a provider exception.

- document helpers:

```python
def build_document_source_markdown(*, title: str, document_content: str) -> str:
    body = _unwrap_markdown_fence(document_content.strip())
    if not _has_h1(body):
        body = f"# {safe_document_title(title)}\n\n{body}"
    return body.rstrip() + "\n"
```

- file-name helpers:
  - strip path separators using `PurePosixPath(value.replace("\\", "/")).name`.
  - strip control characters and unsafe quotes.
  - default to `生成文档.md` or `生成文档.pdf`.

- artifact helper:

```python
def create_external_document_artifact(*, file_name: str, url: str) -> dict[str, object]:
    artifact_id = f"artifact_{uuid4().hex}"
    return {
        "artifact_id": artifact_id,
        "artifact_type": "document",
        "source": "document_generation",
        "file_name": safe_pdf_file_name(file_name),
        "mime_type": "application/pdf",
        "url": url,
        "object_key": f"external/java-agent-file/{artifact_id}",
        "format": "pdf",
        "target_format": "pdf",
        "conversion_required": False,
        "conversion_owner": None,
    }
```

- `JavaFileDocumentProvider`
  - constructor accepts `settings`, optional `java_file_client`.
  - `from_settings()` builds `JavaAgentFileClient`.
  - `generate()` builds Markdown, uploads it, creates artifact, and returns
    `DocumentGenerationResult`.
  - safe output includes `source_format`, `source_file_name`,
    `source_content_length`, `source_content_sha256`, and `artifact_count`.

- [ ] **Step 4: Add content aliases to handler**

In `lingneng/tools/document_generation.py`, change `_build_document_request()` so
`raw_content` selects the first non-empty value from:

```python
(
    raw_args.get("document_content"),
    raw_args.get("content"),
    raw_args.get("markdown"),
    raw_args.get("content_brief"),
)
```

Keep existing content bounding and public-output behavior.

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/tools/test_real_business_providers.py \
  tests/lingneng/tools/test_generation_tools.py::test_document_generation_returns_artifact_metadata_and_bounded_request \
  -q
```

Expected: pass.

- [ ] **Step 6: Regression check**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_generation_tools.py tests/lingneng/events/test_artifact_events.py -q
```

Expected: pass.

- [ ] **Step 7: Commit and push**

```bash
git add lingneng/tools/document_provider.py lingneng/tools/document_generation.py lingneng/tools/providers.py tests/lingneng/tools/test_real_business_providers.py tests/lingneng/tools/test_generation_tools.py
git commit -m "feat: 接入 Java 文件文档提供方"
git push origin dev
```

## Task 12.4: Implement AIGC Image Provider And Chart Provider

**Files:**
- Create: `lingneng/tools/image_provider.py`
- Create: `lingneng/tools/chart_provider.py`
- Modify: `lingneng/tools/providers.py`
- Modify: `tests/lingneng/tools/test_real_business_providers.py`
- Test: `tests/lingneng/tools/test_generation_tools.py`

- [ ] **Step 1: Add failing image/chart provider tests**

Append to `tests/lingneng/tools/test_real_business_providers.py`:

```python
from lingneng.tools.chart_provider import ChartImageGenerationProvider
from lingneng.tools.chart_visualization import ChartVisualizationRequest
from lingneng.tools.image_generation import ImageGenerationRequest
from lingneng.tools.image_provider import (
    AigcImageClient,
    AigcImageGenerationProvider,
    AigcMaterialTaskResult,
)


def test_aigc_image_client_submits_expected_payload(tmp_path):
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"code": 200, "msg": "ok", "data": {"taskId": "task-img-1"}})

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
    class FakeClient:
        def __init__(self):
            self.calls = []
            self.task_ids = ["task-ok", "task-error"]

        def submit_text_to_image(self, *, prompt, size, quality):
            self.calls.append({"prompt": prompt, "size": size, "quality": quality})
            return self.task_ids.pop(0)

    class FakeStore:
        def wait(self, task_id, *, timeout_seconds, poll_interval_seconds):
            del timeout_seconds, poll_interval_seconds
            if task_id == "task-ok":
                return AigcMaterialTaskResult(
                    task_id=task_id,
                    status="success",
                    task_type="IMAGE",
                    material_urls=["https://files.example/generated.png"],
                )
            return AigcMaterialTaskResult(
                task_id=task_id,
                status="error",
                task_type="IMAGE",
                msg="failed",
            )

    provider = AigcImageGenerationProvider(
        settings(tmp_path),
        client=FakeClient(),
        result_store=FakeStore(),
    )

    result = provider.generate(
        ImageGenerationRequest(prompt="海报", count=2, size="", quality="", style="")
    )

    assert result.artifacts[0]["artifact_type"] == "image"
    assert result.artifacts[0]["source"] == "image_generation"
    assert result.artifacts[0]["object_key"] == "external/aigc-image/task-ok/1"
    assert result.safe_output["requested_count"] == 2
    assert result.safe_output["succeeded_count"] == 1
    assert result.safe_output["failed_count"] == 1


def test_chart_provider_delegates_to_image_provider_and_rewrites_source(tmp_path):
    class FakeImageProvider:
        def __init__(self):
            self.request = None

        def generate(self, request):
            self.request = request
            return {
                "summary": "图片生成完成",
                "safe_output": {"requested_count": 1, "succeeded_count": 1, "failed_count": 0},
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
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_real_business_providers.py::test_aigc_image_client_submits_expected_payload tests/lingneng/tools/test_real_business_providers.py::test_aigc_image_client_accepts_full_endpoint_url tests/lingneng/tools/test_real_business_providers.py::test_aigc_image_provider_returns_partial_success_artifacts tests/lingneng/tools/test_real_business_providers.py::test_chart_provider_delegates_to_image_provider_and_rewrites_source -q
```

Expected: fail because image/chart provider modules are missing.

- [ ] **Step 3: Implement image provider**

Create `lingneng/tools/image_provider.py`:

- Pydantic models:
  - `TextToImageSubmitResponse` accepting `task_id` or `taskId`.
  - `AigcMaterialTaskResult` with `status` in `success/error/pending`, task type
    `IMAGE/VIDEO`, and `material_urls`.
- `aigc_environment_for_app_env(app_env)`:
  - `prod`, `production`, `main` -> `PROD`
  - everything else -> `DEV`
- `AigcImageClient`:
  - sync `submit_text_to_image(prompt, size, quality)`.
  - URL helper appends `/api/aigc/image/text2img` unless already present.
  - sends JSON `prompt`, normalized `size`, normalized `quality`, and `env`.
  - disables environment proxies when constructing its own `httpx.Client`.
  - raises internal exceptions on HTTP, non-JSON, non-200 code, or missing task id.
- `RedisAigcResultStore`:
  - uses `redis.Redis.from_url(settings.aigc_redis_url, decode_responses=True)`.
  - key shape: `<prefix>:aigc:image_task:<task_id>`.
  - `get()` parses JSON into `AigcMaterialTaskResult`.
  - `wait()` uses `time.monotonic()` and `time.sleep(min(poll_interval, remaining))`
    until non-`pending` or timeout.
- `AigcImageGenerationProvider`:
  - constructor accepts `settings`, optional `client`, optional `result_store`.
  - `from_settings()` builds both concrete pieces.
  - defaults size to `1024x1024`, quality to `standard`.
  - loops over request count, captures task ids, waits for results, creates
    external image artifacts with object key
    `external/aigc-image/<task_id>/<index>`.
  - returns `ImageGenerationResult` with partial success artifacts if any exist.
  - raises internal exception if no artifacts are produced so the existing
    handler returns `IMAGE_GENERATION_PROVIDER_ERROR` or
    `IMAGE_GENERATION_NO_VALID_ARTIFACTS`.

- [ ] **Step 4: Implement chart provider**

Create `lingneng/tools/chart_provider.py`:

```python
from __future__ import annotations

from typing import Any

from lingneng.config.settings import LingNengSettings
from lingneng.tools.chart_visualization import ChartVisualizationRequest, ChartVisualizationResult
from lingneng.tools.document_generation import _bounded_text
from lingneng.tools.image_generation import ImageGenerationProvider, ImageGenerationRequest, ImageGenerationResult


class ChartImageGenerationProvider:
    def __init__(
        self,
        *,
        settings: LingNengSettings,
        image_provider: ImageGenerationProvider,
    ) -> None:
        self.settings = settings
        self.image_provider = image_provider

    def generate(self, request: ChartVisualizationRequest) -> ChartVisualizationResult:
        image_result = ImageGenerationResult.model_validate(
            self.image_provider.generate(
                ImageGenerationRequest(
                    prompt=_chart_prompt(request),
                    count=1,
                    size="1024x1024",
                    quality="standard",
                    style="business chart",
                )
            )
        )
        artifacts = [
            {**artifact, "source": "chart_visualization", "file_name": _chart_file_name(request.title, index, artifact)}
            for index, artifact in enumerate(image_result.artifacts, start=1)
        ]
        return ChartVisualizationResult(
            summary=_chart_summary(len(artifacts), image_result.safe_output),
            artifacts=artifacts,
            safe_output={
                **image_result.safe_output,
                "title": request.title,
                "chart_type": request.chart_type,
                "artifact_count": len(artifacts),
            },
            metadata={**image_result.metadata, "artifact_count": len(artifacts)},
        )
```

Fill `_chart_prompt`, `_chart_file_name`, and `_chart_summary` with bounded text
and safe file-name logic. Do not include raw `request.data`.

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_real_business_providers.py tests/lingneng/tools/test_generation_tools.py::test_image_generation_partial_success_returns_valid_artifacts tests/lingneng/tools/test_generation_tools.py::test_chart_visualization_returns_image_artifact_with_chart_source -q
```

Expected: pass.

- [ ] **Step 6: Run generation regression**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_generation_tools.py -q
```

Expected: pass.

- [ ] **Step 7: Commit and push**

```bash
git add lingneng/tools/image_provider.py lingneng/tools/chart_provider.py lingneng/tools/providers.py tests/lingneng/tools/test_real_business_providers.py
git commit -m "feat: 接入 AIGC 图片和图表提供方"
git push origin dev
```

## Task 12.5: Add Run-Scoped Tool Limits And Duplicate Guard

**Files:**
- Create: `lingneng/tools/limits.py`
- Modify: `lingneng/tools/document_generation.py`
- Modify: `lingneng/tools/image_generation.py`
- Modify: `lingneng/tools/chart_visualization.py`
- Modify: `lingneng/tools/web_search.py`
- Create: `tests/lingneng/tools/test_generation_tool_guards.py`

- [ ] **Step 1: Write failing guard tests**

Create `tests/lingneng/tools/test_generation_tool_guards.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

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
    def __init__(self):
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        return DocumentGenerationResult(summary="ok", artifacts=[DOC_ARTIFACT])


def test_duplicate_document_generation_is_suppressed_within_run(tmp_path):
    cfg = settings(tmp_path)
    provider = CountingDocumentProvider()

    with tool_run_guard_context(cfg), document_generation_context(cfg, provider=provider):
        first = json.loads(document_generation_handler({"title": "报告", "content": "正文"}))
        second = json.loads(document_generation_handler({"title": "报告", "content": "正文"}))

    assert first["success"] is True
    assert second["success"] is False
    assert second["status"] == "skipped"
    assert second["code"] == "DUPLICATE_TOOL_CALL_SUPPRESSED"
    assert provider.calls == 1


def test_call_limit_is_enforced_when_duplicate_guard_disabled(tmp_path):
    cfg = settings(tmp_path, LINGNENG_DUPLICATE_ARTIFACT_GUARD_ENABLED="false")
    provider = CountingDocumentProvider()

    with tool_run_guard_context(cfg), document_generation_context(cfg, provider=provider):
        first = json.loads(document_generation_handler({"title": "A", "content": "正文 A"}))
        second = json.loads(document_generation_handler({"title": "B", "content": "正文 B"}))

    assert first["success"] is True
    assert second["code"] == "TOOL_CALL_LIMIT_EXCEEDED"
    assert second["metadata"]["limit"] == 1
    assert provider.calls == 1


def test_guard_context_is_run_scoped(tmp_path):
    cfg = settings(tmp_path)
    provider = CountingDocumentProvider()

    with tool_run_guard_context(cfg), document_generation_context(cfg, provider=provider):
        assert json.loads(document_generation_handler({"title": "报告", "content": "正文"}))["success"] is True

    with tool_run_guard_context(cfg), document_generation_context(cfg, provider=provider):
        assert json.loads(document_generation_handler({"title": "报告", "content": "正文"}))["success"] is True

    assert provider.calls == 2


def test_missing_provider_is_not_rewritten_by_guard(tmp_path):
    cfg = settings(tmp_path)

    with tool_run_guard_context(cfg), document_generation_context(cfg, provider=None):
        result = json.loads(document_generation_handler({"title": "报告", "content": "正文"}))

    assert result["code"] == "NOT_CONFIGURED"
```

Add equivalent targeted tests for `web_search`:

```python
def test_web_search_limit_uses_web_search_limit(tmp_path):
    from lingneng.tools.web_search import WebSearchResult, web_search_context, web_search_handler

    class Provider:
        def __init__(self):
            self.calls = 0

        def search(self, request):
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
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_generation_tool_guards.py -q
```

Expected: fail because `lingneng.tools.limits` does not exist.

- [ ] **Step 3: Implement guard context**

Create `lingneng/tools/limits.py`:

```python
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator

from lingneng.config.settings import LingNengSettings
from lingneng.tools.document_generation import _json_result, _public_result

_CURRENT_GUARD: ContextVar["ToolRunGuard | None"] = ContextVar(
    "lingneng_tool_run_guard",
    default=None,
)


@dataclass
class ToolRunGuard:
    settings: LingNengSettings
    counts: dict[str, int] = field(default_factory=dict)
    signatures: set[tuple[str, str]] = field(default_factory=set)

    def check(self, tool_name: str, args: dict[str, Any]) -> str | None:
        signature = _signature(tool_name, args)
        if self.settings.duplicate_artifact_guard_enabled:
            key = (tool_name, signature)
            if key in self.signatures:
                return "DUPLICATE_TOOL_CALL_SUPPRESSED"
            self.signatures.add(key)
        limit = _limit_for(tool_name, self.settings)
        next_count = self.counts.get(tool_name, 0) + 1
        if next_count > limit:
            return "TOOL_CALL_LIMIT_EXCEEDED"
        self.counts[tool_name] = next_count
        return None


@contextmanager
def tool_run_guard_context(settings: LingNengSettings) -> Iterator[ToolRunGuard]:
    guard = ToolRunGuard(settings=settings)
    token = _CURRENT_GUARD.set(guard)
    try:
        yield guard
    finally:
        _CURRENT_GUARD.reset(token)


def guarded_tool_skip_result(
    tool_name: str,
    args: dict[str, Any],
    settings: LingNengSettings,
) -> str | None:
    guard = _CURRENT_GUARD.get()
    if guard is None:
        return None
    code = guard.check(tool_name, args)
    if code is None:
        return None
    reason = (
        "duplicate_suppressed"
        if code == "DUPLICATE_TOOL_CALL_SUPPRESSED"
        else "limit_exceeded"
    )
    return _json_result(
        _public_result(
            tool_name=tool_name,
            success=False,
            status="skipped",
            summary="Tool call was skipped by LingNeng run guard.",
            safe_output={"reason": reason},
            artifacts=[],
            metadata={"limit": _limit_for(tool_name, settings)},
            code=code,
            message=_message(tool_name, code),
        ),
        settings=settings,
    )
```

Complete helpers:

- `_limit_for("web_search")` returns `settings.web_search_max_calls_per_run`.
- other guarded tools return `settings.tool_artifact_max_calls_per_run`.
- `_signature()` hashes normalized selected fields:
  - document: `title`, `instruction`, `format`, `target_format`,
    `sha256(content/document_content/markdown/content_brief)`.
  - image: `prompt` hash, `count`, `size`, `quality`, `style`.
  - chart: `instruction` hash, `title`, `chart_type`, `data_summary` hash, stable
    JSON hash of `data`.
  - web: `query` hash, `top_k`, `recency_filter`, `site_filter`.
- signatures store only hashes, not full prompts or document content.

- [ ] **Step 4: Hook guard into handlers**

In each handler, after settings and provider are resolved and before the
provider call, add:

```python
    from lingneng.tools.limits import guarded_tool_skip_result

    guard_result = guarded_tool_skip_result("document_generation", raw_args, settings)
    if guard_result is not None:
        return guard_result
```

Use the correct tool name in each file.

Important: keep the existing missing-provider `NOT_CONFIGURED` branch before the
guard check so absent providers do not consume call limits.

Add public messages for the new codes in
`lingneng/tools/document_generation.py`:

```python
    "TOOL_CALL_LIMIT_EXCEEDED": "LingNeng tool call limit was reached for this run.",
    "DUPLICATE_TOOL_CALL_SUPPRESSED": "LingNeng duplicate tool call was suppressed for this run.",
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_generation_tool_guards.py -q
```

Expected: pass.

- [ ] **Step 6: Regression check**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_generation_tools.py tests/lingneng/events/test_artifact_events.py -q
```

Expected: pass.

- [ ] **Step 7: Commit and push**

```bash
git add lingneng/tools/limits.py lingneng/tools/document_generation.py lingneng/tools/image_generation.py lingneng/tools/chart_visualization.py lingneng/tools/web_search.py tests/lingneng/tools/test_generation_tool_guards.py
git commit -m "feat: 增加业务工具调用限流和防重"
git push origin dev
```

## Task 12.6: Wire Providers Into Hermes Adapter And Verify SSE Contract

**Files:**
- Modify: `lingneng/runtime/hermes_adapter.py`
- Modify: `tests/lingneng/runtime/test_hermes_adapter_config.py`
- Modify: `tests/lingneng/contract/test_artifact_chat_stream.py`
- Test: `tests/lingneng/tools/test_real_business_providers.py`
- Test: `tests/lingneng/tools/test_generation_tool_guards.py`

- [ ] **Step 1: Write failing adapter wiring test**

Append to `tests/lingneng/runtime/test_hermes_adapter_config.py`:

```python
@pytest.mark.asyncio
async def test_hermes_adapter_enters_configured_business_provider_contexts(
    tmp_path,
    monkeypatch,
):
    from lingneng.tools.document_generation import DocumentGenerationResult
    from tests.lingneng.tools.test_generation_tools import DOC_ARTIFACT

    class FakeProviders:
        def __init__(self):
            self.document_generation = FakeDocumentProvider()
            self.image_generation = None
            self.chart_visualization = None
            self.web_search = None

    class FakeDocumentProvider:
        def __init__(self):
            self.calls = 0

        def generate(self, request):
            self.calls += 1
            return DocumentGenerationResult(summary="ok", artifacts=[DOC_ARTIFACT])

    providers = FakeProviders()
    monkeypatch.setattr(
        hermes_adapter_module,
        "build_lingneng_tool_providers",
        lambda settings: providers,
    )
    ToolDispatchingAgent.dispatched_results = []
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=ToolDispatchingAgent,
    )

    events = [event async for event in adapter.stream(request, resolved, "run-1")]

    assert providers.document_generation.calls == 1
    assert any(event.event == "artifact_created" for event in events)
    final = events[-1]
    assert isinstance(final, FinalEvent)
    assert final.artifacts[0].artifact_id == "artifact-doc-1"
```

Add helper agent in the same file:

```python
class ToolDispatchingAgent(RecordingSystemPromptAgent):
    dispatched_results: list[str] = []

    def run_conversation(
        self,
        user_message,
        system_message=None,
        conversation_history=None,
        task_id=None,
        stream_callback=None,
        persist_user_message=None,
    ):
        from tools.registry import registry

        result = registry.dispatch(
            "document_generation",
            {"title": "报告", "content": "正文"},
        )
        type(self).dispatched_results.append(result)
        callback = self.init_kwargs_seen.get("tool_progress_callback")
        if callback:
            callback(
                "tool.completed",
                "document_generation",
                None,
                None,
                is_error=False,
                result=result,
            )
        return {"final_response": "完成", "messages": []}
```

If `RecordingSystemPromptAgent` does not retain `init_kwargs_seen` per subclass,
store `self.tool_progress_callback = kwargs.get("tool_progress_callback")` in
the helper agent's `__init__`.

- [ ] **Step 2: Write failing contract test for guard isolation through adapter**

Append to `tests/lingneng/contract/test_artifact_chat_stream.py` or
`tests/lingneng/runtime/test_hermes_adapter_config.py`:

```python
@pytest.mark.asyncio
async def test_hermes_adapter_tool_guard_isolated_per_stream(tmp_path, monkeypatch):
    from lingneng.tools.document_generation import DocumentGenerationResult
    from tests.lingneng.tools.test_generation_tools import DOC_ARTIFACT

    class CountingProvider:
        def __init__(self):
            self.calls = 0

        def generate(self, request):
            self.calls += 1
            return DocumentGenerationResult(summary="ok", artifacts=[DOC_ARTIFACT])

    class Providers:
        def __init__(self, provider):
            self.document_generation = provider
            self.image_generation = None
            self.chart_visualization = None
            self.web_search = None

    provider = CountingProvider()
    monkeypatch.setattr(
        hermes_adapter_module,
        "build_lingneng_tool_providers",
        lambda settings: Providers(provider),
    )
    cfg = settings(
        tmp_path,
        LINGNENG_AGENT_MODE="hermes",
        LINGNENG_TOOL_ARTIFACT_MAX_CALLS_PER_RUN="1",
    )
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)

    for run_id in ["run-1", "run-2"]:
        adapter = HermesAgentRunAdapter(settings=cfg, agent_cls=ToolDispatchingAgent)
        [event async for event in adapter.stream(request, resolved, run_id)]

    assert provider.calls == 2
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/runtime/test_hermes_adapter_config.py::test_hermes_adapter_enters_configured_business_provider_contexts \
  tests/lingneng/runtime/test_hermes_adapter_config.py::test_hermes_adapter_tool_guard_isolated_per_stream \
  -q
```

Expected: fail because Hermes adapter does not enter business provider contexts.

- [ ] **Step 4: Wire provider contexts**

In `lingneng/runtime/hermes_adapter.py`, import:

```python
from lingneng.tools.chart_visualization import chart_visualization_context
from lingneng.tools.document_generation import document_generation_context
from lingneng.tools.image_generation import image_generation_context
from lingneng.tools.limits import tool_run_guard_context
from lingneng.tools.providers import build_lingneng_tool_providers
from lingneng.tools.web_search import web_search_context
```

In `run_agent()` before entering the tool contexts, build providers:

```python
                    providers = build_lingneng_tool_providers(self.settings)
```

Replace the current `lingneng_tool_context(self.settings)` context with
`web_search_context(self.settings, provider=providers.web_search)` and add the
other contexts:

```python
                    with (
                        web_search_context(self.settings, provider=providers.web_search),
                        document_generation_context(
                            self.settings,
                            provider=providers.document_generation,
                        ),
                        image_generation_context(
                            self.settings,
                            provider=providers.image_generation,
                        ),
                        chart_visualization_context(
                            self.settings,
                            provider=providers.chart_visualization,
                        ),
                        tool_run_guard_context(self.settings),
                        skill_tool_context(self.settings),
                        employee_handoff_context(handoff_context),
                    ):
```

Remove the now-unused `lingneng_tool_context` import if no longer referenced.

- [ ] **Step 5: Run focused adapter tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/runtime/test_hermes_adapter_config.py::test_hermes_adapter_enters_configured_business_provider_contexts \
  tests/lingneng/runtime/test_hermes_adapter_config.py::test_hermes_adapter_tool_guard_isolated_per_stream \
  -q
```

Expected: pass.

- [ ] **Step 6: Run Phase 12 focused suite**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/config/test_settings.py \
  tests/lingneng/tools/test_real_business_providers.py \
  tests/lingneng/tools/test_generation_tools.py \
  tests/lingneng/tools/test_generation_tool_guards.py \
  tests/lingneng/events/test_artifact_events.py \
  tests/lingneng/runtime/test_hermes_adapter_config.py \
  tests/lingneng/contract/test_artifact_chat_stream.py \
  -q
```

Expected: pass.

- [ ] **Step 7: Run broader LingNeng regression**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng -q
```

Expected: pass.

- [ ] **Step 8: Run lint and import-boundary checks**

Run:

```bash
uv run --extra dev python -m ruff check lingneng tests/lingneng
rg -n "from app\\.|import app\\.|/Users/rotas/Documents/work/hailun/LingNengAI/app" lingneng tests/lingneng || true
```

Expected:

- ruff passes.
- `rg` prints no runtime/test imports from old LingNengAI `app.*`.

- [ ] **Step 9: Commit and push**

```bash
git add lingneng/runtime/hermes_adapter.py tests/lingneng/runtime/test_hermes_adapter_config.py tests/lingneng/contract/test_artifact_chat_stream.py
git commit -m "feat: 接入真实业务工具运行时上下文"
git push origin dev
```

## Final Phase 12 Verification

After Task 12.6 and its reviews pass, run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/config/test_settings.py \
  tests/lingneng/tools/test_real_business_providers.py \
  tests/lingneng/tools/test_generation_tools.py \
  tests/lingneng/tools/test_generation_tool_guards.py \
  tests/lingneng/events/test_artifact_events.py \
  tests/lingneng/runtime/test_hermes_adapter_config.py \
  tests/lingneng/contract/test_artifact_chat_stream.py \
  -q
uv run --extra dev python -m pytest tests/lingneng -q
uv run --extra dev python -m ruff check lingneng tests/lingneng
rg -n "from app\\.|import app\\.|/Users/rotas/Documents/work/hailun/LingNengAI/app" lingneng tests/lingneng || true
git status --short --branch
```

Expected:

- focused suite passes;
- full `tests/lingneng` passes;
- ruff passes;
- old `app.*` import scan is empty;
- working tree is clean after final commit/push.

## Rollback Notes

Phase 12 is additive and fail-closed:

- Clear `LINGNENG_WEB_SEARCH_PROVIDER` to disable Bocha search.
- Clear `LINGNENG_DOCUMENT_PROVIDER` to disable Java file document generation.
- Clear `LINGNENG_IMAGE_PROVIDER` or `LINGNENG_AIGC_RESULT_STORE` to disable
  image and chart providers.
- Clear provider secrets without changing code; tools should return
  `NOT_CONFIGURED`.
- Revert the task commit for a faulty provider module without affecting the
  Phase 5 public tool envelope or artifact event bridge.

## Plan Self-Review

- Spec coverage: all Phase 12 requirements are mapped to tasks: settings/factory
  in 12.1, web search in 12.2, document provider in 12.3, image/chart in 12.4,
  limits/duplicate guard in 12.5, runtime/SSE integration in 12.6.
- Placeholder scan: no unresolved markers or incomplete sections remain.
- Scope check: attachments, RAG hardening, training ingestion, deployment, and
  CI/CD are excluded.
- Type consistency: provider factory types match the existing tool handler
  protocol names; runtime wiring uses existing context managers.
- Test realism: automated tests use mock transports and fake stores; live
  provider tests are not required.
