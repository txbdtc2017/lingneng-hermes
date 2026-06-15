# Phase 17 LingNeng Business Decision Mapping Spec

## Status

Drafted on `dev` after Phase 16 completed the first pass of digital employee
answer semantics.

This phase is a boundary and mapping phase. It does not add another runtime
orchestrator. Its purpose is to decide, document, and test how old LingNengAI
business judgment knowledge should live inside Hermes-native skills, tools, run
guards, and fixtures.

Target migration shape:

```text
old LingNeng business judgments -> Hermes skill guidance, tool contracts, run guards, and deterministic tests
```

Rejected migration shape:

```text
old LingNeng runtime_decision / entry_decision / request_plan graph -> Hermes pre-agent router
```

## Required Context Reloaded

Reloaded before writing this spec:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-11-lingneng-business-capability-hermes-migration-spec.md`
- `docs/lingneng-migration/specs/2026-06-11-phase-10-agent-native-employee-handoff-spec.md`
- `docs/lingneng-migration/specs/2026-06-14-phase-16-employee-answer-semantics-spec.md`

Current Hermes-side modules inspected:

- `lingneng/runtime/hermes_adapter.py`
- `lingneng/context/prompt.py`
- `lingneng/skills/loader.py`
- `lingneng/skills/models.py`
- `lingneng/tools/employee_handoff.py`
- `lingneng/tools/limits.py`
- `lingneng/tools/toolset.py`
- `lingneng/tools/rag.py`
- `lingneng/events/bridge.py`
- `skills/lingneng/employees/*/SKILL.md`
- `skills/lingneng/infrastructure/employee-answer-semantics-contract/SKILL.md`
- `skills/lingneng/infrastructure/rag-citation-contract/SKILL.md`

LingNengAI reference modules inspected from the sibling checkout:

- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/chat/graph.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/chat/nodes/runtime_decision.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/chat/nodes/execute_runtime_decision.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/chat/nodes/entry_decision.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/runtime_decision/models.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/runtime_decision/service.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/runtime_decision/fast_path.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/request_plan/planner.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/routing/policy.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/tools/admission.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/tools/capability_policy.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/employees/smalltalk_reply.py`

The sibling LingNengAI checkout is reference material only. Runtime code in this
repository must not import old `app.*` modules.

## Current Baseline

The Hermes fork already has the runtime surfaces required to carry LingNeng
business behavior:

- Java-compatible `/internal/agent/chat/stream`.
- Hermes-owned SessionDB history and request idempotency.
- Dedicated `lingneng` toolset with high-risk Hermes tools excluded.
- Repo-bundled LingNeng employee, task, capability, and infrastructure skills.
- Agent-native `employee_handoff` tool with `current`, `suggest`, and
  `confirm` actions.
- Route SSE bridge for `route_result`, `route_suggestion`, and
  `route_confirm_required`.
- Route pending store for confirmation state.
- Tool provider boundaries for RAG, web search, document generation, image
  generation, chart visualization, artifacts, and attachment understanding.
- `ToolRunGuard` for tool call limits and duplicate suppression.
- Phase 16 employee answer profiles and deterministic semantic fixtures.

The gap is not another router. The gap is that old LingNengAI scattered business
judgment rules still have not been captured as a single Hermes-native mapping.
Without that mapping, future work can accidentally reintroduce old graph nodes
or duplicate old decision layers.

## Problem Statement

Old LingNengAI used a LangGraph-style chat graph where several pre-agent nodes
jointly decided:

- whether to answer directly;
- whether to route, suggest, confirm, or fallback to boss assistant;
- whether to fetch or ignore selected history;
- which tools should be admitted;
- whether RAG should run first;
- whether attachments should be parsed or answered directly;
- whether to use a business agent or tool-only agent profile;
- whether to emit a compliance block;
- how to shape final SSE events and trace metadata.

That design helped old LingNengAI compensate for a weaker agent runtime, but it
is the wrong shape for Hermes. Hermes already has a mature agent loop, tool
schema exposure, SessionDB history, streaming callbacks, and skill system. If
the old pre-agent decision layers are copied into Hermes, the project will have
two competing runtimes and will inherit the old complexity.

Phase 17 therefore treats old LingNengAI as a source of business judgment
knowledge, not as an execution architecture.

## Goal

Phase 17 should make the migration boundary explicit and enforceable:

1. Create a durable mapping from old LingNengAI business judgments to
   Hermes-native destinations.
2. Define a prohibited migration list for old graph and classifier components
   that must not be rebuilt inside Hermes.
3. Fill missing Hermes-native guidance where the current skill/tool contracts
   are too vague.
4. Add deterministic tests and fixtures that catch accidental old-runtime
   leakage and key routing behavior regressions.
5. Keep the Java stream API, SSE contract, session policy, and toolset boundary
   unchanged.

## Scope

Phase 17 includes:

1. Add a durable migration mapping report that covers old LingNengAI judgment
   areas:
   - route/current/suggest/confirm/fallback;
   - non-jump intents such as smalltalk, meta, and general tasks;
   - explicit employee switch requests;
   - ambiguous employee ownership;
   - current employee direct answer;
   - RAG-vs-web guidance;
   - artifact and side-effect tool intent;
   - attachment processing boundary;
   - compliance and out-of-domain boundary;
   - Java history and Hermes SessionDB boundary.
2. Strengthen existing infrastructure and employee skills only where needed,
   without changing the overall prompt architecture:
   - `employee-answer-semantics-contract`;
   - handoff guidance fragment in the skill loader;
   - employee base `target_employee_types` and handoff guidance;
   - tool observation, artifact, and RAG guidance if tests show gaps.
3. Add deterministic fixture cases for business decision behavior:
   - greeting or thanks should not require handoff;
   - identity/meta questions should stay with the current employee;
   - an in-scope request should be directly answerable by the current employee;
   - a clearly cross-employee request should be expected to use
     `employee_handoff` with `suggest`;
   - an ambiguous cross-employee request should be expected to use
     `employee_handoff` with `confirm`;
   - explicit switch language should be expected to use handoff suggestion;
   - artifact generation should require explicit file/image/chart/export intent;
   - internal knowledge should prefer `retrieve_rag`;
   - realtime public facts should prefer `web_search`;
   - missing business data should produce assumptions and requested fields.
4. Add leak prevention tests:
   - no production `lingneng/` module imports sibling LingNengAI `app.*`;
   - no new `RuntimeDecisionService`, `EntryDecisionService`, `RequestPlanner`,
     `tool_only_agent`, `light_llm_answer`, or `direct_attachment_answer`
     implementation appears under the Hermes LingNeng runtime;
   - the Java API still exposes only the dedicated `lingneng` toolset.
5. Add or update prompt/skill tests that prove the mapping is visible to the
   model through bounded Hermes-native prompt sections.
6. Add optional live LLM evaluation cases behind an explicit environment gate.

## Non-Goals

Phase 17 does not:

- Modify Java code or change `/internal/agent/chat/stream`.
- Change the SSE event contract.
- Add a new pre-agent router, route graph, LangGraph, request planner, or
  hidden classifier.
- Rebuild old `RuntimeDecisionService`, `EntryDecisionService`,
  `SemanticDecisionService`, `RequestPlanner`, `ToolAdmissionService`,
  `light_llm_answer`, `tool_only_agent`, `smalltalk_final_reply`, or
  `direct_attachment_answer` as runtime paths.
- Add confirmed-employee auto-switch and continue-answer behavior in Python.
- Add a model-based tool admission layer before Hermes `AIAgent`.
- Add a deterministic keyword fast path for smalltalk.
- Add a RAG-first pre-node.
- Add native training ingestion, chunking, embedding, vector indexing, or RAG
  activation inside Hermes.
- Implement full native RAG indexing; `retrieve_rag` continues to use the
  configured external provider boundary.
- Enable `read_workspace` or `write_workspace`.
- Expose terminal, arbitrary filesystem, browser automation, code execution,
  cross-channel messaging, dashboard, or Kanban tools to the Java API.
- Require exact live LLM answer text in CI.
- Add Docker, deployment, or GitHub Actions changes.

## Accepted Decisions

1. **Business judgments become guidance and contracts, not a graph.**
   Old LingNengAI judgment knowledge should be represented in skills, tool
   schemas, prompt contracts, fixtures, and mechanical guards.
2. **Hermes remains the only chat runtime.**
   `HermesAgentRunAdapter` and `AIAgent` remain responsible for the model loop,
   history, tool calling, and streaming behavior.
3. **Routing remains agent-native.**
   Cross-employee behavior is expressed through `employee_handoff`. There is no
   separate route classifier before the agent.
4. **Current employee direct answer is the default.**
   If the current employee can answer, the model should answer without calling
   a handoff tool.
5. **Non-business weak inputs do not jump.**
   Smalltalk, identity, meta, and general task inputs should stay with the
   current employee unless the user explicitly asks to switch employees.
6. **Ambiguity uses confirmation only when useful.**
   The model may call `employee_handoff action=confirm` when two to four
   employee choices are plausible. It should not ask confirmation for every
   low-confidence request.
7. **Boss fallback becomes guidance, not automatic routing.**
   Old fallback-to-boss behavior is preserved as a recommendation: when a
   business request is broad or unclear and no other employee is a clear owner,
   the current employee may suggest boss assistant. There is no automatic
   threshold-based fallback.
8. **Tool admission stays mechanical.**
   Tool schemas, explicit intent guidance, provider configuration, call limits,
   duplicate suppression, and safe error normalization are the enforcement
   points. There is no LLM admission pass before the main agent.
9. **History stays Hermes-owned.**
   Old history selection logic and Java `history` context injection are not
   migrated. Phase 17 may test that guidance does not reintroduce it.
10. **RAG is a normal tool.**
    The model is guided to use `retrieve_rag` for internal learned knowledge,
    but no mandatory RAG prefetch node is added.
11. **Attachments stay as controlled context/tool boundary.**
    Attachment direct-answer nodes are not restored. Attachment content, when
    available, is exposed through the existing untrusted prompt/tool boundary.
12. **Compliance remains narrow.**
    Phase 17 may define minimal out-of-domain and unsafe-answer guidance, but it
    does not add a broad compliance classifier.

## Open Decisions

There are no open product or architecture decisions for Phase 17 before writing
the plan.

Implementation details that the Phase 17 plan may decide without additional
product confirmation:

- whether the mapping fixture is a single JSON file or split into focused JSON
  files by judgment area;
- whether existing infrastructure skills are sufficient or one new
  infrastructure skill is needed to keep prompt contracts readable;
- whether optional live LLM evals are added as a pytest module behind an
  environment gate or as a small script under `scripts/`.

The plan must not reinterpret these as permission to add a router, graph,
pre-agent classifier, fast path, or auto-switch behavior.

## Business Judgment Mapping

| Old LingNengAI judgment | Hermes destination | Phase 17 action |
| --- | --- | --- |
| `runtime_decision.answer_mode=business_agent` | Default Hermes agent loop | Document as default; no new code path |
| `runtime_decision.answer_mode=direct_final` | Employee skill guidance | Keep as model answer behavior; no fast path |
| Deterministic greeting/thanks fast path | Employee answer semantics contract | Fixture expectations only |
| `light_llm_answer` | Hermes normal one-turn answer | Prohibit node migration |
| `tool_only_agent` | Tool schemas and model loop | Prohibit profile migration |
| Route current | `employee_handoff action=current` only when useful, or direct answer | Tighten guidance and tests |
| Route suggestion | `employee_handoff action=suggest` | Fixture and bridge tests |
| Route confirmation | `employee_handoff action=confirm` + pending store | Fixture and pending-store tests |
| Confirmed different employee | Existing terminal route suggestion | Preserve; do not auto-run new employee |
| Fallback to boss assistant | Handoff guidance, not threshold router | Preserve as recommendation |
| Non-jump intents | Employee skill and handoff guidance | Test smalltalk/meta/general no handoff |
| Explicit switch request | `employee_handoff action=suggest` | Add fixture expectation |
| History dependency decision | Hermes SessionDB and compression | Prohibit old history selector |
| Tool admission | Tool schema, provider boundary, `ToolRunGuard` | Test explicit artifact intent guidance |
| RAG required first | `retrieve_rag` guidance | No prefetch node; fixture expectation |
| Public realtime facts | `web_search` guidance | Fixture expectation |
| Attachment processing gate | Existing attachment provider and untrusted context | No direct-answer node |
| Compliance block | Narrow skill guidance and existing SSE schema | No broad classifier |
| Agent step/final/citation/artifact protocol | Existing SSE bridge | Regression coverage only |

## Routing Behavior Contract

Phase 17 defines routing behavior as model-visible policy, not pre-agent
classification:

1. The current employee answers when the request is in scope.
2. The current employee answers smalltalk, thanks, identity, and capability
   questions without handoff.
3. The model uses `employee_handoff action=suggest` when another known employee
   is clearly a better owner or the user explicitly asks to switch.
4. The model uses `employee_handoff action=confirm` when ownership is ambiguous
   across two to four known employees and asking the user is more useful than
   guessing.
5. The model does not invent employee types, display names, thresholds, scores,
   hidden policies, or private route reasons.
6. After terminal `suggest` or `confirm`, the public reply from the tool is the
   user-visible response for the turn.
7. Python does not automatically run the target employee after confirmation.

## Tool Governance Contract

Phase 17 keeps tool governance inside Hermes-native controls:

1. The Java API exposes only the dedicated `lingneng` toolset.
2. Artifact tools require explicit user intent for a file, image, chart,
   visual, PDF, Word, export, download, or equivalent deliverable.
3. Pure advice, analysis, strategy, copy, or planning requests should not claim
   that a file, image, or chart was generated unless a tool result produced it.
4. `retrieve_rag` is preferred for internal learned knowledge, training
   material, store rules, historical cases, and business knowledge that should
   cite internal sources.
5. `web_search` is preferred for public, realtime, policy, news, trend, or
   internet facts.
6. Tool provider unavailability is a normal degradation path. The answer should
   explain the limitation and continue with safe text where possible.
7. `ToolRunGuard` remains responsible for duplicate suppression and per-run
   limits. Phase 17 does not add a second admission runtime.

## Prompt And Skill Boundary

Phase 17 may update existing skills and prompt fragments, but must keep these
boundaries:

- Employee-specific behavior belongs in `skills/lingneng/employees/*/SKILL.md`.
- Cross-employee handoff policy belongs in infrastructure skill guidance and
  the loader's bounded handoff fragment.
- RAG, artifact, and tool observation behavior belongs in existing
  infrastructure contracts, not in ad hoc prompt strings spread through the
  API layer.
- Prompt additions must remain bounded and deterministic. They must not inject
  entire old LingNengAI source files or unbounded skill content.
- Untrusted user, attachment, or external service content must remain separated
  from trusted runtime instructions.

## Data And API Contracts

No external Java contract changes are allowed in Phase 17:

- Request schema remains the current Java-compatible `ChatStreamRequest`.
- Response remains `text/event-stream`.
- Existing event names remain unchanged:
  - `run_started`
  - `agent_step`
  - `route_result`
  - `route_suggestion`
  - `route_confirm_required`
  - `citation_delta`
  - `rag_context`
  - `artifact_created`
  - `answer_delta`
  - `final`
  - `compliance_block`
  - `error`
- `request_id` remains the idempotency key.
- Python-owned SessionDB remains the history source.
- Java `history` remains accepted, counted, and traced, but not injected into
  Hermes conversation context.

## Module Boundaries

Expected files that Phase 17 may create or modify:

- Create:
  - `docs/lingneng-migration/reports/2026-06-15-business-decision-mapping.md`
  - `tests/lingneng/fixtures/business_decision_mapping.json`
  - `tests/lingneng/evals/test_business_decision_mapping_fixtures.py`
  - `tests/lingneng/runtime/test_no_old_decision_runtime_leakage.py`
- Modify if needed:
  - `lingneng/skills/loader.py`
  - `lingneng/skills/models.py`
  - `skills/lingneng/infrastructure/employee-answer-semantics-contract/SKILL.md`
  - `skills/lingneng/infrastructure/rag-citation-contract/SKILL.md`
  - `skills/lingneng/infrastructure/artifact-output-contract/SKILL.md`
  - `skills/lingneng/infrastructure/tool-observation-contract/SKILL.md`
  - `skills/lingneng/employees/*/SKILL.md`
  - `tests/lingneng/runtime/test_employee_answer_prompt.py`
  - `tests/lingneng/skills/test_employee_answer_profiles.py`
  - `tests/lingneng/evals/test_employee_answer_semantics_fixtures.py`

Files Phase 17 must not modify for new orchestration behavior:

- `run_agent.py`
- `model_tools.py`
- `toolsets.py`, except if a deterministic test exposes a current toolset
  whitelist regression
- `gateway/platforms/api_server.py`

Phase 17 must not create:

- `lingneng/runtime/runtime_decision.py`
- `lingneng/runtime/entry_decision.py`
- `lingneng/runtime/request_plan.py`
- `lingneng/runtime/tool_only_agent.py`
- `lingneng/runtime/light_llm_answer.py`
- `lingneng/runtime/direct_attachment_answer.py`
- any module whose purpose is a pre-agent semantic router or admission LLM call

## Test Strategy

Phase 17 tests should be deterministic by default.

Required tests:

1. **Mapping fixture tests**
   - validate fixture schema;
   - cover each old judgment category in the mapping table;
   - assert every case has a Hermes destination and migration decision.
2. **Prompt/skill contract tests**
   - current employee direct-answer policy is present;
   - non-jump smalltalk/meta/general policy is present;
   - handoff suggest/confirm guidance is present;
   - no hidden route thresholds or score values are exposed to the model.
3. **Old runtime leakage tests**
   - production `lingneng/` modules do not import sibling LingNengAI `app.*`;
   - prohibited class/function names are not introduced under `lingneng/`;
   - no new pre-agent decision service appears in Phase 17 files.
4. **Tool governance tests**
   - artifact guidance requires explicit deliverable intent;
   - RAG-vs-web guidance is visible in bounded prompt or skill contracts;
   - `ToolRunGuard` remains the run-level enforcement point.
5. **Routing behavior fixture tests**
   - smalltalk/meta/general examples expect no handoff;
   - clear cross-employee examples expect `employee_handoff` suggest;
   - ambiguous examples expect `employee_handoff` confirm;
   - explicit employee switch examples expect `employee_handoff` suggest.

Optional tests:

- Live LLM acceptance cases behind an environment gate such as
  `LINGNENG_LIVE_LLM_EVAL=1`.
- Live tests must check structural behavior and tool expectations, not exact
  answer text.

## Acceptance Criteria

Phase 17 is accepted when:

1. A durable business decision mapping report exists and covers all old
   LingNengAI judgment categories listed in this spec.
2. Existing skill and prompt contracts clearly encode routing, non-jump,
   explicit switch, ambiguous ownership, RAG-vs-web, artifact intent, and
   insufficient-data behavior.
3. Deterministic tests prove no old runtime decision, entry decision, request
   planner, light answer node, tool-only agent, or direct attachment answer path
   has been introduced.
4. Deterministic fixtures cover current/direct answer, smalltalk/meta,
   cross-employee suggest, ambiguous confirm, explicit switch, artifact intent,
   RAG, web search, and missing-data behavior.
5. The Java API and SSE contract remain unchanged.
6. The dedicated LingNeng toolset remains the only Java API tool surface.
7. Focused Phase 17 tests pass.
8. The full LingNeng test suite passes or any unrelated failure is documented
   with evidence.

## User Confirmations Before Phase 17 Plan

No additional confirmation is required before writing the Phase 17 plan if
these assumptions remain accepted:

- Phase 17 should not add a new router, graph, or pre-agent decision service.
- Old LingNengAI route/tool/RAG/history/attachment judgment logic should be
  migrated only as skills, prompt contracts, tool guidance, run guards,
  fixtures, and tests.
- Confirmed employee handoff should remain terminal for the current Python
  request; Hermes should not auto-run the target employee after confirmation.
- Full old capability policy and tool admission should not be rebuilt. Tool
  governance remains schema/guidance/provider/guard based.
- Smalltalk and direct answers should remain normal model behavior, not a
  deterministic keyword fast path.
