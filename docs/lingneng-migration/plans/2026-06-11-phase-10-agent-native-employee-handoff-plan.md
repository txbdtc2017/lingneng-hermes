# Phase 10 Agent-Native Employee Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Hermes-native LingNeng employee handoff so the current employee agent can emit Java-compatible route events through a validated `employee_handoff` tool.

**Architecture:** Keep Hermes `AIAgent` as the only chat loop. Add a small `lingneng/routing/` layer for employee directory, route models, and pending confirmation storage, then expose one controlled `employee_handoff` tool through the existing `lingneng` toolset and bridge its tool result into P1 SSE route events.

**Tech Stack:** Python 3.11-3.13, Pydantic v2, SQLite, contextvars, Hermes tool registry/toolsets, FastAPI SSE facade, pytest, uv, ruff.

---

## Approved Spec

This plan implements:

```text
docs/lingneng-migration/specs/2026-06-11-phase-10-agent-native-employee-handoff-spec.md
```

Required context was reloaded before writing this plan:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-11-lingneng-business-capability-hermes-migration-spec.md`
- `docs/lingneng-migration/specs/2026-06-11-phase-9-hermes-native-skill-catalog-spec.md`
- `docs/lingneng-migration/specs/2026-06-11-phase-10-agent-native-employee-handoff-spec.md`

## Execution Gate

No additional user confirmation is required before execution if these accepted
decisions remain true:

- Do not add same-request automatic employee rerun.
- Use one tool named `employee_handoff`.
- Implement deterministic validation and pending-confirmation storage only.
- Keep compliance as event-schema boundary without a classifier or block flow.

If any of those changes, update the spec and this plan before code execution.

## Scope

Implement:

- route event Pydantic models
- route settings
- employee directory from Phase 9 skill catalog plus static fallback
- route model validation
- route pending-confirmation SQLite store
- real `employee_handoff` tool and context
- route event extraction in `lingneng/events/bridge.py`
- route event emission in `HermesAgentRunAdapter`
- prompt guidance for handoff behavior
- tests and final regression checks

Do not implement:

- a pre-agent router graph
- an LLM route classifier
- Java changes
- session-key changes
- cross-employee session merging
- RAG training
- attachment understanding
- provider wiring unrelated to route events
- workspace read/write
- deployment or CI/CD

## File Map

Create:

- `lingneng/routing/__init__.py`
  - Lazy package exports only. Importing `lingneng.routing` must not load
    `run_agent`.
- `lingneng/routing/employees.py`
  - Employee display names, static fallback directory, and catalog-backed
    directory builder.
- `lingneng/routing/models.py`
  - Tool-facing route command, normalized route result, candidate validation,
    and safe public envelope helpers.
- `lingneng/routing/store.py`
  - SQLite pending confirmation store with save, lookup, consume, expiry, and
    cleanup.
- `lingneng/tools/employee_handoff.py`
  - Context manager, request context builder, and real handler for
    `employee_handoff`.
- `tests/lingneng/routing/test_employee_directory.py`
- `tests/lingneng/routing/test_route_models.py`
- `tests/lingneng/routing/test_pending_store.py`
- `tests/lingneng/tools/test_employee_handoff_tool.py`
- `tests/lingneng/events/test_route_events.py`
- `tests/lingneng/runtime/test_hermes_adapter_route_events.py`

Modify:

- `lingneng/config/settings.py`
  - Add non-secret route settings.
- `lingneng/schemas/chat_events.py`
  - Add `RouteCandidate`, `RouteResultEvent`, `RouteSuggestionEvent`,
    `RouteConfirmRequiredEvent`, and `ComplianceBlockEvent`.
- `lingneng/events/bridge.py`
  - Parse route events from `employee_handoff` results and pass route trace into
    final events.
- `lingneng/tools/stubs.py`
  - Add `employee_handoff` schema and mark it as a real Phase 10 tool.
- `lingneng/tools/toolset.py`
  - Register `employee_handoff` handler.
- `toolsets.py`
  - Whitelist `employee_handoff` in the `lingneng` toolset.
- `lingneng/runtime/hermes_adapter.py`
  - Activate handoff context, collect route events, emit them after tool
    completion, and include route trace in final.
- `lingneng/skills/loader.py`
  - Add bounded handoff prompt guidance.
- `tests/lingneng/schemas/test_chat_event_schema.py`
- `tests/lingneng/config/test_settings.py`
- `tests/lingneng/tools/test_toolset_policy.py`
- `tests/lingneng/skills/test_skill_loader.py`
- `tests/lingneng/runtime/test_hermes_adapter_config.py`

Avoid modifying:

- `run_agent.py`
- `model_tools.py`
- unrelated Hermes toolsets
- gateway platform adapters
- old `/Users/rotas/Documents/work/hailun/LingNengAI` files

## Task 10.1: Add Route Event Schemas And Route Settings

**Files:**
- Modify: `lingneng/schemas/chat_events.py`
- Modify: `lingneng/config/settings.py`
- Modify: `tests/lingneng/schemas/test_chat_event_schema.py`
- Modify: `tests/lingneng/config/test_settings.py`

- [ ] **Step 1: Write failing route schema tests**

Add tests to `tests/lingneng/schemas/test_chat_event_schema.py`:

```python
import pytest
from pydantic import ValidationError

from lingneng.schemas.chat_events import (
    ComplianceBlockEvent,
    RouteCandidate,
    RouteConfirmRequiredEvent,
    RouteResultEvent,
    RouteSuggestionEvent,
)


def test_route_event_payloads_dump_without_event_field():
    result = RouteResultEvent(
        target_employee_type="marketing_content_creator",
        confidence=0.91,
        need_confirm=False,
        is_current_employee=False,
    )
    suggestion = RouteSuggestionEvent(
        current_employee_type="marketing_planner",
        target_employee_type="marketing_content_creator",
        confidence=0.88,
        reason="需要生成可直接发布的营销内容",
        reply="这个问题更适合由营销内容创作处理，我为你切换到对应数字员工。",
    )
    confirm = RouteConfirmRequiredEvent(
        query="做一个营销活动",
        candidates=[
            RouteCandidate(
                employee_type="marketing_planner",
                confidence=0.62,
                label="营销策划",
                reason="需要活动方案",
            ),
            RouteCandidate(
                employee_type="marketing_content_creator",
                confidence=0.58,
                label="营销内容创作",
                reason="需要文案内容",
            ),
        ],
        reply="这个问题可能需要不同数字员工处理，请选择一个方向。",
    )
    compliance = ComplianceBlockEvent(
        risk_level="medium",
        risk_categories=["policy"],
        reply="该请求暂时无法处理。",
    )

    assert "event" not in result.model_dump()
    assert "event" not in suggestion.model_dump()
    assert "event" not in confirm.model_dump()
    assert "event" not in compliance.model_dump()
    assert result.model_dump()["target_employee_type"] == "marketing_content_creator"
    assert suggestion.model_dump()["current_employee_type"] == "marketing_planner"
    assert confirm.model_dump()["candidates"][0]["label"] == "营销策划"


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_route_candidate_rejects_invalid_confidence(confidence):
    with pytest.raises(ValidationError):
        RouteCandidate(
            employee_type="marketing_planner",
            confidence=confidence,
            label="营销策划",
            reason="需要活动方案",
        )


@pytest.mark.parametrize("candidate_count", [0, 1, 5])
def test_route_confirm_required_rejects_wrong_candidate_count(candidate_count):
    candidates = [
        RouteCandidate(
            employee_type="marketing_planner",
            confidence=0.6,
            label="营销策划",
            reason="需要活动方案",
        )
        for _ in range(candidate_count)
    ]
    with pytest.raises(ValidationError):
        RouteConfirmRequiredEvent(
            query="做一个营销活动",
            candidates=candidates,
            reply="请选择处理方向。",
        )
```

- [ ] **Step 2: Write failing route settings tests**

Add to `tests/lingneng/config/test_settings.py`:

```python
def test_route_settings_defaults(tmp_path):
    settings = LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})

    assert settings.route_pending_db_path == tmp_path / "route_pending.sqlite3"
    assert settings.route_pending_ttl_seconds == 600
    assert settings.route_reason_max_chars == 300
    assert settings.route_reply_max_chars == 500


def test_route_settings_from_env(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path / "runtime"),
            "LINGNENG_ROUTE_PENDING_DB_PATH": str(tmp_path / "route.sqlite3"),
            "LINGNENG_ROUTE_PENDING_TTL_SECONDS": "120",
            "LINGNENG_ROUTE_REASON_MAX_CHARS": "80",
            "LINGNENG_ROUTE_REPLY_MAX_CHARS": "160",
        }
    )

    assert settings.route_pending_db_path == tmp_path / "route.sqlite3"
    assert settings.route_pending_ttl_seconds == 120
    assert settings.route_reason_max_chars == 80
    assert settings.route_reply_max_chars == 160
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/schemas/test_chat_event_schema.py \
  tests/lingneng/config/test_settings.py \
  -q
```

Expected: fail because route event models and route settings are not defined.

- [ ] **Step 4: Implement event models**

In `lingneng/schemas/chat_events.py`:

- Import `model_validator` from Pydantic.
- Reuse existing `EmployeeType` from `lingneng.schemas.chat_request`.
- Add models:

```python
class RouteCandidate(LingNengEventModel):
    employee_type: EmployeeType
    confidence: float = Field(ge=0, le=1)
    label: str
    reason: str


class RouteResultEvent(LingNengEventModel):
    target_employee_type: EmployeeType
    confidence: float = Field(ge=0, le=1)
    need_confirm: bool
    is_current_employee: bool


class RouteSuggestionEvent(LingNengEventModel):
    current_employee_type: EmployeeType
    target_employee_type: EmployeeType
    confidence: float = Field(ge=0, le=1)
    reason: str
    reply: str


class RouteConfirmRequiredEvent(LingNengEventModel):
    query: str
    candidates: list[RouteCandidate]
    reply: str

    @model_validator(mode="after")
    def validate_candidate_count(self) -> "RouteConfirmRequiredEvent":
        if len(self.candidates) < 2 or len(self.candidates) > 4:
            raise ValueError("route confirmation requires 2 to 4 candidates")
        employee_types = [candidate.employee_type for candidate in self.candidates]
        if len(employee_types) != len(set(employee_types)):
            raise ValueError("route confirmation candidates must be unique")
        return self


class ComplianceBlockEvent(LingNengEventModel):
    risk_level: str
    risk_categories: list[str]
    reply: str
```

Keep `FORMAL_EVENT_NAMES` unchanged.

- [ ] **Step 5: Implement route settings**

In `LingNengSettings`:

- Add fields:

```python
route_pending_db_path: Path | None = None
route_pending_ttl_seconds: int = Field(default=600, ge=1)
route_reason_max_chars: int = Field(default=300, ge=20)
route_reply_max_chars: int = Field(default=500, ge=20)
```

- Extend the existing `model_validator` to set:

```python
if self.route_pending_db_path is None:
    self.route_pending_db_path = self.runtime_dir / "route_pending.sqlite3"
```

- Extend `from_env()` to read:

```python
route_pending_value = source.get("LINGNENG_ROUTE_PENDING_DB_PATH")
route_pending_db_path=Path(route_pending_value) if route_pending_value else None
route_pending_ttl_seconds=int(source.get("LINGNENG_ROUTE_PENDING_TTL_SECONDS", "600"))
route_reason_max_chars=int(source.get("LINGNENG_ROUTE_REASON_MAX_CHARS", "300"))
route_reply_max_chars=int(source.get("LINGNENG_ROUTE_REPLY_MAX_CHARS", "500"))
```

- Add `route_pending_db_path` to `ready_summary()` as a string.

- [ ] **Step 6: Run task tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/schemas/test_chat_event_schema.py \
  tests/lingneng/config/test_settings.py \
  -q
```

Expected: pass.

- [ ] **Step 7: Commit and push**

Run:

```bash
git add \
  lingneng/schemas/chat_events.py \
  lingneng/config/settings.py \
  tests/lingneng/schemas/test_chat_event_schema.py \
  tests/lingneng/config/test_settings.py
git commit -m "feat: 增加员工跳转事件模型"
git push origin dev
```

Rollback: revert this commit. No runtime behavior depends on the new models
until later tasks wire the tool and bridge.

## Task 10.2: Add Employee Directory, Route Models, And Pending Store

**Files:**
- Create: `lingneng/routing/__init__.py`
- Create: `lingneng/routing/employees.py`
- Create: `lingneng/routing/models.py`
- Create: `lingneng/routing/store.py`
- Create: `tests/lingneng/routing/test_employee_directory.py`
- Create: `tests/lingneng/routing/test_route_models.py`
- Create: `tests/lingneng/routing/test_pending_store.py`

- [ ] **Step 1: Write failing employee directory tests**

Create `tests/lingneng/routing/test_employee_directory.py`:

```python
from lingneng.config.settings import LingNengSettings
from lingneng.routing.employees import (
    EMPLOYEE_PUBLIC_DISPLAY_NAMES,
    LingNengEmployeeDirectory,
)
from lingneng.schemas.chat_request import EmployeeType


def settings(tmp_path):
    return LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})


def test_static_employee_directory_covers_all_employee_types(tmp_path):
    directory = LingNengEmployeeDirectory(settings(tmp_path))
    items = directory.items()

    assert {item.employee_type for item in items} == {member for member in EmployeeType}
    assert EMPLOYEE_PUBLIC_DISPLAY_NAMES["marketing_content_creator"] == "营销内容创作"
    assert directory.label_for(EmployeeType.MARKETING_CONTENT_CREATOR) == "营销内容创作"


def test_employee_directory_reads_bundled_skill_metadata(tmp_path):
    directory = LingNengEmployeeDirectory(settings(tmp_path))
    item = directory.get(EmployeeType.MARKETING_CONTENT_CREATOR)

    assert item is not None
    assert item.employee_type is EmployeeType.MARKETING_CONTENT_CREATOR
    assert item.skill_id == "employee-marketing-content-creator"
    assert item.display_name
    assert isinstance(item.recommended_task_skills, list)
    assert isinstance(item.recommended_capabilities, list)
```

- [ ] **Step 2: Write failing route model tests**

Create `tests/lingneng/routing/test_route_models.py`:

```python
import pytest
from pydantic import ValidationError

from lingneng.routing.models import (
    EmployeeHandoffCommand,
    NormalizedRouteDecision,
    normalize_handoff_command,
)
from lingneng.schemas.chat_request import EmployeeType


def test_normalizes_suggest_command():
    command = normalize_handoff_command(
        {
            "action": "suggest",
            "target_employee_type": "marketing_content_creator",
            "confidence": 0.86,
            "reason": "需要生成可直接发布的营销内容",
            "reply": "这个问题更适合由营销内容创作处理。",
        },
        current_employee_type=EmployeeType.MARKETING_PLANNER,
        reason_max_chars=300,
        reply_max_chars=500,
    )

    assert isinstance(command, EmployeeHandoffCommand)
    assert command.action == "suggest"
    assert command.target_employee_type is EmployeeType.MARKETING_CONTENT_CREATOR


def test_confirm_rejects_duplicate_candidates():
    with pytest.raises(ValidationError):
        normalize_handoff_command(
            {
                "action": "confirm",
                "confidence": 0.5,
                "reason": "方向不明确",
                "reply": "请选择一个方向。",
                "candidates": [
                    {
                        "employee_type": "marketing_planner",
                        "confidence": 0.6,
                        "label": "营销策划",
                        "reason": "活动方案",
                    },
                    {
                        "employee_type": "marketing_planner",
                        "confidence": 0.5,
                        "label": "营销策划",
                        "reason": "也是活动方案",
                    },
                ],
            },
            current_employee_type=EmployeeType.MARKETING_CONTENT_CREATOR,
            reason_max_chars=300,
            reply_max_chars=500,
        )


def test_public_decision_dump_excludes_private_fields():
    decision = NormalizedRouteDecision(
        route_event_type="route_suggestion",
        terminal=True,
        current_employee_type=EmployeeType.MARKETING_PLANNER,
        target_employee_type=EmployeeType.MARKETING_CONTENT_CREATOR,
        confidence=0.86,
        reason="需要生成可直接发布的营销内容",
        reply="这个问题更适合由营销内容创作处理。",
        candidates=[],
        public_reply="这个问题更适合由营销内容创作处理。",
        degradation_codes=[],
    )

    data = decision.public_tool_result()

    assert data["success"] is True
    assert data["tool_name"] == "employee_handoff"
    assert data["route_event_type"] == "route_suggestion"
    assert data["route"]["target_employee_type"] == "marketing_content_creator"
    assert forbidden_keys().isdisjoint(data)
    assert forbidden_keys().isdisjoint(data["route"])


def forbidden_keys():
    return {
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
```

- [ ] **Step 3: Write failing pending store tests**

Create `tests/lingneng/routing/test_pending_store.py`:

```python
from datetime import timedelta

from lingneng.routing.store import LingNengRoutePendingStore, PendingRouteConfirmation
from lingneng.schemas.chat_events import RouteCandidate


def pending():
    return PendingRouteConfirmation(
        tenant_id="tenant-a",
        user_id="user-a",
        conversation_id="conv-a",
        request_id="req-1",
        query_message_id="msg-1",
        current_employee_type="marketing_planner",
        previous_user_query="做一个营销活动",
        clarification_question="请选择营销策划还是内容创作。",
        candidates=[
            RouteCandidate(
                employee_type="marketing_planner",
                confidence=0.6,
                label="营销策划",
                reason="活动方案",
            ),
            RouteCandidate(
                employee_type="marketing_content_creator",
                confidence=0.55,
                label="营销内容创作",
                reason="文案内容",
            ),
        ],
    )


def test_pending_store_saves_finds_and_consumes(tmp_path):
    store = LingNengRoutePendingStore(tmp_path / "route.sqlite3", ttl_seconds=600)
    record = store.save(pending())

    latest = store.latest(
        tenant_id="tenant-a",
        user_id="user-a",
        conversation_id="conv-a",
        current_employee_type="marketing_planner",
    )
    by_message = store.find_by_message_id(
        tenant_id="tenant-a",
        user_id="user-a",
        conversation_id="conv-a",
        current_employee_type="marketing_planner",
        query_message_id="msg-1",
    )

    assert latest is not None
    assert by_message is not None
    assert latest.request_id == "req-1"
    assert by_message.candidates[1].employee_type == "marketing_content_creator"
    consumed = store.consume(record.pending_id)
    assert consumed is not None
    assert store.consume(record.pending_id) is None


def test_pending_store_ignores_expired_records(tmp_path):
    store = LingNengRoutePendingStore(tmp_path / "route.sqlite3", ttl_seconds=1)
    record = store.save(pending())
    store.force_update_expires_at(record.pending_id, delta=timedelta(seconds=-5))

    assert store.latest(
        tenant_id="tenant-a",
        user_id="user-a",
        conversation_id="conv-a",
        current_employee_type="marketing_planner",
    ) is None
    assert store.cleanup_expired() == 1
```

- [ ] **Step 4: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/routing -q
```

Expected: fail because `lingneng.routing` does not exist.

- [ ] **Step 5: Implement `lingneng/routing/employees.py`**

Create:

```python
EMPLOYEE_PUBLIC_DISPLAY_NAMES = {
    "boss_assistant": "老板助手",
    "operation_specialist": "运营专员",
    "product_combo_advisor": "商品组合顾问",
    "marketing_planner": "营销策划",
    "marketing_content_creator": "营销内容创作",
    "member_operator": "会员运营",
}
```

Implement:

- `EmployeeDirectoryItem(BaseModel)`
- `LingNengEmployeeDirectory.__init__(settings: LingNengSettings)`
- `LingNengEmployeeDirectory.items() -> list[EmployeeDirectoryItem]`
- `LingNengEmployeeDirectory.get(employee_type: EmployeeType | str)`
- `LingNengEmployeeDirectory.label_for(employee_type: EmployeeType | str)`

Directory rules:

- Build from `LingNengSkillCatalog(settings).list_skills(kind="employee_base")`.
- Use package metadata when available.
- Fill any missing employee from `EMPLOYEE_PUBLIC_DISPLAY_NAMES`.
- Never return duplicate employee types.
- On catalog failure, return static fallback for all six employee types.

- [ ] **Step 6: Implement `lingneng/routing/models.py`**

Implement:

- `RouteToolCandidate`
- `EmployeeHandoffCommand`
- `NormalizedRouteDecision`
- `normalize_handoff_command(raw_args, current_employee_type, reason_max_chars, reply_max_chars)`
- `failure_tool_result(code: str, message: str) -> dict`

Validation rules:

- `action` is one of `current`, `suggest`, `confirm`.
- `confidence` is clamped only by Pydantic field constraints, not silently
  changed.
- `reason` is required for all actions.
- `reply` is required for `suggest` and `confirm`.
- `current` target must equal current employee.
- `suggest` target must be present.
- `confirm` must contain 2 to 4 unique candidates.
- Public strings are stripped, control characters removed, and bounded by
  settings values.

- [ ] **Step 7: Implement `lingneng/routing/store.py`**

Implement:

- `PendingRouteConfirmation(BaseModel)`
- `PendingRouteConfirmationRecord(BaseModel)`
- `LingNengRoutePendingStore`

SQLite table:

```sql
CREATE TABLE IF NOT EXISTS lingneng_route_pending (
    pending_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    query_message_id TEXT,
    current_employee_type TEXT NOT NULL,
    previous_user_query TEXT NOT NULL,
    clarification_question TEXT NOT NULL,
    candidates_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT
)
```

Methods:

- `save(pending: PendingRouteConfirmation) -> PendingRouteConfirmationRecord`
- `latest(tenant_id, user_id, conversation_id, current_employee_type) -> PendingRouteConfirmationRecord | None`
- `find_by_message_id(tenant_id, user_id, conversation_id, current_employee_type, query_message_id) -> PendingRouteConfirmationRecord | None`
- `consume(pending_id: str) -> PendingRouteConfirmationRecord | None`
- `cleanup_expired() -> int`
- `force_update_expires_at(pending_id: str, delta: timedelta) -> None` for tests

Use timezone-aware UTC ISO timestamps. Do not expose absolute DB paths in public
results.

- [ ] **Step 8: Run task tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/routing -q
```

Expected: pass.

- [ ] **Step 9: Commit and push**

Run:

```bash
git add lingneng/routing tests/lingneng/routing
git commit -m "feat: 增加员工跳转路由基础"
git push origin dev
```

Rollback: revert this commit. Later tasks depend on these modules, so revert
later route tool and bridge commits first if they already exist.

## Task 10.3: Add The `employee_handoff` Tool And Toolset Exposure

**Files:**
- Create: `lingneng/tools/employee_handoff.py`
- Modify: `lingneng/tools/stubs.py`
- Modify: `lingneng/tools/toolset.py`
- Modify: `toolsets.py`
- Create: `tests/lingneng/tools/test_employee_handoff_tool.py`
- Modify: `tests/lingneng/tools/test_toolset_policy.py`

- [ ] **Step 1: Write failing handoff tool tests**

Create `tests/lingneng/tools/test_employee_handoff_tool.py`:

```python
import json

from lingneng.config.settings import LingNengSettings
from lingneng.routing.store import LingNengRoutePendingStore
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from lingneng.tools.employee_handoff import (
    build_handoff_request_context,
    employee_handoff_context,
    employee_handoff_handler,
)
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def settings(tmp_path):
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_ROUTE_REASON_MAX_CHARS": "120",
            "LINGNENG_ROUTE_REPLY_MAX_CHARS": "180",
        }
    )


def context(tmp_path, payload=None):
    request = ChatStreamRequest.model_validate(payload or full_payload())
    cfg = settings(tmp_path)
    return build_handoff_request_context(
        settings=cfg,
        request=request,
        resolved_session=resolve_session_key(request),
        pending_store=LingNengRoutePendingStore(
            cfg.route_pending_db_path,
            ttl_seconds=cfg.route_pending_ttl_seconds,
        ),
    )


def dispatch(ctx, args):
    with employee_handoff_context(ctx):
        return json.loads(employee_handoff_handler(args))


def test_current_action_returns_route_result(tmp_path):
    payload = full_payload()
    payload["employee"]["employee_type"] = "marketing_content_creator"
    payload["routing"] = {}
    result = dispatch(
        context(tmp_path, payload),
        {
            "action": "current",
            "target_employee_type": "marketing_content_creator",
            "confidence": 0.9,
            "reason": "当前员工可以处理",
        },
    )

    assert result["success"] is True
    assert result["route_event_type"] == "route_result"
    assert result["terminal"] is False
    assert result["route"]["is_current_employee"] is True
    assert result["route"]["need_confirm"] is False


def test_suggest_action_returns_route_suggestion(tmp_path):
    payload = full_payload()
    payload["employee"]["employee_type"] = "marketing_planner"
    payload["routing"] = {}
    result = dispatch(
        context(tmp_path, payload),
        {
            "action": "suggest",
            "target_employee_type": "marketing_content_creator",
            "confidence": 0.86,
            "reason": "需要生成可直接发布的营销内容",
            "reply": "这个问题更适合由营销内容创作处理，我为你切换到对应数字员工。",
        },
    )

    assert result["success"] is True
    assert result["route_event_type"] == "route_suggestion"
    assert result["terminal"] is True
    assert result["public_reply"] == result["route"]["reply"]
    assert result["route"]["current_employee_type"] == "marketing_planner"
    assert result["route"]["target_employee_type"] == "marketing_content_creator"


def test_confirm_action_saves_pending_confirmation(tmp_path):
    payload = full_payload()
    payload["employee"]["employee_type"] = "marketing_planner"
    payload["routing"] = {}
    result = dispatch(
        context(tmp_path, payload),
        {
            "action": "confirm",
            "confidence": 0.52,
            "reason": "问题可能属于营销策划或内容创作",
            "reply": "请选择营销策划还是营销内容创作。",
            "candidates": [
                {
                    "employee_type": "marketing_planner",
                    "confidence": 0.62,
                    "label": "营销策划",
                    "reason": "需要活动方案",
                },
                {
                    "employee_type": "marketing_content_creator",
                    "confidence": 0.58,
                    "label": "营销内容创作",
                    "reason": "需要文案内容",
                },
            ],
        },
    )

    assert result["success"] is True
    assert result["route_event_type"] == "route_confirm_required"
    assert result["terminal"] is True
    assert result["pending_confirmation"]["saved"] is True
    assert result["route"]["candidates"][0]["employee_type"] == "marketing_planner"


def test_handoff_without_context_fails_closed():
    result = json.loads(
        employee_handoff_handler(
            {
                "action": "suggest",
                "target_employee_type": "marketing_content_creator",
                "confidence": 0.8,
                "reason": "需要内容创作",
                "reply": "切换到内容员工。",
            }
        )
    )

    assert result["success"] is False
    assert result["code"] == "HANDOFF_CONTEXT_MISSING"


def test_tool_result_excludes_forbidden_keys(tmp_path):
    result = dispatch(
        context(tmp_path),
        {
            "action": "suggest",
            "target_employee_type": "marketing_planner",
            "confidence": 0.8,
            "reason": "需要策划",
            "reply": "交给营销策划处理。",
        },
    )

    text = json.dumps(result, ensure_ascii=False)
    for forbidden in [
        "api_key",
        "secret",
        "token",
        "traceback",
        "history",
        "payload",
        "request",
        "args",
    ]:
        assert forbidden not in text
```

- [ ] **Step 2: Update failing toolset policy tests**

In `tests/lingneng/tools/test_toolset_policy.py`:

- Add `"employee_handoff"` to `APPROVED_LINGNENG_TOOLS`.
- Add `"employee_handoff"` to `REAL_PHASE_9_TOOLS` only after renaming the set to
  `REAL_LINGNENG_TOOLS` or creating a new `REAL_PHASE_10_TOOLS` set.
- Keep `STUB_ONLY_TOOLS = {"read_workspace", "write_workspace"}`.
- Add:

```python
def test_employee_handoff_registered_handler_is_not_phase_3_stub():
    result = json.loads(registry.dispatch("employee_handoff", {"action": "current"}))

    assert result["success"] is False
    assert result["tool_name"] == "employee_handoff"
    assert result.get("phase") != "phase_3_stub"
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/tools/test_employee_handoff_tool.py \
  tests/lingneng/tools/test_toolset_policy.py \
  -q
```

Expected: fail because `employee_handoff` is not implemented or whitelisted.

- [ ] **Step 4: Implement `lingneng/tools/employee_handoff.py`**

Implement:

- `EmployeeHandoffContext`
- `build_handoff_request_context(settings, request, resolved_session, pending_store=None)`
- `employee_handoff_context(context)`
- `employee_handoff_handler(args, **kwargs)`

Context fields:

```python
settings: LingNengSettings
tenant_id: str
user_id: str
conversation_id: str | None
session_key: str
request_id: str
query_message_id: str | None
query: str
current_employee_type: EmployeeType
confirmed_employee_type: EmployeeType | None
confirmation_message_id: str | None
employee_directory: LingNengEmployeeDirectory
pending_store: LingNengRoutePendingStore | None
```

Handler behavior:

- Missing context returns `HANDOFF_CONTEXT_MISSING`.
- Invalid args return `INVALID_HANDOFF_ARGUMENT`.
- Unknown employee returns `INVALID_TARGET_EMPLOYEE`.
- `current` returns `route_result`.
- `suggest` returns `route_suggestion`.
- `confirm` returns `route_confirm_required` and saves pending if
  `conversation_id` and `pending_store` are present.
- If `routing.confirmed_employee_type` exists in context, include
  `confirmation` metadata in the result and consume a matching pending record
  when found.
- Never include raw args, request body, history, traceback, or secrets in the
  result.

- [ ] **Step 5: Register schema and handler**

In `lingneng/tools/stubs.py`:

- Add `"employee_handoff"` to `LINGNENG_TOOL_NAMES`.
- Add it to `REAL_TOOL_NAMES`.
- Add schema:

```python
"employee_handoff": _object_schema(
    "employee_handoff",
    "Validate and emit a LingNeng employee handoff decision.",
    {
        "action": {
            "type": "string",
            "description": "Handoff action: current, suggest, or confirm.",
            "enum": ["current", "suggest", "confirm"],
        },
        "target_employee_type": _string("Target employee type when known."),
        "confidence": {
            "type": "number",
            "description": "Decision confidence between 0 and 1.",
            "minimum": 0,
            "maximum": 1,
        },
        "reason": _string("Short public reason for the decision."),
        "reply": _string("Public reply to show to the user for terminal handoff."),
        "candidates": {
            "type": "array",
            "description": "Candidate employees for confirm action.",
            "items": {
                "type": "object",
                "properties": {
                    "employee_type": _string("Candidate employee type."),
                    "confidence": {
                        "type": "number",
                        "description": "Candidate confidence between 0 and 1.",
                        "minimum": 0,
                        "maximum": 1,
                    },
                    "label": _string("Candidate display label."),
                    "reason": _string("Public candidate reason."),
                },
                "required": ["employee_type", "confidence", "reason"],
                "additionalProperties": False,
            },
        },
    },
    ("action", "confidence", "reason"),
)
```

In `lingneng/tools/toolset.py`:

- Import `employee_handoff_handler`.
- Add it to `_REAL_HANDLERS`.

In `toolsets.py`:

- Add `"employee_handoff"` to the `lingneng` tool list.

- [ ] **Step 6: Run task tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/tools/test_employee_handoff_tool.py \
  tests/lingneng/tools/test_toolset_policy.py \
  -q
```

Expected: pass.

- [ ] **Step 7: Commit and push**

Run:

```bash
git add \
  lingneng/tools/employee_handoff.py \
  lingneng/tools/stubs.py \
  lingneng/tools/toolset.py \
  toolsets.py \
  tests/lingneng/tools/test_employee_handoff_tool.py \
  tests/lingneng/tools/test_toolset_policy.py
git commit -m "feat: 增加员工跳转工具"
git push origin dev
```

Rollback: remove `employee_handoff` from `toolsets.py`,
`LINGNENG_TOOL_NAMES`, and `_REAL_HANDLERS`, then delete the tool module.

## Task 10.4: Bridge Handoff Tool Results Into SSE Route Events

**Files:**
- Modify: `lingneng/events/bridge.py`
- Modify: `lingneng/runtime/hermes_adapter.py`
- Create: `tests/lingneng/events/test_route_events.py`
- Create: `tests/lingneng/runtime/test_hermes_adapter_route_events.py`

- [ ] **Step 1: Write failing bridge tests**

Create `tests/lingneng/events/test_route_events.py`:

```python
import json

from lingneng.events.bridge import route_events_from_tool_result
from lingneng.schemas.chat_events import (
    RouteConfirmRequiredEvent,
    RouteResultEvent,
    RouteSuggestionEvent,
)


def payload(event_type, route):
    return json.dumps(
        {
            "success": True,
            "tool_name": "employee_handoff",
            "route_event_type": event_type,
            "terminal": event_type != "route_result",
            "public_reply": route.get("reply", ""),
            "route": route,
        },
        ensure_ascii=False,
    )


def test_bridge_extracts_route_result():
    events, trace = route_events_from_tool_result(
        tool_name="employee_handoff",
        result=payload(
            "route_result",
            {
                "target_employee_type": "marketing_content_creator",
                "confidence": 0.9,
                "need_confirm": False,
                "is_current_employee": True,
            },
        ),
    )

    assert [type(event) for event in events] == [RouteResultEvent]
    assert trace["route_event_type"] == "route_result"


def test_bridge_extracts_route_suggestion():
    events, trace = route_events_from_tool_result(
        tool_name="employee_handoff",
        result=payload(
            "route_suggestion",
            {
                "current_employee_type": "marketing_planner",
                "target_employee_type": "marketing_content_creator",
                "confidence": 0.86,
                "reason": "需要生成营销内容",
                "reply": "交给营销内容创作处理。",
            },
        ),
    )

    assert [type(event) for event in events] == [RouteSuggestionEvent]
    assert events[0].target_employee_type == "marketing_content_creator"


def test_bridge_extracts_route_confirm_required():
    events, trace = route_events_from_tool_result(
        tool_name="employee_handoff",
        result=payload(
            "route_confirm_required",
            {
                "query": "做一个营销活动",
                "reply": "请选择一个处理方向。",
                "candidates": [
                    {
                        "employee_type": "marketing_planner",
                        "confidence": 0.6,
                        "label": "营销策划",
                        "reason": "活动方案",
                    },
                    {
                        "employee_type": "marketing_content_creator",
                        "confidence": 0.55,
                        "label": "营销内容创作",
                        "reason": "文案内容",
                    },
                ],
            },
        ),
    )

    assert [type(event) for event in events] == [RouteConfirmRequiredEvent]
    assert len(events[0].candidates) == 2


def test_bridge_ignores_unrelated_tool():
    events, trace = route_events_from_tool_result(
        tool_name="retrieve_rag",
        result=payload("route_result", {}),
    )

    assert events == []
    assert trace is None
```

- [ ] **Step 2: Write failing adapter route event tests**

Create `tests/lingneng/runtime/test_hermes_adapter_route_events.py`:

```python
import json

import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.schemas.chat_events import FinalEvent, RouteSuggestionEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def settings(tmp_path):
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_AGENT_MODE": "hermes",
            "LINGNENG_INTERNAL_API_KEY": "key",
        }
    )


class HandoffToolProgressAgent:
    def __init__(self, **kwargs):
        self.tool_progress_callback = kwargs.get("tool_progress_callback")

    def run_conversation(self, *args, **kwargs):
        self.tool_progress_callback(
            "tool.completed",
            "employee_handoff",
            None,
            None,
            duration=0.01,
            is_error=False,
            result=json.dumps(
                {
                    "success": True,
                    "tool_name": "employee_handoff",
                    "route_event_type": "route_suggestion",
                    "terminal": True,
                    "public_reply": "交给营销内容创作处理。",
                    "route": {
                        "current_employee_type": "marketing_planner",
                        "target_employee_type": "marketing_content_creator",
                        "confidence": 0.86,
                        "reason": "需要生成营销内容",
                        "reply": "交给营销内容创作处理。",
                    },
                },
                ensure_ascii=False,
            ),
        )
        return {"final_response": "交给营销内容创作处理。", "messages": []}


@pytest.mark.asyncio
async def test_adapter_emits_route_event_before_final(tmp_path):
    payload = full_payload()
    payload["employee"]["employee_type"] = "marketing_planner"
    request = ChatStreamRequest.model_validate(payload)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path),
        agent_cls=HandoffToolProgressAgent,
    )

    events = [
        event async for event in adapter.stream(request, resolve_session_key(request), "run-1")
    ]
    names = [type(event).__name__ for event in events]

    assert "RouteSuggestionEvent" in names
    assert names.index("RouteSuggestionEvent") < names.index("FinalEvent")
    route_event = next(event for event in events if isinstance(event, RouteSuggestionEvent))
    final = events[-1]
    assert isinstance(final, FinalEvent)
    assert route_event.target_employee_type == "marketing_content_creator"
    assert final.trace_summary["route"]["route_event_type"] == "route_suggestion"
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/events/test_route_events.py \
  tests/lingneng/runtime/test_hermes_adapter_route_events.py \
  -q
```

Expected: fail because bridge extraction and adapter emission are not wired.

- [ ] **Step 4: Implement bridge extraction**

In `lingneng/events/bridge.py`:

- Import route models.
- Add `_ROUTE_TOOL_NAME = "employee_handoff"`.
- Add:

```python
RouteBridgeEvent = RouteResultEvent | RouteSuggestionEvent | RouteConfirmRequiredEvent


def route_events_from_tool_result(
    *,
    tool_name: str,
    result: Any,
) -> tuple[list[RouteBridgeEvent], dict[str, Any] | None]:
    # Parse only employee_handoff public results and return validated route events.
    # Invalid payloads return ([], None).
```

Rules:

- Ignore non-`employee_handoff` tools.
- Parse JSON via existing `_parse_tool_result`.
- Require `success is True`.
- Require `route_event_type`.
- Validate payload using the route event model.
- Return `([], None)` for malformed payloads.
- Return trace with only public fields:

```python
{
    "route_event_type": route_event_type,
    "terminal": bool(payload.get("terminal")),
    "target_employee_type": route.get("target_employee_type"),
    "current_employee_type": route.get("current_employee_type"),
    "confidence": route.get("confidence"),
}
```

- Extend `final_answer()` signature:

```python
def final_answer(
    run_id: str,
    answer: str,
    citations: list[dict[str, Any]] | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    settings: LingNengSettings | None = None,
    trace_summary: dict[str, Any] | None = None,
) -> FinalEvent:
```

Pass `trace_summary=trace_summary or {}` into `FinalEvent`.

- [ ] **Step 5: Wire adapter route emission**

In `lingneng/runtime/hermes_adapter.py`:

- Import `route_events_from_tool_result`.
- Add `route_trace: dict[str, Any] | None = None` near existing citations and
  artifacts collectors.
- In `on_tool_progress` for `"tool.completed"`, after artifact and RAG
  extraction, call:

```python
route_events, next_route_trace = route_events_from_tool_result(
    tool_name=tool_name,
    result=kwargs.get("result"),
)
if next_route_trace is not None:
    route_trace = next_route_trace
events = [event, *artifact_events, *rag_events, *route_events]
```

Use `nonlocal route_trace` in the callback.

- When yielding final:

```python
trace_summary = {"route": route_trace} if route_trace else {}
yield final_answer(
    run_id=run_id,
    answer=final_text,
    citations=rag_citations if request.stream_options.include_citations else [],
    artifacts=artifacts,
    settings=self.settings,
    trace_summary=trace_summary,
)
```

Keep existing RAG and artifact event order stable. Route events should be added
after the `agent_step` completion event for the tool and before `final`.

- [ ] **Step 6: Run task tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/events/test_route_events.py \
  tests/lingneng/runtime/test_hermes_adapter_route_events.py \
  tests/lingneng/runtime/test_hermes_answer_stream.py \
  -q
```

Expected: pass.

- [ ] **Step 7: Commit and push**

Run:

```bash
git add \
  lingneng/events/bridge.py \
  lingneng/runtime/hermes_adapter.py \
  tests/lingneng/events/test_route_events.py \
  tests/lingneng/runtime/test_hermes_adapter_route_events.py
git commit -m "feat: 串接员工跳转流式事件"
git push origin dev
```

Rollback: revert this commit. The `employee_handoff` tool can remain registered
but route SSE events will no longer be emitted until the bridge is restored.

## Task 10.5: Activate Handoff Context And Prompt Guidance

**Files:**
- Modify: `lingneng/runtime/hermes_adapter.py`
- Modify: `lingneng/skills/loader.py`
- Modify: `tests/lingneng/skills/test_skill_loader.py`
- Modify: `tests/lingneng/runtime/test_hermes_adapter_config.py`
- Modify: `tests/lingneng/runtime/test_hermes_adapter_route_events.py`

- [ ] **Step 1: Write failing prompt guidance tests**

Add to `tests/lingneng/skills/test_skill_loader.py`:

```python
from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.skills.loader import LingNengSkillLoader
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def test_skill_prompt_contains_handoff_guidance(tmp_path):
    settings = LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})
    request = ChatStreamRequest.model_validate(full_payload())
    prompt = LingNengSkillLoader(settings).build_prompt_context(request).to_prompt_text()

    assert "employee_handoff" in prompt
    assert "route_employee" not in prompt
    assert "entry_decision" not in prompt
    assert "/Users/rotas/Documents/work/hailun/LingNengAI" not in prompt
```

- [ ] **Step 2: Write failing adapter context tests**

Add to `tests/lingneng/runtime/test_hermes_adapter_route_events.py`:

```python
class HandoffContextProbeAgent:
    def __init__(self, **kwargs):
        pass

    def run_conversation(self, *args, **kwargs):
        import json

        from lingneng.tools.employee_handoff import employee_handoff_handler

        result = json.loads(
            employee_handoff_handler(
                {
                    "action": "suggest",
                    "target_employee_type": "marketing_content_creator",
                    "confidence": 1.0,
                    "reason": "用户已确认切换员工",
                    "reply": "我为你切换到营销内容创作。",
                }
            )
        )
        if not result["success"]:
            raise AssertionError(result)
        if result["route"]["target_employee_type"] != "marketing_content_creator":
            raise AssertionError(result)
        return {"final_response": "我为你切换到营销内容创作。", "messages": []}


@pytest.mark.asyncio
async def test_adapter_activates_employee_handoff_context(tmp_path):
    payload = full_payload()
    payload["employee"]["employee_type"] = "marketing_planner"
    payload["routing"]["confirmed_employee_type"] = "marketing_content_creator"
    request = ChatStreamRequest.model_validate(payload)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path),
        agent_cls=HandoffContextProbeAgent,
    )

    events = [
        event async for event in adapter.stream(request, resolve_session_key(request), "run-1")
    ]

    final = events[-1]
    assert isinstance(final, FinalEvent)
    assert final.status == "succeeded"
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/skills/test_skill_loader.py \
  tests/lingneng/runtime/test_hermes_adapter_route_events.py \
  -q
```

Expected: fail because prompt guidance and handoff context are not active.

- [ ] **Step 4: Activate handoff request context in adapter**

In `lingneng/runtime/hermes_adapter.py`:

- Import:

```python
from lingneng.tools.employee_handoff import (
    build_handoff_request_context,
    employee_handoff_context,
)
from lingneng.routing.store import LingNengRoutePendingStore
```

- Add helper:

```python
def _build_route_pending_store(settings: LingNengSettings) -> LingNengRoutePendingStore:
    return LingNengRoutePendingStore(
        settings.route_pending_db_path,
        ttl_seconds=settings.route_pending_ttl_seconds,
    )
```

- In `run_agent()`, before calling `agent.run_conversation`, build:

```python
handoff_context = build_handoff_request_context(
    settings=self.settings,
    request=request,
    resolved_session=resolved_session,
    pending_store=_build_route_pending_store(self.settings),
)
```

- Extend the context manager stack:

```python
with (
    lingneng_tool_context(self.settings),
    skill_tool_context(self.settings),
    employee_handoff_context(handoff_context),
):
    attachment_context = build_attachment_prompt_context(self.settings, request)
    agent = self._build_agent(
        resolved_session,
        active_session_id=active_session_id,
        stream_delta_callback=on_delta,
        tool_progress_callback=on_tool_progress,
        ephemeral_system_prompt=ephemeral_system_prompt,
    )
    rag_context = build_rag_request_context(
        settings=self.settings,
        request=request,
        resolved_session=resolved_session,
    )
    with rag_request_context(
        rag_context,
        provider=_build_rag_provider(self.settings),
    ):
        result = agent.run_conversation(
            request.query.content,
            system_message=self._build_system_message(request),
            conversation_history=history,
            task_id=run_id,
            persist_user_message=request.query.content,
        )
```

Keep `rag_request_context(rag_context, provider=_build_rag_provider(self.settings))`
scoped around `agent.run_conversation` as it is.

- [ ] **Step 5: Add bounded handoff prompt guidance**

In `lingneng/skills/loader.py`, import `SkillResourceManifest` from
`lingneng.skills.models` and add a private helper:

```python
def _handoff_guidance_fragment() -> SkillPromptFragment:
    return SkillPromptFragment(
        package_name="lingneng-employee-handoff-guidance",
        kind=SkillKind.INFRASTRUCTURE,
        version="1.0.0",
        description="员工跳转工具使用边界",
        body_excerpt=(
            "## Employee Handoff Guidance\n"
            "- Answer directly when the current employee can handle the request.\n"
            "- Use read_skill or search_skills when employee boundaries are unclear.\n"
            "- Do not hand off smalltalk, meta questions, or general assistant tasks.\n"
            "- Use employee_handoff action=suggest when another employee is clearly the better owner.\n"
            "- Use employee_handoff action=confirm when 2 to 4 employee choices are ambiguous.\n"
            "- After terminal suggest or confirm, reply with the tool public_reply and stop business execution for this turn.\n"
            "- Never invent employee types, employee names, hidden route thresholds, or private route reasons."
        ),
        resource_manifest=SkillResourceManifest(),
        display_name="员工跳转指引",
        recommended_task_skills=[],
        recommended_capabilities=[],
        tools=["employee_handoff", "search_skills", "read_skill"],
        truncated=False,
    )
```

In `lingneng/skills/models.py`, extend `SkillPromptContext` with:

```python
infrastructure_fragments: list[SkillPromptFragment] = Field(default_factory=list)
```

Update `to_prompt_text()` so each infrastructure fragment is rendered after the
selected skill and before warnings:

```python
for fragment in self.infrastructure_fragments:
    sections.append(
        "\n".join(
            [
                f"### Infrastructure Skill: {fragment.package_name}",
                *fragment.to_prompt_lines(),
            ]
        )
    )
```

In `LingNengSkillLoader.build_prompt_context()`, pass:

```python
infrastructure_fragments=[_handoff_guidance_fragment()]
```

Remove the old Phase 9 sentence from the default skill tool guidance:

```text
Do not require route or handoff tools in this phase; handoff/route belongs to Phase 10.
```

- [ ] **Step 6: Run task tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/skills/test_skill_loader.py \
  tests/lingneng/runtime/test_hermes_adapter_config.py \
  tests/lingneng/runtime/test_hermes_adapter_route_events.py \
  -q
```

Expected: pass.

- [ ] **Step 7: Commit and push**

Run:

```bash
git add \
  lingneng/runtime/hermes_adapter.py \
  lingneng/skills/loader.py \
  lingneng/skills/models.py \
  tests/lingneng/skills/test_skill_loader.py \
  tests/lingneng/runtime/test_hermes_adapter_config.py \
  tests/lingneng/runtime/test_hermes_adapter_route_events.py
git commit -m "feat: 注入员工跳转上下文"
git push origin dev
```

Rollback: remove `employee_handoff_context(handoff_context)` from the adapter and remove
the handoff guidance fragment from the loader. Earlier tool and schema commits
can remain in place while disabled from prompt use.

## Task 10.6: Final Regression, Safety Scans, And Acceptance Review

**Files:**
- Modify only if the checks below reveal a concrete regression in Phase 10
  files.

- [ ] **Step 1: Run focused Phase 10 tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/schemas/test_chat_event_schema.py \
  tests/lingneng/config/test_settings.py \
  tests/lingneng/routing \
  tests/lingneng/tools/test_employee_handoff_tool.py \
  tests/lingneng/tools/test_toolset_policy.py \
  tests/lingneng/events/test_route_events.py \
  tests/lingneng/runtime/test_hermes_adapter_route_events.py \
  tests/lingneng/skills/test_skill_loader.py \
  -q
```

Expected: pass.

- [ ] **Step 2: Run full LingNeng regression**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng -q
```

Expected: pass.

- [ ] **Step 3: Run lint**

Run:

```bash
uv run --extra dev python -m ruff check \
  lingneng/routing \
  lingneng/tools/employee_handoff.py \
  lingneng/schemas/chat_events.py \
  lingneng/events/bridge.py \
  lingneng/runtime/hermes_adapter.py \
  lingneng/skills \
  tests/lingneng
```

Expected: pass.

- [ ] **Step 4: Verify no old LingNengAI runtime imports**

Run:

```bash
rg -n "from app\\.|import app\\.|/Users/rotas/Documents/work/hailun/LingNengAI|route_employee|entry_decision|request_plan|history_policy|light_answer" \
  lingneng tests/lingneng
```

Expected: no output, except test names or comments that explicitly assert old
route node names are absent. If a test assertion creates output, inspect it and
confirm it is not a runtime import or prompt leak.

- [ ] **Step 5: Verify toolset boundary**

Run:

```bash
uv run --extra dev python - <<'PY'
from toolsets import resolve_toolset

tools = set(resolve_toolset("lingneng"))
print(sorted(tools))
assert "employee_handoff" in tools
assert "terminal" not in tools
assert "execute_code" not in tools
assert "browser_navigate" not in tools
PY
```

Expected: command prints LingNeng business tools and exits with status 0.

- [ ] **Step 6: Review acceptance criteria against spec**

Check these items manually:

- `employee_handoff` is a real registered tool.
- Route schemas dump without `event`.
- Bridge emits route events from `employee_handoff`.
- Confirm-required handoff saves pending confirmation.
- Confirmed employee request fields are available to handoff context.
- Prompt tells terminal handoff to stop business execution.
- No old `app.*` imports are present.
- No disallowed Hermes tools are exposed through `lingneng`.

- [ ] **Step 7: Commit final fixes if any were needed**

If Step 1 through Step 6 required changes, run:

```bash
git add \
  lingneng/routing \
  lingneng/tools/employee_handoff.py \
  lingneng/tools/stubs.py \
  lingneng/tools/toolset.py \
  lingneng/schemas/chat_events.py \
  lingneng/events/bridge.py \
  lingneng/runtime/hermes_adapter.py \
  lingneng/skills \
  toolsets.py \
  tests/lingneng
git commit -m "fix: 完善员工跳转验收项"
git push origin dev
```

If no changes were required, do not create an empty commit.

Rollback: use the per-task rollback notes. If only final verification fixes are
bad, revert the final fix commit first.

## Implementation Order

Execute strictly in this order:

1. Task 10.1: event schemas and settings.
2. Task 10.2: routing directory, models, and pending store.
3. Task 10.3: `employee_handoff` tool and toolset exposure.
4. Task 10.4: bridge extraction and adapter route event emission.
5. Task 10.5: adapter context and prompt guidance.
6. Task 10.6: final regression and acceptance review.

Do not start Task 10.4 before Task 10.3 passes because bridge tests rely on the
tool result contract. Do not start Task 10.5 before Task 10.4 passes because the
adapter context is only useful after route events can be emitted.

## Commit Policy

Each task has its own commit and push after verification passes. Commit messages
must remain Chinese with conventional prefixes:

- `feat: 增加员工跳转事件模型`
- `feat: 增加员工跳转路由基础`
- `feat: 增加员工跳转工具`
- `feat: 串接员工跳转流式事件`
- `feat: 注入员工跳转上下文`
- `fix: 完善员工跳转验收项`

Never push a task commit before that task's verification commands pass.

## Plan Self-Review

- Spec coverage: every Phase 10 requirement maps to a task: schemas and
  settings in Task 10.1, employee directory and pending store in Task 10.2,
  handoff tool and toolset in Task 10.3, bridge and adapter emission in Task
  10.4, prompt and confirmed request context in Task 10.5, and final
  acceptance in Task 10.6.
- Placeholder scan: no unfinished placeholder tokens remain.
- Type consistency: all planned code uses existing `EmployeeType`,
  `LingNengSettings`, `ChatStreamRequest`, `ResolvedSessionKey`,
  `LingNengSkillCatalog`, and existing adapter callback patterns.
- Scope check: the plan does not add a pre-agent router graph, LLM classifier,
  Java change, same-request rerun, cross-employee session merge, deployment
  change, RAG training, or unrelated provider work.
