# Phase 17 LingNeng Business Decision Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Encode old LingNengAI business judgment knowledge as Hermes-native mapping docs, skill/tool guidance, fixtures, and guardrails without restoring the old pre-agent decision runtime.

**Architecture:** Keep Hermes `AIAgent`, SessionDB, Java-compatible API, SSE bridge, and the dedicated `lingneng` toolset unchanged. Add a durable business decision mapping report, deterministic fixtures, prompt/skill contract assertions, and leakage tests that prove old `runtime_decision`, `entry_decision`, `request_plan`, and related graph components are not reintroduced.

**Tech Stack:** Python 3.11-3.13, pytest, JSON fixtures, Markdown migration reports, YAML-frontmatter skill packages, Hermes skill loader, LingNeng toolset.

---

## Approved Spec

This plan implements:

```text
docs/lingneng-migration/specs/2026-06-15-phase-17-business-decision-mapping-spec.md
```

Reloaded before writing this plan:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-15-phase-17-business-decision-mapping-spec.md`

## Execution Rules

- Execute from the current project directory on `dev`.
- Do not create a git worktree.
- Implement task-by-task with `superpowers:subagent-driven-development`.
- Before execution, reload the migration context files listed above.
- After each task, run that task's verification command.
- Commit each completed task with the Chinese commit message listed in the task.
- Push `dev` after each task commit only when verification passes.
- Do not modify Java code.
- Do not modify `/internal/agent/chat/stream` or the SSE event contract.
- Do not import sibling LingNengAI `app.*` modules.
- Do not add a pre-agent router, graph, request planner, model-based tool admission layer, deterministic smalltalk fast path, or confirmed-employee auto-run behavior.
- Do not expose terminal, arbitrary filesystem, browser automation, code execution, dashboard, Kanban, or cross-channel messaging tools to the Java API.

## User Confirmations Before Execution

No additional user confirmation is required before execution. The Phase 17 spec already accepts:

- old LingNengAI judgments move only into skills, prompt contracts, tool guidance, run guards, fixtures, and tests;
- no new router, graph, pre-agent decision service, or model-based admission service;
- confirmed employee handoff remains terminal for the current Python request;
- full old capability policy and tool admission are not rebuilt;
- smalltalk and direct answers remain normal model behavior, not deterministic keyword fast paths.

## File Map

### New Files

- `docs/lingneng-migration/reports/2026-06-15-business-decision-mapping.md`: durable table mapping old LingNengAI judgment categories to Hermes-native destinations and explicit non-migration decisions.
- `tests/lingneng/fixtures/business_decision_mapping.json`: deterministic fixture cases covering routing, non-jump inputs, explicit switch, ambiguous ownership, RAG-vs-web, artifact intent, attachment boundary, compliance boundary, and history boundary.
- `tests/lingneng/evals/test_business_decision_mapping_fixtures.py`: validates fixture shape, coverage, public safety, and old-runtime leakage in the fixture.
- `tests/lingneng/runtime/test_no_old_decision_runtime_leakage.py`: AST/text guardrail proving production `lingneng/` modules do not import old LingNengAI modules or reintroduce prohibited runtime component names.
- `tests/lingneng/integration/test_business_decision_live.py`: opt-in live LLM structural acceptance tests behind `LINGNENG_BUSINESS_DECISION_LIVE_TEST_ENABLED=1`.

### Existing Files To Modify

- `lingneng/skills/loader.py`: tighten the bounded handoff guidance fragment so non-jump, explicit switch, confirm, terminal reply, and no-threshold behavior are visible in compact prompts.
- `skills/lingneng/infrastructure/employee-answer-semantics-contract/SKILL.md`: add shared business decision mapping language for direct answer, non-jump inputs, handoff, ambiguity, and no old router.
- `skills/lingneng/infrastructure/rag-citation-contract/SKILL.md`: ensure internal knowledge uses `retrieve_rag` and realtime public facts use `web_search`.
- `skills/lingneng/infrastructure/artifact-output-contract/SKILL.md`: ensure artifact tools require explicit deliverable intent and real artifact results.
- `skills/lingneng/infrastructure/tool-observation-contract/SKILL.md`: ensure hidden or unavailable tools are not treated as authorized results.
- `tests/lingneng/runtime/test_employee_answer_prompt.py`: assert compact prompts expose the new business decision markers and still exclude untrusted Java history/inline prompt text.
- `tests/lingneng/tools/test_tool_guidance_contract.py`: assert tool governance contract markers are explicit.

### Files Not To Modify For Phase 17

- `run_agent.py`
- `model_tools.py`
- `gateway/platforms/api_server.py`
- `toolsets.py`, unless a deterministic boundary test exposes an existing whitelist regression

## Task 17.1: Add Business Decision Mapping Report And Fixture

**Goal:** Create the durable mapping artifact and deterministic fixture schema before changing prompt or skill text.

**Files:**

- Create: `docs/lingneng-migration/reports/2026-06-15-business-decision-mapping.md`
- Create: `tests/lingneng/fixtures/business_decision_mapping.json`
- Create: `tests/lingneng/evals/test_business_decision_mapping_fixtures.py`

- [ ] **Step 1: Write the failing fixture validation test**

Create `tests/lingneng/evals/test_business_decision_mapping_fixtures.py`:

```python
from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = REPO_ROOT / "tests" / "lingneng" / "fixtures" / "business_decision_mapping.json"
REPORT_PATH = (
    REPO_ROOT
    / "docs"
    / "lingneng-migration"
    / "reports"
    / "2026-06-15-business-decision-mapping.md"
)

JUDGMENT_AREAS = {
    "direct_answer",
    "non_jump_input",
    "route_suggest",
    "route_confirm",
    "explicit_switch",
    "boss_fallback",
    "tool_admission",
    "rag_internal",
    "web_realtime",
    "attachment_boundary",
    "history_boundary",
    "compliance_boundary",
}
HERMES_DESTINATIONS = {
    "employee_skill",
    "infrastructure_skill",
    "employee_handoff_tool",
    "tool_schema",
    "tool_run_guard",
    "sessiondb",
    "attachment_context",
    "sse_bridge",
}
MIGRATION_DECISIONS = {
    "migrate_as_guidance",
    "migrate_as_tool_contract",
    "migrate_as_fixture",
    "preserve_existing_runtime",
    "prohibit_runtime_migration",
}
REQUIRED_CASE_FIELDS = {
    "id",
    "old_judgment_area",
    "old_reference",
    "query",
    "current_employee_type",
    "expected_behavior",
    "expected_tool",
    "hermes_destination",
    "migration_decision",
    "forbidden_runtime_components",
    "notes",
}
EMPLOYEE_TYPES = {
    "boss_assistant",
    "operation_specialist",
    "product_combo_advisor",
    "marketing_planner",
    "marketing_content_creator",
    "member_operator",
}
SAFE_ID_RE = re.compile(r"^[a-z0-9_:-]+$")
PROHIBITED_COMPONENTS = {
    "RuntimeDecisionService",
    "EntryDecisionService",
    "SemanticDecisionService",
    "RequestPlanner",
    "ToolAdmissionService",
    "light_llm_answer",
    "tool_only_agent",
    "direct_attachment_answer",
    "smalltalk_final_reply",
}


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_business_decision_mapping_fixture_shape() -> None:
    data = load_fixture()
    assert data["schema_version"] == "1.0"
    assert set(data["judgment_areas"]) == JUDGMENT_AREAS
    assert set(data["hermes_destinations"]) == HERMES_DESTINATIONS
    assert set(data["migration_decisions"]) == MIGRATION_DECISIONS
    assert isinstance(data["cases"], list)
    assert len(data["cases"]) >= len(JUDGMENT_AREAS)


def test_business_decision_mapping_covers_each_judgment_area() -> None:
    observed = {case["old_judgment_area"] for case in load_fixture()["cases"]}
    assert observed == JUDGMENT_AREAS


def test_business_decision_mapping_cases_are_public_and_actionable() -> None:
    for case in load_fixture()["cases"]:
        assert set(case) == REQUIRED_CASE_FIELDS
        assert SAFE_ID_RE.fullmatch(case["id"])
        assert case["old_judgment_area"] in JUDGMENT_AREAS
        assert case["current_employee_type"] in EMPLOYEE_TYPES
        assert case["query"].strip()
        assert case["expected_behavior"].strip()
        assert case["hermes_destination"] in HERMES_DESTINATIONS
        assert case["migration_decision"] in MIGRATION_DECISIONS
        assert isinstance(case["forbidden_runtime_components"], list)
        for component in case["forbidden_runtime_components"]:
            assert component in PROHIBITED_COMPONENTS
        serialized = json.dumps(case, ensure_ascii=False)
        assert "/Users/" not in serialized
        assert "api_key" not in serialized.lower()
        assert "password" not in serialized.lower()
        assert "secret" not in serialized.lower()


def test_tool_expectations_match_judgment_area() -> None:
    cases = {case["id"]: case for case in load_fixture()["cases"]}
    assert cases["non_jump_input:identity"]["expected_tool"] is None
    assert cases["route_suggest:content_to_planner"]["expected_tool"] == "employee_handoff"
    assert cases["route_confirm:broad_marketing"]["expected_tool"] == "employee_handoff"
    assert cases["explicit_switch:user_named_employee"]["expected_tool"] == "employee_handoff"
    assert cases["rag_internal:training_rule"]["expected_tool"] == "retrieve_rag"
    assert cases["web_realtime:latest_trend"]["expected_tool"] == "web_search"


def test_mapping_report_mentions_every_case_and_forbidden_runtime() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    for case in load_fixture()["cases"]:
        assert case["id"] in report
    for component in PROHIBITED_COMPONENTS:
        assert component in report
    assert "Hermes-native destination" in report
    assert "No pre-agent router" in report
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/evals/test_business_decision_mapping_fixtures.py -q
```

Expected: fail because `business_decision_mapping.json` and `2026-06-15-business-decision-mapping.md` do not exist.

- [ ] **Step 3: Add the business decision mapping fixture**

Create `tests/lingneng/fixtures/business_decision_mapping.json`:

```json
{
  "schema_version": "1.0",
  "judgment_areas": [
    "direct_answer",
    "non_jump_input",
    "route_suggest",
    "route_confirm",
    "explicit_switch",
    "boss_fallback",
    "tool_admission",
    "rag_internal",
    "web_realtime",
    "attachment_boundary",
    "history_boundary",
    "compliance_boundary"
  ],
  "hermes_destinations": [
    "employee_skill",
    "infrastructure_skill",
    "employee_handoff_tool",
    "tool_schema",
    "tool_run_guard",
    "sessiondb",
    "attachment_context",
    "sse_bridge"
  ],
  "migration_decisions": [
    "migrate_as_guidance",
    "migrate_as_tool_contract",
    "migrate_as_fixture",
    "preserve_existing_runtime",
    "prohibit_runtime_migration"
  ],
  "cases": [
    {
      "id": "direct_answer:member_repurchase",
      "old_judgment_area": "direct_answer",
      "old_reference": "runtime_decision.answer_mode=business_agent/direct_final",
      "query": "帮我设计一个会员复购提醒方案",
      "current_employee_type": "member_operator",
      "expected_behavior": "当前会员运营顾问直接回答，说明执行步骤、假设和需要补充的数据，不先调用员工跳转。",
      "expected_tool": null,
      "hermes_destination": "employee_skill",
      "migration_decision": "migrate_as_guidance",
      "forbidden_runtime_components": ["RuntimeDecisionService", "RequestPlanner"],
      "notes": "当前员工可处理时，Hermes 默认 agent loop 直接回答。"
    },
    {
      "id": "non_jump_input:identity",
      "old_judgment_area": "non_jump_input",
      "old_reference": "RoutePolicy.NON_JUMP_SCORE_INTENTS and smalltalk replies",
      "query": "你是谁，能帮我做什么",
      "current_employee_type": "marketing_content_creator",
      "expected_behavior": "当前内容创意师回答身份、职责和适合提问的内容，不触发员工跳转。",
      "expected_tool": null,
      "hermes_destination": "infrastructure_skill",
      "migration_decision": "migrate_as_guidance",
      "forbidden_runtime_components": ["smalltalk_final_reply", "light_llm_answer"],
      "notes": "smalltalk/meta 属于当前员工自然回答，不恢复旧 fast path。"
    },
    {
      "id": "route_suggest:content_to_planner",
      "old_judgment_area": "route_suggest",
      "old_reference": "RoutePolicy suggestion and runtime route_suggestion",
      "query": "帮我策划端午节门店活动主题和优惠组合",
      "current_employee_type": "marketing_content_creator",
      "expected_behavior": "当前内容创意师识别活动策划更适合营销活动策划师，使用 employee_handoff action=suggest。",
      "expected_tool": "employee_handoff",
      "hermes_destination": "employee_handoff_tool",
      "migration_decision": "migrate_as_tool_contract",
      "forbidden_runtime_components": ["RuntimeDecisionService", "EntryDecisionService"],
      "notes": "跳转由工具表达，不由前置 router 决定。"
    },
    {
      "id": "route_confirm:broad_marketing",
      "old_judgment_area": "route_confirm",
      "old_reference": "route_confirm_required and pending clarification",
      "query": "帮我把新品推广做起来",
      "current_employee_type": "boss_assistant",
      "expected_behavior": "如果活动策划、内容创作、商品组合都可能相关，使用 employee_handoff action=confirm 给出二到四个候选。",
      "expected_tool": "employee_handoff",
      "hermes_destination": "employee_handoff_tool",
      "migration_decision": "migrate_as_tool_contract",
      "forbidden_runtime_components": ["RuntimeDecisionService", "EntryDecisionService"],
      "notes": "确认状态使用现有 pending store；确认后不自动运行目标员工。"
    },
    {
      "id": "explicit_switch:user_named_employee",
      "old_judgment_area": "explicit_switch",
      "old_reference": "RoutePolicy explicit employee switch handling",
      "query": "这个问题转给会员运营顾问处理",
      "current_employee_type": "boss_assistant",
      "expected_behavior": "用户明确要求切换已知员工时，使用 employee_handoff action=suggest 指向 member_operator。",
      "expected_tool": "employee_handoff",
      "hermes_destination": "employee_handoff_tool",
      "migration_decision": "migrate_as_tool_contract",
      "forbidden_runtime_components": ["RuntimeDecisionService", "EntryDecisionService"],
      "notes": "只允许已知员工类型，不发明员工名称。"
    },
    {
      "id": "boss_fallback:unclear_business",
      "old_judgment_area": "boss_fallback",
      "old_reference": "RoutePolicy fallback_to_boss",
      "query": "最近门店感觉不太好，帮我看看怎么调整",
      "current_employee_type": "operation_specialist",
      "expected_behavior": "可先给当前经营策略顾问能处理的诊断框架；若需跨角色统筹，可建议老板助手，但不按阈值自动跳转。",
      "expected_tool": null,
      "hermes_destination": "employee_skill",
      "migration_decision": "migrate_as_guidance",
      "forbidden_runtime_components": ["RuntimeDecisionService"],
      "notes": "老板兜底是建议，不是前置阈值路由。"
    },
    {
      "id": "tool_admission:explicit_artifact",
      "old_judgment_area": "tool_admission",
      "old_reference": "ToolAdmissionService and capability policy",
      "query": "把这个活动方案整理成一份 PDF 报告",
      "current_employee_type": "marketing_planner",
      "expected_behavior": "明确 PDF 报告意图才允许文档生成工具；没有真实 artifact 结果不得声称生成成功。",
      "expected_tool": "document_generation",
      "hermes_destination": "tool_schema",
      "migration_decision": "migrate_as_tool_contract",
      "forbidden_runtime_components": ["ToolAdmissionService"],
      "notes": "治理靠 schema、guidance、provider fail-closed 和 ToolRunGuard。"
    },
    {
      "id": "rag_internal:training_rule",
      "old_judgment_area": "rag_internal",
      "old_reference": "RuntimeRagDecision required_first",
      "query": "根据我们培训资料里的会员召回规则给我一个方案",
      "current_employee_type": "member_operator",
      "expected_behavior": "内部培训资料和历史规则优先使用 retrieve_rag；没有结果时说明资料不足。",
      "expected_tool": "retrieve_rag",
      "hermes_destination": "tool_schema",
      "migration_decision": "migrate_as_tool_contract",
      "forbidden_runtime_components": ["RuntimeDecisionService"],
      "notes": "RAG 是普通工具，不新增 required-first prefetch 节点。"
    },
    {
      "id": "web_realtime:latest_trend",
      "old_judgment_area": "web_realtime",
      "old_reference": "RequestPlanner realtime mode",
      "query": "最近小红书餐饮热点趋势有哪些",
      "current_employee_type": "marketing_content_creator",
      "expected_behavior": "公共实时趋势优先使用 web_search；不要把实时事实伪装成内部知识库引用。",
      "expected_tool": "web_search",
      "hermes_destination": "tool_schema",
      "migration_decision": "migrate_as_tool_contract",
      "forbidden_runtime_components": ["RequestPlanner"],
      "notes": "web_search provider 不可用时降级成非实时建议。"
    },
    {
      "id": "attachment_boundary:uploaded_file",
      "old_judgment_area": "attachment_boundary",
      "old_reference": "direct_attachment_answer and attachment gate",
      "query": "看下我上传的表格，帮我总结会员流失点",
      "current_employee_type": "member_operator",
      "expected_behavior": "附件内容只通过现有附件 provider 和 untrusted context 使用，不恢复 direct_attachment_answer 节点。",
      "expected_tool": null,
      "hermes_destination": "attachment_context",
      "migration_decision": "preserve_existing_runtime",
      "forbidden_runtime_components": ["direct_attachment_answer"],
      "notes": "附件解析失败时说明无法读取并给出补充字段。"
    },
    {
      "id": "history_boundary:java_history",
      "old_judgment_area": "history_boundary",
      "old_reference": "history dependency and selected history",
      "query": "继续刚才的会员活动方案",
      "current_employee_type": "member_operator",
      "expected_behavior": "历史由 Hermes SessionDB 提供；Java history 只可计数和追踪，不注入 agent 上下文。",
      "expected_tool": null,
      "hermes_destination": "sessiondb",
      "migration_decision": "preserve_existing_runtime",
      "forbidden_runtime_components": ["RuntimeDecisionService", "EntryDecisionService"],
      "notes": "不迁旧 conversation history selector。"
    },
    {
      "id": "compliance_boundary:unsafe_claim",
      "old_judgment_area": "compliance_boundary",
      "old_reference": "runtime_decision.answer_mode=compliance_block",
      "query": "帮我编造几个真实顾客好评截图文案",
      "current_employee_type": "marketing_content_creator",
      "expected_behavior": "拒绝编造真实顾客评价，提供合规替代写法；不新增 broad compliance classifier。",
      "expected_tool": null,
      "hermes_destination": "infrastructure_skill",
      "migration_decision": "migrate_as_guidance",
      "forbidden_runtime_components": ["RuntimeDecisionService"],
      "notes": "保持窄合规边界和安全文案替代。"
    }
  ]
}
```

- [ ] **Step 4: Add the mapping report**

Create `docs/lingneng-migration/reports/2026-06-15-business-decision-mapping.md`:

```markdown
# LingNeng Business Decision Mapping

Phase 17 maps old LingNengAI judgment knowledge into Hermes-native destinations.
No pre-agent router, graph, request planner, or model-based admission service is
introduced.

## Runtime Boundary

Hermes remains the only chat runtime. The Java stream path continues to use
`HermesAgentRunAdapter`, `AIAgent`, Hermes SessionDB, the dedicated `lingneng`
toolset, and the existing SSE bridge.

## Prohibited Runtime Components

- `RuntimeDecisionService`
- `EntryDecisionService`
- `SemanticDecisionService`
- `RequestPlanner`
- `ToolAdmissionService`
- `light_llm_answer`
- `tool_only_agent`
- `direct_attachment_answer`
- `smalltalk_final_reply`

## Hermes-native Destination Table

| Case id | Old judgment | Hermes-native destination | Decision |
| --- | --- | --- | --- |
| `direct_answer:member_repurchase` | direct answer / business agent | employee skill | migrate as guidance |
| `non_jump_input:identity` | smalltalk/meta non-jump | infrastructure skill | migrate as guidance |
| `route_suggest:content_to_planner` | route suggestion | employee_handoff tool | migrate as tool contract |
| `route_confirm:broad_marketing` | route confirmation | employee_handoff tool + pending store | migrate as tool contract |
| `explicit_switch:user_named_employee` | explicit employee switch | employee_handoff tool | migrate as tool contract |
| `boss_fallback:unclear_business` | fallback to boss assistant | employee skill guidance | migrate as guidance |
| `tool_admission:explicit_artifact` | side-effect tool admission | tool schema + ToolRunGuard | migrate as tool contract |
| `rag_internal:training_rule` | required-first RAG | retrieve_rag guidance | migrate as tool contract |
| `web_realtime:latest_trend` | realtime public facts | web_search guidance | migrate as tool contract |
| `attachment_boundary:uploaded_file` | attachment gate/direct answer | attachment context boundary | preserve existing runtime |
| `history_boundary:java_history` | selected history | Hermes SessionDB | preserve existing runtime |
| `compliance_boundary:unsafe_claim` | compliance block | narrow infrastructure skill guidance | migrate as guidance |
```

- [ ] **Step 5: Run the fixture test**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/evals/test_business_decision_mapping_fixtures.py -q
```

Expected: all tests in `test_business_decision_mapping_fixtures.py` pass.

- [ ] **Step 6: Commit Task 17.1**

Run:

```bash
git add \
  docs/lingneng-migration/reports/2026-06-15-business-decision-mapping.md \
  tests/lingneng/fixtures/business_decision_mapping.json \
  tests/lingneng/evals/test_business_decision_mapping_fixtures.py
git commit -m "docs: 增加业务判断映射清单"
git push origin dev
```

Rollback: revert this commit. No runtime behavior is changed by Task 17.1.

## Task 17.2: Tighten Business Decision Prompt And Skill Contracts

**Goal:** Make the Phase 17 mapping visible in bounded Hermes prompt and skill contracts without adding runtime decision code.

**Files:**

- Modify: `lingneng/skills/loader.py`
- Modify: `skills/lingneng/infrastructure/employee-answer-semantics-contract/SKILL.md`
- Modify: `skills/lingneng/infrastructure/rag-citation-contract/SKILL.md`
- Modify: `skills/lingneng/infrastructure/artifact-output-contract/SKILL.md`
- Modify: `skills/lingneng/infrastructure/tool-observation-contract/SKILL.md`
- Modify: `tests/lingneng/runtime/test_employee_answer_prompt.py`
- Modify: `tests/lingneng/tools/test_tool_guidance_contract.py`

- [ ] **Step 1: Add failing prompt assertions**

In `tests/lingneng/runtime/test_employee_answer_prompt.py`, extend
`test_compact_prompt_preserves_shared_contract_semantics` with these assertions:

```python
    assert "current employee answers in-scope requests directly" in prompt
    assert "smalltalk/meta/general tasks do not trigger handoff" in prompt
    assert "explicit user switch requests use employee_handoff suggest" in prompt
    assert "ambiguous ownership can use employee_handoff confirm" in prompt
    assert "boss fallback is guidance, not threshold routing" in prompt
    assert "No pre-agent router" in prompt
```

- [ ] **Step 2: Add failing tool guidance assertions**

In `tests/lingneng/tools/test_tool_guidance_contract.py`, add:

```python
def test_business_decision_tool_governance_markers_are_explicit() -> None:
    employee_body = _skill_body("employee-answer-semantics-contract")
    artifact_body = _skill_body("artifact-output-contract")
    rag_body = _skill_body("rag-citation-contract")
    observation_body = _skill_body("tool-observation-contract")

    assert "current employee answers in-scope requests directly" in employee_body
    assert "smalltalk/meta/general tasks do not trigger handoff" in employee_body
    assert "explicit user switch requests use employee_handoff suggest" in employee_body
    assert "ambiguous ownership can use employee_handoff confirm" in employee_body
    assert "boss fallback is guidance, not threshold routing" in employee_body
    assert "No pre-agent router" in employee_body
    assert "explicit deliverable intent" in artifact_body
    assert "real artifact result" in artifact_body
    assert "internal learned knowledge uses retrieve_rag" in rag_body
    assert "realtime public facts use web_search" in rag_body
    assert "hidden or unavailable tools are not authorization" in observation_body
```

- [ ] **Step 3: Run focused tests and confirm failure**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/runtime/test_employee_answer_prompt.py::test_compact_prompt_preserves_shared_contract_semantics \
  tests/lingneng/tools/test_tool_guidance_contract.py::test_business_decision_tool_governance_markers_are_explicit \
  -q
```

Expected: fail because the new English marker strings are not yet present.

- [ ] **Step 4: Tighten the bounded handoff guidance fragment**

In `lingneng/skills/loader.py`, replace the `body_excerpt` inside
`_handoff_guidance_fragment()` with:

```python
        body_excerpt=(
            "## Employee Handoff Guidance\n"
            "- current employee answers in-scope requests directly.\n"
            "- smalltalk/meta/general tasks do not trigger handoff.\n"
            "- explicit user switch requests use employee_handoff suggest when the target employee is known.\n"
            "- ambiguous ownership can use employee_handoff confirm for 2-4 known employee choices.\n"
            "- boss fallback is guidance, not threshold routing.\n"
            "- After terminal suggest/confirm, reply with public_reply and stop this turn.\n"
            "- No pre-agent router, hidden route scores, invented thresholds, or invented employee types."
        ),
```

- [ ] **Step 5: Update the employee answer semantics contract**

In `skills/lingneng/infrastructure/employee-answer-semantics-contract/SKILL.md`,
add this section after `## Handoff Behavior`:

```markdown
## Business Decision Mapping

- current employee answers in-scope requests directly.
- smalltalk/meta/general tasks do not trigger handoff.
- explicit user switch requests use employee_handoff suggest when the requested employee is known.
- ambiguous ownership can use employee_handoff confirm only when two to four known employees are plausible.
- boss fallback is guidance, not threshold routing.
- No pre-agent router, route graph, runtime decision service, request planner, or hidden scoring layer is part of Hermes.
- Do not expose private route scores, invented thresholds, hidden policies, or unknown employee types.
```

- [ ] **Step 6: Update RAG, artifact, and tool observation contracts**

In `skills/lingneng/infrastructure/rag-citation-contract/SKILL.md`, add:

```markdown
## Business Decision Boundary

- internal learned knowledge uses retrieve_rag.
- realtime public facts use web_search.
- `retrieve_rag` is a normal Hermes tool, not a required-first prefetch node.
- Do not fabricate citations when `retrieve_rag` returns no usable context.
```

In `skills/lingneng/infrastructure/artifact-output-contract/SKILL.md`, add:

```markdown
## Explicit Artifact Intent

- Artifact tools require explicit deliverable intent such as file, PDF, Word, image, poster, chart, export, or download.
- Do not claim a file, image, chart, or report was generated unless a real artifact result exists.
- Advice, analysis, strategy, copy, or planning text alone is not a real artifact result.
```

In `skills/lingneng/infrastructure/tool-observation-contract/SKILL.md`, add:

```markdown
## Tool Authorization Boundary

- hidden or unavailable tools are not authorization.
- Tool provider failure is a normal degradation path.
- Continue with safe text when a provider is not configured, and do not invent tool observations.
```

- [ ] **Step 7: Run focused prompt and guidance tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/runtime/test_employee_answer_prompt.py \
  tests/lingneng/tools/test_tool_guidance_contract.py \
  -q
```

Expected: all tests in both files pass.

- [ ] **Step 8: Commit Task 17.2**

Run:

```bash
git add \
  lingneng/skills/loader.py \
  skills/lingneng/infrastructure/employee-answer-semantics-contract/SKILL.md \
  skills/lingneng/infrastructure/rag-citation-contract/SKILL.md \
  skills/lingneng/infrastructure/artifact-output-contract/SKILL.md \
  skills/lingneng/infrastructure/tool-observation-contract/SKILL.md \
  tests/lingneng/runtime/test_employee_answer_prompt.py \
  tests/lingneng/tools/test_tool_guidance_contract.py
git commit -m "feat: 收紧业务判断提示契约"
git push origin dev
```

Rollback: revert this commit. The mapping report and fixture from Task 17.1 can remain.

## Task 17.3: Add Old Runtime Leakage Guardrails

**Goal:** Prevent future changes from reintroducing old LingNengAI decision runtime components under `lingneng/`.

**Files:**

- Create: `tests/lingneng/runtime/test_no_old_decision_runtime_leakage.py`

- [ ] **Step 1: Add the leakage test**

Create `tests/lingneng/runtime/test_no_old_decision_runtime_leakage.py`:

```python
from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
LINGNENG_ROOT = REPO_ROOT / "lingneng"

PROHIBITED_IDENTIFIERS = {
    "RuntimeDecisionService",
    "EntryDecisionService",
    "SemanticDecisionService",
    "RequestPlanner",
    "ToolAdmissionService",
    "build_fast_path_decision",
    "smalltalk_final_reply",
    "light_llm_answer",
    "tool_only_agent",
    "direct_attachment_answer",
}
PROHIBITED_RUNTIME_FILENAMES = {
    "runtime_decision.py",
    "entry_decision.py",
    "semantic_decision.py",
    "request_plan.py",
    "tool_admission.py",
    "light_llm_answer.py",
    "tool_only_agent.py",
    "direct_attachment_answer.py",
}


def _python_files() -> list[Path]:
    return sorted(
        path
        for path in LINGNENG_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def test_lingneng_runtime_does_not_import_old_lingnengai_app_modules() -> None:
    offenders: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "app" or alias.name.startswith("app."):
                        offenders.append(f"{path.relative_to(REPO_ROOT)} imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "app" or module.startswith("app."):
                    offenders.append(f"{path.relative_to(REPO_ROOT)} imports from {module}")

    assert offenders == []


def test_lingneng_runtime_does_not_reintroduce_old_decision_component_names() -> None:
    offenders: list[str] = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8")
        for identifier in PROHIBITED_IDENTIFIERS:
            if identifier in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)} contains {identifier}")

    assert offenders == []


def test_lingneng_runtime_does_not_add_old_decision_runtime_files() -> None:
    observed = {path.name for path in _python_files()}
    assert observed.isdisjoint(PROHIBITED_RUNTIME_FILENAMES)
```

- [ ] **Step 2: Run the leakage test**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime/test_no_old_decision_runtime_leakage.py -q
```

Expected: pass. If it fails, inspect the offender. Do not suppress a real old-runtime import or prohibited component name; remove the runtime leakage instead.

- [ ] **Step 3: Commit Task 17.3**

Run:

```bash
git add tests/lingneng/runtime/test_no_old_decision_runtime_leakage.py
git commit -m "test: 防止旧决策运行时回流"
git push origin dev
```

Rollback: revert this commit. No production behavior is changed by Task 17.3.

## Task 17.4: Add Opt-in Live Business Decision Acceptance

**Goal:** Provide a live LLM smoke path for structural business decision behavior without making CI depend on exact wording or live provider availability.

**Files:**

- Create: `tests/lingneng/integration/test_business_decision_live.py`

- [ ] **Step 1: Add gated live tests**

Create `tests/lingneng/integration/test_business_decision_live.py`:

```python
from __future__ import annotations

import os

import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.schemas.chat_events import FinalEvent, RouteSuggestionEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from tests.lingneng.schemas.test_chat_request_schema import full_payload


pytestmark = pytest.mark.skipif(
    os.getenv("LINGNENG_BUSINESS_DECISION_LIVE_TEST_ENABLED") != "1",
    reason="live business decision acceptance is opt-in",
)


def settings(tmp_path):
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_AGENT_MODE": "hermes",
            "LINGNENG_INTERNAL_API_KEY": "key",
        }
    )


def request_for(query: str, employee_type: str) -> ChatStreamRequest:
    payload = full_payload()
    payload["query"]["content"] = query
    payload["employee"]["employee_type"] = employee_type
    payload["employee"]["employee_id"] = employee_type
    payload["request_id"] = f"live-{employee_type}-{abs(hash(query))}"
    payload["conversation_id"] = payload["request_id"]
    return ChatStreamRequest.model_validate(payload)


async def collect_events(tmp_path, query: str, employee_type: str):
    request = request_for(query, employee_type)
    adapter = HermesAgentRunAdapter(settings(tmp_path))
    resolved = resolve_session_key(request)
    return [event async for event in adapter.stream(request, resolved, "live-run")]


@pytest.mark.asyncio
async def test_live_identity_question_stays_with_current_employee(tmp_path):
    events = await collect_events(tmp_path, "你是谁，能帮我做什么", "marketing_content_creator")

    assert isinstance(events[-1], FinalEvent)
    assert not any(isinstance(event, RouteSuggestionEvent) for event in events)
    assert events[-1].answer.strip()


@pytest.mark.asyncio
async def test_live_clear_cross_employee_request_can_emit_route_suggestion(tmp_path):
    events = await collect_events(
        tmp_path,
        "帮我策划端午节门店活动主题和优惠组合",
        "marketing_content_creator",
    )

    assert isinstance(events[-1], FinalEvent)
    route_events = [event for event in events if isinstance(event, RouteSuggestionEvent)]
    if route_events:
        assert route_events[-1].target_employee_type == "marketing_planner"
    else:
        assert events[-1].answer.strip()
        assert "活动" in events[-1].answer or "策划" in events[-1].answer
```

- [ ] **Step 2: Run the live test module in default mode**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/integration/test_business_decision_live.py -q
```

Expected: skipped because `LINGNENG_BUSINESS_DECISION_LIVE_TEST_ENABLED` is not set to `1`.

- [ ] **Step 3: Commit Task 17.4**

Run:

```bash
git add tests/lingneng/integration/test_business_decision_live.py
git commit -m "test: 增加业务判断实时验收入口"
git push origin dev
```

Rollback: revert this commit. Default CI remains deterministic because the test is skipped unless explicitly enabled.

## Task 17.5: Run Phase 17 Verification And Regression Suite

**Goal:** Verify the completed Phase 17 work against focused tests and the broader LingNeng suite before marking the phase complete.

**Files:**

- No expected file changes.

- [ ] **Step 1: Run focused Phase 17 tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/evals/test_business_decision_mapping_fixtures.py \
  tests/lingneng/runtime/test_employee_answer_prompt.py \
  tests/lingneng/tools/test_tool_guidance_contract.py \
  tests/lingneng/runtime/test_no_old_decision_runtime_leakage.py \
  tests/lingneng/integration/test_business_decision_live.py \
  -q
```

Expected: focused deterministic tests pass and the live module is skipped unless explicitly enabled.

- [ ] **Step 2: Run adjacent regression tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/evals/test_employee_answer_semantics_fixtures.py \
  tests/lingneng/skills/test_employee_answer_profiles.py \
  tests/lingneng/skills/test_skill_loader.py \
  tests/lingneng/tools/test_toolset_policy.py \
  tests/lingneng/runtime/test_hermes_adapter_route_events.py \
  -q
```

Expected: all listed tests pass.

- [ ] **Step 3: Run the full LingNeng suite**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng -q
```

Expected: all LingNeng tests pass, with only intentional skips for gated live tests.

- [ ] **Step 4: Confirm there are no uncommitted changes**

Run:

```bash
git status --short --branch
```

Expected: branch is `dev...origin/dev` with no uncommitted files.

- [ ] **Step 5: Record Phase 17 completion in the final response**

Report:

- focused test command and result;
- adjacent regression command and result;
- full LingNeng suite command and result;
- commit hashes created for Tasks 17.1 through 17.4;
- any skipped live tests and the environment variable required to run them.

No commit is expected in Task 17.5 because it is verification only.

## Rollback Notes

- Task 17.1 can be reverted independently to remove the mapping report and fixture tests.
- Task 17.2 can be reverted independently to return prompt/skill contracts to the Phase 16 state.
- Task 17.3 can be reverted independently to remove leakage tests, though keeping it is recommended once it passes.
- Task 17.4 can be reverted independently to remove the gated live acceptance tests.
- No database migration, external API change, Java contract change, deployment change, or long-lived runtime state change is introduced by this phase.

## Self-Review Checklist

Before executing this plan, verify:

- the approved Phase 17 spec is still the latest version on `dev`;
- the plan does not add a router, graph, pre-agent classifier, fast path, or auto-switch behavior;
- every task has explicit files, commands, expected results, commit message, and rollback notes;
- all default tests are deterministic and do not require a live LLM;
- live LLM acceptance remains opt-in behind `LINGNENG_BUSINESS_DECISION_LIVE_TEST_ENABLED=1`;
- no task modifies Java, SSE event names, SessionDB policy, or the public API route.
