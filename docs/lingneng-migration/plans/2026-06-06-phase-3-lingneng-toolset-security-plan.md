# Phase 3 Dedicated LingNeng Toolset And Security Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the dedicated LingNeng business toolset and public tool-progress SSE bridge without exposing Hermes high-risk defaults or implementing real business backends.

**Architecture:** Keep LingNeng-specific tool definitions, stub handlers, and event bridge helpers inside `lingneng/`. Add one static `lingneng` toolset entry to `toolsets.py`, register LingNeng stub tools through the existing Hermes registry, and wire `HermesAgentRunAdapter` to use `enabled_toolsets=["lingneng"]` plus `tool_progress_callback` to emit `agent_step`.

**Tech Stack:** Python 3.11-3.13, Pydantic v2, Hermes tool registry/toolsets, Hermes `AIAgent` callbacks, FastAPI SSE route encoding, pytest, uv.

---

## Approved Inputs

- Master context: `LINGNENG_MIGRATION_CONTEXT.md`
- Master design: `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- Master roadmap: `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- Phase 1 spec: `docs/lingneng-migration/specs/2026-06-06-phase-1-java-compatible-api-mvp-spec.md`
- Phase 1 plan: `docs/lingneng-migration/plans/2026-06-06-phase-1-java-compatible-api-mvp-plan.md`
- Phase 2 spec: `docs/lingneng-migration/specs/2026-06-06-phase-2-hermes-agent-integration-spec.md`
- Phase 2 plan: `docs/lingneng-migration/plans/2026-06-06-phase-2-hermes-agent-integration-plan.md`
- Phase 3 spec: `docs/lingneng-migration/specs/2026-06-06-phase-3-lingneng-toolset-security-spec.md`

## Execution Order

Execute tasks in this exact order:

1. Task 3.1 LingNeng toolset stubs and policy tests
2. Task 3.2 Agent step event model and bridge helpers
3. Task 3.3 Hermes adapter wiring and Phase 3 verification

Each task must follow:

```text
reload durable context -> write failing tests -> run focused test and confirm expected failure -> implement -> run focused test -> run task review checks -> commit in Chinese -> push dev
```

Do not start Task N+1 until Task N is verified, committed, and pushed.

## User Confirmations Before Execution

No additional user confirmation is required before Phase 3 execution. The Phase
3 spec locks these decisions:

- Phase 3 registers explicit `NOT_CONFIGURED` stub tools only.
- Phase 3 enables `enabled_toolsets=["lingneng"]` for Hermes-mode Java API
  requests.
- `disabled_toolsets=["kanban"]`, kanban env isolation, LingNeng SessionDB, and
  Java history exclusion from Phase 2 remain required.
- RAG, skills, artifacts, attachments, LingNeng-safe search, document
  generation, image generation, chart generation, Docker, Compose, deployment
  scripts, and GitHub Actions workflows remain outside Phase 3.
- Tests must not call real providers or external LingNeng business services.

## Shared Worker Rules

- Work in `/Users/rotas/Documents/work/hailun/demos/lingneng-hermes`.
- Do not use git worktrees.
- Do not modify Java code or `/Users/rotas/Documents/work/hailun/LingNengAI`.
- Do not modify `run_agent.py`, `agent/tool_executor.py`, `model_tools.py`,
  `tools/registry.py`, `hermes_state.py`, `gateway/platforms/api_server.py`, or
  `hermes_cli/web_server.py` in Phase 3.
- Keep edits scoped to `lingneng/`, `toolsets.py`, `tests/lingneng/`, and this
  Phase 3 plan unless a test proves the existing Hermes extension surface is
  insufficient.
- Use `uv run --extra dev python -m pytest` for repository-local pytest.
- Use `apply_patch` for manual edits.
- Keep secrets, API keys, raw Java `history`, and raw exception details out of
  public event payloads and stub outputs.
- No local service is required. Use direct unit tests and injected fake agents.
- If a local server is manually started for debugging, first run
  `lsof -nP -iTCP:18083 -sTCP:LISTEN` and do not kill unrelated processes.
- After each task, run `git diff --check` before commit.
- Commit messages are Chinese conventional-prefix messages listed per task.
- Push `origin dev` after each verified task commit.

## File Map

Runtime modules created or modified in Phase 3:

- `toolsets.py`: add static `lingneng` toolset entry with direct approved tool
  names and no includes.
- `lingneng/tools/__init__.py`: lightweight package marker; importing it must
  not load Hermes `run_agent`.
- `lingneng/tools/stubs.py`: owns approved tool names, small OpenAI schemas,
  `NOT_CONFIGURED` result builder, and handler factories.
- `lingneng/tools/toolset.py`: imports stub definitions and registers all
  LingNeng tools with `tools.registry.registry`.
- `lingneng/schemas/chat_events.py`: add `AgentStepEvent` and event/status
  literals.
- `lingneng/events/bridge.py`: add `agent_step_started`,
  `agent_step_completed`, and `agent_step_skipped` helper functions.
- `lingneng/runtime/agent_adapter.py`: include `AgentStepEvent` in
  `LingNengStreamEvent`.
- `lingneng/runtime/hermes_adapter.py`: ensure LingNeng stubs are registered,
  construct `AIAgent` with `enabled_toolsets=["lingneng"]`, and bridge
  `tool_progress_callback` into queued `AgentStepEvent` objects.
- `lingneng/api/routes.py`: encode `AgentStepEvent` as SSE event name
  `agent_step`.

Tests created or modified in Phase 3:

- `tests/lingneng/tools/test_toolset_policy.py`
- `tests/lingneng/events/test_agent_step_bridge.py`
- `tests/lingneng/runtime/test_hermes_adapter_config.py`
- `tests/lingneng/runtime/test_hermes_answer_stream.py`
- `tests/lingneng/api/test_chat_stream_contract.py` only if route-level
  `agent_step` coverage belongs there after Task 3.3.

## Shared Constants For Workers

Use this exact approved tool-name set in tests and code:

```python
APPROVED_LINGNENG_TOOLS = {
    "retrieve_rag",
    "list_skills",
    "search_skills",
    "read_skill",
    "read_skill_resource",
    "document_generation",
    "image_generation",
    "chart_visualization",
    "read_workspace",
    "write_workspace",
}
```

Use this exact disallowed Hermes-name set in policy tests:

```python
DISALLOWED_HERMES_TOOLS = {
    "terminal",
    "web_search",
    "process",
    "read_file",
    "write_file",
    "patch",
    "search_files",
    "browser_navigate",
    "browser_snapshot",
    "browser_click",
    "browser_type",
    "browser_scroll",
    "browser_back",
    "browser_press",
    "browser_get_images",
    "browser_vision",
    "browser_console",
    "browser_cdp",
    "browser_dialog",
    "execute_code",
    "delegate_task",
    "send_message",
    "kanban_show",
    "kanban_list",
    "kanban_complete",
    "kanban_block",
    "kanban_heartbeat",
    "kanban_comment",
    "kanban_create",
    "kanban_link",
    "kanban_unblock",
}
```

## Review Checks For Every Task

Run these before each task commit:

```bash
git diff --check
rg -n "T[B]D|T[O]DO|t[o]do|fill[[:space:]]in|implement[[:space:]]later|place[h]older|待[补]充|待[定]|占[位]" lingneng tests/lingneng docs/lingneng-migration/plans/2026-06-06-phase-3-lingneng-toolset-security-plan.md docs/lingneng-migration/specs/2026-06-06-phase-3-lingneng-toolset-security-spec.md
```

Expected:

- `git diff --check` exits 0.
- The incomplete-marker scan exits 1 with no matches.

---

### Task 3.1: LingNeng Toolset Stubs And Policy Tests

**Goal:** Register a dedicated `lingneng` toolset with safe stub tools and prove no Hermes high-risk defaults are exposed through it.

**Files:**
- Create: `lingneng/tools/__init__.py`
- Create: `lingneng/tools/stubs.py`
- Create: `lingneng/tools/toolset.py`
- Modify: `toolsets.py`
- Create: `tests/lingneng/tools/test_toolset_policy.py`

- [ ] **Step 1: Reload durable context**

Run:

```bash
sed -n '1,220p' LINGNENG_MIGRATION_CONTEXT.md
sed -n '1,360p' docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md
sed -n '1,260p' docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md
sed -n '1,520p' docs/lingneng-migration/specs/2026-06-06-phase-3-lingneng-toolset-security-spec.md
```

Expected: files define Phase 3 as stub-only toolset and security-boundary work.

- [ ] **Step 2: Write failing toolset policy tests**

Create `tests/lingneng/tools/test_toolset_policy.py`:

```python
from __future__ import annotations

import json

import lingneng.tools.toolset  # noqa: F401
from lingneng.tools.stubs import LINGNENG_TOOL_NAMES, handler_for
from model_tools import get_tool_definitions
from toolsets import resolve_toolset, validate_toolset
from tools.registry import registry


APPROVED_LINGNENG_TOOLS = {
    "retrieve_rag",
    "list_skills",
    "search_skills",
    "read_skill",
    "read_skill_resource",
    "document_generation",
    "image_generation",
    "chart_visualization",
    "read_workspace",
    "write_workspace",
}

DISALLOWED_HERMES_TOOLS = {
    "terminal",
    "web_search",
    "process",
    "read_file",
    "write_file",
    "patch",
    "search_files",
    "browser_navigate",
    "browser_snapshot",
    "browser_click",
    "browser_type",
    "browser_scroll",
    "browser_back",
    "browser_press",
    "browser_get_images",
    "browser_vision",
    "browser_console",
    "browser_cdp",
    "browser_dialog",
    "execute_code",
    "delegate_task",
    "send_message",
    "kanban_show",
    "kanban_list",
    "kanban_complete",
    "kanban_block",
    "kanban_heartbeat",
    "kanban_comment",
    "kanban_create",
    "kanban_link",
    "kanban_unblock",
}


def test_lingneng_toolset_is_valid_and_resolves_only_approved_tools():
    assert validate_toolset("lingneng") is True
    assert set(resolve_toolset("lingneng")) == APPROVED_LINGNENG_TOOLS
    assert set(resolve_toolset("lingneng")).isdisjoint(DISALLOWED_HERMES_TOOLS)


def test_lingneng_tool_registry_entries_are_registered():
    assert set(LINGNENG_TOOL_NAMES) == APPROVED_LINGNENG_TOOLS
    for tool_name in APPROVED_LINGNENG_TOOLS:
        entry = registry.get_entry(tool_name)
        assert entry is not None
        assert entry.toolset == "lingneng"


def test_lingneng_tool_definitions_expose_only_lingneng_schemas():
    definitions = get_tool_definitions(
        enabled_toolsets=["lingneng"],
        disabled_toolsets=["kanban"],
        quiet_mode=True,
    )
    names = {tool["function"]["name"] for tool in definitions}

    assert names == APPROVED_LINGNENG_TOOLS
    assert names.isdisjoint(DISALLOWED_HERMES_TOOLS)
    for definition in definitions:
        schema = definition["function"]
        assert schema["description"]
        assert schema["parameters"]["type"] == "object"
        assert "properties" in schema["parameters"]
        assert schema["parameters"]["additionalProperties"] is False


def test_lingneng_stub_handlers_return_not_configured_shape():
    forbidden_keys = {
        "args",
        "request",
        "payload",
        "history",
        "traceback",
        "exception",
        "api_key",
        "token",
        "secret",
    }
    for tool_name in APPROVED_LINGNENG_TOOLS:
        result = json.loads(handler_for(tool_name)({"query": "hello"}))
        assert result["success"] is False
        assert result["code"] == "NOT_CONFIGURED"
        assert result["tool_name"] == tool_name
        assert result["phase"] == "phase_3_stub"
        assert "not configured" in result["message"].lower()
        assert forbidden_keys.isdisjoint(result)
```

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_toolset_policy.py -q
```

Expected: FAIL because `lingneng.tools` modules and the static `lingneng`
toolset entry do not exist.

- [ ] **Step 4: Create LingNeng tools package marker**

Create `lingneng/tools/__init__.py`:

```python
"""LingNeng business tool registration and stub handlers."""
```

- [ ] **Step 5: Implement stub schemas and handlers**

Create `lingneng/tools/stubs.py` with this structure:

```python
from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from typing import Any


LINGNENG_TOOL_NAMES = (
    "retrieve_rag",
    "list_skills",
    "search_skills",
    "read_skill",
    "read_skill_resource",
    "document_generation",
    "image_generation",
    "chart_visualization",
    "read_workspace",
    "write_workspace",
)


def _string(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def _integer(description: str, minimum: int | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "integer", "description": description}
    if minimum is not None:
        schema["minimum"] = minimum
    return schema


def _object_schema(
    description: str,
    properties: Mapping[str, dict[str, Any]],
    required: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "description": description,
        "parameters": {
            "type": "object",
            "properties": dict(properties),
            "required": list(required),
            "additionalProperties": False,
        },
    }


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "retrieve_rag": _object_schema(
        "Retrieve LingNeng business knowledge. Phase 3 returns NOT_CONFIGURED.",
        {
            "query": _string("Business question to retrieve context for."),
            "top_k": _integer("Maximum number of references to retrieve.", minimum=1),
            "filters": {
                "type": "object",
                "description": "Business filters.",
                "additionalProperties": True,
            },
        },
        ("query",),
    ),
    "list_skills": _object_schema(
        "List LingNeng employee skills. Phase 3 returns NOT_CONFIGURED.",
        {"employee_type": _string("Optional employee type filter.")},
    ),
    "search_skills": _object_schema(
        "Search LingNeng employee skills. Phase 3 returns NOT_CONFIGURED.",
        {
            "query": _string("Skill search query."),
            "employee_type": _string("Optional employee type filter."),
        },
        ("query",),
    ),
    "read_skill": _object_schema(
        "Read a LingNeng skill. Phase 3 returns NOT_CONFIGURED.",
        {"skill_id": _string("Skill identifier.")},
        ("skill_id",),
    ),
    "read_skill_resource": _object_schema(
        "Read a LingNeng skill resource. Phase 3 returns NOT_CONFIGURED.",
        {
            "skill_id": _string("Skill identifier."),
            "resource_id": _string("Resource identifier."),
        },
        ("skill_id", "resource_id"),
    ),
    "document_generation": _object_schema(
        "Request LingNeng document generation. Phase 3 returns NOT_CONFIGURED.",
        {
            "instruction": _string("Document generation instruction."),
            "format": _string("Optional output format."),
        },
        ("instruction",),
    ),
    "image_generation": _object_schema(
        "Request LingNeng image generation. Phase 3 returns NOT_CONFIGURED.",
        {
            "prompt": _string("Image prompt."),
            "style": _string("Optional visual style."),
        },
        ("prompt",),
    ),
    "chart_visualization": _object_schema(
        "Request LingNeng chart generation. Phase 3 returns NOT_CONFIGURED.",
        {
            "instruction": _string("Chart instruction."),
            "data": {
                "type": "object",
                "description": "Optional chart data.",
                "additionalProperties": True,
            },
        },
        ("instruction",),
    ),
    "read_workspace": _object_schema(
        "Read from a LingNeng-controlled workspace. Phase 3 returns NOT_CONFIGURED.",
        {
            "path": _string("Workspace-relative path."),
            "purpose": _string("Why the content is needed."),
        },
        ("path",),
    ),
    "write_workspace": _object_schema(
        "Write through a LingNeng-controlled workspace. Phase 3 returns NOT_CONFIGURED.",
        {
            "path": _string("Workspace-relative path."),
            "content": _string("Content to write."),
            "purpose": _string("Why the write is needed."),
        },
        ("path", "content"),
    ),
}


def not_configured_result(tool_name: str) -> str:
    return json.dumps(
        {
            "success": False,
            "code": "NOT_CONFIGURED",
            "tool_name": tool_name,
            "phase": "phase_3_stub",
            "message": (
                f"LingNeng tool '{tool_name}' is not configured in this "
                "runtime phase."
            ),
        },
        ensure_ascii=False,
    )


def handler_for(tool_name: str) -> Callable[[dict[str, Any]], str]:
    def _handler(args: dict[str, Any] | None = None, **kwargs: Any) -> str:
        return not_configured_result(tool_name)

    return _handler


def iter_tool_entries() -> Iterator[tuple[str, dict[str, Any], Callable[[dict[str, Any]], str]]]:
    for tool_name in LINGNENG_TOOL_NAMES:
        yield tool_name, TOOL_SCHEMAS[tool_name], handler_for(tool_name)
```

- [ ] **Step 6: Register LingNeng tools**

Create `lingneng/tools/toolset.py`:

```python
from __future__ import annotations

from lingneng.tools.stubs import iter_tool_entries
from tools.registry import registry


for _tool_name, _schema, _handler in iter_tool_entries():
    registry.register(
        name=_tool_name,
        toolset="lingneng",
        schema={"name": _tool_name, **_schema},
        handler=_handler,
        description=_schema["description"],
    )
```

- [ ] **Step 7: Add static LingNeng toolset entry**

Modify `toolsets.py` and add this entry near the basic/scenario toolsets:

```python
    "lingneng": {
        "description": (
            "LingNeng Java API business toolset. Phase 3 exposes only "
            "LingNeng-owned NOT_CONFIGURED stubs; real business adapters "
            "land in later phases."
        ),
        "tools": [
            "retrieve_rag",
            "list_skills",
            "search_skills",
            "read_skill",
            "read_skill_resource",
            "document_generation",
            "image_generation",
            "chart_visualization",
            "read_workspace",
            "write_workspace",
        ],
        "includes": [],
    },
```

- [ ] **Step 8: Run focused tests and verify pass**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_toolset_policy.py -q
```

Expected: PASS.

- [ ] **Step 9: Run task review checks**

Run:

```bash
git diff --check
rg -n "T[B]D|T[O]DO|t[o]do|fill[[:space:]]in|implement[[:space:]]later|place[h]older|待[补]充|待[定]|占[位]" lingneng tests/lingneng docs/lingneng-migration/plans/2026-06-06-phase-3-lingneng-toolset-security-plan.md docs/lingneng-migration/specs/2026-06-06-phase-3-lingneng-toolset-security-spec.md
```

Expected: `git diff --check` exits 0; incomplete-marker scan exits 1 with no
matches.

- [ ] **Step 10: Commit and push**

Run:

```bash
git add toolsets.py lingneng/tools tests/lingneng/tools/test_toolset_policy.py
git commit -m "feat: 增加灵能专用工具集"
git push origin dev
```

---

### Task 3.2: Agent Step Event Model And Bridge Helpers

**Goal:** Add the formal `AgentStepEvent` model and pure bridge helpers for started, succeeded, skipped, and failed tool progress.

**Files:**
- Modify: `lingneng/schemas/chat_events.py`
- Modify: `lingneng/events/bridge.py`
- Create: `tests/lingneng/events/test_agent_step_bridge.py`

- [ ] **Step 1: Reload durable context**

Run:

```bash
sed -n '1,220p' LINGNENG_MIGRATION_CONTEXT.md
sed -n '1,360p' docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md
sed -n '1,260p' docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md
sed -n '1,520p' docs/lingneng-migration/specs/2026-06-06-phase-3-lingneng-toolset-security-spec.md
```

Expected: files define `AgentStepEvent` and helper functions as Phase 3 scope.

- [ ] **Step 2: Write failing agent-step bridge tests**

Create `tests/lingneng/events/test_agent_step_bridge.py`:

```python
from __future__ import annotations

from pydantic import ValidationError
import pytest

from lingneng.events.bridge import (
    agent_step_completed,
    agent_step_skipped,
    agent_step_started,
)
from lingneng.schemas.chat_events import AgentStepEvent, FORMAL_EVENT_NAMES


def test_agent_step_is_formal_event_name():
    assert "agent_step" in FORMAL_EVENT_NAMES


def test_agent_step_event_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        AgentStepEvent(
            sequence=1,
            step_id="tool-1",
            phase="tool",
            status="started",
            title="Tool started",
            short_text="Starting tool.",
            refs=[],
            raw_args={"query": "secret"},
        )


def test_tool_started_maps_to_public_agent_step():
    event = agent_step_started(
        sequence=1,
        tool_name="retrieve_rag",
        preview="query='sales'",
    )

    assert event.sequence == 1
    assert event.step_id == "tool-1"
    assert event.phase == "tool"
    assert event.status == "started"
    assert event.title == "retrieve_rag"
    assert event.short_text == "Starting retrieve_rag."
    assert event.summary == "query='sales'"
    assert event.refs == []


def test_tool_success_maps_to_public_agent_step():
    event = agent_step_completed(
        sequence=2,
        tool_name="retrieve_rag",
        duration=1.25,
        is_error=False,
        result='{"success": false, "code": "NOT_CONFIGURED"}',
    )

    assert event.sequence == 2
    assert event.step_id == "tool-2"
    assert event.status == "succeeded"
    assert event.short_text == "Completed retrieve_rag."
    assert event.summary == "Duration: 1.25s"


def test_tool_skip_maps_to_public_agent_step():
    event = agent_step_skipped(
        sequence=3,
        tool_name="retrieve_rag",
        reason="blocked by policy",
    )

    assert event.sequence == 3
    assert event.step_id == "tool-3"
    assert event.status == "skipped"
    assert event.short_text == "Skipped retrieve_rag."
    assert event.summary == "blocked by policy"


def test_tool_failure_does_not_leak_internal_exception_text():
    event = agent_step_completed(
        sequence=4,
        tool_name="retrieve_rag",
        duration=0.5,
        is_error=True,
        result="RuntimeError: private provider detail api_key=secret",
    )

    dumped = event.model_dump_json()
    assert event.status == "failed"
    assert event.short_text == "retrieve_rag failed."
    assert event.summary == "Tool failed with a public error summary."
    assert "private provider detail" not in dumped
    assert "api_key" not in dumped
    assert "secret" not in dumped
```

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/events/test_agent_step_bridge.py -q
```

Expected: FAIL because `AgentStepEvent` and bridge helpers do not exist.

- [ ] **Step 4: Add AgentStepEvent model**

Modify `lingneng/schemas/chat_events.py`:

```python
AgentStepPhase = Literal["tool"]
AgentStepStatus = Literal["started", "succeeded", "skipped", "failed"]


class AgentStepEvent(LingNengEventModel):
    sequence: int
    step_id: str
    phase: AgentStepPhase
    status: AgentStepStatus
    title: str
    short_text: str
    summary: str | None = None
    refs: list[dict] = Field(default_factory=list)
```

Keep `LingNengEventModel.model_config = ConfigDict(extra="forbid")`, so
`AgentStepEvent` rejects unknown fields.

- [ ] **Step 5: Add bridge helpers**

Modify `lingneng/events/bridge.py`:

```python
from typing import Any

from lingneng.schemas.chat_events import (
    AgentStepEvent,
    AnswerDeltaEvent,
    FinalEvent,
    RunStartedEvent,
)


def _tool_step_id(sequence: int) -> str:
    return f"tool-{sequence}"


def _public_tool_name(tool_name: str) -> str:
    safe = "".join(ch for ch in tool_name if ch.isalnum() or ch in {"_", "-", "."})
    return safe or "tool"


def agent_step_started(
    sequence: int,
    tool_name: str,
    preview: str | None = None,
) -> AgentStepEvent:
    safe_name = _public_tool_name(tool_name)
    return AgentStepEvent(
        sequence=sequence,
        step_id=_tool_step_id(sequence),
        phase="tool",
        status="started",
        title=safe_name,
        short_text=f"Starting {safe_name}.",
        summary=preview,
        refs=[],
    )


def agent_step_completed(
    sequence: int,
    tool_name: str,
    duration: float | None = None,
    is_error: bool = False,
    result: Any = None,
) -> AgentStepEvent:
    safe_name = _public_tool_name(tool_name)
    if is_error:
        return AgentStepEvent(
            sequence=sequence,
            step_id=_tool_step_id(sequence),
            phase="tool",
            status="failed",
            title=safe_name,
            short_text=f"{safe_name} failed.",
            summary="Tool failed with a public error summary.",
            refs=[],
        )
    summary = f"Duration: {duration:.2f}s" if duration is not None else None
    return AgentStepEvent(
        sequence=sequence,
        step_id=_tool_step_id(sequence),
        phase="tool",
        status="succeeded",
        title=safe_name,
        short_text=f"Completed {safe_name}.",
        summary=summary,
        refs=[],
    )


def agent_step_skipped(
    sequence: int,
    tool_name: str,
    reason: str | None = None,
) -> AgentStepEvent:
    safe_name = _public_tool_name(tool_name)
    return AgentStepEvent(
        sequence=sequence,
        step_id=_tool_step_id(sequence),
        phase="tool",
        status="skipped",
        title=safe_name,
        short_text=f"Skipped {safe_name}.",
        summary=reason,
        refs=[],
    )
```

- [ ] **Step 6: Run focused tests and verify pass**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/events/test_agent_step_bridge.py -q
```

Expected: PASS.

- [ ] **Step 7: Run related schema/event tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/schemas/test_chat_event_schema.py tests/lingneng/events/test_agent_step_bridge.py -q
```

Expected: PASS.

- [ ] **Step 8: Run task review checks**

Run:

```bash
git diff --check
rg -n "T[B]D|T[O]DO|t[o]do|fill[[:space:]]in|implement[[:space:]]later|place[h]older|待[补]充|待[定]|占[位]" lingneng tests/lingneng docs/lingneng-migration/plans/2026-06-06-phase-3-lingneng-toolset-security-plan.md docs/lingneng-migration/specs/2026-06-06-phase-3-lingneng-toolset-security-spec.md
```

Expected: `git diff --check` exits 0; incomplete-marker scan exits 1 with no
matches.

- [ ] **Step 9: Commit and push**

Run:

```bash
git add lingneng/schemas/chat_events.py lingneng/events/bridge.py tests/lingneng/events/test_agent_step_bridge.py
git commit -m "feat: 增加灵能工具进度事件"
git push origin dev
```

---

### Task 3.3: Hermes Adapter Wiring And Phase 3 Verification

**Goal:** Wire the dedicated LingNeng toolset and `agent_step` events into the Java API Hermes stream, then verify the complete Phase 3 contract.

**Files:**
- Modify: `lingneng/runtime/agent_adapter.py`
- Modify: `lingneng/runtime/hermes_adapter.py`
- Modify: `lingneng/api/routes.py`
- Modify: `tests/lingneng/runtime/test_hermes_adapter_config.py`
- Modify: `tests/lingneng/runtime/test_hermes_answer_stream.py`
- Create or modify: `tests/lingneng/api/test_chat_stream_contract.py` only if
  route-level `agent_step` encoding needs focused coverage outside runtime
  tests.

- [ ] **Step 1: Reload durable context**

Run:

```bash
sed -n '1,220p' LINGNENG_MIGRATION_CONTEXT.md
sed -n '1,360p' docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md
sed -n '1,260p' docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md
sed -n '1,520p' docs/lingneng-migration/specs/2026-06-06-phase-3-lingneng-toolset-security-spec.md
```

Expected: files require `enabled_toolsets=["lingneng"]`, route `agent_step`
encoding, and adapter callback bridging.

- [ ] **Step 2: Write failing adapter configuration update**

Modify `tests/lingneng/runtime/test_hermes_adapter_config.py` in
`test_hermes_adapter_constructs_agent_with_no_tool_lingneng_context`:

```python
    assert kwargs["enabled_toolsets"] == ["lingneng"]
    assert kwargs["disabled_toolsets"] == ["kanban"]
```

Rename the test to:

```python
async def test_hermes_adapter_constructs_agent_with_lingneng_tool_context(tmp_path):
```

Add this focused test to the same file:

```python
def test_hermes_adapter_import_does_not_register_lingneng_tools_in_fake_mode():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import lingneng.runtime; "
                "print('lingneng.tools.toolset' in sys.modules)"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False"
```

- [ ] **Step 3: Write failing adapter agent-step stream test**

Add this fake agent to `tests/lingneng/runtime/test_hermes_answer_stream.py`:

```python
class ToolProgressAgent:
    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")
        self.tool_progress_callback = kwargs.get("tool_progress_callback")

    def run_conversation(self, *args, **kwargs):
        self.tool_progress_callback(
            "tool.started",
            "retrieve_rag",
            "query='sales'",
            {"query": "sales"},
        )
        self.tool_progress_callback(
            "tool.completed",
            "retrieve_rag",
            None,
            None,
            duration=0.25,
            is_error=False,
            result='{"success": false, "code": "NOT_CONFIGURED"}',
        )
        return {"final_response": "完成", "messages": []}
```

Add this test:

```python
@pytest.mark.asyncio
async def test_tool_progress_callback_becomes_agent_step_events(tmp_path):
    request, resolved = request_and_session()
    adapter = HermesAgentRunAdapter(settings(tmp_path), agent_cls=ToolProgressAgent)

    events = [event async for event in adapter.stream(request, resolved, "run-1")]
    agent_steps = [event for event in events if event.__class__.__name__ == "AgentStepEvent"]

    assert [event.status for event in agent_steps] == ["started", "succeeded"]
    assert [event.sequence for event in agent_steps] == [1, 2]
    assert agent_steps[0].short_text == "Starting retrieve_rag."
    assert agent_steps[0].summary == "query='sales'"
    assert agent_steps[1].short_text == "Completed retrieve_rag."
    assert events[-1].answer == "完成"
```

- [ ] **Step 4: Write failing route event-name test**

Add this test to `tests/lingneng/api/test_chat_stream_contract.py` or the most
focused existing route test file:

```python
from lingneng.schemas.chat_events import AgentStepEvent


class AgentStepAdapter:
    async def stream(self, request, resolved_session, run_id):
        yield RunStartedEvent(run_id=run_id, request_id=request.request_id)
        yield AgentStepEvent(
            sequence=1,
            step_id="tool-1",
            phase="tool",
            status="started",
            title="retrieve_rag",
            short_text="Starting retrieve_rag.",
            refs=[],
        )
        yield AnswerDeltaEvent(text="完成", sequence=1)
        yield FinalEvent(run_id=run_id, status="succeeded", answer="完成")


def test_chat_stream_encodes_agent_step_event(tmp_path):
    app = create_app(
        settings=settings(tmp_path),
        adapter=AgentStepAdapter(),
        run_store=LingNengRunStore(tmp_path / "runs.sqlite3"),
    )
    response = post(TestClient(app), full_payload())
    frames = parse_sse(response.text)

    assert response.status_code == 200
    assert [event for event, _ in frames] == [
        "run_started",
        "agent_step",
        "answer_delta",
        "final",
    ]
    assert frames[1][1]["status"] == "started"
```

If the target test file already has `settings`, `post`, and `parse_sse`
helpers, reuse them. Otherwise define local helpers following
`tests/lingneng/api/test_chat_stream_idempotency.py`.

- [ ] **Step 5: Run focused tests and confirm failure**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime/test_hermes_adapter_config.py tests/lingneng/runtime/test_hermes_answer_stream.py tests/lingneng/api/test_chat_stream_contract.py -q
```

Expected: FAIL because adapter still passes `enabled_toolsets=[]`,
`AgentStepEvent` is not in `LingNengStreamEvent`, `tool_progress_callback` is
not wired, and route `_event_name()` does not handle `AgentStepEvent`.

- [ ] **Step 6: Update stream event union**

Modify `lingneng/runtime/agent_adapter.py`:

```python
from lingneng.schemas.chat_events import (
    AgentStepEvent,
    AnswerDeltaEvent,
    ErrorEvent,
    FinalEvent,
    RunStartedEvent,
)


LingNengStreamEvent = Union[
    RunStartedEvent,
    AgentStepEvent,
    AnswerDeltaEvent,
    FinalEvent,
    ErrorEvent,
]
```

- [ ] **Step 7: Update route event-name mapping**

Modify `lingneng/api/routes.py`:

```python
from lingneng.schemas.chat_events import (
    AgentStepEvent,
    AnswerDeltaEvent,
    ErrorEvent,
    FinalEvent,
    RunStartedEvent,
)
```

Then update `_event_name()`:

```python
def _event_name(
    event: RunStartedEvent | AgentStepEvent | AnswerDeltaEvent | FinalEvent | ErrorEvent,
) -> str:
    if isinstance(event, RunStartedEvent):
        return "run_started"
    if isinstance(event, AgentStepEvent):
        return "agent_step"
    if isinstance(event, AnswerDeltaEvent):
        return "answer_delta"
    if isinstance(event, FinalEvent):
        return "final"
    if isinstance(event, ErrorEvent):
        return "error"
    _unsupported_event(event)
```

- [ ] **Step 8: Wire LingNeng toolset and tool progress in adapter**

Modify `lingneng/runtime/hermes_adapter.py`:

```python
from lingneng.events.bridge import (
    agent_step_completed,
    agent_step_started,
    answer_delta,
    final_answer,
    run_started,
)
from lingneng.schemas.chat_events import AgentStepEvent, AnswerDeltaEvent, ErrorEvent
```

Update the queue type inside `stream()`:

```python
queue: asyncio.Queue[AgentStepEvent | AnswerDeltaEvent | _ThreadResult] = asyncio.Queue()
```

Add a separate `tool_sequence` counter and callback inside `stream()`:

```python
tool_sequence = 0

def on_tool_progress(
    event_name: str,
    tool_name: str,
    preview: str | None = None,
    args: dict | None = None,
    **kwargs,
) -> None:
    nonlocal tool_sequence
    if event_name == "tool.started":
        tool_sequence += 1
        event = agent_step_started(
            sequence=tool_sequence,
            tool_name=tool_name,
            preview=preview,
        )
    elif event_name == "tool.completed":
        tool_sequence += 1
        event = agent_step_completed(
            sequence=tool_sequence,
            tool_name=tool_name,
            duration=kwargs.get("duration"),
            is_error=bool(kwargs.get("is_error")),
            result=kwargs.get("result"),
        )
    else:
        return
    loop.call_soon_threadsafe(queue.put_nowait, event)
```

Pass the callback through `_build_agent()`:

```python
agent = self._build_agent(
    resolved_session,
    stream_delta_callback=on_delta,
    tool_progress_callback=on_tool_progress,
)
```

Update `_build_agent()` signature and construction:

```python
def _build_agent(
    self,
    resolved_session: ResolvedSessionKey,
    stream_delta_callback=None,
    tool_progress_callback=None,
):
    import lingneng.tools.toolset  # noqa: F401

    agent = self.agent_cls(
        platform="lingneng",
        session_id=resolved_session.session_key,
        session_db=self.session_store.db,
        enabled_toolsets=["lingneng"],
        disabled_toolsets=["kanban"],
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
        stream_delta_callback=stream_delta_callback,
        tool_progress_callback=tool_progress_callback,
    )
```

Keep the existing `_without_kanban_worker_env()` and
`_install_lingneng_activity_tracker()` behavior unchanged.

- [ ] **Step 9: Run focused tests and verify pass**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime/test_hermes_adapter_config.py tests/lingneng/runtime/test_hermes_answer_stream.py tests/lingneng/api/test_chat_stream_contract.py -q
```

Expected: PASS.

- [ ] **Step 10: Run Phase 3 focused verification**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_toolset_policy.py tests/lingneng/events/test_agent_step_bridge.py tests/lingneng/runtime/test_hermes_adapter_config.py tests/lingneng/runtime/test_hermes_answer_stream.py -q
```

Expected: PASS.

- [ ] **Step 11: Run full LingNeng verification**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/config tests/lingneng/schemas tests/lingneng/session tests/lingneng/api tests/lingneng/runtime tests/lingneng/tools tests/lingneng/events tests/lingneng/contract -q
```

Expected: PASS.

- [ ] **Step 12: Run LingNengAI reference contract**

Run:

```bash
/Users/rotas/Documents/work/hailun/LingNengAI/.venv/bin/python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py -q
```

Expected: PASS.

- [ ] **Step 13: Run lint and task review checks**

Run:

```bash
uv run --extra dev python -m ruff check lingneng tests/lingneng
git diff --check
rg -n "T[B]D|T[O]DO|t[o]do|fill[[:space:]]in|implement[[:space:]]later|place[h]older|待[补]充|待[定]|占[位]" lingneng tests/lingneng docs/lingneng-migration/plans/2026-06-06-phase-3-lingneng-toolset-security-plan.md docs/lingneng-migration/specs/2026-06-06-phase-3-lingneng-toolset-security-spec.md
```

Expected: `ruff` passes; `git diff --check` exits 0; incomplete-marker scan
exits 1 with no matches.

- [ ] **Step 14: Commit and push**

Run:

```bash
git add lingneng/runtime/agent_adapter.py lingneng/runtime/hermes_adapter.py lingneng/api/routes.py tests/lingneng/runtime/test_hermes_adapter_config.py tests/lingneng/runtime/test_hermes_answer_stream.py tests/lingneng/api/test_chat_stream_contract.py
git commit -m "feat: 接入灵能工具进度流"
git push origin dev
```

## Phase 3 Final Review

After Task 3.3 is pushed, run a final code review over the Phase 3 implementation range.

Use:

```bash
git log --oneline --decorate -10
```

Set the Phase 3 review base to the commit before Task 3.1 and the head to the
latest `dev` commit. The reviewer must check:

- `lingneng` toolset exposes only approved LingNeng tools.
- High-risk Hermes defaults and the colliding Hermes `web_search` tool are
  absent from Java API tool definitions.
- Stub handlers return stable `NOT_CONFIGURED` JSON and do not include raw args
  or secrets.
- `HermesAgentRunAdapter` uses `enabled_toolsets=["lingneng"]` and keeps
  `disabled_toolsets=["kanban"]`.
- `agent_step` events are public, sanitized, and route-encoded.
- Phase 1 and Phase 2 SSE/idempotency/session behavior remains intact.
- No deployment, RAG, skills, artifact, attachment, or real backend work was
  pulled into Phase 3.

If the review finds Critical or Important issues, fix them before moving to
Phase 4. If no Critical or Important issues remain, Phase 3 is complete.
