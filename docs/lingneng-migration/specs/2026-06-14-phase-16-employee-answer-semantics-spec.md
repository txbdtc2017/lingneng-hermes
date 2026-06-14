# Phase 16 LingNeng Employee Answer Semantics Spec

## Status

Drafted on `dev` after Phase 15 locked the training and RAG ingestion boundary
to the old LingNengAI service.

This phase migrates the remaining LingNeng business answer behavior that is
valuable for Java stream chat, without bringing back the old LingNengAI
LangGraph runtime:

```text
old LingNeng employee answer semantics -> Hermes-native skills, prompt context, tool guidance, and eval fixtures
```

## Required Context Reloaded

Reloaded before writing this spec:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-11-lingneng-business-capability-hermes-migration-spec.md`
- `docs/lingneng-migration/specs/2026-06-11-phase-9-hermes-native-skill-catalog-spec.md`
- `docs/lingneng-migration/specs/2026-06-11-phase-10-agent-native-employee-handoff-spec.md`
- `docs/lingneng-migration/specs/2026-06-11-phase-11-time-context-prompt-hardening-spec.md`
- `docs/lingneng-migration/specs/2026-06-11-phase-12-real-business-tool-providers-spec.md`
- `docs/lingneng-migration/specs/2026-06-12-phase-14-rag-provider-hardening-spec.md`
- `docs/lingneng-migration/specs/2026-06-12-phase-15-training-boundary-decision.md`

Current Hermes-side modules inspected:

- `lingneng/runtime/hermes_adapter.py`
- `lingneng/context/prompt.py`
- `lingneng/skills/catalog.py`
- `lingneng/skills/loader.py`
- `lingneng/skills/models.py`
- `lingneng/tools/employee_handoff.py`
- `lingneng/tools/limits.py`
- `lingneng/tools/toolset.py`
- `skills/lingneng/employees/*/SKILL.md`
- `skills/lingneng/tasks/*/SKILL.md`
- `skills/lingneng/capabilities/*/SKILL.md`
- `skills/lingneng/infrastructure/*/SKILL.md`

LingNengAI reference modules inspected from the sibling checkout:

- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/chat/graph.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/chat/nodes/entry_decision.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/chat/nodes/request_plan.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/chat/nodes/business_agent.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/chat/nodes/smalltalk_final_reply.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/prompt/builders/business_agent.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/prompt/sections.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/employees/smalltalk_reply.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/tools/admission.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/tools/capability_policy.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/skills/**/SKILL.md`

The sibling LingNengAI checkout was on
`2026061317-stream-acceptance-suite` during inspection. Runtime code must still
not import old `app.*` modules. If strict comparison against another LingNengAI
branch is required, re-check that branch before writing the Phase 16 plan.

## Current Baseline

The Hermes fork already has the runtime shell required for this phase:

- Java-compatible `/internal/agent/chat/stream`.
- Hermes-managed SessionDB history and request idempotency.
- Dedicated `lingneng` toolset with high-risk Hermes tools excluded.
- Repo-bundled LingNeng skill packages under `skills/lingneng/`.
- Skill list/search/read/resource tools.
- Agent-native `employee_handoff` tool and route SSE bridge.
- Deterministic time context and trusted/untrusted prompt sections.
- Real provider boundaries for RAG query, web search, document generation,
  image generation, chart visualization, artifacts, and attachment
  understanding.
- Training and RAG ingestion explicitly left in the old LingNengAI service.

The current gap is not another runtime framework. The gap is answer quality and
business behavior parity:

- Employee skills are present, but they are still thin compared with old
  LingNeng's production answer prompts and employee smalltalk behavior.
- Old business prompt rules such as answer structure, tool-use ordering,
  artifact caution, RAG-vs-web guidance, and insufficient-data behavior are not
  fully represented in Hermes-native skill or prompt contracts.
- Old `entry_decision`, `request_plan`, and `tool_admission` contain useful
  judgment rules, but they are tied to a pre-agent graph and LLM classifier
  shape that should not be copied.
- There is no deterministic comparison fixture that proves each digital
  employee answers with the expected business scope, style, handoff behavior,
  and tool-use policy.

## Goal

Make LingNeng-Hermes answer like LingNeng's digital employees while preserving
Hermes as the only agent runtime.

Phase 16 should:

1. Extract the old LingNeng digital employee answer semantics into
   Hermes-native skill packages and infrastructure contracts.
2. Strengthen each employee's role identity, service audience, scope,
   answer style, smalltalk/scope reply, handoff boundary, and degradation
   behavior.
3. Move old useful business judgment rules into deterministic prompt guidance
   and tool policy text, not into a second pre-agent router.
4. Make artifact, RAG, web search, and business tool usage expectations clear
   to the model through existing Hermes tool schemas and skill guidance.
5. Add tests and fixtures that can catch regressions without depending on live
   LLM output by default.
6. Provide an optional live acceptance path for configured LLM environments.

## Scope

Phase 16 includes:

1. Audit the old LingNengAI employee smalltalk replies, business prompt builder,
   request planning shortcuts, tool admission prompt, and capability policy.
2. Define a Hermes-native employee answer profile contract for the six current
   LingNeng employee types:
   - `boss_assistant`
   - `operation_specialist`
   - `product_combo_advisor`
   - `marketing_planner`
   - `marketing_content_creator`
   - `member_operator`
3. Update the six employee base skills so each profile has explicit:
   - role identity
   - service audience
   - business scope
   - operating principles
   - communication style
   - normal answer structure
   - identity/smalltalk reply guidance
   - out-of-scope and insufficient-data behavior
   - recommended handoff targets
   - recommended task and capability skills
   - recommended tools and tool constraints
4. Strengthen infrastructure skills where needed:
   - `business-answer-contract`
   - `tool-observation-contract`
   - `artifact-output-contract`
   - `rag-citation-contract`
5. Add a new infrastructure skill only if the existing contracts become too
   overloaded. The expected name is `employee-answer-semantics-contract`.
6. Preserve progressive disclosure: full employee/task/reference content must
   not be injected unbounded into the system prompt.
7. Update prompt construction only where the existing skill prompt cannot carry
   the profile safely. Any new prompt section must remain under the existing
   LingNeng trusted prompt boundary.
8. Convert old useful `entry_decision` and `request_plan` rules into
   guidance, fixtures, or deterministic tests:
   - direct smalltalk/identity behavior
   - tool-use caution for artifact and external-action tools
   - RAG before public web search for internal learned business knowledge
   - public web search for realtime public facts
   - answer with a conservative checklist when required data is missing
9. Convert old useful `tool_admission` behavior into Hermes-native guardrails:
   - artifact tools should require explicit file/image/chart/export intent
   - hidden or unavailable tools are not authorized
   - generated artifact claims must be backed by a real artifact result
   - duplicate artifact attempts remain suppressed by the existing run guard
10. Add answer semantics fixtures for the six employee types, covering:
    - identity and capability question
    - in-scope business question
    - out-of-scope question
    - handoff-needed question
    - insufficient-data question
    - tool-needed question
11. Add prompt regression tests that assert profile and infrastructure contract
    text appears in stable, bounded sections for the current employee.
12. Add old-runtime leakage tests proving Phase 16 does not import or depend on
    the sibling LingNengAI checkout.
13. Add optional live LLM acceptance scripts or tests behind an explicit
    environment gate.

## Non-Goals

Phase 16 does not:

- Modify Java code or change `/internal/agent/chat/stream`.
- Add a new LangGraph, router graph, request-planning graph, or old
  `business_agent` harness.
- Rebuild old `entry_decision`, `request_plan`, `history_policy`,
  `light_llm_answer`, or `tool_only_agent` as pre-agent nodes.
- Add a hidden LLM classifier before Hermes `AIAgent`.
- Automatically re-run another employee inside the same Python request.
- Migrate old conversation history fetching or Java `history` selection.
- Migrate training intake, document parsing, chunking, embedding, vector
  indexing, activation, cancellation, or training events.
- Implement native in-Hermes RAG retrieval/indexing beyond the existing external
  RAG query tool boundary.
- Add new live providers beyond those already configured by previous phases.
- Enable `read_workspace` or `write_workspace`.
- Expose terminal, arbitrary filesystem, browser automation, code execution,
  messaging, dashboard, or Kanban tools to the Java API.
- Require exact text equality from live LLM answers in CI.
- Add Docker, deployment, or GitHub Actions changes.

## Accepted Decisions

1. **Answer semantics live in skills and prompt contracts.** Digital employee
   behavior is represented through validated skill packages, infrastructure
   skills, and bounded prompt sections.
2. **Hermes remains the only chat loop.** `HermesAgentRunAdapter` and
   `AIAgent` continue to own the conversation. Old LingNeng graph nodes are
   reference input only.
3. **Smalltalk is scoped, not globally appended.** Old employee fixed replies
   become identity, capability, and out-of-scope guidance. Normal business
   answers should not be polluted with repeated self-introduction text.
4. **Tool admission becomes deterministic guidance and guardrails.** Phase 16
   does not add another LLM admission classifier. The existing toolset boundary,
   tool schemas, and run guard remain the enforcement points.
5. **Routing stays agent-native.** When a request belongs to another employee,
   the current agent should use `employee_handoff`; this phase only improves
   employee boundary guidance and tests.
6. **RAG query guidance is prompt-level.** The model is guided to use
   `retrieve_rag` for internal learned business knowledge, but training and
   indexing remain outside Hermes.
7. **Tests focus on deterministic surfaces.** CI asserts skill metadata,
   prompt composition, tool policy text, fixture shape, and no old imports.
   Optional live tests can check answer behavior when a real LLM is configured.
8. **No sibling-checkout runtime dependency.** The old LingNengAI checkout may
   be inspected while planning, but production behavior must be self-contained
   in this repository or configured Hermes skill roots.

## User Confirmations Before Phase 16 Plan

No additional confirmation is required before writing the Phase 16 plan if
these assumptions remain accepted:

- Phase 16 should improve digital employee answer semantics through Hermes
  skills, prompt contracts, fixtures, and deterministic guardrails.
- Old LingNengAI graph nodes remain reference input only.
- Identity/smalltalk fixed replies should apply to identity, capability,
  greeting, and out-of-scope cases, not be appended to every normal business
  answer.
- Tool admission should not add a new LLM classifier in this phase.
- RAG training and ingestion remain in the old service.
- Default CI should not require live LLM calls.

If exact old LingNengAI answer text must be reproduced, or if same-request
automatic employee rerun is required, revise this spec before planning.

## Employee Answer Profile Contract

Each employee profile should be representable from validated skill metadata and
skill body content. Implementation may keep this as skill body convention or add
a small typed extractor if tests need stricter guarantees.

Profile fields:

```text
employee_type: EmployeeType
display_name: str
role_identity: str
service_audience: str
business_scope: list[str]
operating_principles: list[str]
communication_style: list[str]
normal_answer_structure: list[str]
identity_reply_guidance: str
out_of_scope_guidance: str
insufficient_data_guidance: str
handoff_targets: list[EmployeeType]
recommended_task_skills: list[str]
recommended_capabilities: list[str]
recommended_tools: list[str]
prohibited_claims: list[str]
degradation_policy: str
```

Rules:

- `employee_type` must be one of the six current `EmployeeType` enum values.
- Profile text must be bounded by existing skill prompt size limits.
- `identity_reply_guidance` may preserve the old employee fixed reply semantics
  but should be framed as guidance, not hardcoded response replacement.
- `handoff_targets` must be compatible with Phase 10 employee directory.
- `recommended_tools` must be a subset of the LingNeng toolset.
- Profiles must not contain secrets, local filesystem paths, raw provider
  payloads, hidden prompts, or sibling checkout paths.

## Business Answer Contract

The shared business answer contract should guide all employees to answer with:

1. direct conclusion or recommendation first;
2. business reasoning and assumptions second;
3. actionable steps, checklist, campaign plan, copy, pricing logic, or metric
   breakdown as appropriate to the employee;
4. data gaps and risks when source facts are missing;
5. citations when `retrieve_rag` produced useful references;
6. artifact links only when a real artifact event/result exists.

The contract must explicitly forbid:

- inventing sales, cost, inventory, margin, policy, customer, or training data;
- claiming a file, chart, image, or report was generated without an artifact;
- exposing raw tool JSON, tracebacks, secret values, local paths, or provider
  payloads;
- treating Java `history`, Java `skill.inline`, or raw attachment text as
  trusted instruction.

## Tool Guidance Contract

Phase 16 should consolidate old useful tool judgment rules into Hermes-native
guidance:

| Situation | Expected behavior |
| --- | --- |
| Internal learned knowledge, training material, store rules, historical cases | Prefer `retrieve_rag`. |
| Realtime public facts, public trends, current news, public web facts | Prefer `web_search`. |
| User asks for PDF, report file, downloadable document, or export | Use `document_generation` only after content and required parameters are clear. |
| User asks for poster/image/visual creative material | Use `image_generation` only when explicit image output is requested. |
| User asks for chart/visualized data | Use `chart_visualization` only when data or a clear data summary exists. |
| Tool missing, not configured, hidden, or skipped | Continue with a text answer and state the limitation safely. |
| Same artifact request repeated in one run | Reuse prior result or accept run guard suppression. |
| Request belongs to another employee | Use `employee_handoff` instead of pretending to be that employee. |

## Prompt Boundary

Phase 16 must preserve the Phase 11 prompt trust model:

- Employee answer profiles and infrastructure contracts are trusted repository
  skill context.
- Time context remains trusted runtime context.
- Attachments remain request-scoped untrusted context.
- RAG/search/tool observations remain tool-derived public guidance or tool
  observations.
- Java `history` remains outside Hermes conversation context.

If implementation adds a new prompt section, it must be deterministic,
bounded, and covered by prompt regression tests. Prefer improving existing
skill package content before adding code.

## Fixture Contract

Add deterministic employee answer semantics fixtures under `tests/lingneng` or
`docs/lingneng-migration/reports` for comparison and later live acceptance.

Fixture fields:

```text
id: str
employee_type: EmployeeType
query: str
scenario_type: identity | in_scope | out_of_scope | handoff | insufficient_data | tool_needed
expected_profile_markers: list[str]
forbidden_markers: list[str]
expected_handoff_target: EmployeeType | null
expected_tool_guidance: list[str]
expected_answer_shape: list[str]
requires_live_llm: bool
notes: str
```

Rules:

- CI fixtures should not require a live LLM.
- Live answer checks, if added, must be opt-in through an explicit environment
  flag such as `LINGNENG_EMPLOYEE_SEMANTICS_LIVE_TEST_ENABLED=true`.
- Fixture assertions should use semantic markers, public event order, and tool
  result presence. They must not require exact live model wording.

## Target File Map

Likely files for the Phase 16 plan:

- Modify: `skills/lingneng/employees/*/SKILL.md`
- Modify: `skills/lingneng/infrastructure/business-answer-contract/SKILL.md`
- Modify: `skills/lingneng/infrastructure/tool-observation-contract/SKILL.md`
- Modify: `skills/lingneng/infrastructure/artifact-output-contract/SKILL.md`
- Modify: `skills/lingneng/infrastructure/rag-citation-contract/SKILL.md`
- Optional add:
  `skills/lingneng/infrastructure/employee-answer-semantics-contract/SKILL.md`
- Optional modify: `lingneng/skills/models.py`
- Optional modify: `lingneng/skills/loader.py`
- Optional modify: `lingneng/context/prompt.py`
- Optional modify: `lingneng/runtime/hermes_adapter.py`
- Add tests:
  - `tests/lingneng/skills/test_employee_answer_profiles.py`
  - `tests/lingneng/runtime/test_employee_answer_prompt.py`
  - `tests/lingneng/tools/test_tool_guidance_contract.py`
  - `tests/lingneng/evals/test_employee_answer_semantics_fixtures.py`
  - `tests/lingneng/guardrails/test_no_old_lingneng_runtime_imports.py`
- Optional add report template:
  `docs/lingneng-migration/reports/2026-06-14-employee-answer-semantics-comparison-template.md`

The plan must inspect exact existing tests and may adjust names to match the
current test directory layout.

## Test Strategy

Required deterministic verification:

1. Skill package tests:
   - all six employee profiles are present and active;
   - each profile has identity, scope, out-of-scope, handoff, and degradation
     guidance;
   - recommended tools are valid LingNeng tools;
   - profile content stays within prompt limits.
2. Prompt tests:
   - current employee profile appears in the Hermes system prompt;
   - unrelated employee profiles are not injected unbounded;
   - infrastructure answer/tool/RAG/artifact contracts are present;
   - Java `history`, Java `skill.inline`, local paths, and raw attachment
     bodies do not become trusted prompt text.
3. Tool guidance tests:
   - RAG vs web search guidance is present;
   - artifact tools require explicit output intent;
   - generated artifact claims require real artifact results.
4. Fixture tests:
   - each employee has identity, in-scope, out-of-scope, handoff,
     insufficient-data, and tool-needed fixture coverage;
   - fixture employee and target types are valid;
   - expected markers and forbidden markers are non-empty where required.
5. Guardrail tests:
   - Phase 16 code does not import old `/LingNengAI/app.*`;
   - no new `lingneng/training` package is introduced;
   - no high-risk Hermes tool is added to the Java LingNeng toolset.

Optional live verification:

- Run a configured LLM chat smoke for representative employee scenarios.
- Assert public stream completes with `final`.
- Assert handoff scenarios produce `route_suggestion` or
  `route_confirm_required` when the model uses `employee_handoff`.
- Record comparison notes without failing default CI on wording drift.

## Acceptance Criteria

Phase 16 is complete when:

- The six employee base skills contain complete answer semantics profiles.
- Shared business answer, tool observation, artifact, and RAG citation contracts
  express the useful old LingNeng answer rules in Hermes-native form.
- Hermes prompt construction exposes the current employee's answer profile and
  relevant infrastructure contracts without unbounded injection.
- The model is guided to use `employee_handoff` for cross-employee requests, not
  to recreate a hidden router.
- The model is guided to use `retrieve_rag`, `web_search`, and artifact tools
  under clear business conditions.
- Deterministic tests cover skill profiles, prompt composition, tool guidance,
  fixtures, and no-old-runtime-import guardrails.
- Training and RAG ingestion remain outside Hermes.
- All Phase 16 verification commands in the approved plan pass.

## Risks And Controls

| Risk | Control |
| --- | --- |
| Skill prompts become too large | Keep profile fields bounded and rely on progressive disclosure. |
| Business behavior drifts because LLM wording varies | Test deterministic prompt/profile surfaces and use optional live semantic fixtures. |
| Old graph behavior is accidentally rebuilt | Explicit non-goal, no-old-import tests, and plan review before execution. |
| Tool guidance conflicts with existing schemas | Keep existing Hermes tool schemas authoritative and update skill guidance to match them. |
| Identity reply overappears in normal answers | Scope old fixed replies to identity, greeting, capability, and out-of-scope scenarios. |
| RAG training scope expands by accident | Keep Phase 15 boundary decision referenced and test that no `lingneng/training` package appears. |

## Rollback

Rollback should be simple because Phase 16 is primarily skill and prompt
contract work:

- Revert modified `skills/lingneng/**/SKILL.md` files.
- Revert any optional prompt/model helper changes.
- Keep Phase 9-15 runtime modules, providers, SessionDB behavior, RAG query
  boundary, Docker assets, and Java SSE contract unchanged.

If an optional prompt helper is added, the Phase 16 plan should include a small
rollback note for disabling or reverting that helper without affecting the Java
stream endpoint.

## Next Step

After this spec is reviewed, write the dedicated Phase 16 implementation plan:

```text
docs/lingneng-migration/plans/2026-06-14-phase-16-employee-answer-semantics-plan.md
```

The plan must follow the existing migration rule:

```text
phase spec -> phase plan -> subagent-driven execution
```
