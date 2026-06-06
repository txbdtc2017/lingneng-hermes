# Phase 8 Java Integration, Regression Comparison, And Pruning Decision Spec

## Status

Drafted after Phase 6 completion on `dev`.

Required durable context reloaded before writing this spec:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-06-phase-6-session-quality-observability-spec.md`
- `docs/lingneng-migration/plans/2026-06-06-phase-6-session-quality-observability-plan.md`

Repository state before drafting:

- Branch: `dev`
- Phase 6 final runtime HEAD: `995e2ce3e`
- Phase 6 final verification:
  - `uv run --extra dev python -m pytest tests/lingneng/session/test_long_conversation_compression.py tests/lingneng/session/test_cleanup.py tests/lingneng/observability/test_trace_logging.py -q` -> `20 passed`
  - `uv run --extra dev python -m pytest tests/lingneng -q` -> `354 passed`
  - `uv run --extra dev python -m ruff check lingneng tests/lingneng model_tools.py tools/registry.py` -> passed
  - LingNengAI reference contract tests -> `16 passed`

Phase 7 deployment work remains explicitly deferred by the user's earlier
deployment boundary. Phase 8 may proceed because the master roadmap allows
starting Phase N+1 when Phase N is explicitly deferred.

## Goal

Prove the Java-compatible LingNeng-Hermes runtime is ready for business-side
validation without changing Java code or implementing deployment assets:

1. Provide a reusable Java-call-compatible SSE smoke script.
2. Define a structured output comparison fixture and report template for
   comparing LingNengAI and LingNeng-Hermes behavior.
3. Document Hermes feature pruning decisions and the evidence required before
   any actual removal or default-disable work beyond the LingNeng API boundary.

## Scope

### Java-Compatible Smoke Script

Phase 8 adds a repository script that can call an already running
LingNeng-Hermes-compatible endpoint:

```text
POST /internal/agent/chat/stream
Accept: text/event-stream
```

The script must:

- Build a Java-compatible request payload with current LingNeng fields.
- Send `X-Internal-Key` when configured.
- Parse SSE frames using the `event:` line and JSON `data:` payload.
- Ignore heartbeat comment frames such as `: ping`.
- Stream or record event names in order.
- Exit successfully only after receiving a terminal `final` event.
- Exit non-zero on HTTP error, malformed SSE, timeout, SSE `error`, or stream
  ending before `final`.
- Avoid logging secrets, request body content, attachment signed URLs, local
  filesystem paths, or bearer/API keys.

The smoke script should be testable without starting a real service by using a
TestClient-backed local fake server in tests.

If a developer later points the script at a real local or deployed dev/test
endpoint, normal port/service preflight rules apply before starting that
endpoint. Phase 8 itself does not start a long-running service.

### Output Comparison Fixture

Phase 8 adds a comparison template and fixture schema for migration validation.
The fixture must cover these employee/business cases:

- boss assistant.
- operation specialist.
- marketing planner.
- marketing content creator.
- member operator.
- product combo advisor.

The fixture set must include at least these scenario types:

- no-tool conversation.
- RAG-backed answer.
- artifact generation.
- attachment-aware answer.
- long conversation / compression continuity.

For each case, the template and fixture schema should capture:

- request metadata.
- expected employee identity and business intent.
- LingNengAI output placeholder.
- LingNeng-Hermes output placeholder.
- SSE event order.
- tool calls or absence of tool calls.
- citations.
- artifacts.
- trace summary fields.
- evaluator notes.
- pass/fail/deferred status.

The template is a migration report scaffold. Phase 8 does not need real
production comparison results, live RAG output, or human evaluation scores.

### Feature Pruning Decision

Phase 8 documents what Hermes features are:

- kept for LingNeng.
- disabled by default for the LingNeng Java API surface.
- eligible for future removal after production soak.

The decision document must make actual removal conditional on evidence. At a
minimum, before deleting or disabling broad Hermes features outside the
LingNeng API boundary, the project must have links or references to:

- passing Java-compatible integration smoke.
- passing LingNeng contract tests.
- successful Docker/server deployment validation from the later deployment
  phase.
- output comparison report.
- production or test soak notes.

Because Phase 7 deployment is deferred, Phase 8 must not claim that pruning is
approved for execution now. It should document the decision gate and candidates
only.

## Non-Goals

Phase 8 does not:

- Implement Docker, compose, deployment scripts, rollback, or GitHub Actions.
- Start or require a long-running local service unless a later smoke run is
  explicitly requested.
- Modify Java code.
- Change the Java request contract or SSE event names.
- Remove Hermes CLI, TUI, Gateway, desktop, Cron, Kanban, plugins, or default
  upstream files.
- Disable Hermes features globally.
- Run live RAG, MinIO, Milvus, Redis, MQ, Nacos, web search, or AIGC services.
- Produce final business quality judgments for LingNengAI versus
  LingNeng-Hermes.
- Require real production credentials or secrets in tests.

## Accepted Decisions

1. Phase 7 deployment remains deferred until the user explicitly resumes it.
2. Phase 8 may proceed as a non-deployment validation/documentation phase.
3. The Java-compatible smoke script is a client-side tool, not a server or
   deployment asset.
4. Smoke-script tests must use fake/local in-process HTTP surfaces rather than
   live external services.
5. Output comparison fixtures store placeholders and schema-valid examples, not
   real confidential business transcripts.
6. Feature pruning is documentation-only in Phase 8. Actual removal requires a
   later approved spec and plan.
7. No user secret, signed URL, bearer token, API key, local path, prompt body,
   Java history content, or raw tool output may be committed in fixtures,
   templates, or smoke logs.

## Open Decisions

No user decision is required before writing the Phase 8 implementation plan.

Implementation details for the plan:

- CLI flags and defaults for `scripts/lingneng-chat-smoke.py`.
- Whether the smoke script uses `urllib.request`, `httpx`, or `requests`.
- Exact comparison fixture format.
- Exact feature taxonomy in the pruning decision document.

## Contracts

### Smoke Script Input Contract

The smoke script should accept CLI arguments for at least:

```text
--url
--internal-key
--request-id
--tenant-id
--user-id
--session-id
--conversation-id
--employee-id
--employee-type
--query
--timeout-seconds
```

It should have deterministic non-secret defaults suitable for local fake-mode
testing, except `--internal-key`, which should also be readable from an
environment variable and should not be printed.

### Smoke Script Output Contract

Human-readable stdout may include:

- endpoint host/path without credentials.
- event names in order.
- final answer length.
- citation count.
- artifact count.
- trace summary keys.

Stdout and stderr must not include:

- internal key.
- full query content when it could be sensitive.
- request body JSON.
- signed URLs.
- local paths.
- raw tool output.

### Comparison Fixture Contract

The fixture should be structured data, preferably JSON or YAML, plus a Markdown
report template. Each case should include fields equivalent to:

```text
case_id
employee_type
scenario_type
request
expected_event_order
expected_tool_policy
lingnengai_output
lingneng_hermes_output
citations
artifacts
trace_summary
evaluator_notes
status
```

Tests should validate the fixture schema and ensure no secret-like fields are
populated with real-looking credentials.

## Module Boundaries

Expected new files:

- `scripts/lingneng-chat-smoke.py`
- `tests/lingneng/contract/test_chat_smoke_script.py`
- `docs/lingneng-migration/reports/2026-06-06-output-comparison-template.md`
- `tests/lingneng/evals/test_comparison_fixture.py`
- `docs/lingneng-migration/specs/2026-06-06-hermes-feature-pruning-decision.md`

Expected modified files:

- None unless tests reveal a narrow compatibility issue in existing LingNeng
  schemas or SSE helpers.

Files that should remain untouched in Phase 8:

- Java reference project under `/Users/rotas/Documents/work/hailun/LingNengAI`
- Docker, compose, deploy scripts, and `.github/workflows/`
- Hermes core runtime files unless a smoke-script test proves a narrow
  compatibility bug.

## Test Strategy

Phase 8 tests should cover:

- Smoke script can post a Java-compatible request to a fake SSE server.
- Smoke script exits 0 only after `final`.
- Smoke script exits non-zero on SSE `error`.
- Smoke script ignores heartbeat comments.
- Smoke script does not print internal key or request body secrets.
- Comparison fixture contains required employee/scenario cases.
- Comparison fixture validates event/tool/citation/artifact/trace placeholders.
- Comparison fixture and template contain no real secrets.
- Pruning decision document references required evidence gates and does not
  authorize immediate deletion.

Expected Phase 8 verification:

```bash
uv run --extra dev python -m pytest tests/lingneng/contract/test_chat_smoke_script.py -q
uv run --extra dev python -m pytest tests/lingneng/evals/test_comparison_fixture.py -q
uv run --extra dev python -m pytest tests/lingneng -q
uv run --extra dev python -m ruff check scripts/lingneng-chat-smoke.py tests/lingneng/contract/test_chat_smoke_script.py tests/lingneng/evals/test_comparison_fixture.py
git diff --check
```

If a real local smoke run is explicitly requested later, run port/service
preflight before starting any service.

## Acceptance Criteria

Phase 8 is complete when:

1. `scripts/lingneng-chat-smoke.py` can call a LingNeng-compatible SSE endpoint
   and exits 0 only after `final`.
2. Smoke-script tests prove Java-compatible payload shape, SSE parsing,
   heartbeat handling, terminal behavior, and safe output.
3. Output comparison template and fixture cover required employee and scenario
   cases.
4. Comparison fixture tests validate schema and secret hygiene.
5. Feature pruning decision lists kept, disabled-by-default, and future removal
   candidate features.
6. Feature pruning decision blocks actual removal until Java integration,
   deployment validation, contract tests, output comparison, and soak evidence
   exist.
7. No deployment assets, GitHub Actions, Java code, or Hermes feature removals
   are added.
8. Full LingNeng tests and relevant lint/whitespace checks pass.

## User Confirmations Needed Before Phase Plan

None. Phase 8 follows the approved master roadmap while keeping Phase 7
deployment deferred and preserving the no-Java-change constraint.

## Spec Self-Review

- Scope coverage: Java-compatible smoke, output comparison, and feature pruning
  decision are covered.
- Non-goal check: deployment, GitHub Actions, Java changes, live services, and
  actual feature removal are excluded.
- Contract consistency: the Java endpoint, request shape, SSE event framing,
  and `final` terminal behavior stay unchanged.
- Security check: secrets, signed URLs, local paths, prompts, history content,
  attachment text, and raw tool data are excluded from scripts, fixtures, logs,
  and templates.
- Execution readiness: no user confirmation is needed before writing the Phase
  8 implementation plan.
