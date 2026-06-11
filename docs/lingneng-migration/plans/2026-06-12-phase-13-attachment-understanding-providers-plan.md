# Phase 13 Attachment Understanding Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire configured attachment-understanding providers into the Hermes LingNeng runtime so Java request attachments can become safe, bounded, current-turn context.

**Architecture:** Keep the existing `lingneng.tools.attachments` safety shell and prompt injection contract. Add provider configuration, a fail-closed provider factory, an external HTTP provider for rich parsing, a narrow local text/CSV provider, and adapter wiring through `attachment_processing_context(provider=...)`.

**Tech Stack:** Python 3.11-3.13, Pydantic v2, httpx, stdlib csv, Hermes `AIAgent`, LingNeng FastAPI/SSE adapter, pytest, uv, ruff.

---

## Approved Spec

This plan implements:

```text
docs/lingneng-migration/specs/2026-06-12-phase-13-attachment-understanding-providers-spec.md
```

Required context was reloaded before writing this plan:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-11-lingneng-business-capability-hermes-migration-spec.md`
- `docs/lingneng-migration/specs/2026-06-12-phase-13-attachment-understanding-providers-spec.md`

## Execution Gate

No additional user confirmation is required before execution if these accepted
decisions remain true:

- Rich PDF/Office/OCR/Excel handling is bridged through a configured external
  HTTP provider in this phase.
- The local provider is limited to text/Markdown/CSV-like files.
- Excel direct-answer graph behavior remains out of scope.
- Live service tests stay disabled unless explicitly enabled later.

If any of those decisions changes, update the spec and this plan before code
execution.

## Scope

Implement:

- attachment provider settings and ready-summary booleans
- provider factory with fail-closed construction
- external HTTP attachment-processing provider
- local text/Markdown/CSV attachment provider
- safe response normalization and warning mapping
- runtime adapter wiring
- deterministic unit and contract tests

Do not implement:

- old `app.*` imports from the sibling LingNengAI checkout
- old LangGraph attachment nodes
- Excel direct-answer shortcut
- live PDF/Office/OCR/vision/Excel clients
- RAG hardening, training ingestion, deployment, or Java changes

## File Map

Create:

- `lingneng/tools/attachment_provider.py`
  - Provider factory, fail-closed construction wrapper, provider-specific
    warning helpers, shared response coercion helpers.
- `lingneng/tools/attachment_http_provider.py`
  - `HttpAttachmentProcessingProvider`, request serializer, response byte
    limiting, and response normalizer.
- `lingneng/tools/attachment_local_text_provider.py`
  - `LocalTextAttachmentProcessingProvider`, bounded downloader, text/CSV
    parsing, chunking, lexical chunk selection, and prompt context formatter.
- `tests/lingneng/tools/test_attachment_providers.py`
  - Focused provider and factory tests.

Modify:

- `lingneng/config/settings.py`
  - Add Phase 13 provider settings and readiness properties.
- `lingneng/tools/attachments.py`
  - Add optional bounded `query` field to `AttachmentProcessingRequest`; keep
    backward compatibility for existing fake providers.
- `lingneng/runtime/hermes_adapter.py`
  - Build configured attachment provider and enter
    `attachment_processing_context(provider=...)`.
- `tests/lingneng/config/test_settings.py`
- `tests/lingneng/tools/test_attachments.py`
- `tests/lingneng/runtime/test_hermes_adapter_config.py`

Avoid modifying:

- `run_agent.py`
- `model_tools.py`
- `toolsets.py`
- old `/Users/rotas/Documents/work/hailun/LingNengAI` files

## Task 13.1: Add Settings And Provider Factory Skeleton

**Files:**
- Modify: `lingneng/config/settings.py`
- Create: `lingneng/tools/attachment_provider.py`
- Modify: `tests/lingneng/config/test_settings.py`
- Create: `tests/lingneng/tools/test_attachment_providers.py`

- [ ] **Step 1: Add failing settings tests**

Append these tests to `tests/lingneng/config/test_settings.py`:

```python
def test_phase_13_attachment_provider_settings_defaults(tmp_path):
    settings = LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})

    assert settings.attachment_provider == ""
    assert settings.attachment_http_endpoint == ""
    assert settings.attachment_http_api_key == ""
    assert settings.attachment_http_timeout_seconds == 30.0
    assert settings.attachment_http_max_response_bytes == 1048576
    assert settings.attachment_local_text_max_bytes == 2097152
    assert settings.attachment_local_text_max_chars_per_file == 12000
    assert settings.attachment_selected_chunk_limit == 4
    assert settings.attachment_chunk_size == 3000
    assert settings.attachment_chunk_overlap == 300
    assert settings.attachment_provider_configured is False
    assert settings.attachment_http_provider_configured is False
    assert settings.attachment_local_text_provider_configured is False

    summary = settings.ready_summary()
    assert summary["attachment_provider_configured"] is False
    assert summary["attachment_http_provider_configured"] is False
    assert summary["attachment_local_text_provider_configured"] is False


def test_phase_13_attachment_provider_settings_from_env_are_secret_safe(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_ATTACHMENT_PROVIDER": "http",
            "LINGNENG_ATTACHMENT_HTTP_ENDPOINT": "https://attachments.example/process",
            "LINGNENG_ATTACHMENT_HTTP_API_KEY": "attachment-secret",
            "LINGNENG_ATTACHMENT_HTTP_TIMEOUT_SECONDS": "9",
            "LINGNENG_ATTACHMENT_HTTP_MAX_RESPONSE_BYTES": "2048",
            "LINGNENG_ATTACHMENT_LOCAL_TEXT_MAX_BYTES": "1024",
            "LINGNENG_ATTACHMENT_LOCAL_TEXT_MAX_CHARS_PER_FILE": "1000",
            "LINGNENG_ATTACHMENT_SELECTED_CHUNK_LIMIT": "2",
            "LINGNENG_ATTACHMENT_CHUNK_SIZE": "700",
            "LINGNENG_ATTACHMENT_CHUNK_OVERLAP": "50",
        }
    )

    assert settings.attachment_provider_configured is True
    assert settings.attachment_http_provider_configured is True
    assert settings.attachment_local_text_provider_configured is False
    assert settings.attachment_http_timeout_seconds == 9.0
    assert settings.attachment_http_max_response_bytes == 2048
    assert settings.attachment_local_text_max_bytes == 1024
    assert settings.attachment_local_text_max_chars_per_file == 1000
    assert settings.attachment_selected_chunk_limit == 2
    assert settings.attachment_chunk_size == 700
    assert settings.attachment_chunk_overlap == 50
    assert "attachment-secret" not in repr(settings.ready_summary())
```

Extend the existing invalid-settings parametrization with:

```python
("LINGNENG_ATTACHMENT_HTTP_TIMEOUT_SECONDS", "0.09"),
("LINGNENG_ATTACHMENT_HTTP_MAX_RESPONSE_BYTES", "1023"),
("LINGNENG_ATTACHMENT_LOCAL_TEXT_MAX_BYTES", "0"),
("LINGNENG_ATTACHMENT_LOCAL_TEXT_MAX_CHARS_PER_FILE", "499"),
("LINGNENG_ATTACHMENT_SELECTED_CHUNK_LIMIT", "0"),
("LINGNENG_ATTACHMENT_CHUNK_SIZE", "499"),
("LINGNENG_ATTACHMENT_CHUNK_OVERLAP", "-1"),
```

- [ ] **Step 2: Add failing factory tests**

Create `tests/lingneng/tools/test_attachment_providers.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.tools.attachment_provider import (
    build_attachment_processing_provider,
)


def settings(tmp_path: Path, **overrides: str) -> LingNengSettings:
    env = {"LINGNENG_RUNTIME_DIR": str(tmp_path)}
    env.update(overrides)
    return LingNengSettings.from_env(env)


def test_attachment_provider_factory_returns_none_for_incomplete_config(tmp_path):
    assert build_attachment_processing_provider(settings(tmp_path)) is None
    assert (
        build_attachment_processing_provider(
            settings(
                tmp_path,
                LINGNENG_ATTACHMENT_PROVIDER="http",
                LINGNENG_ATTACHMENT_HTTP_ENDPOINT="",
            )
        )
        is None
    )


def test_attachment_provider_factory_builds_local_text_provider(tmp_path):
    provider = build_attachment_processing_provider(
        settings(tmp_path, LINGNENG_ATTACHMENT_PROVIDER="local_text")
    )

    assert provider.__class__.__name__ == "LocalTextAttachmentProcessingProvider"


def test_attachment_provider_factory_fail_closes_construction_errors(
    tmp_path,
    monkeypatch,
    caplog,
):
    import lingneng.tools.attachment_local_text_provider as local_provider_module

    class ExplodingProvider:
        def __init__(self, settings):
            del settings
            raise ValueError("https://secret.example?token=secret-token")

    monkeypatch.setattr(
        local_provider_module,
        "LocalTextAttachmentProcessingProvider",
        ExplodingProvider,
    )

    with caplog.at_level("WARNING", logger="lingneng.tools.attachment_provider"):
        provider = build_attachment_processing_provider(
            settings(tmp_path, LINGNENG_ATTACHMENT_PROVIDER="local_text")
        )

    assert provider is None
    assert "attachment local_text provider construction failed" in caplog.text
    assert "secret-token" not in caplog.text
    assert "https://secret.example" not in caplog.text
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/config/test_settings.py::test_phase_13_attachment_provider_settings_defaults \
  tests/lingneng/config/test_settings.py::test_phase_13_attachment_provider_settings_from_env_are_secret_safe \
  tests/lingneng/tools/test_attachment_providers.py::test_attachment_provider_factory_returns_none_for_incomplete_config \
  -q
```

Expected: fail because settings and provider factory do not exist yet.

- [ ] **Step 4: Implement settings**

In `lingneng/config/settings.py`, add fields:

```python
    attachment_provider: str = ""
    attachment_http_endpoint: str = ""
    attachment_http_api_key: str = Field(default="", repr=False)
    attachment_http_timeout_seconds: float = Field(default=30.0, ge=0.1)
    attachment_http_max_response_bytes: int = Field(default=1048576, ge=1024)
    attachment_local_text_max_bytes: int = Field(default=2097152, ge=1)
    attachment_local_text_max_chars_per_file: int = Field(default=12000, ge=500)
    attachment_selected_chunk_limit: int = Field(default=4, ge=1)
    attachment_chunk_size: int = Field(default=3000, ge=500)
    attachment_chunk_overlap: int = Field(default=300, ge=0)
```

Parse env values in `from_env()` with the exact `LINGNENG_*` names from the
spec.

Add properties:

```python
    @property
    def attachment_http_provider_configured(self) -> bool:
        return (
            self.attachment_provider.strip().lower() == "http"
            and bool(self.attachment_http_endpoint.strip())
        )

    @property
    def attachment_local_text_provider_configured(self) -> bool:
        return self.attachment_provider.strip().lower() == "local_text"

    @property
    def attachment_provider_configured(self) -> bool:
        return (
            self.attachment_http_provider_configured
            or self.attachment_local_text_provider_configured
        )
```

Add the three booleans to `ready_summary()`.

- [ ] **Step 5: Implement factory skeleton**

Create `lingneng/tools/attachment_provider.py`:

```python
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeVar

from lingneng.config.settings import LingNengSettings
from lingneng.tools.attachments import AttachmentProcessingProvider


_LOGGER = logging.getLogger(__name__)
_ProviderT = TypeVar("_ProviderT")


def build_attachment_processing_provider(
    settings: LingNengSettings,
) -> AttachmentProcessingProvider | None:
    provider_name = settings.attachment_provider.strip().lower()
    if provider_name == "http":
        if not settings.attachment_http_endpoint.strip():
            return None
        from lingneng.tools.attachment_http_provider import (
            HttpAttachmentProcessingProvider,
        )

        return _construct_provider(
            "http",
            lambda: HttpAttachmentProcessingProvider.from_settings(settings),
        )
    if provider_name == "local_text":
        from lingneng.tools.attachment_local_text_provider import (
            LocalTextAttachmentProcessingProvider,
        )

        return _construct_provider(
            "local_text",
            lambda: LocalTextAttachmentProcessingProvider(settings),
        )
    return None


def _construct_provider(
    provider_name: str,
    factory: Callable[[], _ProviderT],
) -> _ProviderT | None:
    try:
        return factory()
    except Exception:
        _LOGGER.warning(
            "LingNeng attachment %s provider construction failed; provider disabled.",
            provider_name,
        )
        return None
```

Create minimal temporary classes so factory tests can pass; later tasks replace
them with real behavior:

```python
# lingneng/tools/attachment_http_provider.py
class HttpAttachmentProcessingProvider:
    @classmethod
    def from_settings(cls, settings):
        return cls(settings=settings)

    def __init__(self, *, settings, http_client=None):
        self.settings = settings
        self.http_client = http_client
```

```python
# lingneng/tools/attachment_local_text_provider.py
class LocalTextAttachmentProcessingProvider:
    def __init__(self, settings, *, http_client=None):
        self.settings = settings
        self.http_client = http_client
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/config/test_settings.py \
  tests/lingneng/tools/test_attachment_providers.py \
  -q
```

Expected: pass for Task 13.1 tests.

- [ ] **Step 7: Commit and push**

```bash
git add \
  lingneng/config/settings.py \
  lingneng/tools/attachment_provider.py \
  lingneng/tools/attachment_http_provider.py \
  lingneng/tools/attachment_local_text_provider.py \
  tests/lingneng/config/test_settings.py \
  tests/lingneng/tools/test_attachment_providers.py
git commit -m "feat: 增加附件理解提供方配置"
git push origin dev
```

## Task 13.2: Implement HTTP Attachment Provider

**Files:**
- Modify: `lingneng/tools/attachment_http_provider.py`
- Modify: `tests/lingneng/tools/test_attachment_providers.py`

- [ ] **Step 1: Add failing HTTP provider tests**

Append to `tests/lingneng/tools/test_attachment_providers.py`:

```python
import json

import httpx

from lingneng.tools.attachment_http_provider import (
    HttpAttachmentProcessingProvider,
)
from lingneng.tools.attachments import AttachmentProcessingRequest


def attachment_request() -> AttachmentProcessingRequest:
    from lingneng.schemas.chat_request import AttachmentPayload

    return AttachmentProcessingRequest(
        tenant_id="tenant-1",
        user_id="user-1",
        session_id="session-1",
        conversation_id="conv-1",
        request_id="req-1",
        employee_type="marketing_content_creator",
        attachments=[
            AttachmentPayload.model_validate(
                {
                    "file_id": "file-1",
                    "file_name": "menu.pdf",
                    "mime_type": "application/pdf",
                    "size": 100,
                    "download_url": "https://files.example.test/menu.pdf",
                    "usage": "session_context",
                }
            )
        ],
        timeout_seconds=3,
        context_max_chars=500,
        max_files=5,
        max_total_bytes=1000,
        max_file_bytes=800,
        max_image_bytes=500,
    )


def test_http_attachment_provider_sends_bounded_request_and_normalizes_response(tmp_path):
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "status": "succeeded",
                "context_text": "### menu.pdf\n菜品摘要",
                "processed_count": 1,
                "failed_count": 0,
                "selected_count": 1,
                "warnings": [{"code": "ATTACHMENT_CONTEXT_TRUNCATED", "file_id": "file-1"}],
                "files": [{"file_id": "file-1", "file_name": "menu.pdf", "status": "processed"}],
            },
        )

    provider = HttpAttachmentProcessingProvider(
        endpoint="https://attachments.example/process",
        api_key="secret-key",
        timeout_seconds=3,
        max_response_bytes=4096,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.process(attachment_request())

    assert captured["url"] == "https://attachments.example/process"
    assert captured["authorization"] == "Bearer secret-key"
    assert captured["body"]["request_id"] == "req-1"
    assert captured["body"]["limits"]["max_file_bytes"] == 800
    assert captured["body"]["attachments"][0]["download_url"] == "https://files.example.test/menu.pdf"
    assert result.status == "succeeded"
    assert result.context_text == "### menu.pdf\n菜品摘要"
    assert result.processed_count == 1
    assert result.warnings[0].code == "ATTACHMENT_CONTEXT_TRUNCATED"


def test_http_attachment_provider_rejects_oversized_response(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, content=b'{"status":"succeeded","context_text":"' + b"x" * 200 + b'"}')

    provider = HttpAttachmentProcessingProvider(
        endpoint="https://attachments.example/process",
        api_key="secret-key",
        timeout_seconds=3,
        max_response_bytes=100,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.process(attachment_request())

    assert result.status == "failed"
    assert result.code == "ATTACHMENT_PROVIDER_INVALID_RESULT"
    assert result.context_text == ""


def test_http_attachment_provider_sanitizes_failures(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(500, text="secret-token traceback /Users/rotas/private")

    provider = HttpAttachmentProcessingProvider(
        endpoint="https://attachments.example/process?token=secret-token",
        api_key="secret-key",
        timeout_seconds=3,
        max_response_bytes=4096,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.process(attachment_request())

    dumped = result.model_dump_json()
    assert result.status == "failed"
    assert result.code == "ATTACHMENT_PROVIDER_ERROR"
    assert "secret-token" not in dumped
    assert "traceback" not in dumped
    assert "/Users/rotas" not in dumped
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/tools/test_attachment_providers.py::test_http_attachment_provider_sends_bounded_request_and_normalizes_response \
  tests/lingneng/tools/test_attachment_providers.py::test_http_attachment_provider_rejects_oversized_response \
  tests/lingneng/tools/test_attachment_providers.py::test_http_attachment_provider_sanitizes_failures \
  -q
```

Expected: fail because the HTTP provider is still a skeleton.

- [ ] **Step 3: Implement HTTP provider**

Implement `lingneng/tools/attachment_http_provider.py` with:

- `HttpAttachmentProcessingProviderError`.
- `from_settings(settings)`.
- sync `process(request)`.
- `_request_payload(request)`.
- `_post(payload)` using injected client or `httpx.Client(timeout=..., trust_env=False)`.
- response byte limit before JSON parse:

```python
content = response.content
if len(content) > self.max_response_bytes:
    return _failure("ATTACHMENT_PROVIDER_INVALID_RESULT")
```

- safe failure result:

```python
def _failure(code: str) -> AttachmentProcessingResult:
    return AttachmentProcessingResult(
        status="failed",
        context_text="",
        processed_count=0,
        failed_count=0,
        selected_count=0,
        warnings=[AttachmentWarning(code=code)],
        code=code,
    )
```

- response normalization through `AttachmentProcessingResult.model_validate`.
- public warning normalization can rely on `build_attachment_prompt_context()`,
  but provider should still avoid adding raw failure messages.

Use `Authorization: Bearer <api_key>` when an API key is present. Do not include
the endpoint or key in returned result messages.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_attachment_providers.py -q
uv run --extra dev python -m ruff check lingneng/tools/attachment_http_provider.py tests/lingneng/tools/test_attachment_providers.py
```

Expected: pass.

- [ ] **Step 5: Commit and push**

```bash
git add lingneng/tools/attachment_http_provider.py tests/lingneng/tools/test_attachment_providers.py
git commit -m "feat: 接入 HTTP 附件理解提供方"
git push origin dev
```

## Task 13.3: Implement Local Text Attachment Provider

**Files:**
- Modify: `lingneng/tools/attachments.py`
- Modify: `lingneng/tools/attachment_local_text_provider.py`
- Modify: `tests/lingneng/tools/test_attachment_providers.py`
- Modify: `tests/lingneng/tools/test_attachments.py`

- [ ] **Step 1: Add failing local provider tests**

Append to `tests/lingneng/tools/test_attachment_providers.py`:

```python
from lingneng.tools.attachment_local_text_provider import (
    LocalTextAttachmentProcessingProvider,
)


def test_local_text_provider_downloads_text_and_selects_relevant_chunks(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://files.example.test/menu.txt"
        body = (
            "菜单说明\n"
            "会员复购活动适合工作日午餐。\n"
            "无关内容 " * 50
        )
        return httpx.Response(200, content=body.encode("utf-8"))

    request = attachment_request()
    request.attachments[0].file_name = "menu.txt"
    request.attachments[0].mime_type = "text/plain"
    request.query = "会员复购"
    provider = LocalTextAttachmentProcessingProvider(
        settings(
            tmp_path,
            LINGNENG_ATTACHMENT_CHUNK_SIZE="80",
            LINGNENG_ATTACHMENT_CHUNK_OVERLAP="10",
            LINGNENG_ATTACHMENT_SELECTED_CHUNK_LIMIT="1",
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.process(request)

    assert result.status == "succeeded"
    assert result.processed_count == 1
    assert result.selected_count == 1
    assert "### menu.txt" in result.context_text
    assert "会员复购活动" in result.context_text
    assert "history content marker" not in result.context_text


def test_local_text_provider_formats_csv_rows(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            content="month,revenue\nJan,10\nFeb,20\n".encode("utf-8"),
            headers={"content-length": "28"},
        )

    request = attachment_request()
    request.attachments[0].file_name = "sales.csv"
    request.attachments[0].mime_type = "text/csv"
    provider = LocalTextAttachmentProcessingProvider(
        settings(tmp_path),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.process(request)

    assert result.status == "succeeded"
    assert "month | revenue" in result.context_text
    assert "Jan | 10" in result.context_text
    assert result.processed_count == 1


def test_local_text_provider_rejects_unsupported_pdf_without_download(tmp_path):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"pdf")

    provider = LocalTextAttachmentProcessingProvider(
        settings(tmp_path),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.process(attachment_request())

    assert calls == 0
    assert result.status == "skipped"
    assert result.processed_count == 0
    assert result.failed_count == 1
    assert result.warnings[0].code == "ATTACHMENT_PROVIDER_NOT_CONFIGURED"


def test_local_text_provider_enforces_download_byte_limit(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            content=b"x" * 20,
            headers={"content-length": "20"},
        )

    request = attachment_request()
    request.attachments[0].file_name = "menu.txt"
    request.attachments[0].mime_type = "text/plain"
    provider = LocalTextAttachmentProcessingProvider(
        settings(tmp_path, LINGNENG_ATTACHMENT_LOCAL_TEXT_MAX_BYTES="5"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.process(request)

    assert result.status == "failed"
    assert result.code == "ATTACHMENT_FILE_TOO_LARGE"
    assert result.context_text == ""
```

- [ ] **Step 2: Add query to provider request**

In `lingneng/tools/attachments.py`, add a backward-compatible field:

```python
    query: str = ""
```

to `AttachmentProcessingRequest`. When constructing `provider_request`, set:

```python
        query=_bounded_query(request.query.content),
```

Add helper:

```python
def _bounded_query(value: str) -> str:
    return _sanitize_prompt_text(value)[:2000]
```

Update `tests/lingneng/tools/test_attachments.py` with:

```python
def test_attachment_provider_request_includes_current_query_only(tmp_path):
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(
            context_text="ok",
            selected_count=1,
            processed_count=1,
        )
    )
    request = request_with_attachments(attachment())

    with attachment_processing_context(provider=provider):
        build_attachment_prompt_context(settings(tmp_path), request)

    assert provider.requests[0].query == request.query.content
    assert "history content marker" not in provider.requests[0].query
```

- [ ] **Step 3: Implement local text provider**

Implement `lingneng/tools/attachment_local_text_provider.py` with:

- supported suffix/mime checks for `.txt`, `.md`, `.markdown`, `.csv`,
  `text/plain`, `text/markdown`, `text/csv`;
- sync download using injected client or `httpx.Client(..., follow_redirects=False, trust_env=False)`;
- content-length and streamed byte checks against
  `settings.attachment_local_text_max_bytes`;
- UTF-8 decode with `utf-8-sig`;
- CSV formatting using `csv.reader`;
- chunking:

```python
def _chunks(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    chunks = []
    start = 0
    safe_overlap = min(max(overlap, 0), max(0, chunk_size - 1))
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(end - safe_overlap, start + 1)
    return chunks
```

- lexical selection using the old reference approach: ASCII tokens plus CJK
  characters, sorted by score desc and original order;
- per-file context formatting:

```text
### menu.txt
类型: text/plain
内容摘要/片段:
- 会员复购活动适合工作日午餐。
```

- return `AttachmentProcessingResult` with public warning codes only.

For unsupported rich files, return `status="skipped"`, `failed_count` equal to
the unsupported count, and warning `ATTACHMENT_PROVIDER_NOT_CONFIGURED`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_attachment_providers.py tests/lingneng/tools/test_attachments.py -q
uv run --extra dev python -m ruff check lingneng/tools/attachments.py lingneng/tools/attachment_local_text_provider.py tests/lingneng/tools/test_attachment_providers.py tests/lingneng/tools/test_attachments.py
```

Expected: pass.

- [ ] **Step 5: Commit and push**

```bash
git add \
  lingneng/tools/attachments.py \
  lingneng/tools/attachment_local_text_provider.py \
  tests/lingneng/tools/test_attachment_providers.py \
  tests/lingneng/tools/test_attachments.py
git commit -m "feat: 增加本地文本附件解析"
git push origin dev
```

## Task 13.4: Wire Attachment Provider Into Hermes Adapter

**Files:**
- Modify: `lingneng/runtime/hermes_adapter.py`
- Modify: `tests/lingneng/runtime/test_hermes_adapter_config.py`

- [ ] **Step 1: Add failing adapter tests**

Append to `tests/lingneng/runtime/test_hermes_adapter_config.py`:

```python
@pytest.mark.asyncio
async def test_hermes_adapter_uses_configured_attachment_provider(
    tmp_path,
    monkeypatch,
):
    class Provider:
        def __init__(self):
            self.requests = []

        def process(self, request):
            self.requests.append(request)
            return AttachmentProcessingResult(
                context_text="配置 provider 附件摘要",
                selected_count=1,
                processed_count=1,
            )

    provider = Provider()
    monkeypatch.setattr(
        hermes_adapter_module,
        "build_attachment_processing_provider",
        lambda settings: provider,
        raising=False,
    )
    payload = full_payload()
    payload["attachments"] = [
        {
            "file_id": "file-1",
            "file_name": "menu.txt",
            "mime_type": "text/plain",
            "size": 100,
            "download_url": "https://files.example.test/menu.txt",
        }
    ]
    request = ChatStreamRequest.model_validate(payload)
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(
            tmp_path,
            LINGNENG_AGENT_MODE="hermes",
            LINGNENG_ATTACHMENT_ALLOWED_HOSTS="files.example.test",
        ),
        agent_cls=RecordingSystemPromptAgent,
    )

    events = [event async for event in adapter.stream(request, resolved, "run-1")]

    assert provider.requests
    assert isinstance(events[-1], FinalEvent)
    assert "配置 provider 附件摘要" in effective_system_prompt()


@pytest.mark.asyncio
async def test_hermes_adapter_attachment_provider_build_failure_is_fail_closed(
    tmp_path,
    monkeypatch,
    caplog,
):
    def fail_build(settings):
        del settings
        raise RuntimeError("secret-token /Users/rotas/private")

    monkeypatch.setattr(
        hermes_adapter_module,
        "build_attachment_processing_provider",
        fail_build,
        raising=False,
    )
    payload = full_payload()
    payload["attachments"] = [
        {
            "file_id": "file-1",
            "file_name": "menu.txt",
            "mime_type": "text/plain",
            "size": 100,
            "download_url": "https://files.example.test/menu.txt",
        }
    ]
    request = ChatStreamRequest.model_validate(payload)
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(
            tmp_path,
            LINGNENG_AGENT_MODE="hermes",
            LINGNENG_ATTACHMENT_ALLOWED_HOSTS="files.example.test",
        ),
        agent_cls=RecordingSystemPromptAgent,
    )

    with caplog.at_level("WARNING", logger="lingneng.runtime.hermes_adapter"):
        events = [event async for event in adapter.stream(request, resolved, "run-1")]

    assert isinstance(events[-1], FinalEvent)
    assert not any(isinstance(event, ErrorEvent) for event in events)
    assert "secret-token" not in caplog.text
    assert "/Users/rotas" not in caplog.text
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/runtime/test_hermes_adapter_config.py::test_hermes_adapter_uses_configured_attachment_provider \
  tests/lingneng/runtime/test_hermes_adapter_config.py::test_hermes_adapter_attachment_provider_build_failure_is_fail_closed \
  -q
```

Expected: fail because adapter does not build configured attachment providers.

- [ ] **Step 3: Wire provider in adapter**

In `lingneng/runtime/hermes_adapter.py`, import:

```python
from lingneng.tools.attachment_provider import build_attachment_processing_provider
from lingneng.tools.attachments import attachment_processing_context
```

Add helper:

```python
def _build_attachment_provider(settings: LingNengSettings):
    try:
        return build_attachment_processing_provider(settings)
    except Exception:
        _LOGGER.warning(
            "LingNeng attachment provider construction failed; provider disabled."
        )
        return None
```

Inside `run_agent()`, before the `with (...)` context, build:

```python
                    attachment_provider = _build_attachment_provider(self.settings)
```

Add to the context manager stack that already wraps attachment prompt flow:

```python
                        attachment_processing_context(provider=attachment_provider),
```

Keep all existing attachment started/finished emission and prompt composition
unchanged.

- [ ] **Step 4: Update old adapter tests to use the adapter-owned provider hook**

Existing runtime tests that manually wrap `adapter.stream(...)` with
`attachment_processing_context(provider=...)` must be updated because Phase 13
makes the adapter own the attachment provider context. Replace each runtime test
wrapper with a monkeypatch against the adapter module factory:

```python
monkeypatch.setattr(
    hermes_adapter_module,
    "build_attachment_processing_provider",
    lambda settings: provider,
    raising=False,
)
```

Update affected tests in `tests/lingneng/runtime/test_hermes_adapter_config.py`
that currently contain `with attachment_processing_context(provider=provider):`.
Keep lower-level `tests/lingneng/tools/test_attachments.py` tests using
`attachment_processing_context(...)`; that file still tests the attachment shell
directly.

- [ ] **Step 5: Run focused runtime tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime/test_hermes_adapter_config.py -q
uv run --extra dev python -m pytest tests/lingneng/tools/test_attachments.py tests/lingneng/tools/test_attachment_providers.py -q
uv run --extra dev python -m ruff check lingneng/runtime/hermes_adapter.py tests/lingneng/runtime/test_hermes_adapter_config.py
```

Expected: pass.

- [ ] **Step 6: Commit and push**

```bash
git add lingneng/runtime/hermes_adapter.py tests/lingneng/runtime/test_hermes_adapter_config.py
git commit -m "feat: 接入附件理解运行时上下文"
git push origin dev
```

## Task 13.5: Final Phase 13 Verification And Boundary Scan

**Files:**
- No intended runtime changes unless verification reveals a regression.

- [ ] **Step 1: Run focused Phase 13 suite**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/config/test_settings.py \
  tests/lingneng/tools/test_attachments.py \
  tests/lingneng/tools/test_attachment_providers.py \
  tests/lingneng/runtime/test_hermes_adapter_config.py \
  -q
```

Expected: pass.

- [ ] **Step 2: Run broader LingNeng regression**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng -q
```

Expected: pass.

- [ ] **Step 3: Run lint and import-boundary checks**

Run:

```bash
uv run --extra dev python -m ruff check lingneng tests/lingneng
rg -n "from app\\.|import app\\.|/Users/rotas/Documents/work/hailun/LingNengAI/app" lingneng tests/lingneng || true
git status --short --branch
```

Expected:

- ruff passes;
- old `app.*` scan prints no matches;
- working tree is clean after the final task commit/push.

- [ ] **Step 4: Fix regressions if any**

If a verification command fails, create the smallest targeted fix, rerun the
failing command, then rerun all commands in this task before marking Phase 13
complete. Commit with:

```bash
git commit -m "fix: 修正附件理解阶段回归"
git push origin dev
```

## Rollback Notes

Phase 13 remains additive and fail-closed:

- Clear `LINGNENG_ATTACHMENT_PROVIDER` to return to the existing Phase 5
  behavior where attachments are selected but no configured provider runs.
- Use `LINGNENG_ATTACHMENT_PROVIDER=local_text` only for narrow text/CSV
  parsing.
- Disable the HTTP provider by clearing `LINGNENG_ATTACHMENT_HTTP_ENDPOINT`.
- Revert the HTTP/local provider commits without affecting the Java stream
  endpoint, SessionDB, RAG, skills, or Phase 12 generation providers.

## Plan Self-Review

- Spec coverage: settings/factory are in Task 13.1, HTTP provider in Task 13.2,
  local text provider and query field in Task 13.3, adapter wiring in Task 13.4,
  and final suite/import-boundary verification in Task 13.5.
- Scope check: no task imports old `app.*`, reintroduces LangGraph attachment
  nodes, adds direct-answer routing, or implements live PDF/Office/OCR/Excel
  clients.
- Safety check: every provider path is fail-closed, bounded, and tested for
  secret/raw-path leakage.
- Type consistency: settings names, factory names, provider class names, and
  request field names match across tasks.
- Red-flag scan: no task uses unspecified plan gaps; each task includes
  concrete test names, code snippets, commands, and commit messages.
