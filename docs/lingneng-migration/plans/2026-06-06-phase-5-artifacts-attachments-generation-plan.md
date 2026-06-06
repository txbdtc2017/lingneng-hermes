# Phase 5 Artifacts, Attachments, And Business Generation Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 5 from `docs/lingneng-migration/specs/2026-06-06-phase-5-artifacts-attachments-generation-spec.md`: Java-compatible artifacts, artifact streaming, document/image/chart/web generation tools, request-scoped attachment context, and final artifact replay.

**Architecture:** Keep Phase 5 business behavior inside `lingneng/`. Artifact models are shared by SSE events, tool results, and run-store replay. Generation and attachment capabilities use provider protocols/context injection so tests are deterministic and no live Java/AIGC/search/parser service is required.

**Tech Stack:** Python 3.11-3.13, Pydantic v2, FastAPI SSE, SQLite, Hermes tool registry, pytest, uv, ruff.

---

## Approved Spec

This plan implements:

```text
docs/lingneng-migration/specs/2026-06-06-phase-5-artifacts-attachments-generation-spec.md
```

The master migration sequence remains:

```text
phase spec -> phase plan -> subagent-driven execution
```

## Locked Decisions

- Work on branch `dev`.
- Do not use git worktrees.
- Do not modify `/Users/rotas/Documents/work/hailun/LingNengAI`; use it only as reference.
- Do not implement Docker, compose, deployment scripts, rollback scripts, or GitHub Actions in Phase 5.
- Do not modify Java code or require Java request changes.
- Do not expose Hermes terminal, filesystem, browser automation, code execution, delegation, cross-channel messaging, Kanban, or unrelated default tools.
- `chart_visualization` returns image artifacts with `source == "chart_visualization"`.
- `web_search` is a controlled LingNeng provider-backed tool, not Hermes browser automation.
- Attachment context is scoped to the current request only and is not persisted as durable session memory.
- Commit messages are Chinese conventional-prefix style.
- Push only after the task verification commands pass.

## File Map

Create:

- `lingneng/tools/artifacts.py`: artifact validation, URL/object-key sanitization, artifact dedupe, public tool result helpers.
- `lingneng/tools/document_generation.py`: document provider protocol, request/result models, handler.
- `lingneng/tools/image_generation.py`: image provider protocol, request/result models, count clamp, handler.
- `lingneng/tools/chart_visualization.py`: chart provider protocol or image-provider delegation, handler.
- `lingneng/tools/web_search.py`: controlled web search provider protocol, result normalizer, handler.
- `lingneng/tools/attachments.py`: attachment context models, provider protocol, host/size/timeout checks, prompt fragment builder.
- `tests/lingneng/tools/test_artifact_models.py`
- `tests/lingneng/tools/test_generation_tools.py`
- `tests/lingneng/tools/test_attachments.py`
- `tests/lingneng/events/test_artifact_events.py`
- `tests/lingneng/contract/test_artifact_chat_stream.py`

Modify:

- `lingneng/config/settings.py`: Phase 5 settings and readiness summary.
- `tests/lingneng/config/test_settings.py`: Phase 5 setting defaults/parsing/summary tests.
- `lingneng/schemas/chat_events.py`: `Artifact`, `ArtifactCreatedEvent`, typed `FinalEvent.artifacts`.
- `tests/lingneng/schemas/test_chat_event_schema.py`: artifact event model tests.
- `lingneng/events/bridge.py`: artifact extraction, dedupe, `final_answer(..., artifacts=...)`.
- `lingneng/runtime/agent_adapter.py`: stream union includes `ArtifactCreatedEvent`.
- `lingneng/runtime/hermes_adapter.py`: attachment context injection, artifact event emission, final artifact accumulation.
- `lingneng/api/routes.py`: event name routing for `artifact_created`, final artifact persistence/replay.
- `lingneng/session/run_store.py`: validate/sanitize stored artifacts without changing the existing `artifacts_json` column.
- `tests/lingneng/api/test_chat_stream_idempotency.py`: replay final artifacts with typed artifacts.
- `tests/lingneng/runtime/test_hermes_answer_stream.py`: artifact stream order and attachment context tests.
- `lingneng/tools/stubs.py`: include controlled `web_search`; exclude Phase 5 real tools from stubs.
- `lingneng/tools/toolset.py`: register real Phase 5 handlers.
- `tests/lingneng/tools/test_toolset_policy.py`: approved tool list and real/stub boundary updates.

## Task 5.1: Add Phase 5 Settings And Artifact Models

**Files:**

- Create: `lingneng/tools/artifacts.py`
- Create: `tests/lingneng/tools/test_artifact_models.py`
- Modify: `lingneng/config/settings.py`
- Modify: `tests/lingneng/config/test_settings.py`
- Modify: `lingneng/schemas/chat_events.py`
- Modify: `tests/lingneng/schemas/test_chat_event_schema.py`

- [ ] **Step 1: Write failing settings tests**

Add tests to `tests/lingneng/config/test_settings.py`:

```python
def test_phase_5_artifact_generation_and_attachment_settings_defaults(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_INTERNAL_API_KEY": "key",
        }
    )

    assert settings.artifact_public_base_url == ""
    assert settings.artifact_url_allowed_hosts == []
    assert settings.tool_result_max_chars == 6000
    assert settings.document_max_content_chars == 20000
    assert settings.image_max_count == 4
    assert settings.generation_timeout_seconds == 300.0
    assert settings.web_search_default_top_k == 5
    assert settings.web_search_max_top_k == 10
    assert settings.attachment_allowed_hosts == []
    assert settings.attachment_max_files == 5
    assert settings.attachment_max_total_bytes == 52428800
    assert settings.attachment_max_file_bytes == 20971520
    assert settings.attachment_max_image_bytes == 10485760
    assert settings.attachment_timeout_seconds == 30.0
    assert settings.attachment_context_max_chars == 6000
```

Add parsing/summary tests:

```python
def test_phase_5_string_list_settings_parse_json_comma_and_newline(tmp_path):
    first = "files.example.test"
    second = "cdn.example.test"

    json_settings = LingNengSettings.from_env(
        {"LINGNENG_ARTIFACT_URL_ALLOWED_HOSTS": f'["{first}", "{second}"]'}
    )
    comma_settings = LingNengSettings.from_env(
        {"LINGNENG_ATTACHMENT_ALLOWED_HOSTS": f"{first},{second}"}
    )
    newline_settings = LingNengSettings.from_env(
        {"LINGNENG_ATTACHMENT_ALLOWED_HOSTS": f"{first}\n{second}"}
    )

    assert json_settings.artifact_url_allowed_hosts == [first, second]
    assert comma_settings.attachment_allowed_hosts == [first, second]
    assert newline_settings.attachment_allowed_hosts == [first, second]


def test_ready_summary_reports_phase_5_non_secret_counts(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_INTERNAL_API_KEY": "key",
            "LINGNENG_ARTIFACT_URL_ALLOWED_HOSTS": "files.example.test",
            "LINGNENG_ATTACHMENT_ALLOWED_HOSTS": "files.example.test,cdn.example.test",
        }
    )

    summary = settings.ready_summary()

    assert summary["artifact_url_allow_list_count"] == 1
    assert summary["attachment_host_allow_list_count"] == 2
    assert "api_key" not in summary
    assert "secret" not in repr(summary).lower()
```

- [ ] **Step 2: Write failing artifact schema/event tests**

Add to `tests/lingneng/schemas/test_chat_event_schema.py`:

```python
from lingneng.schemas.chat_events import Artifact, ArtifactCreatedEvent


def test_artifact_event_payloads_dump_without_event_field():
    artifact = Artifact(
        artifact_id="artifact-doc-1",
        artifact_type="document",
        source="document_generation",
        file_name="report.pdf",
        mime_type="application/pdf",
        url="https://files.example.test/report.pdf",
        object_key="external/java-agent-file/artifact-doc-1",
        format="pdf",
        target_format="pdf",
        conversion_required=False,
        conversion_owner=None,
    )
    event = ArtifactCreatedEvent.model_validate(artifact.model_dump())
    final = FinalEvent(
        run_id="run-1",
        status="succeeded",
        answer="完成",
        artifacts=[artifact],
    )

    assert event.artifact_id == "artifact-doc-1"
    assert event.model_dump()["artifact_type"] == "document"
    assert final.model_dump()["artifacts"][0]["artifact_id"] == "artifact-doc-1"
    assert "event" not in event.model_dump()
    assert "event" not in final.model_dump()
```

- [ ] **Step 3: Write failing artifact helper tests**

Create `tests/lingneng/tools/test_artifact_models.py`:

```python
import json

from pydantic import ValidationError

from lingneng.schemas.chat_events import Artifact
from lingneng.tools.artifacts import (
    artifact_from_public_dict,
    dedupe_artifacts,
    sanitize_artifact_public_dict,
)


ARTIFACT = {
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


def test_artifact_from_public_dict_accepts_java_fields():
    artifact = artifact_from_public_dict(ARTIFACT)

    assert isinstance(artifact, Artifact)
    assert artifact.artifact_id == "artifact-doc-1"
    assert artifact.object_key == "external/java-agent-file/artifact-doc-1"


def test_artifact_rejects_local_paths_and_secret_urls():
    unsafe = {
        **ARTIFACT,
        "url": "file:///Users/rotas/secret.pdf",
        "object_key": "/Users/rotas/secret.pdf",
    }

    sanitized = sanitize_artifact_public_dict(unsafe)

    dumped = json.dumps(sanitized, ensure_ascii=False)
    assert "file://" not in dumped
    assert "/Users/rotas" not in dumped
    with pytest.raises(ValidationError):
        artifact_from_public_dict(sanitized)


def test_dedupe_artifacts_by_artifact_id_preserves_first_seen():
    duplicate = {**ARTIFACT, "file_name": "duplicate.pdf"}
    second = {**ARTIFACT, "artifact_id": "artifact-img-1", "artifact_type": "image"}

    assert dedupe_artifacts([ARTIFACT, duplicate, second]) == [ARTIFACT, second]
```

Ensure the test imports `pytest`.

- [ ] **Step 4: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/config/test_settings.py tests/lingneng/schemas/test_chat_event_schema.py tests/lingneng/tools/test_artifact_models.py -q
```

Expected: fail because Phase 5 settings, artifact event models, and artifact
helper module do not exist.

- [ ] **Step 5: Implement settings**

In `lingneng/config/settings.py`:

- Add a `_str_list_from_env(value: str | None) -> list[str]` helper mirroring
  the existing path-list parsing style.
- Add the Phase 5 settings from the spec with minimum bounds.
- Add non-secret summary keys:
  - `artifact_url_allow_list_count`
  - `attachment_host_allow_list_count`
  - `web_search_configured` if a provider endpoint/key setting is added in the
    implementation.

- [ ] **Step 6: Implement artifact models**

In `lingneng/schemas/chat_events.py`:

```python
ArtifactType = Literal["image", "document"]


class Artifact(LingNengEventModel):
    artifact_id: str
    artifact_type: ArtifactType
    source: str
    file_name: str
    mime_type: str
    url: str
    object_key: str
    format: str | None = None
    target_format: str | None = None
    conversion_required: bool = False
    conversion_owner: str | None = None


class ArtifactCreatedEvent(Artifact):
    pass


class FinalEvent(LingNengEventModel):
    ...
    artifacts: list[Artifact] = Field(default_factory=list)
```

Keep existing `FinalEvent.citations` behavior unchanged.

- [ ] **Step 7: Implement artifact helpers**

In `lingneng/tools/artifacts.py`, implement:

```python
def artifact_from_public_dict(value: dict[str, Any]) -> Artifact: ...
def sanitize_artifact_public_dict(value: dict[str, Any]) -> dict[str, Any]: ...
def dedupe_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
```

Rules:

- Only HTTP/HTTPS URLs are public by default.
- `local://`, `file://`, absolute paths, path traversal object keys, control
  characters, and secret-shaped query strings are stripped or rejected.
- Preserve Java external object keys like
  `external/java-agent-file/artifact-doc-1`.
- Dedupe by non-empty `artifact_id`.

- [ ] **Step 8: Run task tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/config/test_settings.py tests/lingneng/schemas/test_chat_event_schema.py tests/lingneng/tools/test_artifact_models.py -q
uv run --extra dev python -m ruff check lingneng/config lingneng/schemas lingneng/tools/artifacts.py tests/lingneng/config tests/lingneng/schemas tests/lingneng/tools/test_artifact_models.py
```

Expected: pass.

- [ ] **Step 9: Commit and push**

Run:

```bash
git add lingneng/config/settings.py lingneng/schemas/chat_events.py lingneng/tools/artifacts.py tests/lingneng/config/test_settings.py tests/lingneng/schemas/test_chat_event_schema.py tests/lingneng/tools/test_artifact_models.py
git commit -m "feat: 增加灵能生成物模型"
git push origin dev
```

## Task 5.2: Bridge Artifact Events And Persist Final Artifacts

**Files:**

- Create: `tests/lingneng/events/test_artifact_events.py`
- Modify: `lingneng/events/bridge.py`
- Modify: `lingneng/runtime/agent_adapter.py`
- Modify: `lingneng/runtime/hermes_adapter.py`
- Modify: `lingneng/api/routes.py`
- Modify: `lingneng/session/run_store.py`
- Modify: `tests/lingneng/api/test_chat_stream_idempotency.py`
- Modify: `tests/lingneng/runtime/test_hermes_answer_stream.py`

- [ ] **Step 1: Write failing bridge tests**

Create `tests/lingneng/events/test_artifact_events.py`:

```python
import json

from lingneng.events.bridge import (
    artifact_events_from_tool_result,
    dedupe_artifacts,
    final_answer,
)
from lingneng.schemas.chat_events import ArtifactCreatedEvent, FinalEvent


ARTIFACT = {
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


def result_payload(**overrides):
    payload = {
        "success": True,
        "tool_name": "document_generation",
        "status": "succeeded",
        "summary": "PDF 文档生成完成",
        "safe_output": {"artifact_count": 1},
        "artifacts": [ARTIFACT],
        "metadata": {},
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def test_artifact_tool_result_emits_artifact_created():
    events, artifacts = artifact_events_from_tool_result(
        tool_name="document_generation",
        result=result_payload(),
    )

    assert [type(event) for event in events] == [ArtifactCreatedEvent]
    assert events[0].artifact_id == "artifact-doc-1"
    assert artifacts == [ARTIFACT]


def test_non_artifact_tool_result_is_ignored():
    events, artifacts = artifact_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(tool_name="retrieve_rag"),
    )

    assert events == []
    assert artifacts == []


def test_invalid_artifacts_are_ignored():
    events, artifacts = artifact_events_from_tool_result(
        tool_name="document_generation",
        result=result_payload(artifacts=[ARTIFACT, {**ARTIFACT, "url": "file:///tmp/a"}]),
    )

    assert len(events) == 1
    assert artifacts == [ARTIFACT]


def test_dedupe_artifacts_by_artifact_id():
    duplicate = {**ARTIFACT, "file_name": "duplicate.pdf"}
    second = {**ARTIFACT, "artifact_id": "artifact-img-1", "artifact_type": "image"}

    assert dedupe_artifacts([ARTIFACT, duplicate, second]) == [ARTIFACT, second]


def test_final_answer_accepts_artifacts():
    event = final_answer(run_id="run-1", answer="完成", artifacts=[ARTIFACT])

    assert isinstance(event, FinalEvent)
    assert event.model_dump()["artifacts"] == [ARTIFACT]
```

- [ ] **Step 2: Write failing route replay test**

Add to `tests/lingneng/api/test_chat_stream_idempotency.py`:

```python
class CountingArtifactSuccessAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def stream(self, request, resolved_session, run_id):
        self.calls += 1
        yield RunStartedEvent(run_id=run_id, request_id=request.request_id)
        yield AnswerDeltaEvent(text="完成", sequence=1)
        yield FinalEvent(
            run_id=run_id,
            status="succeeded",
            answer="完成",
            artifacts=[ARTIFACT],
        )


def test_repeated_success_replays_final_artifacts(tmp_path):
    adapter = CountingArtifactSuccessAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    app = create_app(settings=settings(tmp_path), adapter=adapter, run_store=store)
    client = TestClient(app)

    first = post(client, full_payload())
    second = post(client, full_payload())
    frames = parse_sse(second.text)

    assert first.status_code == 200
    assert second.status_code == 200
    assert frames[-1][1]["artifacts"][0]["artifact_id"] == "artifact-doc-1"
    assert adapter.calls == 1
```

Define `ARTIFACT` in the test module or import a local helper.

- [ ] **Step 3: Write failing Hermes adapter artifact stream test**

Add to `tests/lingneng/runtime/test_hermes_answer_stream.py`:

```python
class ArtifactToolProgressAgent:
    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")
        self.tool_progress_callback = kwargs.get("tool_progress_callback")

    def run_conversation(self, *args, **kwargs):
        self.tool_progress_callback("tool.started", "document_generation", None, {})
        self.tool_progress_callback(
            "tool.completed",
            "document_generation",
            None,
            None,
            duration=0.01,
            is_error=False,
            result=json.dumps({
                "success": True,
                "tool_name": "document_generation",
                "status": "succeeded",
                "summary": "完成",
                "safe_output": {"artifact_count": 1},
                "artifacts": [ARTIFACT],
                "metadata": {},
            }, ensure_ascii=False),
        )
        self.stream_delta_callback("完成")
        return {"final_response": "完成", "messages": []}


@pytest.mark.asyncio
async def test_artifact_tool_completion_emits_artifact_before_answer(tmp_path):
    request, resolved = request_and_session()
    adapter = HermesAgentRunAdapter(settings(tmp_path), agent_cls=ArtifactToolProgressAgent)

    events = [event async for event in adapter.stream(request, resolved, "run-1")]
    names = [type(event).__name__ for event in events]
    completed_index = next(
        index
        for index, event in enumerate(events)
        if isinstance(event, AgentStepEvent) and event.status == "succeeded"
    )
    artifact_index = names.index("ArtifactCreatedEvent")
    answer_index = names.index("AnswerDeltaEvent")
    final = events[-1]

    assert completed_index < artifact_index < answer_index
    assert final.artifacts[0].artifact_id == "artifact-doc-1"
```

- [ ] **Step 4: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/events/test_artifact_events.py tests/lingneng/api/test_chat_stream_idempotency.py tests/lingneng/runtime/test_hermes_answer_stream.py -q
```

Expected: fail because artifact bridge/event routing is not implemented.

- [ ] **Step 5: Implement bridge and adapter changes**

In `lingneng/events/bridge.py`:

- Import `Artifact`, `ArtifactCreatedEvent`.
- Add `artifact_events_from_tool_result(...)`.
- Use artifact helper validation and ignore invalid artifacts.
- Add `dedupe_artifacts(...)` or re-export from `lingneng.tools.artifacts`.
- Extend `final_answer(run_id, answer, citations=None, artifacts=None)`.

In `lingneng/runtime/hermes_adapter.py`:

- Add `artifacts: list[dict[str, Any]] = []`.
- In `on_tool_progress`, after `agent_step_completed`, call
  `artifact_events_from_tool_result(...)`.
- Under `tool_progress_lock`, dedupe accumulated artifacts by `artifact_id`.
- Enqueue artifact events immediately after the completed `agent_step`.
- Pass artifacts into final answer.

- [ ] **Step 6: Implement route and run-store compatibility**

In `lingneng/runtime/agent_adapter.py`, include `ArtifactCreatedEvent` in
`LingNengStreamEvent`.

In `lingneng/api/routes.py`:

- `_event_name()` maps `ArtifactCreatedEvent` to `artifact_created`.
- `mark_succeeded()` continues to persist final artifacts.
- Replay uses typed/sanitized artifacts.

In `lingneng/session/run_store.py`:

- Keep the existing `artifacts_json` column.
- Ensure `mark_succeeded()` serializes Pydantic artifacts and dict artifacts.
- Ensure `_record_from_row()` returns only valid public artifact dicts.
- Invalid stored artifact records degrade to an empty artifact list.

- [ ] **Step 7: Run task tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/events/test_artifact_events.py tests/lingneng/api/test_chat_stream_idempotency.py tests/lingneng/runtime/test_hermes_answer_stream.py tests/lingneng/session/test_run_store.py -q
uv run --extra dev python -m ruff check lingneng/events lingneng/runtime lingneng/api lingneng/session tests/lingneng/events tests/lingneng/api tests/lingneng/runtime tests/lingneng/session
```

Expected: pass.

- [ ] **Step 8: Commit and push**

Run:

```bash
git add lingneng/events/bridge.py lingneng/runtime/agent_adapter.py lingneng/runtime/hermes_adapter.py lingneng/api/routes.py lingneng/session/run_store.py tests/lingneng/events/test_artifact_events.py tests/lingneng/api/test_chat_stream_idempotency.py tests/lingneng/runtime/test_hermes_answer_stream.py
git commit -m "feat: 增加灵能生成物事件"
git push origin dev
```

## Task 5.3: Implement Generation And Web Search Tool Handlers

**Files:**

- Create: `lingneng/tools/document_generation.py`
- Create: `lingneng/tools/image_generation.py`
- Create: `lingneng/tools/chart_visualization.py`
- Create: `lingneng/tools/web_search.py`
- Modify: `lingneng/tools/stubs.py`
- Modify: `lingneng/tools/toolset.py`
- Modify: `tests/lingneng/tools/test_toolset_policy.py`
- Test: `tests/lingneng/tools/test_generation_tools.py`

- [ ] **Step 1: Write failing generation tool tests**

Create `tests/lingneng/tools/test_generation_tools.py` with fake providers:

```python
import json

from lingneng.config.settings import LingNengSettings
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
from lingneng.tools.chart_visualization import chart_visualization_context, chart_visualization_handler
from lingneng.tools.web_search import WebSearchResult, web_search_context, web_search_handler


ARTIFACT = {
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


class FakeDocumentProvider:
    def generate(self, request):
        self.request = request
        return DocumentGenerationResult(summary="PDF 文档生成完成", artifacts=[ARTIFACT])


def settings(tmp_path):
    return LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_IMAGE_MAX_COUNT": "2",
            "LINGNENG_WEB_SEARCH_MAX_TOP_K": "3",
        }
    )


def test_document_generation_returns_artifact_metadata(tmp_path):
    provider = FakeDocumentProvider()

    with document_generation_context(settings(tmp_path), provider=provider):
        result = json.loads(document_generation_handler({"title": "报告", "content": "正文"}))

    assert result["success"] is True
    assert result["tool_name"] == "document_generation"
    assert result["artifacts"][0]["artifact_id"] == "artifact-doc-1"
    assert provider.request.title == "报告"
    assert "正文" not in json.dumps(result["safe_output"], ensure_ascii=False)
```

Add equivalent tests for:

- `image_generation_handler` clamps count to `settings.image_max_count`.
- `chart_visualization_handler` returns image artifacts with
  `source == "chart_visualization"`.
- `web_search_handler` clamps `top_k`, rejects URLs with credentials, and
  returns normalized public sources only.
- Provider exception returns `success=false`, public code, and no traceback or
  secret text.
- Missing provider returns `NOT_CONFIGURED`.

- [ ] **Step 2: Update toolset policy failing tests**

In `tests/lingneng/tools/test_toolset_policy.py`:

- Add `web_search` to `APPROVED_LINGNENG_TOOLS`.
- Define real tools:

```python
REAL_PHASE_5_TOOLS = {
    "retrieve_rag",
    "document_generation",
    "image_generation",
    "chart_visualization",
    "web_search",
}
STUB_ONLY_TOOLS = APPROVED_LINGNENG_TOOLS - REAL_PHASE_5_TOOLS
```

- Add assertions that Phase 5 real handlers do not return
  `phase == "phase_3_stub"` under missing provider context.
- Keep disallowed Hermes browser/terminal/code tools excluded.

- [ ] **Step 3: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_generation_tools.py tests/lingneng/tools/test_toolset_policy.py -q
```

Expected: fail because Phase 5 tool modules and `web_search` registration do not
exist.

- [ ] **Step 4: Implement document generation handler**

In `lingneng/tools/document_generation.py`:

- Define `DocumentGenerationRequest`, `DocumentGenerationResult`,
  `DocumentGenerationProvider`.
- Add `document_generation_context(settings, provider=None)`.
- Build request from `title`, `instruction`, `content`, and `format`.
- Truncate document content to `settings.document_max_content_chars`.
- On success, return stable public JSON with `artifacts`.
- On missing provider, return `NOT_CONFIGURED`.
- On provider error, return `DOCUMENT_GENERATION_PROVIDER_ERROR` without raw
  exception text.

- [ ] **Step 5: Implement image and chart handlers**

In `lingneng/tools/image_generation.py`:

- Define request/result/provider models.
- Clamp count to `settings.image_max_count`.
- Return partial success if provider returns some artifacts.
- Return safe failure if zero artifacts or provider error.

In `lingneng/tools/chart_visualization.py`:

- Define request/result/provider models.
- Ensure artifacts have `artifact_type == "image"` and
  `source == "chart_visualization"`.
- Sanitize data summary and reject raw secret-like metadata.

- [ ] **Step 6: Implement controlled web search handler**

In `lingneng/tools/web_search.py`:

- Define `WebSearchRequest`, `WebSearchResult`, `WebSearchProvider`.
- Clamp top_k to settings.
- Normalize provider result into public web sources.
- Drop URLs with non-http schemes, username/password, control characters, or
  whitespace in authority.
- Return `WEB_SEARCH_PROVIDER_ERROR` on provider error without raw exception
  text.

- [ ] **Step 7: Register real handlers**

In `lingneng/tools/stubs.py`:

- Add `web_search` to `LINGNENG_TOOL_NAMES`.
- Exclude the Phase 5 real tools from `STUB_TOOL_NAMES`.
- Add/update `TOOL_SCHEMAS["web_search"]` with `query`, `top_k`,
  `recency_filter`, and `site_filter`.

In `lingneng/tools/toolset.py`:

- Register handlers for `document_generation`, `image_generation`,
  `chart_visualization`, and `web_search`.
- Keep remaining tools registered as stubs.

- [ ] **Step 8: Run task tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_generation_tools.py tests/lingneng/tools/test_toolset_policy.py tests/lingneng/tools/test_artifact_models.py -q
uv run --extra dev python -m ruff check lingneng/tools tests/lingneng/tools
```

Expected: pass.

- [ ] **Step 9: Commit and push**

Run:

```bash
git add lingneng/tools/document_generation.py lingneng/tools/image_generation.py lingneng/tools/chart_visualization.py lingneng/tools/web_search.py lingneng/tools/stubs.py lingneng/tools/toolset.py tests/lingneng/tools/test_generation_tools.py tests/lingneng/tools/test_toolset_policy.py
git commit -m "feat: 接入灵能生成与搜索工具"
git push origin dev
```

## Task 5.4: Implement Request-Scoped Attachment Context

**Files:**

- Create: `lingneng/tools/attachments.py`
- Create: `tests/lingneng/tools/test_attachments.py`
- Modify: `lingneng/runtime/hermes_adapter.py`
- Modify: `tests/lingneng/runtime/test_hermes_adapter_config.py`

- [ ] **Step 1: Write failing attachment tests**

Create `tests/lingneng/tools/test_attachments.py`:

```python
import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.tools.attachments import (
    AttachmentProcessingResult,
    attachment_processing_context,
    build_attachment_prompt_context,
)
from tests.lingneng.schemas.test_chat_request_schema import full_payload


class FakeAttachmentProvider:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def process(self, request):
        self.requests.append(request)
        return self.result


def settings(tmp_path, **overrides):
    env = {
        "LINGNENG_RUNTIME_DIR": str(tmp_path),
        "LINGNENG_ATTACHMENT_ALLOWED_HOSTS": "files.example.test",
        "LINGNENG_ATTACHMENT_MAX_FILES": "2",
        "LINGNENG_ATTACHMENT_MAX_TOTAL_BYTES": "1000",
        "LINGNENG_ATTACHMENT_MAX_FILE_BYTES": "800",
        "LINGNENG_ATTACHMENT_CONTEXT_MAX_CHARS": "120",
    }
    env.update(overrides)
    return LingNengSettings.from_env(env)


def request_with_attachment(**overrides):
    payload = full_payload()
    attachment = {
        "file_id": "file-1",
        "file_name": "menu.pdf",
        "mime_type": "application/pdf",
        "size": 100,
        "download_url": "https://files.example.test/menu.pdf",
        "usage": "session_context",
    }
    attachment.update(overrides)
    payload["attachments"] = [attachment]
    return ChatStreamRequest.model_validate(payload)


def test_attachment_context_uses_current_request_only(tmp_path):
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(
            context_text="当前附件摘要",
            processed_count=1,
            failed_count=0,
            selected_count=1,
        )
    )

    with attachment_processing_context(provider=provider):
        result = build_attachment_prompt_context(settings(tmp_path), request_with_attachment())

    assert "当前附件摘要" in result.prompt_text
    assert provider.requests[0].attachments[0].file_id == "file-1"


def test_attachment_rejects_unallowed_host(tmp_path):
    with attachment_processing_context(provider=FakeAttachmentProvider(None)):
        result = build_attachment_prompt_context(
            settings(tmp_path),
            request_with_attachment(download_url="https://evil.example.test/menu.pdf"),
        )

    assert result.prompt_text == ""
    assert any(warning.code == "ATTACHMENT_HOST_NOT_ALLOWED" for warning in result.warnings)
```

Add tests for:

- file count limit.
- total bytes and per-file bytes limits.
- image byte limit for image suffix/mime type.
- timeout/provider exception safe degradation.
- context truncation to `attachment_context_max_chars`.
- no Java `history` content appears in attachment context.

- [ ] **Step 2: Write failing Hermes adapter prompt test**

Add to `tests/lingneng/runtime/test_hermes_adapter_config.py`:

```python
def test_attachment_context_is_added_to_current_system_prompt_only(tmp_path, monkeypatch):
    request = ChatStreamRequest.model_validate(full_payload())
    payload = full_payload()
    payload["attachments"] = [{
        "file_id": "file-1",
        "file_name": "menu.pdf",
        "mime_type": "application/pdf",
        "size": 100,
        "download_url": "https://files.example.test/menu.pdf",
    }]
    request = ChatStreamRequest.model_validate(payload)
    adapter = HermesAgentRunAdapter(settings(tmp_path), agent_cls=PromptCaptureAgent)
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(context_text="当前附件摘要", processed_count=1)
    )

    with attachment_processing_context(provider=provider):
        events = [event async for event in adapter.stream(request, resolve_session_key(request), "run-1")]

    assert "当前附件摘要" in PromptCaptureAgent.system_message_seen
    assert "history content marker" not in PromptCaptureAgent.system_message_seen
```

Use existing fake agent patterns in the file and keep the test syntax valid.

- [ ] **Step 3: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_attachments.py tests/lingneng/runtime/test_hermes_adapter_config.py -q
```

Expected: fail because attachment module and adapter integration do not exist.

- [ ] **Step 4: Implement attachment module**

In `lingneng/tools/attachments.py`:

- Define `AttachmentProcessingRequest`, `AttachmentProcessingResult`,
  `AttachmentWarning`, `AttachmentPromptContext`, and provider protocol.
- Add `attachment_processing_context(provider=None)`.
- Validate attachment count/size/host before invoking provider.
- Build bounded prompt section:

```text
## LingNeng Current Request Attachments

<bounded provider context>
```

- On disabled/missing provider, return empty prompt plus public warning.
- On provider exception/timeout-like result, return safe warning and no raw
  exception text.

- [ ] **Step 5: Wire attachment context into Hermes adapter**

In `lingneng/runtime/hermes_adapter.py`:

- Build attachment prompt context before `_build_system_message()` or pass it
  into `_compose_system_message()`.
- Add the attachment prompt after skill prompt and before minimal RAG guidance.
- Do not append attachment context to SessionDB or Java history.
- Emit `agent_step` progress for attachment started/completed/failed/skipped by
  reusing public `agent_step_*` helpers with tool name `attachment_processing`.

- [ ] **Step 6: Run task tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_attachments.py tests/lingneng/runtime/test_hermes_adapter_config.py tests/lingneng/runtime/test_hermes_answer_stream.py -q
uv run --extra dev python -m ruff check lingneng/tools/attachments.py lingneng/runtime tests/lingneng/tools/test_attachments.py tests/lingneng/runtime
```

Expected: pass.

- [ ] **Step 7: Commit and push**

Run:

```bash
git add lingneng/tools/attachments.py lingneng/runtime/hermes_adapter.py tests/lingneng/tools/test_attachments.py tests/lingneng/runtime/test_hermes_adapter_config.py
git commit -m "feat: 增加灵能附件理解"
git push origin dev
```

## Task 5.5: Add Artifact Stream Contract And Full Phase Verification

**Files:**

- Create: `tests/lingneng/contract/test_artifact_chat_stream.py`
- Modify if needed: `tests/lingneng/contract/test_rag_skill_chat_stream.py`

- [ ] **Step 1: Write artifact stream contract test**

Create `tests/lingneng/contract/test_artifact_chat_stream.py`:

```python
import json

from fastapi.testclient import TestClient

from lingneng.api.app import create_app
from lingneng.config.settings import LingNengSettings
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.session.run_store import LingNengRunStore
from tests.lingneng.api.test_chat_stream_contract import parse_sse
from tests.lingneng.schemas.test_chat_request_schema import full_payload
from tools.registry import registry


INTERNAL_KEY = "key"
ARTIFACT = {
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


class FakeDocumentProvider:
    def generate(self, request):
        return type("Result", (), {"summary": "PDF 文档生成完成", "artifacts": [ARTIFACT], "safe_output": {"artifact_count": 1}})()


class ContractArtifactAgent:
    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")
        self.tool_progress_callback = kwargs.get("tool_progress_callback")

    def run_conversation(self, *args, **kwargs):
        self.tool_progress_callback("tool.started", "document_generation", None, {})
        result = registry.dispatch("document_generation", {"title": "报告", "content": "正文"})
        self.tool_progress_callback(
            "tool.completed",
            "document_generation",
            None,
            None,
            duration=0.01,
            is_error=False,
            result=result,
        )
        self.stream_delta_callback("文档已生成。")
        return {"final_response": "文档已生成。", "messages": []}
```

Complete the test with:

- Provider monkeypatch/context for `document_generation`.
- `create_app(...)` with `LingNengRunStore`.
- Assert response 200 and SSE content type.
- Assert order:
  `run_started`, `agent_step` started, `agent_step` completed,
  `artifact_created`, `answer_delta`, `final`.
- Assert `final.artifacts[0].artifact_id == artifact_created.artifact_id`.
- Repeat the same request and assert replay emits `run_started`, `answer_delta`,
  `final` with the same final artifact.

- [ ] **Step 2: Run contract test**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/contract/test_artifact_chat_stream.py -q
```

Expected: pass after Tasks 5.1 through 5.4.

- [ ] **Step 3: Run Phase 5 verification suite**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_artifact_models.py tests/lingneng/tools/test_generation_tools.py tests/lingneng/tools/test_attachments.py tests/lingneng/events/test_artifact_events.py tests/lingneng/contract/test_artifact_chat_stream.py -q
```

Expected: pass.

- [ ] **Step 4: Run full LingNeng regression**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng -q
uv run --extra dev python -m ruff check lingneng tests/lingneng
/Users/rotas/Documents/work/hailun/LingNengAI/.venv/bin/python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_tool_artifact_events.py -q
git diff --check HEAD~5..HEAD
```

Expected: all pass.

- [ ] **Step 5: Commit and push**

Run:

```bash
git add tests/lingneng/contract/test_artifact_chat_stream.py tests/lingneng/contract/test_rag_skill_chat_stream.py
git commit -m "test: 增加生成物 SSE 合同测试"
git push origin dev
```

If `test_rag_skill_chat_stream.py` was not modified, omit it from `git add`.

## Final Phase 5 Review

After Task 5.5 is committed and pushed:

- [ ] Dispatch a spec-compliance reviewer subagent for the whole Phase 5
      implementation.
- [ ] Dispatch a code-quality reviewer subagent after spec compliance passes.
- [ ] Fix any reviewer findings in follow-up commits with Chinese
      conventional-prefix messages.
- [ ] Re-run:

```bash
uv run --extra dev python -m pytest tests/lingneng -q
uv run --extra dev python -m ruff check lingneng tests/lingneng
/Users/rotas/Documents/work/hailun/LingNengAI/.venv/bin/python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_tool_artifact_events.py -q
git diff --check HEAD~5..HEAD
```

- [ ] Confirm `git status --short --branch` is clean and `origin/dev` is current.

## Rollback Notes

- Task 5.1 rollback removes `lingneng/tools/artifacts.py`, artifact event models,
  and Phase 5 settings.
- Task 5.2 rollback removes artifact event bridge and final artifact typing;
  existing `artifacts_json` data remains compatible because it already existed.
- Task 5.3 rollback returns document/image/chart/web search tools to stubs and
  removes controlled `web_search` registration.
- Task 5.4 rollback removes attachment context injection and attachment module.
- Task 5.5 rollback removes only the artifact stream contract test unless it
  revealed a required runtime fix.

## User Confirmations Needed Before Execution

None. The approved Phase 5 spec locks the only product-facing decisions:

1. Chart artifacts are image artifacts with `source == "chart_visualization"`.
2. Attachment context is current-request scoped and not durable session memory.
3. Deployment and GitHub Actions remain deferred.

## Plan Self-Review

- Spec coverage: all Phase 5 spec requirements map to Tasks 5.1 through 5.5.
- Placeholder scan: no prohibited placeholder markers are present.
- Type consistency: `Artifact`, `ArtifactCreatedEvent`, `FinalEvent.artifacts`,
  tool JSON `artifacts`, and run-store `artifacts_json` use the same public
  artifact fields.
- Scope check: deployment, Java changes, workspace tools, skill tools, full
  Excel direct-answer, and Hermes high-risk tool exposure remain out of scope.
- Verification: each task has focused tests, a commit point, and a push point;
  final verification includes full LingNeng regression, ruff, old LingNengAI
  artifact event contracts, and `git diff --check`.
