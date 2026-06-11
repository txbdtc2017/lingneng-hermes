# Phase 14 RAG Provider Integration Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make configured external `retrieve_rag` HTTP provider usage bounded, secret-safe, old-service compatible, and non-fatal to the Java chat stream.

**Architecture:** Keep RAG as a normal Hermes tool under `lingneng.tools.rag`. Harden settings first, then replace the simple `httpx.post().json()` provider with a streaming fail-closed HTTP provider, strengthen result sanitization, add adapter construction guardrails, and finish with focused plus full LingNeng verification. Training and indexing remain outside this phase.

**Tech Stack:** Python 3.11-3.13, Pydantic v2, httpx, Hermes tool callbacks, LingNeng SSE bridge, pytest, uv, ruff, ty.

---

## Approved Spec

This plan implements:

```text
docs/lingneng-migration/specs/2026-06-12-phase-14-rag-provider-hardening-spec.md
```

Required context was reloaded before writing this plan:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-11-lingneng-business-capability-hermes-migration-spec.md`
- `docs/lingneng-migration/specs/2026-06-12-phase-14-rag-provider-hardening-spec.md`

## Execution Gate

No additional user confirmation is required before execution if these accepted
decisions remain true:

- RAG query can keep calling an external HTTP endpoint, including old LingNengAI
  in dev/test.
- Training, indexing, embedding, vector search, reranking, and worker lifecycle
  remain out of scope.
- Live RAG integration tests are opt-in and skipped by default.
- Java request/SSE contracts remain unchanged.

If any of those decisions changes, update the Phase 14 spec and this plan before
code execution.

## Scope

Implement:

- Phase 14 RAG settings and secret-safe readiness fields
- public timeout failure code
- streaming HTTP RAG provider with response byte limit
- canonical and old LingNengAI-compatible response normalization
- stronger RAG context/citation/metadata sanitization
- adapter provider construction fail-closed behavior
- skipped-by-default live smoke test gate
- focused and full LingNeng verification

Do not implement:

- old `app.*` imports
- in-Hermes training ingestion or indexing
- vector-store/embedding/rerank providers
- RAG-first answer graph or pre-agent router
- Java changes
- deployment or CI/CD changes

## File Map

Modify:

- `lingneng/config/settings.py`
  - Add Phase 14 settings and readiness fields.
- `lingneng/tools/rag.py`
  - Harden `HttpRagProvider`, response normalization, public sanitization, and
    failure codes.
- `lingneng/runtime/hermes_adapter.py`
  - Make RAG provider construction fail-closed.
- `tests/lingneng/config/test_settings.py`
- `tests/lingneng/tools/test_retrieve_rag.py`
- `tests/lingneng/events/test_rag_events.py`
- `tests/lingneng/runtime/test_hermes_adapter_config.py`

Create:

- `tests/lingneng/integration/test_rag_provider_live.py`
  - Skipped unless live RAG env gate is enabled.

Avoid modifying:

- `run_agent.py`
- `model_tools.py`
- `toolsets.py`
- old `/Users/rotas/Documents/work/hailun/LingNengAI` files

## Task 14.1: Add RAG Hardening Settings And Public Failure Code

**Files:**
- Modify: `lingneng/config/settings.py`
- Modify: `lingneng/tools/rag.py`
- Modify: `tests/lingneng/config/test_settings.py`
- Modify: `tests/lingneng/tools/test_retrieve_rag.py`

- [ ] **Step 1: Add failing settings tests**

Append to `tests/lingneng/config/test_settings.py`:

```python
def test_phase_14_rag_hardening_settings_defaults(tmp_path):
    settings = LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})

    assert settings.rag_http_max_response_bytes == 1048576
    assert settings.rag_live_test_enabled is False
    assert settings.rag_live_test_query == ""

    summary = settings.ready_summary()
    assert summary["rag_configured"] is False
    assert summary["rag_http_max_response_bytes"] == 1048576
    assert summary["rag_live_test_enabled"] is False
    assert "rag_live_test_query" not in summary


def test_phase_14_rag_hardening_settings_from_env_are_secret_safe(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve?token=url-token",
            "LINGNENG_RAG_API_KEY": "secret-rag-key",
            "LINGNENG_RAG_HTTP_MAX_RESPONSE_BYTES": "2048",
            "LINGNENG_RAG_LIVE_TEST_ENABLED": "true",
            "LINGNENG_RAG_LIVE_TEST_QUERY": "secret live query",
        }
    )

    assert settings.rag_http_max_response_bytes == 2048
    assert settings.rag_live_test_enabled is True
    assert settings.rag_live_test_query == "secret live query"

    dumped = repr(settings.ready_summary())
    assert "secret-rag-key" not in dumped
    assert "secret live query" not in dumped
    assert "url-token" not in dumped
```

Extend the existing invalid-settings parametrization with:

```python
("LINGNENG_RAG_HTTP_MAX_RESPONSE_BYTES", "1023"),
```

- [ ] **Step 2: Add failing timeout-code test**

Append to `tests/lingneng/tools/test_retrieve_rag.py`:

```python
def test_retrieve_rag_timeout_failure_code_is_public(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(
            status="failed",
            context="traceback secret-token",
            citations=[],
            metadata={"authorization": "Bearer secret"},
            code="RAG_PROVIDER_TIMEOUT",
        )
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    dumped = json.dumps(result, ensure_ascii=False)
    assert result["success"] is False
    assert result["code"] == "RAG_PROVIDER_TIMEOUT"
    assert result["message"] == "LingNeng RAG provider timed out."
    assert "secret-token" not in dumped
    assert "Bearer" not in dumped
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/config/test_settings.py::test_phase_14_rag_hardening_settings_defaults \
  tests/lingneng/config/test_settings.py::test_phase_14_rag_hardening_settings_from_env_are_secret_safe \
  tests/lingneng/tools/test_retrieve_rag.py::test_retrieve_rag_timeout_failure_code_is_public \
  -q
```

Expected: fail because the new settings and public timeout code do not exist.

- [ ] **Step 4: Implement settings and public code**

In `lingneng/config/settings.py`, add fields:

```python
    rag_http_max_response_bytes: int = Field(default=1048576, ge=1024)
    rag_live_test_enabled: bool = False
    rag_live_test_query: str = Field(default="", repr=False)
```

Parse these env vars in `from_env()`:

```python
rag_http_max_response_bytes=int(
    source.get("LINGNENG_RAG_HTTP_MAX_RESPONSE_BYTES", "1048576")
),
rag_live_test_enabled=_bool_from_env(
    source.get("LINGNENG_RAG_LIVE_TEST_ENABLED"),
    default=False,
),
rag_live_test_query=source.get("LINGNENG_RAG_LIVE_TEST_QUERY", ""),
```

Add to `ready_summary()`:

```python
"rag_http_max_response_bytes": self.rag_http_max_response_bytes,
"rag_live_test_enabled": self.rag_live_test_enabled,
```

In `lingneng/tools/rag.py`, add `RAG_PROVIDER_TIMEOUT` to
`_PUBLIC_FAILURE_CODES` and `_public_error_message(...)`:

```python
"RAG_PROVIDER_TIMEOUT": "LingNeng RAG provider timed out.",
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/config/test_settings.py \
  tests/lingneng/tools/test_retrieve_rag.py \
  -q
uv run --extra dev python -m ruff check \
  lingneng/config/settings.py \
  lingneng/tools/rag.py \
  tests/lingneng/config/test_settings.py \
  tests/lingneng/tools/test_retrieve_rag.py
```

Expected: pass.

- [ ] **Step 6: Commit and push**

```bash
git add \
  lingneng/config/settings.py \
  lingneng/tools/rag.py \
  tests/lingneng/config/test_settings.py \
  tests/lingneng/tools/test_retrieve_rag.py
git commit -m "feat: 增加 RAG 加固配置"
git push origin dev
```

## Task 14.2: Harden HTTP RAG Provider And Response Normalization

**Files:**
- Modify: `lingneng/tools/rag.py`
- Modify: `tests/lingneng/tools/test_retrieve_rag.py`

- [ ] **Step 1: Add failing HTTP provider tests**

Append these tests to `tests/lingneng/tools/test_retrieve_rag.py`:

```python
import httpx
```

Extend the existing `from lingneng.tools.rag import (...)` block with:

```python
    HttpRagProvider,
```

Append:

```python


def test_http_rag_provider_streams_success_request_and_normalizes_response(tmp_path):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "status": "hit",
                "context": "套餐规则",
                "citations": [{"chunk_id": "chunk-1", "score": 0.8}],
                "metadata": {"duration_ms": 11},
            },
        )

    settings_obj = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
            "LINGNENG_RAG_API_KEY": "secret-rag-key",
            "LINGNENG_RAG_TIMEOUT_SECONDS": "2",
            "LINGNENG_RAG_HTTP_MAX_RESPONSE_BYTES": "4096",
        }
    )
    provider = HttpRagProvider(
        settings_obj,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.retrieve(
        RagRetrieveRequest(
            query="会员套餐",
            tenant_id="tenant-a",
            user_id="user-a",
            employee_type="marketing_content_creator",
            conversation_id="conv-a",
            session_key="tenant-a:user-a:emp-001:conv-a",
            request_id="req-001",
            top_k=3,
            filters={"document_type": "menu"},
        )
    )

    assert captured["url"] == "https://rag.example.test/retrieve"
    assert captured["authorization"] == "Bearer secret-rag-key"
    assert captured["body"]["query"] == "会员套餐"
    assert captured["body"]["top_k"] == 3
    assert result.status == "hit"
    assert result.context == "套餐规则"
    assert result.citations[0]["chunk_id"] == "chunk-1"
    assert result.metadata["duration_ms"] == 11


def test_http_rag_provider_normalizes_old_lingneng_shape(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "context": "旧服务上下文",
                "citations": [{"chunk_id": "chunk-old", "score": 0.9}],
                "route_debug": {"retrieval_status": "hit"},
            },
        )

    provider = HttpRagProvider(
        LingNengSettings.from_env(
            {
                "LINGNENG_RUNTIME_DIR": str(tmp_path),
                "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
            }
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.retrieve(
        RagRetrieveRequest(
            query="会员套餐",
            tenant_id="tenant-a",
            user_id="user-a",
            employee_type="marketing_content_creator",
            conversation_id="conv-a",
            session_key="session",
            request_id="req-001",
            top_k=3,
            filters={},
        )
    )

    assert result.status == "hit"
    assert result.context == "旧服务上下文"
    assert result.citations[0]["chunk_id"] == "chunk-old"
    assert result.metadata == {"retrieval_status": "hit"}
```

Also add focused tests named:

```python
def test_http_rag_provider_rejects_oversized_stream_without_buffering(tmp_path): ...
def test_http_rag_provider_rejects_non_2xx_without_reading_body(tmp_path): ...
def test_http_rag_provider_maps_timeout_to_public_failed_result(tmp_path): ...
def test_http_rag_provider_rejects_invalid_json(tmp_path): ...
def test_http_rag_provider_rejects_invalid_schema(tmp_path): ...
def test_http_rag_provider_default_client_disables_env_and_redirects(tmp_path, monkeypatch): ...
```

Use the same fake stream pattern as Phase 13:

```python
class FakeStreamResponse:
    status_code = 200

    @property
    def content(self) -> bytes:
        raise AssertionError("response content must not be buffered")

    def iter_bytes(self, *, chunk_size: int | None = None):
        assert chunk_size == 101
        yield b"x" * 40
        yield b"y" * 40
        yield b"z" * 40
```

For non-2xx tests, `iter_bytes()` must raise `AssertionError` if called.

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/tools/test_retrieve_rag.py::test_http_rag_provider_streams_success_request_and_normalizes_response \
  tests/lingneng/tools/test_retrieve_rag.py::test_http_rag_provider_normalizes_old_lingneng_shape \
  -q
```

Expected: fail because `HttpRagProvider` does not accept an injected client and
does not normalize old response shape.

- [ ] **Step 3: Implement streaming HTTP provider**

In `lingneng/tools/rag.py`, add:

```python
@dataclass(frozen=True)
class _HttpRagResponse:
    status_code: int
    content: bytes = b""
    exceeded_size: bool = False
```

Change `HttpRagProvider` to accept an optional client:

```python
class HttpRagProvider:
    def __init__(
        self,
        settings: LingNengSettings,
        *,
        http_client: Any | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client
```

Implement:

```python
def retrieve(self, request: RagRetrieveRequest) -> RagRetrieveResult:
    try:
        response = self._post(request.model_dump())
    except httpx.TimeoutException:
        return _provider_failure("RAG_PROVIDER_TIMEOUT")
    except Exception:
        return _provider_failure("RAG_PROVIDER_ERROR")

    if response.exceeded_size:
        return _provider_failure("RAG_PROVIDER_INVALID_RESULT")
    if response.status_code < 200 or response.status_code >= 300:
        return _provider_failure("RAG_PROVIDER_ERROR")

    try:
        payload = json.loads(response.content.decode("utf-8"))
        return _coerce_rag_provider_payload(payload)
    except Exception:
        return _provider_failure("RAG_PROVIDER_INVALID_RESULT")
```

Implement `_post(...)` with `client.stream("POST", ..., timeout=..., json=...,
headers=...)`, `trust_env=False`, and `follow_redirects=False` on the default
client. Use:

```python
chunk_size = min(65536, self._settings.rag_http_max_response_bytes + 1)
```

and return `exceeded_size=True` immediately when accumulated bytes exceed the
limit.

Implement:

```python
def _provider_failure(code: str) -> RagRetrieveResult:
    return RagRetrieveResult(status="failed", code=_public_failure_code(code, default="RAG_PROVIDER_ERROR"))
```

Implement `_coerce_rag_provider_payload(payload)`:

```python
if isinstance(payload, dict) and "status" in payload:
    return RagRetrieveResult.model_validate(payload)
if isinstance(payload, dict) and (
    "context" in payload or "citations" in payload or "route_debug" in payload
):
    context = payload.get("context") if isinstance(payload.get("context"), str) else ""
    citations = payload.get("citations") if isinstance(payload.get("citations"), list) else []
    status = "hit" if context or citations else "empty"
    metadata = payload.get("route_debug") if isinstance(payload.get("route_debug"), dict) else {}
    return RagRetrieveResult(status=status, context=context, citations=citations, metadata=metadata)
raise ValueError("invalid RAG provider response")
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_retrieve_rag.py -q
uv run --extra dev python -m ruff check lingneng/tools/rag.py tests/lingneng/tools/test_retrieve_rag.py
uv run --extra dev ty check lingneng/tools/rag.py tests/lingneng/tools/test_retrieve_rag.py
```

Expected: pass, except pre-existing `ty` diagnostics must be noted and not
broadened.

- [ ] **Step 5: Commit and push**

```bash
git add lingneng/tools/rag.py tests/lingneng/tools/test_retrieve_rag.py
git commit -m "feat: 加固 RAG HTTP 提供方"
git push origin dev
```

## Task 14.3: Harden RAG Public Sanitization And Citation Safety

**Files:**
- Modify: `lingneng/tools/rag.py`
- Modify: `tests/lingneng/tools/test_retrieve_rag.py`
- Modify: `tests/lingneng/events/test_rag_events.py`

- [ ] **Step 1: Add failing sanitizer tests**

Append to `tests/lingneng/tools/test_retrieve_rag.py`:

```python
def test_retrieve_rag_sanitizes_percent_encoded_secret_context_and_metadata(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(
            status="hit",
            context="api%5Fkey%3Dabc123 %2FUsers%2Frotas%2Fprivate",
            citations=[],
            metadata={
                "notes": ["x-amz-signature=abc", "public retrieval summary"],
            },
        )
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    dumped = json.dumps(result, ensure_ascii=False).lower()
    assert result["context"] == ""
    assert result["metadata"]["notes"] == ["", "public retrieval summary"]
    assert "api%5fkey" not in dumped
    assert "%2fusers" not in dumped
    assert "x-amz-signature" not in dumped
```

Append:

```python
def test_retrieve_rag_sanitizes_citation_private_fields(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(
            status="hit",
            context="公共上下文",
            citations=[
                {
                    "document_id": "doc-1",
                    "source_file_name": "/Users/rotas/private/menu.pdf",
                    "section_title": "Authorization: Bearer abc123",
                    "chunk_id": "chunk-1",
                    "score": 0.9,
                    "raw_payload": "api_key=secret",
                }
            ],
            metadata={},
        )
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    dumped = json.dumps(result, ensure_ascii=False)
    assert result["citations"][0]["chunk_id"] == "chunk-1"
    assert result["citations"][0]["source_file_name"] == ""
    assert result["citations"][0]["section_title"] == ""
    assert "raw_payload" not in dumped
    assert "api_key" not in dumped
    assert "/Users/rotas" not in dumped
```

Append to `tests/lingneng/events/test_rag_events.py`:

```python
def test_rag_events_allow_benign_token_usage_and_exception_rate_text():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(
            context="token usage trend and exception rate are business metrics.",
            metadata={
                "notes": [
                    "token usage is high",
                    "exception rate changed",
                ]
            },
        ),
        include_citations=True,
        include_rag_context=True,
    )

    assert [type(event) for event in events] == [CitationDeltaEvent, RagContextEvent]
    assert events[1].context == "token usage trend and exception rate are business metrics."
    assert events[1].metadata["notes"] == [
        "token usage is high",
        "exception rate changed",
    ]
    assert citations == [CITATION]
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/tools/test_retrieve_rag.py::test_retrieve_rag_sanitizes_percent_encoded_secret_context_and_metadata \
  tests/lingneng/tools/test_retrieve_rag.py::test_retrieve_rag_sanitizes_citation_private_fields \
  tests/lingneng/events/test_rag_events.py::test_rag_events_allow_benign_token_usage_and_exception_rate_text \
  -q
```

Expected: fail because current sanitizer does not percent-decode and
over-sanitizes ordinary token/exception wording.

- [ ] **Step 3: Implement sanitizer hardening**

In `lingneng/tools/rag.py`, import:

```python
import re
from lingneng.tools.artifacts import stable_percent_decode
```

Replace broad value-deny behavior with credential-shaped checks:

```python
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
_LOCAL_ROOT_FRAGMENT_RE = re.compile(
    r"(?<![A-Za-z0-9._-])[\\/]+(?:Users|home|private|tmp|var|etc|opt|root)\b"
)
_CREDENTIAL_VALUE_RE = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer|credential|password|passwd|secret|signature|token)\s*[:=]\s*\S+|bearer\s+\S+"
)
```

Keep `_FORBIDDEN_KEY_PARTS` strict for metadata keys. Change
`_sanitize_public_text(...)` to:

```python
def _sanitize_public_text(value: str) -> str:
    clean = _CONTROL_CHAR_RE.sub("", value).strip()
    decoded, decode_stable = stable_percent_decode(clean)
    if (
        not decode_stable
        or _has_forbidden_public_text(clean)
        or _has_forbidden_public_text(decoded)
    ):
        return ""
    return clean
```

Implement `_has_forbidden_public_text(...)` so it rejects credential-shaped
values, signed URL markers, raw request/query/payload dumps, local paths, and
URLs containing credentials, but allows ordinary text like `token usage` and
`exception rate`.

Update `_sanitize_citations(...)` so citation items are rebuilt from allowed
public fields only:

```python
_PUBLIC_CITATION_FIELDS = {
    "document_id",
    "source_file_id",
    "source_file_name",
    "page_no",
    "section_title",
    "chunk_id",
    "score",
}
```

Drop unknown fields before returning citations.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/tools/test_retrieve_rag.py \
  tests/lingneng/events/test_rag_events.py \
  -q
uv run --extra dev python -m ruff check \
  lingneng/tools/rag.py \
  tests/lingneng/tools/test_retrieve_rag.py \
  tests/lingneng/events/test_rag_events.py
uv run --extra dev ty check lingneng/tools/rag.py tests/lingneng/tools/test_retrieve_rag.py
```

Expected: pass, except pre-existing `ty` diagnostics must be noted and not
broadened.

- [ ] **Step 5: Commit and push**

```bash
git add \
  lingneng/tools/rag.py \
  tests/lingneng/tools/test_retrieve_rag.py \
  tests/lingneng/events/test_rag_events.py
git commit -m "fix: 加固 RAG 公开结果清洗"
git push origin dev
```

## Task 14.4: Add Adapter Fail-Closed Guard And Live Smoke Gate

**Files:**
- Modify: `lingneng/runtime/hermes_adapter.py`
- Modify: `tests/lingneng/runtime/test_hermes_adapter_config.py`
- Create: `tests/lingneng/integration/test_rag_provider_live.py`

- [ ] **Step 1: Add failing adapter test**

Append to `tests/lingneng/runtime/test_hermes_adapter_config.py`:

```python
@pytest.mark.asyncio
async def test_hermes_adapter_rag_provider_build_failure_is_fail_closed(
    tmp_path,
    monkeypatch,
    caplog,
):
    def fail_build(settings):
        del settings
        raise RuntimeError("secret-rag-key /Users/rotas/private")

    monkeypatch.setattr(
        hermes_adapter_module,
        "_build_rag_provider",
        fail_build,
        raising=False,
    )
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(
            tmp_path,
            LINGNENG_AGENT_MODE="hermes",
            LINGNENG_RAG_ENDPOINT="https://rag.example.test/retrieve",
        ),
        agent_cls=RecordingSystemPromptAgent,
    )

    with caplog.at_level("WARNING", logger="lingneng.runtime.hermes_adapter"):
        events = [event async for event in adapter.stream(request, resolved, "run-1")]

    assert isinstance(events[-1], FinalEvent)
    assert not any(isinstance(event, ErrorEvent) for event in events)
    assert "secret-rag-key" not in caplog.text
    assert "/Users/rotas" not in caplog.text
```

- [ ] **Step 2: Add live smoke test gate**

Create `tests/lingneng/integration/test_rag_provider_live.py`:

```python
from __future__ import annotations

import json
import os

import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.tools.rag import HttpRagProvider, RagRetrieveRequest


def _live_settings() -> LingNengSettings:
    return LingNengSettings.from_env(os.environ)


def _live_enabled(settings: LingNengSettings) -> bool:
    return (
        settings.rag_live_test_enabled
        and bool(settings.rag_endpoint.strip())
        and bool(settings.rag_live_test_query.strip())
    )


def test_live_rag_provider_smoke_is_opt_in_and_secret_safe():
    settings = _live_settings()
    if not _live_enabled(settings):
        pytest.skip("Set LINGNENG_RAG_LIVE_TEST_ENABLED=true, endpoint, and query.")

    provider = HttpRagProvider(settings)
    result = provider.retrieve(
        RagRetrieveRequest(
            query=settings.rag_live_test_query,
            tenant_id="live-tenant",
            user_id="live-user",
            employee_type="marketing_content_creator",
            conversation_id="live-conversation",
            session_key="live-tenant:live-user:marketing_content_creator:live-conversation",
            request_id="live-rag-smoke",
            top_k=settings.rag_default_top_k,
            filters={},
        )
    )

    dumped = json.dumps(result.model_dump(), ensure_ascii=False)
    assert result.status in {"hit", "empty", "failed"}
    if settings.rag_api_key:
        assert settings.rag_api_key not in dumped
    assert settings.rag_live_test_query not in dumped
```

- [ ] **Step 3: Run failing adapter test**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/runtime/test_hermes_adapter_config.py::test_hermes_adapter_rag_provider_build_failure_is_fail_closed \
  -q
```

Expected: fail because `_build_rag_provider` exceptions are not caught by a
secret-safe wrapper.

- [ ] **Step 4: Implement adapter guard**

In `lingneng/runtime/hermes_adapter.py`, replace the direct context provider
build with a guarded helper:

```python
def _safe_build_rag_provider(settings: LingNengSettings) -> HttpRagProvider | None:
    try:
        return _build_rag_provider(settings)
    except Exception:
        _LOGGER.warning("LingNeng RAG provider construction failed; provider disabled.")
        return None
```

Use:

```python
provider=_safe_build_rag_provider(self.settings)
```

inside `rag_request_context(...)`.

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/runtime/test_hermes_adapter_config.py \
  tests/lingneng/integration/test_rag_provider_live.py \
  -q
uv run --extra dev python -m ruff check \
  lingneng/runtime/hermes_adapter.py \
  tests/lingneng/runtime/test_hermes_adapter_config.py \
  tests/lingneng/integration/test_rag_provider_live.py
```

Expected: adapter tests pass and the live smoke test is skipped unless the env
gate is enabled.

- [ ] **Step 6: Commit and push**

```bash
git add \
  lingneng/runtime/hermes_adapter.py \
  tests/lingneng/runtime/test_hermes_adapter_config.py \
  tests/lingneng/integration/test_rag_provider_live.py
git commit -m "feat: 增加 RAG 集成安全门"
git push origin dev
```

## Task 14.5: Final Phase 14 Verification And Boundary Scan

**Files:**
- No intended runtime changes unless verification reveals a regression.

- [ ] **Step 1: Run focused Phase 14 suite**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/config/test_settings.py \
  tests/lingneng/tools/test_retrieve_rag.py \
  tests/lingneng/events/test_rag_events.py \
  tests/lingneng/runtime/test_hermes_adapter_config.py \
  tests/lingneng/integration/test_rag_provider_live.py \
  -q
```

Expected: pass, with the live smoke test skipped unless explicitly enabled.

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
failing command, then rerun all commands in this task before marking Phase 14
complete. Commit with:

```bash
git commit -m "fix: 修正 RAG 加固阶段回归"
git push origin dev
```

## Rollback Notes

Phase 14 remains additive and fail-closed:

- Clear `LINGNENG_RAG_ENDPOINT` to disable external RAG query.
- If the HTTP provider returns invalid data, times out, or exceeds response
  limits, `retrieve_rag` returns a public failed tool result and the chat stream
  continues.
- Revert Phase 14 commits without affecting attachments, generation tools,
  routing/handoff, skills, SessionDB, or the Java stream endpoint.

## Plan Self-Review

- Spec coverage: settings/failure codes are in Task 14.1, streaming HTTP and
  old response normalization in Task 14.2, public sanitization and citations in
  Task 14.3, adapter/live-test gates in Task 14.4, and final verification in
  Task 14.5.
- Scope check: no task imports old `app.*`, migrates training ingestion,
  implements vector search/embedding/reranking, changes Java, or adds deployment
  work.
- Safety check: timeout, non-2xx, oversized response, invalid JSON/schema,
  secrets, signed URLs, local paths, request payloads, citations, metadata, and
  live tests all have explicit tests or gates.
- Type consistency: new settings names, public failure code, helper names, and
  response shapes are consistent across tasks.
