# Phase 16 LingNeng Employee Answer Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate LingNeng digital employee answer semantics into Hermes-native skills, prompt contracts, deterministic fixtures, and guardrails without restoring the old LingNengAI graph runtime.

**Architecture:** Keep Hermes `AIAgent`, SessionDB, LingNeng toolset, provider contexts, and Java-compatible SSE unchanged. Put employee behavior in validated `skills/lingneng` packages, shared infrastructure contracts, bounded prompt injection, and tests that assert deterministic surfaces rather than live LLM wording.

**Tech Stack:** Python 3.11-3.13, pytest, Pydantic v2, YAML front matter, JSON fixtures, Hermes skill loader, LingNeng toolset.

---

## Approved Spec

This plan implements:

```text
docs/lingneng-migration/specs/2026-06-14-phase-16-employee-answer-semantics-spec.md
```

Reloaded before writing this plan:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-14-phase-16-employee-answer-semantics-spec.md`

## Execution Rules

- Execute from the current project directory on `dev`. Do not create a git worktree.
- Implement task-by-task with `superpowers:subagent-driven-development`.
- After each task, run the task verification command.
- Commit each completed task with the Chinese commit message listed in the task.
- Push the active branch after each task commit only when verification passes.
- Do not import or execute old `/Users/rotas/Documents/work/hailun/LingNengAI/app.*` modules.
- Do not add `lingneng/training/` or native Hermes RAG ingestion.
- Do not expose high-risk Hermes tools through the Java LingNeng toolset.

## User Confirmations Before Execution

No additional confirmation is needed before execution. The Phase 16 spec already accepts:

- employee answer semantics move through Hermes skills and prompt contracts;
- old graph nodes remain reference-only;
- smalltalk identity text is scoped to identity, greeting, capability, and out-of-scope cases;
- no new LLM tool-admission classifier in this phase;
- RAG training and ingestion remain in the old service;
- default CI does not require live LLM calls.

## File Map

### Skill Content

- `skills/lingneng/employees/employee-boss-assistant/SKILL.md`: boss assistant profile, handoff targets, tool policy, smalltalk/scope guidance.
- `skills/lingneng/employees/employee-operation-specialist/SKILL.md`: operation specialist profile, handoff targets, tool policy, data-gap guidance.
- `skills/lingneng/employees/employee-product-combo-advisor/SKILL.md`: product and combo advisor profile, handoff targets, pricing/cost caution.
- `skills/lingneng/employees/employee-marketing-planner/SKILL.md`: campaign planner profile, handoff targets, campaign plan structure.
- `skills/lingneng/employees/employee-marketing-content-creator/SKILL.md`: content creator profile, image/content tool boundaries.
- `skills/lingneng/employees/employee-member-operator/SKILL.md`: member operator profile, membership data-gap and recall guidance.
- `skills/lingneng/infrastructure/employee-answer-semantics-contract/SKILL.md`: shared identity, scope, handoff, and answer behavior contract.
- `skills/lingneng/infrastructure/business-answer-contract/SKILL.md`: shared business answer shape and forbidden claims.
- `skills/lingneng/infrastructure/tool-observation-contract/SKILL.md`: tool result usage and missing-provider degradation.
- `skills/lingneng/infrastructure/artifact-output-contract/SKILL.md`: artifact claim and generated-file rules.
- `skills/lingneng/infrastructure/rag-citation-contract/SKILL.md`: RAG evidence and citation behavior.

### Runtime

- `lingneng/skills/loader.py`: include selected infrastructure contracts in the prompt context through existing bounded skill fragments.
- `lingneng/skills/models.py`: no required schema change is expected; use existing `tools` and `target_employee_types` metadata fields.
- `lingneng/runtime/hermes_adapter.py`: no required change expected unless prompt tests show infrastructure contracts are not visible after loader changes.
- `lingneng/context/prompt.py`: no required change expected; Phase 11 trust boundaries stay unchanged.

### Tests And Fixtures

- `tests/lingneng/fixtures/employee_answer_semantics.json`: deterministic scenario matrix for six employees.
- `tests/lingneng/evals/test_employee_answer_semantics_fixtures.py`: fixture schema and coverage tests.
- `tests/lingneng/skills/test_employee_answer_profiles.py`: employee profile metadata/body tests.
- `tests/lingneng/skills/test_skill_catalog.py`: required package count update for the new infrastructure skill.
- `tests/lingneng/runtime/test_employee_answer_prompt.py`: prompt injection and trust-boundary tests.
- `tests/lingneng/tools/test_tool_guidance_contract.py`: tool guidance contract tests.
- `tests/lingneng/guardrails/test_no_old_lingneng_runtime_imports.py`: old-runtime import and training-boundary guardrails.
- `tests/lingneng/integration/test_employee_semantics_live.py`: opt-in live LLM acceptance tests.
- `docs/lingneng-migration/reports/2026-06-14-employee-answer-semantics-comparison-template.md`: manual comparison runbook.

---

## Task 16.1: Add Deterministic Employee Semantics Fixtures

**Goal:** Add a stable, non-live fixture matrix that defines what scenarios Phase 16 must cover.

**Files:**

- Create: `tests/lingneng/fixtures/employee_answer_semantics.json`
- Create: `tests/lingneng/evals/test_employee_answer_semantics_fixtures.py`
- Create: `docs/lingneng-migration/reports/2026-06-14-employee-answer-semantics-comparison-template.md`

- [ ] **Step 1: Add the fixture validation test**

Create `tests/lingneng/evals/test_employee_answer_semantics_fixtures.py` with this structure:

```python
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = REPO_ROOT / "tests" / "lingneng" / "fixtures" / "employee_answer_semantics.json"
TEMPLATE_PATH = (
    REPO_ROOT
    / "docs"
    / "lingneng-migration"
    / "reports"
    / "2026-06-14-employee-answer-semantics-comparison-template.md"
)

EMPLOYEE_TYPES = {
    "boss_assistant",
    "operation_specialist",
    "product_combo_advisor",
    "marketing_planner",
    "marketing_content_creator",
    "member_operator",
}
SCENARIO_TYPES = {
    "identity",
    "in_scope",
    "out_of_scope",
    "handoff",
    "insufficient_data",
    "tool_needed",
}
VALID_TOOLS = {
    "retrieve_rag",
    "employee_handoff",
    "list_skills",
    "search_skills",
    "read_skill",
    "read_skill_resource",
    "document_generation",
    "image_generation",
    "chart_visualization",
    "web_search",
}
REQUIRED_CASE_FIELDS = {
    "id",
    "employee_type",
    "query",
    "scenario_type",
    "expected_profile_markers",
    "forbidden_markers",
    "expected_handoff_target",
    "expected_tool_guidance",
    "expected_answer_shape",
    "requires_live_llm",
    "notes",
}
SAFE_ID_RE = re.compile(r"^[a-z0-9_:-]+$")


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_employee_answer_semantics_fixture_shape() -> None:
    data = load_fixture()
    assert data["schema_version"] == "1.0"
    assert set(data["employee_types"]) == EMPLOYEE_TYPES
    assert set(data["scenario_types"]) == SCENARIO_TYPES
    assert isinstance(data["cases"], list)
    assert len(data["cases"]) == len(EMPLOYEE_TYPES) * len(SCENARIO_TYPES)


def test_employee_answer_semantics_fixture_covers_each_employee_and_scenario() -> None:
    cases = load_fixture()["cases"]
    observed = {(case["employee_type"], case["scenario_type"]) for case in cases}
    expected = {
        (employee_type, scenario_type)
        for employee_type in EMPLOYEE_TYPES
        for scenario_type in SCENARIO_TYPES
    }
    assert observed == expected


def test_employee_answer_semantics_cases_are_public_and_actionable() -> None:
    for case in load_fixture()["cases"]:
        assert set(case) == REQUIRED_CASE_FIELDS
        assert SAFE_ID_RE.fullmatch(case["id"])
        assert case["employee_type"] in EMPLOYEE_TYPES
        assert case["scenario_type"] in SCENARIO_TYPES
        assert case["query"].strip()
        assert isinstance(case["requires_live_llm"], bool)
        assert case["requires_live_llm"] is False
        assert case["expected_profile_markers"]
        assert case["expected_answer_shape"]
        assert "/Users/" not in json.dumps(case, ensure_ascii=False)
        assert "LingNengAI/app" not in json.dumps(case, ensure_ascii=False)
        assert "entry_decision" not in json.dumps(case, ensure_ascii=False)
        assert "request_plan" not in json.dumps(case, ensure_ascii=False)
        assert "business_agent" not in json.dumps(case, ensure_ascii=False)


def test_handoff_and_tool_guidance_values_are_valid() -> None:
    for case in load_fixture()["cases"]:
        target = case["expected_handoff_target"]
        if case["scenario_type"] == "handoff":
            assert target in EMPLOYEE_TYPES - {case["employee_type"]}
            assert "employee_handoff" in case["expected_tool_guidance"]
        else:
            assert target is None
        for tool_name in case["expected_tool_guidance"]:
            assert tool_name in VALID_TOOLS


def test_employee_answer_semantics_template_mentions_all_cases() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    for case in load_fixture()["cases"]:
        assert case["id"] in template
    assert "No exact live LLM wording is required" in template
    assert "LINGNENG_EMPLOYEE_SEMANTICS_LIVE_TEST_ENABLED" in template
```

- [ ] **Step 2: Run the fixture test and confirm it fails**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/evals/test_employee_answer_semantics_fixtures.py -q
```

Expected: fail because `tests/lingneng/fixtures/employee_answer_semantics.json` and the report template do not exist.

- [ ] **Step 3: Add the fixture JSON**

Create `tests/lingneng/fixtures/employee_answer_semantics.json` with:

```json
{
  "schema_version": "1.0",
  "employee_types": [
    "boss_assistant",
    "operation_specialist",
    "product_combo_advisor",
    "marketing_planner",
    "marketing_content_creator",
    "member_operator"
  ],
  "scenario_types": [
    "identity",
    "in_scope",
    "out_of_scope",
    "handoff",
    "insufficient_data",
    "tool_needed"
  ],
  "cases": [
    {
      "id": "boss_assistant:identity",
      "employee_type": "boss_assistant",
      "query": "你是谁，能帮我做什么？",
      "scenario_type": "identity",
      "expected_profile_markers": ["老板助手", "经营", "管理"],
      "forbidden_markers": ["固定介绍反复追加", "财务审计结论"],
      "expected_handoff_target": null,
      "expected_tool_guidance": [],
      "expected_answer_shape": ["身份", "能力范围", "可继续提问"],
      "requires_live_llm": false,
      "notes": "Identity reply should be scoped to capability explanation."
    }
  ]
}
```

Then expand `cases` to exactly thirty-six entries:

| Employee | identity | in_scope | out_of_scope | handoff | insufficient_data | tool_needed |
| --- | --- | --- | --- | --- | --- | --- |
| `boss_assistant` | capability intro | business review | medical/legal request | content creation -> `marketing_content_creator` | missing store data | PDF/report -> `document_generation` |
| `operation_specialist` | capability intro | store diagnosis | non-restaurant tech support | menu combo -> `product_combo_advisor` | missing sales/labor data | chart/report -> `chart_visualization` |
| `product_combo_advisor` | capability intro | combo/pricing | legal contract wording | campaign theme -> `marketing_planner` | missing cost/sales data | chart comparison -> `chart_visualization` |
| `marketing_planner` | capability intro | holiday campaign | unrelated coding task | poster copy -> `marketing_content_creator` | missing audience/budget | public trend -> `web_search` |
| `marketing_content_creator` | capability intro | short copy | medical efficacy claim | campaign mechanism -> `marketing_planner` | missing product/channel details | poster image -> `image_generation` |
| `member_operator` | capability intro | recall campaign | unrelated finance audit | campaign theme -> `marketing_planner` | missing member segment data | member report -> `document_generation` |

Use these marker rules in every entry:

- `expected_profile_markers` contains the display name and two domain words.
- `forbidden_markers` contains at least one unsafe claim type.
- `expected_tool_guidance` is empty unless the case expects a tool.
- all `requires_live_llm` values are `false`.

- [ ] **Step 4: Add the comparison template**

Create `docs/lingneng-migration/reports/2026-06-14-employee-answer-semantics-comparison-template.md` with:

```markdown
# Phase 16 Employee Answer Semantics Comparison Template

## Purpose

Use this template to compare LingNengAI reference behavior and LingNeng-Hermes
behavior for digital employee answer semantics. No exact live LLM wording is
required; evaluate public behavior, scope, tool policy, handoff, and data-gap
handling.

## Live Gate

Live checks are disabled unless:

```text
LINGNENG_EMPLOYEE_SEMANTICS_LIVE_TEST_ENABLED=true
```

## Case Table

| Case id | Employee | Scenario | Status | Notes |
| --- | --- | --- | --- | --- |
| boss_assistant:identity | boss_assistant | identity | pending | capability intro |
```

Add one table row for every case id from the fixture. Keep status as `pending`.

- [ ] **Step 5: Run verification**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/evals/test_employee_answer_semantics_fixtures.py -q
```

Expected: pass.

- [ ] **Step 6: Commit and push**

```bash
git add tests/lingneng/fixtures/employee_answer_semantics.json tests/lingneng/evals/test_employee_answer_semantics_fixtures.py docs/lingneng-migration/reports/2026-06-14-employee-answer-semantics-comparison-template.md
git commit -m "test: 增加数字员工语义验收夹具"
git push
```

Rollback: revert this commit. It only adds fixtures, tests, and a report template.

---

## Task 16.2: Complete Employee Answer Profiles In Bundled Skills

**Goal:** Make all six employee base skills carry complete answer semantics and metadata that can be validated deterministically.

**Files:**

- Modify: `skills/lingneng/employees/employee-boss-assistant/SKILL.md`
- Modify: `skills/lingneng/employees/employee-operation-specialist/SKILL.md`
- Modify: `skills/lingneng/employees/employee-product-combo-advisor/SKILL.md`
- Modify: `skills/lingneng/employees/employee-marketing-planner/SKILL.md`
- Modify: `skills/lingneng/employees/employee-marketing-content-creator/SKILL.md`
- Modify: `skills/lingneng/employees/employee-member-operator/SKILL.md`
- Create: `tests/lingneng/skills/test_employee_answer_profiles.py`

- [ ] **Step 1: Add profile validation tests**

Create `tests/lingneng/skills/test_employee_answer_profiles.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from tests.lingneng.tools.test_toolset_policy import APPROVED_LINGNENG_TOOLS


REPO_ROOT = Path(__file__).resolve().parents[3]
EMPLOYEE_ROOT = REPO_ROOT / "skills" / "lingneng" / "employees"
EMPLOYEE_SKILLS = {
    "boss_assistant": "employee-boss-assistant",
    "operation_specialist": "employee-operation-specialist",
    "product_combo_advisor": "employee-product-combo-advisor",
    "marketing_planner": "employee-marketing-planner",
    "marketing_content_creator": "employee-marketing-content-creator",
    "member_operator": "employee-member-operator",
}
PROFILE_SECTIONS = {
    "## Role Identity",
    "## Service Audience",
    "## Business Scope",
    "## Operating Principles",
    "## Communication Style",
    "## Normal Answer Structure",
    "## Identity Reply Guidance",
    "## Out-of-Scope Guidance",
    "## Insufficient Data Guidance",
    "## Handoff Guidance",
    "## Tool Guidance",
    "## Prohibited Claims",
    "## Degradation",
}
FORBIDDEN_TEXT = {
    "/Users/",
    "LingNengAI/app",
    "entry_decision",
    "request_plan",
    "business_agent_node",
    "langchain_business_agent",
}


def _split_skill(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    assert lines[0] == "---"
    end = next(index for index, line in enumerate(lines[1:], start=1) if line == "---")
    metadata = yaml.safe_load("\n".join(lines[1:end]))
    assert isinstance(metadata, dict)
    return metadata, "\n".join(lines[end + 1 :])


def _employee_skill(employee_type: str) -> tuple[Path, dict, str]:
    package_name = EMPLOYEE_SKILLS[employee_type]
    path = EMPLOYEE_ROOT / package_name / "SKILL.md"
    metadata, body = _split_skill(path.read_text(encoding="utf-8"))
    return path, metadata, body


def test_all_employee_profiles_have_required_sections() -> None:
    for employee_type in EMPLOYEE_SKILLS:
        path, metadata, body = _employee_skill(employee_type)
        assert metadata["metadata"]["lingneng"]["employee_type"] == employee_type
        for heading in PROFILE_SECTIONS:
            assert heading in body, f"{heading} missing in {path.relative_to(REPO_ROOT)}"


def test_employee_profile_metadata_has_valid_tools_and_handoff_targets() -> None:
    employee_types = set(EMPLOYEE_SKILLS)
    for employee_type in EMPLOYEE_SKILLS:
        path, metadata, body = _employee_skill(employee_type)
        lingneng = metadata["metadata"]["lingneng"]
        targets = set(lingneng.get("target_employee_types", []))
        tools = set(lingneng.get("tools", []))
        assert targets, path
        assert targets <= employee_types - {employee_type}
        assert tools, path
        assert tools <= APPROVED_LINGNENG_TOOLS
        assert "employee_handoff" in tools
        assert "retrieve_rag" in tools
        assert "read_skill" in tools
        assert "员工跳转" in body or "转交" in body


def test_employee_profiles_scope_identity_replies_without_global_append() -> None:
    for employee_type in EMPLOYEE_SKILLS:
        path, _, body = _employee_skill(employee_type)
        assert "身份、问候、能力范围或越界" in body, path
        assert "不要把固定介绍追加到每个正常业务回答" in body, path


def test_employee_profiles_do_not_leak_old_runtime_details() -> None:
    for employee_type in EMPLOYEE_SKILLS:
        path, _, body = _employee_skill(employee_type)
        for forbidden in FORBIDDEN_TEXT:
            assert forbidden not in body, f"{forbidden} leaked in {path.relative_to(REPO_ROOT)}"
```

- [ ] **Step 2: Run the new test and confirm it fails**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/skills/test_employee_answer_profiles.py -q
```

Expected: fail because the six employee skills do not yet include every required section and metadata field.

- [ ] **Step 3: Update employee metadata**

In each employee `SKILL.md`, add `target_employee_types` and `tools` under `metadata.lingneng`.

Use these exact values:

```yaml
# employee-boss-assistant
target_employee_types:
  - operation_specialist
  - product_combo_advisor
  - marketing_planner
  - marketing_content_creator
  - member_operator
tools:
  - employee_handoff
  - retrieve_rag
  - read_skill
  - search_skills
  - document_generation
  - chart_visualization
  - web_search

# employee-operation-specialist
target_employee_types:
  - boss_assistant
  - product_combo_advisor
  - marketing_planner
  - member_operator
tools:
  - employee_handoff
  - retrieve_rag
  - read_skill
  - search_skills
  - document_generation
  - chart_visualization
  - web_search

# employee-product-combo-advisor
target_employee_types:
  - boss_assistant
  - operation_specialist
  - marketing_planner
  - marketing_content_creator
tools:
  - employee_handoff
  - retrieve_rag
  - read_skill
  - search_skills
  - document_generation
  - chart_visualization
  - web_search

# employee-marketing-planner
target_employee_types:
  - boss_assistant
  - product_combo_advisor
  - marketing_content_creator
  - member_operator
tools:
  - employee_handoff
  - retrieve_rag
  - read_skill
  - search_skills
  - document_generation
  - image_generation
  - chart_visualization
  - web_search

# employee-marketing-content-creator
target_employee_types:
  - boss_assistant
  - product_combo_advisor
  - marketing_planner
  - member_operator
tools:
  - employee_handoff
  - retrieve_rag
  - read_skill
  - search_skills
  - document_generation
  - image_generation
  - web_search

# employee-member-operator
target_employee_types:
  - boss_assistant
  - operation_specialist
  - marketing_planner
  - marketing_content_creator
tools:
  - employee_handoff
  - retrieve_rag
  - read_skill
  - search_skills
  - document_generation
  - chart_visualization
  - web_search
```

- [ ] **Step 4: Update employee body sections**

For each employee skill body, keep the existing sections and add missing sections with these exact headings:

```markdown
## Normal Answer Structure

优先给结论或建议，再说明判断依据、执行步骤、风险和需要补充的数据。

## Identity Reply Guidance

仅当用户询问身份、问候、能力范围或越界时，说明当前数字员工身份、适合处理的问题和可以继续提供的帮助；不要把固定介绍追加到每个正常业务回答。

## Out-of-Scope Guidance

当请求不属于当前员工职责时，先简短说明边界，再使用 `employee_handoff` 建议更合适的数字员工；如果请求不属于餐饮经营场景，给出安全拒答或通用建议。

## Insufficient Data Guidance

缺少关键经营事实时，不编造数据；先给保守方案、假设条件和最小补数清单。

## Handoff Guidance

当问题明显属于 `target_employee_types` 中的其他员工时，使用 `employee_handoff`。不要假装具备其他员工的专业职责，也不要自行发明员工类型。

## Prohibited Claims

不得编造销量、成本、毛利、库存、会员画像、平台政策、用户评价、文件生成结果或知识库引用。
```

Then customize these employee-specific lines inside existing or new sections:

| Employee | Required customized marker |
| --- | --- |
| `boss_assistant` | `跨角色经营统筹` |
| `operation_specialist` | `指标、原因、动作、负责人和周期` |
| `product_combo_advisor` | `价格带、毛利约束和验证指标` |
| `marketing_planner` | `主题、机制、渠道节奏和评估指标` |
| `marketing_content_creator` | `渠道、卖点、语气和行动号召` |
| `member_operator` | `会员分层、权益、触达节奏和复盘指标` |

- [ ] **Step 5: Run verification**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/skills/test_employee_answer_profiles.py tests/lingneng/skills/test_skill_loader.py tests/lingneng/skills/test_skill_catalog.py -q
```

Expected: pass.

- [ ] **Step 6: Commit and push**

```bash
git add skills/lingneng/employees tests/lingneng/skills/test_employee_answer_profiles.py
git commit -m "feat: 完善数字员工回答画像"
git push
```

Rollback: revert this commit to restore the previous employee skill bodies and metadata.

---

## Task 16.3: Add Shared Employee Answer Contracts To Prompt Context

**Goal:** Make shared answer/tool/RAG/artifact contracts visible to the current Hermes agent through bounded infrastructure skill fragments.

**Files:**

- Create: `skills/lingneng/infrastructure/employee-answer-semantics-contract/SKILL.md`
- Modify: `skills/lingneng/infrastructure/business-answer-contract/SKILL.md`
- Modify: `skills/lingneng/infrastructure/tool-observation-contract/SKILL.md`
- Modify: `skills/lingneng/infrastructure/artifact-output-contract/SKILL.md`
- Modify: `skills/lingneng/infrastructure/rag-citation-contract/SKILL.md`
- Modify: `lingneng/skills/loader.py`
- Modify: `tests/lingneng/skills/test_skill_catalog.py`
- Create: `tests/lingneng/runtime/test_employee_answer_prompt.py`

- [ ] **Step 1: Add failing prompt contract tests**

Create `tests/lingneng/runtime/test_employee_answer_prompt.py`:

```python
from __future__ import annotations

import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.schemas.chat_events import FinalEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from lingneng.skills.loader import LingNengSkillLoader
from tests.lingneng.runtime.test_hermes_adapter_config import RecordingSystemPromptAgent, effective_system_prompt
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def settings(tmp_path, **overrides) -> LingNengSettings:
    env = {
        "LINGNENG_APP_ENV": "test",
        "LINGNENG_RUNTIME_DIR": str(tmp_path),
        "LINGNENG_AGENT_MODE": "hermes",
        "LINGNENG_INTERNAL_API_KEY": "key",
    }
    env.update(overrides)
    return LingNengSettings.from_env(env)


def request_for_employee(employee_type: str = "marketing_content_creator") -> ChatStreamRequest:
    payload = full_payload()
    payload["employee"]["employee_type"] = employee_type
    payload["employee"]["employee_id"] = f"emp-{employee_type}"
    payload["skill"]["inline"] = {
        "summary": "INLINE MUST NOT APPEAR AS TRUSTED CONTRACT"
    }
    payload["history"] = [
        {
            "role": "user",
            "content": "HISTORY MUST NOT APPEAR AS TRUSTED CONTRACT",
        }
    ]
    return ChatStreamRequest.model_validate(payload)


def test_skill_loader_includes_shared_answer_contracts(tmp_path) -> None:
    prompt = (
        LingNengSkillLoader(settings(tmp_path))
        .build_prompt_context(request_for_employee())
        .to_prompt_text()
    )

    assert "employee-answer-semantics-contract" in prompt
    assert "business-answer-contract" in prompt
    assert "tool-observation-contract" in prompt
    assert "artifact-output-contract" in prompt
    assert "rag-citation-contract" in prompt
    assert "No exact live LLM wording is required" not in prompt
    assert "/Users/rotas/Documents/work/hailun/LingNengAI" not in prompt


@pytest.mark.asyncio
async def test_hermes_system_prompt_contains_employee_and_shared_contracts(tmp_path):
    RecordingSystemPromptAgent.system_message_seen = ""
    RecordingSystemPromptAgent.ephemeral_system_prompt_seen = ""
    request = request_for_employee("marketing_content_creator")
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path),
        agent_cls=RecordingSystemPromptAgent,
    )

    events = [event async for event in adapter.stream(request, resolved, "run-phase16")]

    assert isinstance(events[-1], FinalEvent)
    prompt = effective_system_prompt()
    assert "employee-marketing-content-creator" in prompt
    assert "内容创意师" in prompt
    assert "employee-answer-semantics-contract" in prompt
    assert "business-answer-contract" in prompt
    assert "artifact-output-contract" in prompt
    assert "rag-citation-contract" in prompt
    assert "INLINE MUST NOT APPEAR AS TRUSTED CONTRACT" not in prompt
    assert "HISTORY MUST NOT APPEAR AS TRUSTED CONTRACT" not in prompt
```

- [ ] **Step 2: Run the prompt tests and confirm they fail**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime/test_employee_answer_prompt.py -q
```

Expected: fail because shared infrastructure contracts are not injected by `LingNengSkillLoader` yet and the new contract package does not exist.

- [ ] **Step 3: Add the new infrastructure skill**

Create `skills/lingneng/infrastructure/employee-answer-semantics-contract/SKILL.md`:

```markdown
---
name: employee-answer-semantics-contract
description: 数字员工回答语义平台契约 Skill，定义身份、职责边界、跳转和数据不足时的回答规则。
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: infrastructure
    source: python
    status: active
    user_visible: false
    script_policy: metadata_only
    tags: [infrastructure, employee, answer]
    domains: [restaurant]
    tools:
      - employee_handoff
      - retrieve_rag
      - read_skill
      - search_skills
  hermes:
    tags: [lingneng]
    requires_tools: [read_skill]
    fallback_for_toolsets: [lingneng]
---

## Applies To

适用于所有灵能数字员工在 Java stream 对话中的身份说明、职责边界、跨员工转交和业务回答。

## Runtime Contract

正常业务回答应围绕当前员工职责直接解决问题；身份、问候、能力范围或越界请求才说明数字员工身份和边界。

## Handoff Behavior

当请求明显属于其他数字员工职责时，使用 `employee_handoff` 给出公开、简短、可确认的转交建议；不要恢复旧的前置路由图，也不要发明员工类型。

## Insufficient Data

缺少门店、会员、商品、成本、库存、销量、政策或训练资料时，不编造事实；给出保守方案、假设和最小补数清单。

## Smalltalk Scope

身份和寒暄回答可以说明当前员工能做什么；正常经营、营销、商品、会员或内容任务中不要反复追加固定身份介绍。

## Failure Handling

工具缺失、检索失败或生成物失败时，说明限制并给出可复制的文本方案、检查清单或下一步问题。
```

- [ ] **Step 4: Strengthen existing infrastructure skills**

Update the existing infrastructure skill bodies with these required markers:

- `business-answer-contract`: add `直接结论`, `行动步骤`, `数据缺口`, `不得编造销量、成本、库存、毛利、会员画像或用户评价`.
- `tool-observation-contract`: add `工具缺失或未配置时继续文本回答`, `不得把模型猜测包装成工具观察结果`, `隐藏或不可见工具不代表已授权`.
- `artifact-output-contract`: add `只有真实 artifact 结果才能声明文件、图片或图表已生成`, `没有 artifact_created 时不要声称生成成功`.
- `rag-citation-contract`: add `内部训练资料和历史案例优先使用 retrieve_rag`, `实时公共事实使用 web_search`, `不得编造引用、文件名或条款`.

- [ ] **Step 5: Update required package test**

Modify `tests/lingneng/skills/test_skill_catalog.py`:

Add `"employee-answer-semantics-contract"` to `REQUIRED_PACKAGES`. The set
must still contain the existing twenty-four package names and the new
infrastructure package name, for a total of twenty-five packages. Change the
expected count in
`test_catalog_default_list_includes_all_bundled_skill_kinds_in_order` from
`24` to `25`.

- [ ] **Step 6: Inject infrastructure contracts through the skill loader**

Modify `lingneng/skills/loader.py` with this implementation shape:

```python
INFRASTRUCTURE_CONTRACT_PACKAGES = (
    "employee-answer-semantics-contract",
    "business-answer-contract",
    "tool-observation-contract",
    "artifact-output-contract",
    "rag-citation-contract",
)
```

In `LingNengSkillLoader.build_prompt_context(...)`, replace:

```python
infrastructure_fragments=[_handoff_guidance_fragment()],
```

with:

```python
infrastructure_fragments=[
    *self._infrastructure_contract_fragments(packages, warnings),
    _handoff_guidance_fragment(),
],
```

Add this method:

```python
def _infrastructure_contract_fragments(
    self,
    packages: dict[str, LoadedSkillPackage],
    warnings: list[SkillPromptWarning],
) -> list[SkillPromptFragment]:
    fragments: list[SkillPromptFragment] = []
    for package_name in INFRASTRUCTURE_CONTRACT_PACKAGES:
        package = packages.get(package_name)
        if package is None:
            warnings.append(
                SkillPromptWarning(
                    code="INFRASTRUCTURE_CONTRACT_NOT_FOUND",
                    message="Bundled LingNeng infrastructure contract is missing.",
                    package_name=package_name,
                )
            )
            continue
        lingneng = package.metadata.lingneng
        if lingneng.kind is not SkillKind.INFRASTRUCTURE:
            warnings.append(
                SkillPromptWarning(
                    code="INFRASTRUCTURE_CONTRACT_INVALID",
                    message="Bundled LingNeng contract is not an infrastructure skill.",
                    package_name=package_name,
                )
            )
            continue
        fragments.append(self._fragment(package))
    return fragments
```

- [ ] **Step 7: Run verification**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime/test_employee_answer_prompt.py tests/lingneng/skills/test_skill_catalog.py tests/lingneng/skills/test_skill_loader.py -q
```

Expected: pass.

- [ ] **Step 8: Commit and push**

```bash
git add skills/lingneng/infrastructure lingneng/skills/loader.py tests/lingneng/runtime/test_employee_answer_prompt.py tests/lingneng/skills/test_skill_catalog.py
git commit -m "feat: 注入数字员工回答契约"
git push
```

Rollback: revert this commit. The runtime will return to the previous current-employee skill plus handoff guidance prompt.

---

## Task 16.4: Add Tool Guidance And Old Runtime Guardrails

**Goal:** Prove Phase 16 keeps tool use, artifact claims, RAG/web ordering, old-runtime import boundaries, and training boundaries intact.

**Files:**

- Create: `tests/lingneng/tools/test_tool_guidance_contract.py`
- Create: `tests/lingneng/guardrails/test_no_old_lingneng_runtime_imports.py`

- [ ] **Step 1: Add tool guidance contract tests**

Create `tests/lingneng/tools/test_tool_guidance_contract.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from tests.lingneng.tools.test_toolset_policy import APPROVED_LINGNENG_TOOLS, DISALLOWED_HERMES_TOOLS


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = REPO_ROOT / "skills" / "lingneng"
INFRA_ROOT = SKILL_ROOT / "infrastructure"


def _skill_body(package: str) -> str:
    text = (INFRA_ROOT / package / "SKILL.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    end = next(index for index, line in enumerate(lines[1:], start=1) if line == "---")
    return "\n".join(lines[end + 1 :])


def _frontmatter(package: str) -> dict:
    text = (INFRA_ROOT / package / "SKILL.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    end = next(index for index, line in enumerate(lines[1:], start=1) if line == "---")
    data = yaml.safe_load("\n".join(lines[1:end]))
    assert isinstance(data, dict)
    return data


def test_rag_and_web_search_guidance_is_explicit() -> None:
    body = _skill_body("rag-citation-contract")

    assert "retrieve_rag" in body
    assert "web_search" in body
    assert "内部训练资料" in body
    assert "实时公共事实" in body
    assert "不得编造引用" in body


def test_artifact_claims_require_real_artifact_result() -> None:
    body = _skill_body("artifact-output-contract")

    assert "artifact_created" in body
    assert "真实 artifact" in body
    assert "不要声称生成成功" in body
    assert "本地绝对路径" in body


def test_tool_observation_contract_denies_hidden_or_unavailable_tools() -> None:
    body = _skill_body("tool-observation-contract")

    assert "工具缺失或未配置" in body
    assert "隐藏或不可见工具不代表已授权" in body
    assert "不得把模型猜测包装成工具观察结果" in body


def test_contract_tools_are_lingneng_approved_only() -> None:
    for package in (
        "employee-answer-semantics-contract",
        "business-answer-contract",
        "tool-observation-contract",
        "artifact-output-contract",
        "rag-citation-contract",
    ):
        lingneng = _frontmatter(package)["metadata"]["lingneng"]
        declared = set(lingneng.get("tools", []))
        assert declared <= APPROVED_LINGNENG_TOOLS
        assert declared.isdisjoint(DISALLOWED_HERMES_TOOLS)
```

- [ ] **Step 2: Add guardrail tests**

Create `tests/lingneng/guardrails/test_no_old_lingneng_runtime_imports.py`:

```python
from __future__ import annotations

import ast
from pathlib import Path

from toolsets import resolve_toolset
from tests.lingneng.tools.test_toolset_policy import DISALLOWED_HERMES_TOOLS


ROOT = Path(__file__).resolve().parents[3]


def test_phase_16_runtime_does_not_import_old_lingnengai_app_modules() -> None:
    offenders: list[str] = []
    old_path = "/Users/rotas/Documents/work/hailun/LingNengAI" + "/app"
    for path in sorted((ROOT / "lingneng").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT)
        if old_path in text:
            offenders.append(f"{relative}:old_app_path")
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "app" or alias.name.startswith("app."):
                        offenders.append(f"{relative}:{node.lineno}")
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "app" or module.startswith("app."):
                    offenders.append(f"{relative}:{node.lineno}")
    assert offenders == []


def test_phase_16_does_not_add_native_training_pipeline() -> None:
    assert not (ROOT / "lingneng" / "training").exists()


def test_phase_16_lingneng_toolset_keeps_high_risk_tools_excluded() -> None:
    names = set(resolve_toolset("lingneng"))
    assert names.isdisjoint(DISALLOWED_HERMES_TOOLS)
```

- [ ] **Step 3: Run verification**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_tool_guidance_contract.py tests/lingneng/guardrails/test_no_old_lingneng_runtime_imports.py tests/lingneng/tools/test_toolset_policy.py tests/lingneng/training/test_training_boundary.py -q
```

Expected: pass after Task 16.3 contract text exists.

- [ ] **Step 4: Commit and push**

```bash
git add tests/lingneng/tools/test_tool_guidance_contract.py tests/lingneng/guardrails/test_no_old_lingneng_runtime_imports.py
git commit -m "test: 增加数字员工语义护栏"
git push
```

Rollback: revert this commit. It only adds tests.

---

## Task 16.5: Add Opt-In Live Employee Semantics Acceptance

**Goal:** Provide a live LLM acceptance path that is disabled by default and does not make CI depend on model wording.

**Files:**

- Create: `tests/lingneng/integration/test_employee_semantics_live.py`
- Modify: `docs/lingneng-migration/reports/2026-06-14-employee-answer-semantics-comparison-template.md`

- [ ] **Step 1: Add the opt-in live test**

Create `tests/lingneng/integration/test_employee_semantics_live.py`:

```python
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lingneng.api.app import create_app
from lingneng.config.settings import LingNengSettings
from tests.lingneng.schemas.test_chat_request_schema import full_payload


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = REPO_ROOT / "tests" / "lingneng" / "fixtures" / "employee_answer_semantics.json"


def _enabled() -> bool:
    return os.getenv("LINGNENG_EMPLOYEE_SEMANTICS_LIVE_TEST_ENABLED", "").lower() == "true"


pytestmark = pytest.mark.skipif(
    not _enabled(),
    reason="Set LINGNENG_EMPLOYEE_SEMANTICS_LIVE_TEST_ENABLED=true to run live employee semantics checks.",
)


def _settings(tmp_path: Path) -> LingNengSettings:
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_AGENT_MODE": "hermes",
            "LINGNENG_INTERNAL_API_KEY": "key",
        }
    )


def _representative_cases() -> list[dict]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    wanted = {
        "boss_assistant:identity",
        "marketing_planner:in_scope",
        "marketing_content_creator:tool_needed",
        "member_operator:handoff",
    }
    return [case for case in data["cases"] if case["id"] in wanted]


def test_live_employee_semantics_stream_completes(tmp_path) -> None:
    from fastapi.testclient import TestClient

    app = create_app(settings=_settings(tmp_path))
    client = TestClient(app)
    for case in _representative_cases():
        payload = full_payload()
        payload["request_id"] = f"phase16-{case['id'].replace(':', '-')}"
        payload["conversation_id"] = f"phase16-{case['id'].replace(':', '-')}"
        payload["employee"]["employee_type"] = case["employee_type"]
        payload["employee"]["employee_id"] = f"emp-{case['employee_type']}"
        payload["query"]["content"] = case["query"]

        response = client.post(
            "/internal/agent/chat/stream",
            json=payload,
            headers={"X-Internal-Key": "key"},
        )

        assert response.status_code == 200
        assert "event: run_started" in response.text
        assert "event: final" in response.text
        assert "event: error" not in response.text
```

- [ ] **Step 2: Update the report template live section**

Add this command to `docs/lingneng-migration/reports/2026-06-14-employee-answer-semantics-comparison-template.md`:

```bash
LINGNENG_EMPLOYEE_SEMANTICS_LIVE_TEST_ENABLED=true \
uv run --extra dev python -m pytest tests/lingneng/integration/test_employee_semantics_live.py -q
```

Document that the live test requires a configured Hermes model provider and does not compare exact wording.

- [ ] **Step 3: Run verification with live gate disabled**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/integration/test_employee_semantics_live.py -q
```

Expected: skipped, not failed, when `LINGNENG_EMPLOYEE_SEMANTICS_LIVE_TEST_ENABLED` is not `true`.

- [ ] **Step 4: Commit and push**

```bash
git add tests/lingneng/integration/test_employee_semantics_live.py docs/lingneng-migration/reports/2026-06-14-employee-answer-semantics-comparison-template.md
git commit -m "test: 增加数字员工语义实时验收入口"
git push
```

Rollback: revert this commit. Default runtime behavior is unchanged.

---

## Task 16.6: Phase Verification And Self-Review

**Goal:** Prove Phase 16 satisfies the approved spec before moving to execution closeout.

**Files:**

- Read: `docs/lingneng-migration/specs/2026-06-14-phase-16-employee-answer-semantics-spec.md`
- Read: `docs/lingneng-migration/plans/2026-06-14-phase-16-employee-answer-semantics-plan.md`
- Read: `git status --short --branch`

- [ ] **Step 1: Run focused Phase 16 verification**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/evals/test_employee_answer_semantics_fixtures.py \
  tests/lingneng/skills/test_employee_answer_profiles.py \
  tests/lingneng/runtime/test_employee_answer_prompt.py \
  tests/lingneng/tools/test_tool_guidance_contract.py \
  tests/lingneng/guardrails/test_no_old_lingneng_runtime_imports.py \
  tests/lingneng/integration/test_employee_semantics_live.py \
  -q
```

Expected: pass, with the live test skipped unless explicitly enabled.

- [ ] **Step 2: Run adjacent regression checks**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/skills/test_skill_catalog.py \
  tests/lingneng/skills/test_skill_loader.py \
  tests/lingneng/runtime/test_hermes_adapter_config.py \
  tests/lingneng/tools/test_toolset_policy.py \
  tests/lingneng/training/test_training_boundary.py \
  -q
```

Expected: pass.

- [ ] **Step 3: Run repository-level LingNeng tests when time allows**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng -q
```

Expected: pass, with opt-in live tests skipped unless their environment gates are enabled.

- [ ] **Step 4: Self-review against the spec**

Check these spec requirements and record the result in the final execution summary:

- six employee profiles contain complete answer semantics;
- shared answer/tool/artifact/RAG contracts exist and are injected;
- prompt remains bounded and trust-labeled;
- `employee_handoff` remains the routing mechanism;
- RAG training and ingestion remain outside Hermes;
- deterministic tests cover profiles, prompt, tool guidance, fixtures, and guardrails.

- [ ] **Step 5: Commit only if verification changes docs**

If verification reveals a command correction or report note, commit it:

```bash
git add docs/lingneng-migration/reports docs/lingneng-migration/plans/2026-06-14-phase-16-employee-answer-semantics-plan.md
git commit -m "docs: 更新数字员工语义验证说明"
git push
```

If no files changed, do not create an empty commit.

Rollback: use the per-task commits above. Task 16.6 should not contain required runtime changes.

---

## Phase 16 Verification Matrix

| Area | Command |
| --- | --- |
| Fixtures | `uv run --extra dev python -m pytest tests/lingneng/evals/test_employee_answer_semantics_fixtures.py -q` |
| Employee profiles | `uv run --extra dev python -m pytest tests/lingneng/skills/test_employee_answer_profiles.py -q` |
| Prompt contracts | `uv run --extra dev python -m pytest tests/lingneng/runtime/test_employee_answer_prompt.py -q` |
| Tool guidance | `uv run --extra dev python -m pytest tests/lingneng/tools/test_tool_guidance_contract.py -q` |
| Guardrails | `uv run --extra dev python -m pytest tests/lingneng/guardrails/test_no_old_lingneng_runtime_imports.py tests/lingneng/training/test_training_boundary.py -q` |
| Adjacent regressions | `uv run --extra dev python -m pytest tests/lingneng/skills/test_skill_catalog.py tests/lingneng/skills/test_skill_loader.py tests/lingneng/runtime/test_hermes_adapter_config.py tests/lingneng/tools/test_toolset_policy.py -q` |
| Full LingNeng suite | `uv run --extra dev python -m pytest tests/lingneng -q` |

## Final Acceptance

Phase 16 is complete when all required verification commands pass and every task commit has been pushed. The final implementation summary must state:

- which employee skill packages changed;
- whether `employee-answer-semantics-contract` was added and injected;
- whether any prompt/runtime files changed beyond `lingneng/skills/loader.py`;
- which live tests were skipped or run;
- the final commit range pushed to `origin/dev`.
