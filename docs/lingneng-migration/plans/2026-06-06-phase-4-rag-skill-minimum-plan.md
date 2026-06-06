# Phase 4 RAG And Skill Loader Minimum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 4 from `docs/lingneng-migration/specs/2026-06-06-phase-4-rag-skill-minimum-spec.md`: bounded employee skill prompt loading, a real `retrieve_rag` adapter, Java-compatible RAG/citation SSE events, and final citation replay.

**Architecture:** Keep all LingNeng business logic inside `lingneng/`. Skill packages are read from configured roots and converted into bounded prompt fragments before Hermes runs. RAG is exposed as the existing safe `retrieve_rag` tool; tool completion JSON is bridged into `citation_delta`, optional `rag_context`, and `final.citations`.

**Tech Stack:** Python 3.11-3.13, Pydantic v2, PyYAML, httpx, FastAPI SSE, SQLite, Hermes `AIAgent`, Hermes tool registry, pytest, uv, ruff.

---

## Approved Spec

This plan implements:

```text
docs/lingneng-migration/specs/2026-06-06-phase-4-rag-skill-minimum-spec.md
```

The master migration sequence remains:

```text
phase spec -> phase plan -> subagent-driven execution
```

## Locked Decisions

- Work on branch `dev`.
- Do not use git worktrees.
- Do not modify `/Users/rotas/Documents/work/hailun/LingNengAI`; use it only as reference.
- Do not implement Docker, compose, deployment scripts, rollback scripts, or GitHub Actions in Phase 4.
- Do not trust or inject Java `request.skill.inline`.
- Do not make skill tools real in Phase 4. Only `retrieve_rag` changes from stub to real adapter.
- Use `LINGNENG_SKILL_ROOTS`; do not hardcode the old LingNengAI path as a production default.
- Keep the `lingneng` toolset bounded to the approved tool names from Phase 3.
- Commit messages are Chinese conventional-prefix style.
- Push only after the task verification commands pass.

## File Map

Create:

- `lingneng/skills/__init__.py`: lightweight package exports only; importing it must not import Hermes `run_agent`.
- `lingneng/skills/models.py`: skill package metadata, resource, loaded package, prompt fragment, and public error models.
- `lingneng/skills/loader.py`: root discovery, `SKILL.md` parsing, validation, employee base mapping, selected skill matching, and prompt composition.
- `lingneng/tools/rag.py`: request-scoped context, provider protocol, default HTTP/not-configured providers, result normalizer, and `retrieve_rag` handler.
- `tests/lingneng/skills/test_skill_loader.py`: skill loader and prompt fragment tests.
- `tests/lingneng/tools/test_retrieve_rag.py`: RAG adapter tests.
- `tests/lingneng/events/test_rag_events.py`: citation/RAG event bridge tests.
- `tests/lingneng/contract/test_rag_skill_chat_stream.py`: Phase 4 stream contract test.

Modify:

- `lingneng/config/settings.py`: add skill and RAG env settings.
- `lingneng/runtime/hermes_adapter.py`: compose enriched system prompt, set RAG context, extract RAG events, accumulate final citations.
- `lingneng/runtime/agent_adapter.py`: include `CitationDeltaEvent` and `RagContextEvent` in the stream event union.
- `lingneng/events/bridge.py`: add citation/RAG event helpers and `final_answer(..., citations=...)`.
- `lingneng/schemas/chat_events.py`: add `Citation`, `CitationDeltaEvent`, `RagContextEvent`.
- `lingneng/api/routes.py`: route new event types and persist/replay citations.
- `lingneng/session/run_store.py`: add `citations_json` storage and backward-compatible migration.
- `lingneng/tools/toolset.py`: register real `retrieve_rag` handler and stub handlers for the other tools.
- `lingneng/tools/stubs.py`: keep tool names/schemas, but expose an iterator for non-RAG stubs.
- `tests/lingneng/config/test_settings.py`: cover new env settings and secret-free readiness summary.
- `tests/lingneng/schemas/test_chat_event_schema.py`: cover new event model payloads.
- `tests/lingneng/api/test_chat_stream_idempotency.py`: replay final citations.
- `tests/lingneng/tools/test_toolset_policy.py`: keep tool boundary assertions while excluding `retrieve_rag` from Phase 3 stub-only assertions.

## Task 4.1: Add Skill Settings And Loader

**Files:**

- Create: `lingneng/skills/__init__.py`
- Create: `lingneng/skills/models.py`
- Create: `lingneng/skills/loader.py`
- Create: `tests/lingneng/skills/test_skill_loader.py`
- Modify: `lingneng/config/settings.py`
- Modify: `tests/lingneng/config/test_settings.py`

- [ ] **Step 1: Write failing settings tests**

Add tests to `tests/lingneng/config/test_settings.py`:

```python
def test_skill_and_rag_settings_defaults_are_safe(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_INTERNAL_API_KEY": "key",
        }
    )

    assert settings.skill_roots == []
    assert settings.skill_excerpt_max_chars == 4000
    assert settings.skill_prompt_max_chars == 12000
    assert settings.rag_endpoint == ""
    assert settings.rag_api_key == ""
    assert settings.rag_timeout_seconds == 5.0
    assert settings.rag_default_top_k == 5
    assert settings.rag_max_top_k == 20
    assert settings.rag_context_max_chars == 6000


def test_skill_roots_parse_json_comma_and_newline(tmp_path):
    first = tmp_path / "employees"
    second = tmp_path / "tasks"
    json_settings = LingNengSettings.from_env(
        {
            "LINGNENG_SKILL_ROOTS": f'["{first}", "{second}"]',
        }
    )
    comma_settings = LingNengSettings.from_env(
        {
            "LINGNENG_SKILL_ROOTS": f"{first},{second}",
        }
    )
    newline_settings = LingNengSettings.from_env(
        {
            "LINGNENG_SKILL_ROOTS": f"{first}\n{second}",
        }
    )

    assert json_settings.skill_roots == [first, second]
    assert comma_settings.skill_roots == [first, second]
    assert newline_settings.skill_roots == [first, second]


def test_ready_summary_hides_rag_api_key(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_INTERNAL_API_KEY": "key",
            "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
            "LINGNENG_RAG_API_KEY": "secret-rag-key",
        }
    )

    summary = settings.ready_summary()

    assert summary["rag_configured"] is True
    assert "rag_api_key" not in summary
    assert "secret-rag-key" not in repr(summary)
```

- [ ] **Step 2: Write failing skill loader tests**

Create `tests/lingneng/skills/test_skill_loader.py` with helper writers and these tests:

```python
from pathlib import Path

from lingneng.config.settings import LingNengSettings
from lingneng.skills.loader import LingNengSkillLoader
from lingneng.skills.models import SkillPackageError
from lingneng.schemas.chat_request import ChatStreamRequest
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def write_skill(
    root: Path,
    name: str,
    *,
    kind: str = "task",
    employee_type: str | None = None,
    display_name: str | None = None,
    body: str = "## When to Use\n用于测试。\n",
    script_policy: str = "metadata_only",
    status: str = "active",
    resources: dict[str, str] | None = None,
) -> Path:
    package = root / name
    package.mkdir(parents=True)
    lingneng_lines = [
        '    schema_version: "1.0"',
        f"    kind: {kind}",
        "    source: python",
        f"    status: {status}",
        "    user_visible: true",
        f"    script_policy: {script_policy}",
    ]
    if employee_type:
        lingneng_lines.append(f"    employee_type: {employee_type}")
    if display_name:
        lingneng_lines.append(f"    display_name: {display_name}")
    skill_text = "\n".join(
        [
            "---",
            f"name: {name}",
            f"description: {name} description",
            "version: 1.0.0",
            "metadata:",
            "  lingneng:",
            *lingneng_lines,
            "triggers: []",
            "---",
            "",
            body,
        ]
    )
    (package / "SKILL.md").write_text(skill_text, encoding="utf-8")
    for resource_path, content in (resources or {}).items():
        target = package / resource_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return package


def settings(tmp_path: Path, **overrides) -> LingNengSettings:
    env = {
        "LINGNENG_SKILL_ROOTS": str(tmp_path),
        "LINGNENG_SKILL_EXCERPT_MAX_CHARS": "120",
        "LINGNENG_SKILL_PROMPT_MAX_CHARS": "500",
    }
    env.update(overrides)
    return LingNengSettings.from_env(env)


def request(skill_id: str = "marketing-copy-generation") -> ChatStreamRequest:
    payload = full_payload()
    payload["skill"]["skill_id"] = skill_id
    payload["skill"]["inline"] = {"summary": "INLINE MUST NOT APPEAR"}
    payload["stream_options"]["include_rag_context"] = True
    return ChatStreamRequest.model_validate(payload)


def test_loads_employee_base_skill_by_employee_type(tmp_path):
    write_skill(
        tmp_path,
        "employee-marketing-content-creator",
        kind="employee_base",
        employee_type="marketing_content_creator",
        display_name="内容创意师",
        body="## Role Identity\n你是内容创意师。\n## Boundaries\n不编造。",
    )
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request())

    assert result.employee_base is not None
    assert result.employee_base.package_name == "employee-marketing-content-creator"
    assert "内容创意师" in result.to_prompt_text()


def test_selects_explicit_skill_by_exact_package_name(tmp_path):
    write_skill(
        tmp_path,
        "marketing-copy-generation",
        body="## When to Use\n写营销内容。\n## Workflow\n先确认渠道。",
    )
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request("marketing-copy-generation"))

    assert result.selected_skill is not None
    assert result.selected_skill.package_name == "marketing-copy-generation"
    assert "写营销内容" in result.to_prompt_text()


def test_unknown_skill_id_skips_inline_content(tmp_path):
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request("unknown-java-skill"))
    prompt = result.to_prompt_text()

    assert result.selected_skill is None
    assert "INLINE MUST NOT APPEAR" not in prompt
    assert any(warning.code == "SELECTED_SKILL_NOT_FOUND" for warning in result.warnings)


def test_large_body_and_resources_are_bounded_manifest_only(tmp_path):
    write_skill(
        tmp_path,
        "marketing-copy-generation",
        body="## When to Use\n" + ("长内容" * 200),
        resources={"references/playbook.md": "资源正文" * 200},
    )
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request("marketing-copy-generation"))
    prompt = result.to_prompt_text()

    assert "references/playbook.md" in prompt
    assert "资源正文资源正文资源正文" not in prompt
    assert len(result.selected_skill.body_excerpt) <= 120
    assert result.selected_skill.truncated is True


def test_rejects_non_metadata_only_script_policy(tmp_path):
    write_skill(
        tmp_path,
        "marketing-copy-generation",
        script_policy="python",
    )
    loader = LingNengSkillLoader(settings(tmp_path))

    result = loader.build_prompt_context(request("marketing-copy-generation"))

    assert result.selected_skill is None
    assert any(warning.code == "SKILL_PACKAGE_INVALID" for warning in result.warnings)
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/config/test_settings.py tests/lingneng/skills/test_skill_loader.py -q
```

Expected: fail because `skill_roots` settings and `lingneng.skills` modules do not exist yet.

- [ ] **Step 4: Implement settings**

In `lingneng/config/settings.py`:

- Add `json` import.
- Add `_path_list_from_env(value: str | None) -> list[Path]`.
- Add the fields from the spec to `LingNengSettings`.
- Parse them in `from_env()`.
- Add non-secret summary keys:
  - `skill_root_count`
  - `rag_configured`

Implementation signatures:

```python
def _path_list_from_env(value: str | None) -> list[Path]:
    if value is None:
        return []
    stripped = value.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        parsed = json.loads(stripped)
        if not isinstance(parsed, list):
            raise ValueError("LINGNENG_SKILL_ROOTS JSON value must be a list")
        return [Path(str(item).strip()) for item in parsed if str(item).strip()]
    normalized = stripped.replace("\n", ",")
    return [Path(part.strip()) for part in normalized.split(",") if part.strip()]
```

- [ ] **Step 5: Implement skill models**

In `lingneng/skills/models.py`, implement:

```python
class SkillPackageError(RuntimeError): ...
class SkillKind(str, Enum): ...
class SkillSource(str, Enum): ...
class SkillLifecycle(str, Enum): ...
class LingNengSkillMetadata(BaseModel): ...
class SkillPackageMetadata(BaseModel): ...
class SkillResource(BaseModel): ...
class SkillResourceManifest(BaseModel): ...
class LoadedSkillPackage(BaseModel): ...
class SkillPromptWarning(BaseModel): ...
class SkillPromptFragment(BaseModel): ...
class SkillPromptContext(BaseModel): ...
```

`SkillPromptContext.to_prompt_text()` must return an empty string when no
fragment or warning exists. When fragments exist, it must use stable headings:

```text
## LingNeng Skill Context
### Employee Base Skill: <package>
### Selected Skill: <package>
### Skill Warnings
```

Use relative resource paths only.

- [ ] **Step 6: Implement loader**

In `lingneng/skills/loader.py`, implement:

```python
EMPLOYEE_BASE_SKILL_BY_TYPE = {
    "boss_assistant": "employee-boss-assistant",
    "operation_specialist": "employee-operation-specialist",
    "product_combo_advisor": "employee-product-combo-advisor",
    "marketing_planner": "employee-marketing-planner",
    "marketing_content_creator": "employee-marketing-content-creator",
    "member_operator": "employee-member-operator",
}

class LingNengSkillLoader:
    def __init__(self, settings: LingNengSettings) -> None: ...
    def build_prompt_context(self, request: ChatStreamRequest) -> SkillPromptContext: ...
    def get_package(self, name: str) -> LoadedSkillPackage | None: ...
```

Important implementation details:

- Use PyYAML `yaml.safe_load`.
- Accept root layouts from the spec.
- Validate front matter and package directory name.
- Skip inactive packages.
- Reject non-`metadata_only`.
- Build resource manifest from only `references`, `templates`, `examples`, and
  `assets`.
- For invalid selected skill packages, return a `SkillPromptWarning` instead of
  raising from `build_prompt_context`.
- Do not import `run_agent`.

- [ ] **Step 7: Run task tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/config/test_settings.py tests/lingneng/skills/test_skill_loader.py -q
```

Expected: pass.

- [ ] **Step 8: Task self-review**

Check:

```bash
rg -n "INLINE MUST NOT APPEAR|api_key|secret-rag-key" lingneng tests/lingneng
uv run --extra dev python -m ruff check lingneng/skills lingneng/config tests/lingneng/skills tests/lingneng/config
```

Expected:

- The `rg` output may show test assertions, but runtime files must not contain those test secrets.
- Ruff passes.

- [ ] **Step 9: Commit and push**

Run:

```bash
git add lingneng/skills lingneng/config/settings.py tests/lingneng/config/test_settings.py tests/lingneng/skills/test_skill_loader.py
git commit -m "feat: 增加数字员工技能加载"
git push origin dev
```

## Task 4.2: Wire Skill Prompt Into Hermes Adapter

**Files:**

- Modify: `lingneng/runtime/hermes_adapter.py`
- Test: `tests/lingneng/runtime/test_hermes_adapter_config.py`
- Test: `tests/lingneng/runtime/test_hermes_answer_stream.py`

- [ ] **Step 1: Write failing adapter prompt tests**

Add a test helper in `tests/lingneng/runtime/test_hermes_adapter_config.py` or
create a focused section in the existing file:

```python
class RecordingSystemPromptAgent:
    system_message_seen = ""

    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")

    def run_conversation(self, user_message, system_message=None, **kwargs):
        type(self).system_message_seen = system_message or ""
        return {"final_response": "完成", "messages": []}
```

Add tests:

```python
@pytest.mark.asyncio
async def test_hermes_adapter_injects_bounded_skill_prompt(tmp_path):
    skill_root = tmp_path / "skills"
    write_skill(
        skill_root,
        "employee-marketing-content-creator",
        kind="employee_base",
        employee_type="marketing_content_creator",
        display_name="内容创意师",
        body="## Role Identity\n你是内容创意师。",
    )
    write_skill(
        skill_root,
        "marketing-copy-generation",
        body="## When to Use\n写营销内容。",
    )
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path / "runtime"),
            "LINGNENG_AGENT_MODE": "hermes",
            "LINGNENG_INTERNAL_API_KEY": "key",
            "LINGNENG_SKILL_ROOTS": str(skill_root),
        }
    )
    request.skill.skill_id = "marketing-copy-generation"
    request.skill.inline = {"summary": "INLINE MUST NOT APPEAR"}
    adapter = HermesAgentRunAdapter(settings, agent_cls=RecordingSystemPromptAgent)

    events = [event async for event in adapter.stream(request, resolved, "run-1")]

    assert isinstance(events[-1], FinalEvent)
    prompt = RecordingSystemPromptAgent.system_message_seen
    assert "你是灵能营销内容员工。" in prompt
    assert "employee-marketing-content-creator" in prompt
    assert "marketing-copy-generation" in prompt
    assert "写营销内容" in prompt
    assert "INLINE MUST NOT APPEAR" not in prompt
    assert "上一轮用户问题" not in prompt
```

Add a degradation test:

```python
@pytest.mark.asyncio
async def test_hermes_adapter_continues_when_skill_roots_missing(tmp_path):
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path / "runtime"),
            "LINGNENG_AGENT_MODE": "hermes",
            "LINGNENG_INTERNAL_API_KEY": "key",
            "LINGNENG_SKILL_ROOTS": str(tmp_path / "missing"),
        }
    )
    adapter = HermesAgentRunAdapter(settings, agent_cls=RecordingSystemPromptAgent)

    events = [event async for event in adapter.stream(request, resolved, "run-1")]

    assert isinstance(events[-1], FinalEvent)
    prompt = RecordingSystemPromptAgent.system_message_seen
    assert "你是灵能营销内容员工。" in prompt
    assert "LingNeng Skill Context" in prompt
    assert "SKILL_ROOT_MISSING" in prompt
```

Import the `write_skill` helper from `tests.lingneng.skills.test_skill_loader`.

- [ ] **Step 2: Run failing adapter tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime/test_hermes_adapter_config.py -q
```

Expected: fail because `HermesAgentRunAdapter` still passes only `request.system_prompt.content`.

- [ ] **Step 3: Implement prompt composition**

In `lingneng/runtime/hermes_adapter.py`:

- Import `LingNengSkillLoader`.
- Add `_build_system_message(self, request: ChatStreamRequest) -> str`.
- Use it in `run_agent()`:

```python
system_message = self._build_system_message(request)
result = agent.run_conversation(
    request.query.content,
    system_message=system_message,
    conversation_history=history,
    task_id=run_id,
    persist_user_message=request.query.content,
)
```

Prompt assembly behavior:

```python
def _compose_system_message(base_prompt: str, skill_prompt: str) -> str:
    parts = [base_prompt.strip()]
    if skill_prompt.strip():
        parts.append(skill_prompt.strip())
    parts.append(
        "## LingNeng RAG Guidance\n"
        "Use retrieve_rag for internal learned business knowledge that needs factual support. "
        "Do not use it for realtime public facts."
    )
    return "\n\n".join(part for part in parts if part)
```

Catch skill loader exceptions and add a public warning section instead of
failing the stream.

- [ ] **Step 4: Run task tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime/test_hermes_adapter_config.py tests/lingneng/runtime/test_hermes_answer_stream.py tests/lingneng/skills/test_skill_loader.py -q
```

Expected: pass.

- [ ] **Step 5: Commit and push**

Run:

```bash
git add lingneng/runtime/hermes_adapter.py tests/lingneng/runtime/test_hermes_adapter_config.py tests/lingneng/runtime/test_hermes_answer_stream.py
git commit -m "feat: 接入灵能技能提示词"
git push origin dev
```

## Task 4.3: Implement RAG Tool Adapter

**Files:**

- Create: `lingneng/tools/rag.py`
- Modify: `lingneng/tools/toolset.py`
- Modify: `lingneng/tools/stubs.py`
- Modify: `tests/lingneng/tools/test_toolset_policy.py`
- Test: `tests/lingneng/tools/test_retrieve_rag.py`

- [ ] **Step 1: Write failing RAG adapter tests**

Create `tests/lingneng/tools/test_retrieve_rag.py`:

```python
import json

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from lingneng.tools.rag import (
    RagProvider,
    RagRetrieveRequest,
    RagRetrieveResult,
    build_rag_request_context,
    rag_request_context,
    retrieve_rag_handler,
)
from tests.lingneng.schemas.test_chat_request_schema import full_payload


class FakeRagProvider:
    def __init__(self, result: RagRetrieveResult | Exception):
        self.result = result
        self.requests = []

    def retrieve(self, request: RagRetrieveRequest) -> RagRetrieveResult:
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def make_context(tmp_path, request=None):
    request = request or ChatStreamRequest.model_validate(full_payload())
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_RAG_DEFAULT_TOP_K": "3",
            "LINGNENG_RAG_MAX_TOP_K": "5",
            "LINGNENG_RAG_CONTEXT_MAX_CHARS": "80",
        }
    )
    return build_rag_request_context(
        settings=settings,
        request=request,
        resolved_session=resolve_session_key(request),
    )


def test_retrieve_rag_builds_contextual_request(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(
            status="hit",
            context="套餐规则来自知识库。",
            citations=[
                {
                    "document_id": "doc-1",
                    "source_file_id": "file-1",
                    "source_file_name": "menu.pdf",
                    "page_no": 2,
                    "section_title": "套餐",
                    "chunk_id": "chunk-1",
                    "score": 0.9,
                }
            ],
            metadata={"duration_ms": 12},
        )
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(
            retrieve_rag_handler(
                {
                    "query": "会员套餐怎么写",
                    "top_k": 99,
                    "filters": {"document_type": "menu"},
                }
            )
        )

    assert result["success"] is True
    assert result["status"] == "hit"
    assert result["citations"][0]["chunk_id"] == "chunk-1"
    sent = provider.requests[0]
    assert sent.query == "会员套餐怎么写"
    assert sent.tenant_id == "tenant-a"
    assert sent.user_id == "user-a"
    assert sent.employee_type == "marketing_content_creator"
    assert sent.conversation_id == "conv-a"
    assert sent.session_key == "tenant-a:user-a:emp-001:conv-a"
    assert sent.request_id == "req-001"
    assert sent.top_k == 5
    assert sent.filters == {"document_type": "menu"}


def test_retrieve_rag_empty_result_shape(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(status="empty", context="", citations=[], metadata={})
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "没有资料"}))

    assert result == {
        "success": True,
        "tool_name": "retrieve_rag",
        "status": "empty",
        "context": "",
        "citations": [],
        "metadata": {"selected_count": 0, "citation_count": 0},
    }


def test_retrieve_rag_not_configured_is_safe(tmp_path):
    with rag_request_context(make_context(tmp_path), provider=None):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    assert result["success"] is False
    assert result["code"] == "NOT_CONFIGURED"
    assert result["status"] == "failed"
    assert "api_key" not in json.dumps(result)
    assert "history" not in result


def test_retrieve_rag_provider_exception_is_sanitized(tmp_path):
    provider = FakeRagProvider(RuntimeError("private provider api_key=secret"))

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    dumped = json.dumps(result, ensure_ascii=False)
    assert result["success"] is False
    assert result["code"] == "RAG_PROVIDER_ERROR"
    assert "private provider" not in dumped
    assert "api_key" not in dumped
    assert "secret" not in dumped
```

- [ ] **Step 2: Update toolset policy tests first**

In `tests/lingneng/tools/test_toolset_policy.py`:

- Keep `APPROVED_LINGNENG_TOOLS` unchanged.
- Change the stub-only test to skip `retrieve_rag`.
- Add a new assertion that the registered `retrieve_rag` handler no longer has
  `phase == "phase_3_stub"` when dispatched under a missing provider context.

Expected assertion shape:

```python
STUB_ONLY_TOOLS = APPROVED_LINGNENG_TOOLS - {"retrieve_rag"}
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_retrieve_rag.py tests/lingneng/tools/test_toolset_policy.py -q
```

Expected: fail because `lingneng.tools.rag` does not exist and `retrieve_rag` is still a stub.

- [ ] **Step 4: Implement `lingneng/tools/rag.py`**

Implement these public objects:

```python
@dataclass(frozen=True)
class RagRequestContext:
    settings: LingNengSettings
    tenant_id: str
    user_id: str
    employee_type: str
    conversation_id: str | None
    session_key: str
    request_id: str


class RagRetrieveRequest(BaseModel):
    query: str
    tenant_id: str
    user_id: str
    employee_type: str
    conversation_id: str | None
    session_key: str
    request_id: str
    top_k: int
    filters: dict[str, Any] = Field(default_factory=dict)


class RagRetrieveResult(BaseModel):
    status: Literal["hit", "empty", "failed"]
    context: str = ""
    citations: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    code: str | None = None
    message: str | None = None


class RagProvider(Protocol):
    def retrieve(self, request: RagRetrieveRequest) -> RagRetrieveResult: ...
```

Also implement:

```python
def build_rag_request_context(
    *,
    settings: LingNengSettings,
    request: ChatStreamRequest,
    resolved_session: ResolvedSessionKey,
) -> RagRequestContext: ...

@contextmanager
def rag_request_context(
    context: RagRequestContext,
    *,
    provider: RagProvider | None = None,
): ...

def retrieve_rag_handler(args: dict[str, Any] | None = None, **kwargs: Any) -> str: ...
```

Handler behavior:

- Missing context returns `RAG_CONTEXT_MISSING`.
- Empty query returns `INVALID_RAG_QUERY`.
- Missing provider and empty `settings.rag_endpoint` returns `NOT_CONFIGURED`.
- Provider exception returns `RAG_PROVIDER_ERROR`.
- Success normalizes metadata with `selected_count` and `citation_count`.
- Context is truncated to `settings.rag_context_max_chars`.

Implement `HttpRagProvider` with `httpx.Client(timeout=settings.rag_timeout_seconds)`:

```python
response = client.post(
    settings.rag_endpoint,
    json=request.model_dump(),
    headers={"Authorization": f"Bearer {settings.rag_api_key}"} if settings.rag_api_key else {},
)
response.raise_for_status()
return RagRetrieveResult.model_validate(response.json())
```

- [ ] **Step 5: Register real RAG handler**

In `lingneng/tools/stubs.py`:

- Keep `LINGNENG_TOOL_NAMES` and `TOOL_SCHEMAS`.
- Add `STUB_TOOL_NAMES = tuple(name for name in LINGNENG_TOOL_NAMES if name != "retrieve_rag")`.
- Change `iter_tool_entries()` to iterate `STUB_TOOL_NAMES`.

In `lingneng/tools/toolset.py`:

- Import `retrieve_rag_handler` from `lingneng.tools.rag`.
- Register `retrieve_rag` first or after stubs with the same schema.
- Register remaining stubs through `iter_tool_entries()`.

Registration snippet:

```python
registry.register(
    name="retrieve_rag",
    toolset="lingneng",
    schema=TOOL_SCHEMAS["retrieve_rag"],
    handler=retrieve_rag_handler,
    description=TOOL_SCHEMAS["retrieve_rag"]["description"],
)
```

- [ ] **Step 6: Run task tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_retrieve_rag.py tests/lingneng/tools/test_toolset_policy.py -q
```

Expected: pass.

- [ ] **Step 7: Commit and push**

Run:

```bash
git add lingneng/tools/rag.py lingneng/tools/toolset.py lingneng/tools/stubs.py tests/lingneng/tools/test_retrieve_rag.py tests/lingneng/tools/test_toolset_policy.py
git commit -m "feat: 接入灵能 RAG 工具"
git push origin dev
```

## Task 4.4: Bridge RAG Events And Persist Final Citations

**Files:**

- Modify: `lingneng/schemas/chat_events.py`
- Modify: `lingneng/events/bridge.py`
- Modify: `lingneng/runtime/agent_adapter.py`
- Modify: `lingneng/runtime/hermes_adapter.py`
- Modify: `lingneng/api/routes.py`
- Modify: `lingneng/session/run_store.py`
- Modify: `tests/lingneng/schemas/test_chat_event_schema.py`
- Create: `tests/lingneng/events/test_rag_events.py`
- Modify: `tests/lingneng/api/test_chat_stream_idempotency.py`

- [ ] **Step 1: Write failing event schema tests**

Add to `tests/lingneng/schemas/test_chat_event_schema.py`:

```python
from lingneng.schemas.chat_events import Citation, CitationDeltaEvent, RagContextEvent


def test_rag_event_payloads_dump_without_event_field():
    citation = Citation(
        document_id="doc-1",
        source_file_id="file-1",
        source_file_name="menu.pdf",
        page_no=2,
        section_title="套餐",
        chunk_id="chunk-1",
        score=0.9,
    )
    delta = CitationDeltaEvent.model_validate(citation.model_dump())
    context = RagContextEvent(
        context="套餐规则",
        citations=[citation],
        status="hit",
        metadata={"selected_count": 1},
    )

    assert delta.model_dump()["chunk_id"] == "chunk-1"
    assert context.model_dump()["status"] == "hit"
    assert "event" not in delta.model_dump()
    assert "event" not in context.model_dump()
```

- [ ] **Step 2: Write failing RAG bridge tests**

Create `tests/lingneng/events/test_rag_events.py`:

```python
import json

from lingneng.events.bridge import (
    dedupe_citations,
    final_answer,
    rag_events_from_tool_result,
)
from lingneng.schemas.chat_events import CitationDeltaEvent, FinalEvent, RagContextEvent


CITATION = {
    "document_id": "doc-1",
    "source_file_id": "file-1",
    "source_file_name": "menu.pdf",
    "page_no": 2,
    "section_title": "套餐",
    "chunk_id": "chunk-1",
    "score": 0.9,
}


def result_payload(**overrides):
    payload = {
        "success": True,
        "tool_name": "retrieve_rag",
        "status": "hit",
        "context": "套餐规则",
        "citations": [CITATION],
        "metadata": {"selected_count": 1},
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def test_rag_hit_emits_citation_and_context_when_requested():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(),
        include_citations=True,
        include_rag_context=True,
    )

    assert [type(event) for event in events] == [CitationDeltaEvent, RagContextEvent]
    assert events[0].chunk_id == "chunk-1"
    assert events[1].status == "hit"
    assert citations == [CITATION]


def test_rag_empty_emits_empty_context_only_when_requested():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(status="empty", context="", citations=[]),
        include_citations=True,
        include_rag_context=True,
    )

    assert [type(event) for event in events] == [RagContextEvent]
    assert events[0].status == "empty"
    assert citations == []


def test_rag_events_honor_stream_options():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(),
        include_citations=False,
        include_rag_context=False,
    )

    assert events == []
    assert citations == []


def test_non_rag_tool_result_is_ignored():
    events, citations = rag_events_from_tool_result(
        tool_name="document_generation",
        result=result_payload(),
        include_citations=True,
        include_rag_context=True,
    )

    assert events == []
    assert citations == []


def test_dedupe_citations_by_chunk_id():
    duplicate = {**CITATION, "source_file_name": "duplicate.pdf"}

    assert dedupe_citations([CITATION, duplicate, {**CITATION, "chunk_id": "chunk-2"}]) == [
        CITATION,
        {**CITATION, "chunk_id": "chunk-2"},
    ]


def test_final_answer_accepts_citations():
    event = final_answer(run_id="run-1", answer="完成", citations=[CITATION])

    assert isinstance(event, FinalEvent)
    assert event.citations == [CITATION]
```

- [ ] **Step 3: Write failing idempotency replay test**

Add to `tests/lingneng/api/test_chat_stream_idempotency.py`:

```python
class CountingCitationSuccessAdapter:
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
            citations=[
                {
                    "document_id": "doc-1",
                    "source_file_id": "file-1",
                    "source_file_name": "menu.pdf",
                    "page_no": 2,
                    "section_title": "套餐",
                    "chunk_id": "chunk-1",
                    "score": 0.9,
                }
            ],
        )


def test_repeated_success_replays_final_citations(tmp_path):
    adapter = CountingCitationSuccessAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    app = create_app(settings=settings(tmp_path), adapter=adapter, run_store=store)
    client = TestClient(app)

    first = post(client, full_payload())
    second = post(client, full_payload())
    frames = parse_sse(second.text)

    assert first.status_code == 200
    assert second.status_code == 200
    assert [event for event, _ in frames] == ["run_started", "answer_delta", "final"]
    assert frames[-1][1]["citations"][0]["chunk_id"] == "chunk-1"
    assert adapter.calls == 1
```

- [ ] **Step 4: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/schemas/test_chat_event_schema.py tests/lingneng/events/test_rag_events.py tests/lingneng/api/test_chat_stream_idempotency.py -q
```

Expected: fail because new event models/helpers and citation persistence do not exist.

- [ ] **Step 5: Implement chat event models**

In `lingneng/schemas/chat_events.py`:

```python
class Citation(LingNengEventModel):
    document_id: str
    source_file_id: str
    source_file_name: str
    page_no: int | None = None
    section_title: str | None = None
    chunk_id: str
    score: float = Field(ge=0)


class CitationDeltaEvent(Citation):
    pass


class RagContextEvent(LingNengEventModel):
    context: str
    citations: list[Citation] = Field(default_factory=list)
    status: Literal["hit", "empty", "failed"]
    metadata: dict[str, Any] = Field(default_factory=dict)
```

Update `FinalEvent.citations` type to `list[Citation] | list[dict]` only if
Pydantic coercion needs it; prefer `list[Citation]` if existing tests still pass.

- [ ] **Step 6: Implement bridge helpers**

In `lingneng/events/bridge.py`, implement:

```python
def rag_events_from_tool_result(
    *,
    tool_name: str,
    result: Any,
    include_citations: bool,
    include_rag_context: bool,
) -> tuple[list[CitationDeltaEvent | RagContextEvent], list[dict[str, Any]]]: ...

def dedupe_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]: ...

def final_answer(
    run_id: str,
    answer: str,
    citations: list[dict[str, Any]] | None = None,
) -> FinalEvent: ...
```

Rules:

- Parse only `tool_name == "retrieve_rag"`.
- Invalid JSON returns no events and no citations.
- Validate citations with `Citation.model_validate`.
- Ignore invalid citation items rather than failing the stream.
- Return citations only when `include_citations` is true.
- For `include_rag_context`, build `RagContextEvent` with status from result or
  `"hit"` when valid citations exist and `"empty"` otherwise.

- [ ] **Step 7: Wire events into adapter**

In `lingneng/runtime/agent_adapter.py`, include new event types:

```python
LingNengStreamEvent = Union[
    RunStartedEvent,
    AgentStepEvent,
    CitationDeltaEvent,
    RagContextEvent,
    AnswerDeltaEvent,
    FinalEvent,
    ErrorEvent,
]
```

In `lingneng/runtime/hermes_adapter.py`:

- Add `rag_citations: list[dict[str, Any]] = []`.
- In `on_tool_progress`, after the `AgentStepEvent` is enqueued for
  `tool.completed`, call `rag_events_from_tool_result(...)`.
- Append deduped citations under the existing `tool_progress_lock`.
- Enqueue RAG events immediately after the agent step.
- When yielding final, call:

```python
yield final_answer(
    run_id=run_id,
    answer=final_text,
    citations=rag_citations if request.stream_options.include_citations else [],
)
```

- Around `agent.run_conversation`, set and reset RAG context:

```python
from lingneng.tools.rag import build_rag_provider, build_rag_request_context, rag_request_context

rag_context = build_rag_request_context(
    settings=self.settings,
    request=request,
    resolved_session=resolved_session,
)
with rag_request_context(rag_context, provider=build_rag_provider(self.settings)):
    result = agent.run_conversation(...)
```

- [ ] **Step 8: Persist citations in run store and routes**

In `lingneng/session/run_store.py`:

- Add `citations: list[dict[str, Any]]` to `RunRecord`.
- Add `citations_json TEXT NOT NULL DEFAULT '[]'` in create table.
- Add backward-compatible migration in `_init_db()`:

```python
columns = {row["name"] for row in conn.execute("PRAGMA table_info(lingneng_runs)")}
if "citations_json" not in columns:
    conn.execute("ALTER TABLE lingneng_runs ADD COLUMN citations_json TEXT NOT NULL DEFAULT '[]'")
```

- Add `citations` parameter to `mark_succeeded`.
- Clear citations on `mark_failed`.
- Parse `citations_json` in `_record_from_row`.

In `lingneng/api/routes.py`:

- Include `CitationDeltaEvent` and `RagContextEvent` imports.
- `_event_name()` returns `"citation_delta"` and `"rag_context"` for the new models.
- `mark_succeeded()` receives `citations=event.citations`.
- Replay `FinalEvent(..., citations=record.citations, artifacts=record.artifacts)`.

- [ ] **Step 9: Run task tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/schemas/test_chat_event_schema.py tests/lingneng/events/test_rag_events.py tests/lingneng/api/test_chat_stream_idempotency.py tests/lingneng/runtime/test_hermes_answer_stream.py -q
```

Expected: pass.

- [ ] **Step 10: Commit and push**

Run:

```bash
git add lingneng/schemas/chat_events.py lingneng/events/bridge.py lingneng/runtime/agent_adapter.py lingneng/runtime/hermes_adapter.py lingneng/api/routes.py lingneng/session/run_store.py tests/lingneng/schemas/test_chat_event_schema.py tests/lingneng/events/test_rag_events.py tests/lingneng/api/test_chat_stream_idempotency.py
git commit -m "feat: 增加灵能 RAG 流式事件"
git push origin dev
```

## Task 4.5: Add Phase 4 Contract Scenario And Full Verification

**Files:**

- Create: `tests/lingneng/contract/test_rag_skill_chat_stream.py`
- Modify if needed: `tests/lingneng/contract/test_chat_stream_minimal.py`

- [ ] **Step 1: Write contract test**

Create `tests/lingneng/contract/test_rag_skill_chat_stream.py`:

```python
import json

from fastapi.testclient import TestClient

from lingneng.api.app import create_app
from lingneng.config.settings import LingNengSettings
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.session.run_store import LingNengRunStore
from tools.registry import registry
from tests.lingneng.api.test_chat_stream_contract import parse_sse
from tests.lingneng.schemas.test_chat_request_schema import full_payload
from tests.lingneng.skills.test_skill_loader import write_skill


CITATION = {
    "document_id": "doc-1",
    "source_file_id": "file-1",
    "source_file_name": "menu.pdf",
    "page_no": 2,
    "section_title": "会员套餐",
    "chunk_id": "chunk-1",
    "score": 0.92,
}


class FakeProvider:
    def retrieve(self, request):
        return type("Result", (), {
            "model_dump": lambda self: {
                "status": "hit",
                "context": "会员套餐规则来自知识库。",
                "citations": [CITATION],
                "metadata": {"duration_ms": 3},
            }
        })()


class ContractRagSkillAgent:
    system_message_seen = ""

    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")
        self.tool_progress_callback = kwargs.get("tool_progress_callback")

    def run_conversation(self, user_message, system_message=None, **kwargs):
        type(self).system_message_seen = system_message or ""
        self.tool_progress_callback(
            "tool.started",
            "retrieve_rag",
            "query='会员套餐'",
            {"query": "会员套餐"},
        )
        result = registry.dispatch(
            "retrieve_rag",
            {"query": "会员套餐", "top_k": 1},
        )
        self.tool_progress_callback(
            "tool.completed",
            "retrieve_rag",
            None,
            None,
            duration=0.01,
            is_error=False,
            result=result,
        )
        self.stream_delta_callback("基于知识库，")
        self.stream_delta_callback("建议这样写。")
        return {"final_response": "基于知识库，建议这样写。", "messages": []}


def settings(tmp_path, skill_root):
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path / "runtime"),
            "LINGNENG_AGENT_MODE": "hermes",
            "LINGNENG_INTERNAL_API_KEY": "key",
            "LINGNENG_SKILL_ROOTS": str(skill_root),
        }
    )


def test_rag_skill_chat_stream_contract(tmp_path, monkeypatch):
    skill_root = tmp_path / "skills"
    write_skill(
        skill_root,
        "employee-marketing-content-creator",
        kind="employee_base",
        employee_type="marketing_content_creator",
        display_name="内容创意师",
        body="## Role Identity\n你是内容创意师。\n## RAG Guidance\n需要事实时查知识库。",
    )
    write_skill(
        skill_root,
        "marketing-copy-generation",
        body="## When to Use\n生成营销文案。\n## Workflow\n先确认渠道。",
    )
    monkeypatch.setattr("lingneng.tools.rag.build_rag_provider", lambda settings: FakeProvider())
    resolved_settings = settings(tmp_path, skill_root)
    adapter = HermesAgentRunAdapter(
        settings=resolved_settings,
        agent_cls=ContractRagSkillAgent,
    )
    app = create_app(
        settings=resolved_settings,
        adapter=adapter,
        run_store=LingNengRunStore(tmp_path / "runs.sqlite3"),
    )
    payload = full_payload()
    payload["skill"]["skill_id"] = "marketing-copy-generation"
    payload["skill"]["inline"] = {"summary": "INLINE MUST NOT APPEAR"}
    payload["stream_options"]["include_citations"] = True
    payload["stream_options"]["include_rag_context"] = True

    response = TestClient(app).post(
        "/internal/agent/chat/stream",
        json=payload,
        headers={"X-Internal-Key": "key"},
    )
    frames = parse_sse(response.text)
    event_names = [name for name, _data in frames]
    final = frames[-1][1]

    assert response.status_code == 200
    assert event_names[0] == "run_started"
    assert "agent_step" in event_names
    assert "citation_delta" in event_names
    assert "rag_context" in event_names
    assert "answer_delta" in event_names
    assert event_names[-1] == "final"
    assert final["citations"][0]["chunk_id"] == "chunk-1"
    assert "".join(data["text"] for name, data in frames if name == "answer_delta") == final["answer"]
    prompt = ContractRagSkillAgent.system_message_seen
    assert "employee-marketing-content-creator" in prompt
    assert "marketing-copy-generation" in prompt
    assert "INLINE MUST NOT APPEAR" not in prompt
```

If the fake provider cannot use a simple object with `model_dump`, replace it
with `RagRetrieveResult(...)` imported from `lingneng.tools.rag`.

- [ ] **Step 2: Run contract test**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/contract/test_rag_skill_chat_stream.py -q
```

Expected: pass.

- [ ] **Step 3: Run Phase 4 verification suite**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/skills/test_skill_loader.py tests/lingneng/tools/test_retrieve_rag.py tests/lingneng/events/test_rag_events.py tests/lingneng/contract/test_rag_skill_chat_stream.py -q
```

Expected: pass.

- [ ] **Step 4: Run full LingNeng regression**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/config tests/lingneng/schemas tests/lingneng/session tests/lingneng/api tests/lingneng/runtime tests/lingneng/tools tests/lingneng/events tests/lingneng/contract -q
uv run --extra dev python -m ruff check lingneng tests/lingneng
/Users/rotas/Documents/work/hailun/LingNengAI/.venv/bin/python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit and push**

Run:

```bash
git add tests/lingneng/contract/test_rag_skill_chat_stream.py tests/lingneng/contract/test_chat_stream_minimal.py
git commit -m "test: 增加 RAG 与技能流式合同测试"
git push origin dev
```

If `test_chat_stream_minimal.py` was not modified, omit it from `git add`.

## Final Phase 4 Review

After Task 4.5 is committed and pushed:

- [ ] Dispatch a spec-compliance reviewer subagent for the whole Phase 4 implementation.
- [ ] Dispatch a code-quality reviewer subagent after spec compliance passes.
- [ ] Fix any reviewer findings in follow-up commits with Chinese conventional-prefix messages.
- [ ] Re-run:

```bash
uv run --extra dev python -m pytest tests/lingneng/config tests/lingneng/schemas tests/lingneng/session tests/lingneng/api tests/lingneng/runtime tests/lingneng/tools tests/lingneng/events tests/lingneng/contract -q
uv run --extra dev python -m ruff check lingneng tests/lingneng
git diff --check HEAD~5..HEAD
```

- [ ] Confirm `git status --short --branch` is clean and `origin/dev` is current.

## Rollback Notes

- Task 4.1 rollback removes `lingneng/skills/` and the new settings/tests.
- Task 4.2 rollback restores `HermesAgentRunAdapter` to passing only Java
  `system_prompt.content`.
- Task 4.3 rollback reverts `retrieve_rag` to Phase 3 stub registration.
- Task 4.4 rollback removes new RAG event types and `citations_json`; existing
  SQLite files can keep the extra column safely because old code ignores it.
- Task 4.5 rollback removes only the new contract test unless it revealed a
  required runtime fix.

## User Confirmations Needed Before Execution

None. The approved Phase 4 spec already locks the only two important choices:

1. Skill packages are enabled through `LINGNENG_SKILL_ROOTS`, not a hardcoded old
   repository path.
2. Java `skill.inline` is never trusted as prompt content.

## Plan Self-Review

- Spec coverage: all Phase 4 spec requirements map to Tasks 4.1 through 4.5.
- Placeholder scan: no TBD/TODO placeholders are present.
- Type consistency: RAG uses `RagRequestContext`, `RagRetrieveRequest`,
  `RagRetrieveResult`, `Citation`, `CitationDeltaEvent`, and `RagContextEvent`
  consistently across tasks.
- Scope check: deployment, artifacts, attachment understanding, skill public
  tools, and non-RAG business tools remain out of scope.
- Verification: each task has focused tests, a commit point, and a push point;
  final verification includes the full LingNeng suite, ruff, old LingNengAI
  event contract tests, and `git diff --check`.
