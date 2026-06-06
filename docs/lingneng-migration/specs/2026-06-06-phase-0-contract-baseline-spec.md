# Phase 0 Contract Baseline Spec

## Goal

Phase 0 freezes the external contracts and repository workflow assumptions that
later runtime phases must follow. It creates durable baseline documents for the
LingNeng Java HTTP/SSE contract and the GitHub-based branch/CI assumptions.

## Scope

Phase 0 produces documentation only. It does not create `lingneng/` runtime
modules, API routes, toolsets, Docker assets, GitHub Actions workflows, or test
fixtures in this Hermes fork.

The phase has two deliverables:

1. `docs/lingneng-migration/specs/2026-06-06-lingneng-java-contract-baseline.md`
2. `docs/lingneng-migration/specs/2026-06-06-lingneng-github-workflow-baseline.md`

## Non-Goals

- Do not modify Java code.
- Do not implement the LingNeng API facade.
- Do not add runtime schemas or tests in this phase.
- Do not add Docker, compose, deployment scripts, or GitHub Actions workflows.
- Do not use Java `history` as Python Agent context.
- Do not change Hermes core files such as `run_agent.py`, `model_tools.py`,
  `toolsets.py`, or `gateway/platforms/api_server.py`.

## Required Inputs

Reload these durable files before starting the phase:

1. `LINGNENG_MIGRATION_CONTEXT.md`
2. `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
3. `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`

Use these LingNengAI reference files as read-only sources:

- `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_request.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_events.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/api/internal/chat_stream.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_stream_event_order.py`

## Accepted Decisions

- The LingNeng-Hermes runtime keeps the Java entrypoint
  `POST /internal/agent/chat/stream`.
- The response media type remains `text/event-stream`.
- The minimum Phase 1 SSE event subset is `run_started`, `answer_delta`,
  `final`, and `error`.
- The full LingNeng P1 SSE event name set remains:
  `run_started`, `agent_step`, `route_result`, `route_suggestion`,
  `route_confirm_required`, `citation_delta`, `rag_context`,
  `artifact_created`, `answer_delta`, `final`, `compliance_block`, and `error`.
- The SSE `event:` line carries the event type. The `data` JSON does not need
  an `event` field.
- Heartbeats use SSE comment frames, specifically `: ping\n\n`.
- Python owns Agent session history. Java `history` is accepted for diagnostics
  but must not be merged into Hermes Agent context.
- `request_id` is the idempotency key within a resolved LingNeng session.
- This repository is hosted on GitHub. Future CI/CD planning targets GitHub
  Actions.
- Docker/server deployment is deferred until after the runtime改造 phases.

## Open Decisions

Phase 0 has no user-blocking open decisions. If `git remote -v` does not show
the final GitHub remote, record the observed remote in the GitHub workflow
baseline and do not guess the final URL.

## Contract Baseline Requirements

The Java contract baseline document must record:

- Required request fields and notable optional fields.
- `conversation_id` and `conversationId` compatibility.
- Employee identity fields that affect session key resolution.
- `history` handling policy.
- Attachment field names that future phases must parse.
- Full formal SSE event name set.
- Minimum Phase 1 SSE event subset.
- Event order constraints known from LingNengAI tests.
- Heartbeat frame format.
- Error event minimum fields from the total design spec.
- Reference test commands and observed result.

## GitHub Workflow Baseline Requirements

The GitHub workflow baseline document must record:

- The repository is treated as GitHub-hosted.
- Runtime implementation work happens on `dev`.
- Validation and promotion flow uses `test`.
- Future CI/CD automation targets GitHub Actions.
- Docker/server deployment remains deferred.
- `git remote -v` output observed during Phase 0.

## Test Strategy

Phase 0 validation is documentation-oriented:

- Run the LingNengAI contract test command when the reference environment can
  execute it:

```bash
python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py -q
```

- Run `git remote -v` in this Hermes checkout and record the output.
- Run text checks against the produced documents:
  - no unfinished marker text
  - no trailing whitespace
  - no stale non-GitHub CI target references

If the LingNengAI test command cannot run due to missing reference environment
dependencies, record the exact failure in the contract baseline instead of
inventing a passing result.

## Acceptance Criteria

Phase 0 is complete when:

- Both baseline documents exist in `docs/lingneng-migration/specs/`.
- The contract baseline contains enough detail for Phase 1 schema and SSE tests
  without rereading the entire LingNengAI project.
- The GitHub workflow baseline records GitHub/GitHub Actions as the target
  workflow surface.
- Docker/server deployment is explicitly marked as deferred.
- Text validation passes for the new docs.
- The Phase 0 plan has been executed with `superpowers:subagent-driven-development`.
