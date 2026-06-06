# Phase 8 Java Integration, Regression Comparison, And Pruning Decision Plan

> **Execution rule:** Phase 8 follows the approved migration sequence:
> `phase spec -> phase plan -> subagent-driven execution`.

## Status

Drafted on `dev` after Phase 8 spec commit `30efc346f`.

This plan implements:

- `docs/lingneng-migration/specs/2026-06-06-phase-8-java-integration-regression-pruning-spec.md`

Required durable context loaded before writing this plan:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-06-phase-8-java-integration-regression-pruning-spec.md`

Current baseline:

- Branch: `dev`
- Phase 6 final runtime HEAD: `995e2ce3e`
- Phase 8 spec HEAD: `30efc346f`
- Phase 7 deployment is explicitly deferred by user boundary.
- Worktree before drafting: clean.

## Goal

Complete the non-deployment validation/documentation phase after runtime
改造:

1. Add a Java-compatible SSE smoke client.
2. Add output comparison template and fixture validation.
3. Document Hermes feature pruning gates and candidates without deleting or
   disabling features.

## Scope

Phase 8 includes:

- A client-side script that posts a Java-compatible request to an already
  running LingNeng-Hermes-compatible endpoint and exits only after `final`.
- In-process fake-server tests for that script; no fixed local service port and
  no live external dependency.
- A structured output-comparison fixture and Markdown report template.
- Tests that validate comparison coverage and secret hygiene.
- A pruning decision document with evidence gates.
- Tests that validate the pruning document does not authorize immediate
  removal.

## Non-Goals

Phase 8 must not:

- Implement Docker, compose, deployment scripts, rollback, or GitHub Actions.
- Modify Java code.
- Start a long-running service.
- Bind fixed host ports in tests.
- Change Java request fields or SSE event names.
- Remove or globally disable Hermes features.
- Use live RAG, MinIO, Milvus, Redis, MQ, Nacos, web search, AIGC, or LLM
  services.
- Commit real business transcripts, credentials, signed URLs, local paths,
  prompt bodies, Java history content, raw tool arguments, or raw tool output.

## Decisions

- The smoke script uses the Python standard library (`urllib.request`) to avoid
  adding dependencies.
- Tests for the smoke script use `http.server.ThreadingHTTPServer` bound to
  `127.0.0.1` with port `0`, so the OS chooses a free ephemeral port.
- Because tests do not start a project service on a fixed port, no project port
  reservation is needed for Task 8.1.
- The output comparison fixture is stored as JSON under
  `docs/lingneng-migration/reports/` so tests can validate it directly.
- The Markdown template references the JSON fixture and records how reviewers
  should fill comparison results later.
- The pruning decision document is documentation-only; actual removal requires a
  later approved spec/plan and evidence from Java smoke, contracts, deployment,
  comparison, and soak.

## User Confirmations

No user confirmation is required before Phase 8 execution. The approved spec
keeps Phase 7 deployment deferred and preserves the no-Java-change constraint.

## Execution Sequence

Each task follows this loop:

1. Reload durable context and the Phase 8 spec/plan before starting.
2. Dispatch one implementation subagent for the task.
3. The subagent writes failing tests first.
4. The subagent implements only the task's scoped files.
5. The subagent runs the task verification command.
6. The main agent inspects the worktree and verification output.
7. Dispatch a task spec-compliance reviewer.
8. Dispatch a task code-quality reviewer.
9. Verify review feedback technically before applying it.
10. Fix valid findings and re-run task verification.
11. Commit with the task's Chinese conventional-prefix message.
12. Push `dev` only after verification passes.
13. Move to the next task only after review findings are approved or resolved.

After all tasks:

1. Run full Phase 8 verification.
2. Dispatch final Phase 8 spec-compliance review.
3. Dispatch final Phase 8 code-quality review.
4. Fix valid findings and re-run verification.
5. Mark Phase 8 complete only when all acceptance criteria are met.

## File Map

Expected new files:

- `scripts/lingneng-chat-smoke.py`
- `tests/lingneng/contract/test_chat_smoke_script.py`
- `docs/lingneng-migration/reports/2026-06-06-output-comparison-template.md`
- `docs/lingneng-migration/reports/2026-06-06-output-comparison-fixture.json`
- `tests/lingneng/evals/test_comparison_fixture.py`
- `docs/lingneng-migration/specs/2026-06-06-hermes-feature-pruning-decision.md`
- `tests/lingneng/evals/test_pruning_decision_doc.py`

Expected modified files:

- None, unless tests expose a narrow compatibility bug.

Files that should remain untouched:

- Java reference project under `/Users/rotas/Documents/work/hailun/LingNengAI`
- Docker, compose, deploy scripts, and `.github/workflows/`
- Hermes core runtime files.

## Task 8.1: Java-Compatible Integration Smoke Script

### Goal

Add a reusable client-side script that validates a Java-style call to
`POST /internal/agent/chat/stream` and exits successfully only after a `final`
SSE event.

### Files

- Create: `scripts/lingneng-chat-smoke.py`
- Create: `tests/lingneng/contract/test_chat_smoke_script.py`

### Test-First Work

Write failing tests that:

- Start a fake HTTP SSE server on `127.0.0.1:0` in a background thread.
- Run the script with `sys.executable scripts/lingneng-chat-smoke.py ...`.
- Assert the fake server receives:
  - path `/internal/agent/chat/stream`.
  - method `POST`.
  - `Content-Type: application/json`.
  - optional `X-Internal-Key`.
  - JSON fields compatible with Java contract: `request_id`, `tenant_id`,
    `user_id`, `session_id`, `conversation_id`, `query.content`,
    `employee.employee_id`, `employee.employee_type`, `history`,
    `attachments`, `stream_options`.
- Assert the script ignores `: ping` heartbeat frames.
- Assert success when frames include `run_started`, `answer_delta`, and
  terminal `final`.
- Assert non-zero exit when:
  - server returns HTTP 500.
  - SSE emits `error`.
  - stream ends before `final`.
  - an SSE data frame is malformed JSON.
- Assert stdout/stderr contain event names and safe counts, but not:
  - internal key.
  - full query text.
  - raw request JSON.
  - signed URL.
  - local path.

### Implementation Steps

1. Implement CLI args:
   - `--url`
   - `--internal-key`
   - `--request-id`
   - `--tenant-id`
   - `--user-id`
   - `--session-id`
   - `--conversation-id`
   - `--employee-id`
   - `--employee-type`
   - `--query`
   - `--timeout-seconds`
2. Allow `LINGNENG_INTERNAL_API_KEY` as fallback for `--internal-key`.
3. Build a minimal Java-compatible payload:
   - include empty `history` and `attachments`.
   - set `stream_options.include_citations=true` and
     `stream_options.include_rag_context=true`.
4. Use `urllib.request.Request` and `urlopen` with timeout.
5. Parse SSE incrementally from the response body:
   - split frames by blank line.
   - ignore comment frames.
   - require `event:` for business frames.
   - parse `data:` JSON.
6. Track event names and terminal state.
7. Exit code:
   - `0` after `final`.
   - `1` for HTTP, SSE `error`, malformed data, timeout, no final, or other
     runtime failure.
8. Print only safe summary lines:
   - endpoint host/path without credentials.
   - event order.
   - final answer length.
   - citation/artifact counts.
   - trace summary keys.
9. Do not print the full query, internal key, request body, signed URLs, or
   local paths.

### Verification

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/contract/test_chat_smoke_script.py -q
uv run --extra dev python -m ruff check scripts/lingneng-chat-smoke.py tests/lingneng/contract/test_chat_smoke_script.py
```

Expected:

- Smoke-script tests pass.
- Ruff passes.

### Review

Dispatch after implementation:

- Task 8.1 spec reviewer: verify Java payload shape, SSE parsing, safe output,
  and no fixed service/deployment scope.
- Task 8.1 quality reviewer: verify subprocess/server test reliability,
  timeout behavior, exit codes, and no secret logging.

### Commit

After review findings are resolved and verification passes:

```bash
git add scripts/lingneng-chat-smoke.py tests/lingneng/contract/test_chat_smoke_script.py
git commit -m "test: 增加灵能 Java 调用冒烟脚本"
git push origin dev
```

## Task 8.2: Output Comparison Template And Fixture

### Goal

Create a structured comparison scaffold for validating LingNengAI versus
LingNeng-Hermes outputs after business stakeholders provide real comparison
data.

### Files

- Create: `docs/lingneng-migration/reports/2026-06-06-output-comparison-template.md`
- Create: `docs/lingneng-migration/reports/2026-06-06-output-comparison-fixture.json`
- Create: `tests/lingneng/evals/test_comparison_fixture.py`

### Test-First Work

Write failing tests that:

- Load the JSON fixture.
- Assert it has exactly or at least the required top-level sections:
  - `schema_version`
  - `cases`
  - `status_values`
  - `scenario_types`
  - `required_evidence`
- Assert employee coverage includes:
  - `boss_assistant`
  - `operation_specialist`
  - `marketing_planner`
  - `marketing_content_creator`
  - `member_operator`
  - `product_combo_advisor`
- Assert scenario coverage includes:
  - `no_tool`
  - `rag`
  - `artifact`
  - `attachment`
  - `long_conversation`
- Assert each case has required fields:
  - `case_id`
  - `employee_type`
  - `scenario_type`
  - `request`
  - `expected_event_order`
  - `expected_tool_policy`
  - `lingnengai_output`
  - `lingneng_hermes_output`
  - `citations`
  - `artifacts`
  - `trace_summary`
  - `evaluator_notes`
  - `status`
- Assert each request has Java-compatible identifiers and `query.content`
  placeholder text that is not a real customer transcript.
- Assert `expected_event_order` starts with `run_started` and ends with a
  terminal `final` or `error`.
- Assert fixture/template do not contain secret-like values:
  - `api_key=`
  - `Bearer `
  - `password=`
  - `X-Amz-Signature`
  - `/Users/`
  - `AKIA`
- Assert the Markdown template references the fixture path and includes sections
  for evaluator notes, tool calls, citations, artifacts, trace summary, and
  final decision.

### Implementation Steps

1. Create `docs/lingneng-migration/reports/` if missing.
2. Create the JSON fixture with schema-valid placeholder cases.
3. Use placeholder output fields such as:
   - `"status": "pending"`
   - empty `answer_text`
   - empty citations/artifacts unless the case is designed to exercise those
     placeholders.
4. For RAG/artifact/attachment cases, include expected policy placeholders
   without real service output.
5. Create the Markdown template with:
   - objective.
   - instructions.
   - case table.
   - per-case review checklist.
   - comparison scoring notes.
   - final decision section.
   - links to Phase 8 fixture and prior contract tests.
6. Keep all content non-secret and synthetic.

### Verification

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/evals/test_comparison_fixture.py -q
uv run --extra dev python -m ruff check tests/lingneng/evals/test_comparison_fixture.py
```

Expected:

- Fixture tests pass.
- Ruff passes.

### Review

Dispatch after implementation:

- Task 8.2 spec reviewer: verify required employee/scenario coverage and
  comparison fields.
- Task 8.2 quality reviewer: verify fixture schema stability, secret hygiene,
  and that placeholders are not pretending to be real evaluation results.

### Commit

After review findings are resolved and verification passes:

```bash
git add docs/lingneng-migration/reports/2026-06-06-output-comparison-template.md docs/lingneng-migration/reports/2026-06-06-output-comparison-fixture.json tests/lingneng/evals/test_comparison_fixture.py
git commit -m "docs: 增加灵能输出对比模板"
git push origin dev
```

## Task 8.3: Feature Pruning Decision Document

### Goal

Document which Hermes features are kept, disabled for the LingNeng Java API,
or eligible for future removal, without performing any removal in Phase 8.

### Files

- Create: `docs/lingneng-migration/specs/2026-06-06-hermes-feature-pruning-decision.md`
- Create: `tests/lingneng/evals/test_pruning_decision_doc.py`

### Test-First Work

Write failing tests that read the decision document and assert it includes:

- A status that clearly says `decision gate only` or equivalent wording.
- A kept-for-LingNeng section.
- A disabled-by-default-for-LingNeng-API section.
- A future-removal-candidates section.
- Required evidence gates:
  - Java smoke script pass.
  - LingNeng contract tests pass.
  - Docker/server deployment validation from Phase 7.
  - output comparison report.
  - production or test soak.
- A statement that no removal is authorized in Phase 8.
- References to the Phase 8 smoke script and comparison fixture/template.
- No Docker/compose/GitHub Actions files are created or referenced as already
  complete.
- No secret-like values.

### Implementation Steps

1. Create the decision document.
2. List features kept for LingNeng, such as:
   - `AIAgent` runtime.
   - SessionDB and compression.
   - LingNeng API facade.
   - LingNeng toolset and skills loader.
   - SSE bridge.
   - observability/trace summary.
   - RAG/artifact/attachment business tools.
3. List features disabled by default for LingNeng API, such as:
   - terminal/code execution.
   - arbitrary filesystem access.
   - browser automation.
   - cross-channel messaging.
   - unrelated platform adapters.
   - non-LingNeng toolsets.
4. List future removal candidates after evidence, such as:
   - unused platform/channel adapters for the server runtime image.
   - unused UI surfaces in production deploy packaging.
   - optional plugins not needed by LingNeng server.
5. State that broad removal requires a later approved spec and plan.
6. State that Phase 7 deployment evidence is still pending because deployment
   is deferred.

### Verification

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/evals/test_pruning_decision_doc.py -q
uv run --extra dev python -m pytest tests/lingneng -q
uv run --extra dev python -m ruff check tests/lingneng/evals/test_pruning_decision_doc.py
```

Expected:

- Decision doc tests pass.
- Full LingNeng tests pass.
- Ruff passes.

### Review

Dispatch after implementation:

- Task 8.3 spec reviewer: verify pruning decision is documentation-only and
  evidence-gated.
- Task 8.3 quality reviewer: verify the doc does not overpromise, contradict
  Phase 7 deferral, or authorize immediate deletion.

### Commit

After review findings are resolved and verification passes:

```bash
git add docs/lingneng-migration/specs/2026-06-06-hermes-feature-pruning-decision.md tests/lingneng/evals/test_pruning_decision_doc.py
git commit -m "docs: 明确 Hermes 功能裁剪决策"
git push origin dev
```

## Phase 8 Final Verification

Run after all tasks:

```bash
uv run --extra dev python -m pytest tests/lingneng/contract/test_chat_smoke_script.py tests/lingneng/evals/test_comparison_fixture.py tests/lingneng/evals/test_pruning_decision_doc.py -q
uv run --extra dev python -m pytest tests/lingneng -q
uv run --extra dev python -m ruff check scripts/lingneng-chat-smoke.py tests/lingneng/contract/test_chat_smoke_script.py tests/lingneng/evals/test_comparison_fixture.py tests/lingneng/evals/test_pruning_decision_doc.py
git diff --check 30efc346f^..HEAD
```

Expected:

- Focused Phase 8 tests pass.
- Full LingNeng tests pass.
- Ruff passes.
- Whitespace check has no output.

## Final Review

Dispatch after full verification:

- Final Phase 8 spec reviewer:
  - Compare current work against Phase 8 spec acceptance criteria.
  - Check Phase 7 deployment remains deferred.
  - Check no Java or deploy assets were changed.
  - Check script/template/docs have no secrets or real transcripts.
- Final Phase 8 quality reviewer:
  - Review smoke script robustness.
  - Review fixture and doc tests.
  - Review generated files and diff scope.
  - Check no unnecessary Hermes core churn.

Fix valid findings, then rerun the full Phase 8 verification command set.

## Acceptance Checklist

- [ ] Smoke script posts Java-compatible payloads.
- [ ] Smoke script parses SSE, ignores heartbeats, exits only after `final`, and
      fails on terminal/error/malformed streams.
- [ ] Smoke script output does not leak internal key, request JSON, query text,
      signed URLs, local paths, or raw tool output.
- [ ] Comparison fixture covers required employees and scenario types.
- [ ] Comparison template and fixture use placeholders, not real business
      results.
- [ ] Pruning decision lists kept, disabled-by-default, and future-removal
      candidates.
- [ ] Pruning decision blocks removal until Java smoke, contracts, deployment,
      comparison, and soak evidence exist.
- [ ] No deployment assets, GitHub Actions, Java changes, or Hermes feature
      removals are added.
- [ ] Full LingNeng tests, ruff, and whitespace checks pass.
- [ ] Final Phase 8 reviewers approve.

## Rollback Notes

- Revert Task 8.1 if the smoke script has unsafe output, incorrect SSE parsing,
  or flaky fake-server tests.
- Revert Task 8.2 if the comparison fixture schema is too rigid or stores
  unsafe placeholder data.
- Revert Task 8.3 if the pruning decision over-authorizes removal or conflicts
  with Phase 7 deferral.

All Phase 8 work is scripts/docs/tests only, so rollback should not affect the
runtime API.

## Plan Self-Review

- The plan implements only the approved Phase 8 spec.
- Phase 7 deployment remains deferred.
- No Java code, deployment assets, GitHub Actions, or Hermes feature removals
  are in scope.
- Every task has tests, verification commands, reviewer loops, and commit
  points.
- The smoke script uses standard library dependencies and test-only ephemeral
  local ports.
- Comparison and pruning artifacts are evidence scaffolds, not production
  claims.
