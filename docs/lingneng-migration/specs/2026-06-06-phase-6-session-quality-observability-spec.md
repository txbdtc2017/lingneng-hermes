# Phase 6 Session Quality, Cleanup, And Observability Spec

## Status

Drafted after Phase 5 completion on `dev`.

Required durable context reloaded before writing this spec:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-06-phase-5-artifacts-attachments-generation-spec.md`
- `docs/lingneng-migration/plans/2026-06-06-phase-5-artifacts-attachments-generation-plan.md`

Repository state before drafting:

- Branch: `dev`
- Phase 5 final HEAD: `65a7132c6714bf56ee5494479f910d1dc3d9c910`
- Phase 5 final verification:
  - `uv run --extra dev python -m pytest tests/lingneng -q` -> `334 passed`
  - `uv run --extra dev python -m ruff check lingneng tests/lingneng model_tools.py tools/registry.py` -> passed
  - LingNengAI reference contract tests -> `16 passed`

Reference implementation and Hermes runtime surfaces inspected for this phase:

- `lingneng/session/hermes_session.py`
- `lingneng/runtime/hermes_adapter.py`
- `lingneng/api/routes.py`
- `lingneng/session/run_store.py`
- `lingneng/schemas/chat_events.py`
- `hermes_state.py`
- `run_agent.py`
- `agent/conversation_compression.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py`

## Goal

Make long-lived Java conversations reliable when LingNeng-Hermes owns the
conversation history:

1. Continue a business conversation correctly after Hermes context compression
   rotates the underlying SessionDB session.
2. Provide a safe maintenance entrypoint for stale LingNeng SessionDB rows and
   request idempotency records.
3. Add structured run logging and a public `final.trace_summary` that can
   diagnose a run without leaking Java history, prompts, secrets, attachment
   text, or raw tool output.

## Scope

### Compression-Aware Session Loading

Java still sends the same `conversation_id`, `session_id`, `request_id`, and
other request fields. Phase 6 must not require Java to know about Hermes
compression session rotation.

The existing business session key remains the stable LingNeng root key:

```text
tenant_id:user_id:employee_id:conversation_id
```

When Hermes compression creates a child continuation session, LingNeng runtime
must treat that child as the active Hermes transcript for future turns. The
business root key remains the key for:

- session resolution from Java request fields.
- request idempotency in `LingNengRunStore`.
- trace/log correlation.
- cleanup grouping.

The active Hermes session id is resolved from the root key by following Hermes
SessionDB compression lineage:

1. Prefer `SessionDB.get_compression_tip(root_session_key)` when available.
2. Fall back to `SessionDB.resolve_resume_session_id(root_session_key)` when
   the root is empty and a continuation child contains messages.
3. Fall back to the root key when no continuation exists or lookup fails.

The adapter must build `AIAgent` with the active Hermes session id so new turns
append to the current compression tip. It must not append messages to the stale
root session after compression has rotated the transcript.

`LingNengHermesSessionStore.load_conversation_history()` must load from the
active Hermes session id, not blindly from the root key. Java `history` must
remain diagnostic input only and must never be merged into Hermes context.

### Compression Test Strategy

Phase 6 tests should not require a live compression LLM provider. They may use
SessionDB compression lineage setup or a deterministic fake compression-capable
agent to prove the LingNeng adapter:

- ignores Java `history` as an Agent context source.
- reads compressed continuation history from the active Hermes session id.
- passes the active session id into `AIAgent`.
- keeps the business root key stable for idempotency and trace correlation.

The acceptance test should prove that a compressed summary or continuation
message written to the compression tip is visible to the next LingNeng turn.

### Session And Run Cleanup

Phase 6 adds a LingNeng cleanup module that can be called by a future cron,
CLI command, server startup hook, or deployment maintenance script. Phase 6 does
not add those invokers; it only provides the deterministic library boundary.

Cleanup must use `LingNengSettings` retention values:

```text
session_retention_days: 90
archived_session_retention_days: 180
idempotency_retention_days: 7
```

Cleanup behavior:

- Delete or prune non-archived LingNeng SessionDB sessions older than
  `session_retention_days` when they are no longer active.
- Delete or prune archived LingNeng SessionDB sessions older than
  `archived_session_retention_days`.
- Delete `LingNengRunStore` idempotency records older than
  `idempotency_retention_days`.
- Preserve recent active sessions and recent completed run records.
- Preserve compression continuation chains that are still within retention.
- Return structured counts for each category.
- Log counts, cutoff dates, and database path labels.

Cleanup logs must not include:

- message content.
- Java `history` content.
- system prompts.
- attachment extracted text.
- tool raw output.
- provider exception text.
- API keys, bearer tokens, passwords, signed URLs, or local absolute paths.

The cleanup implementation should reuse existing Hermes SessionDB pruning
helpers when they are safe, but the LingNeng wrapper must keep LingNeng
retention semantics explicit and testable.

### Structured Logging

Phase 6 adds `lingneng/observability/` helpers for structured run logs.

The route layer should emit structured records for at least:

- request accepted.
- duplicate or replayed request.
- adapter stream started.
- adapter stream completed.
- adapter stream failed.
- client stream cancelled.

Tool-level structured logging may be added when the adapter already has public
tool progress data, but raw tool payloads must not be logged.

Every run log record should include stable, non-secret fields when available:

```text
event_name
request_id
run_id
tenant_id
user_id
conversation_id
session_key
employee_id
employee_type
status
duration_ms
agent_mode
tool_name
error_code
recoverable
history_count
attachment_count
citation_count
artifact_count
answer_chars
active_hermes_session_id
compression_root_session_id
compression_active_session_id
deploy_env
deploy_image_ref
deploy_git_sha
deploy_build_id
```

Deployment metadata is optional in Phase 6. It may be read from environment
variables if present, but Phase 6 must not add Docker, compose, server deploy
scripts, or GitHub Actions.

Structured logs should be emitted through the standard Python logging system
using a stable namespace such as `lingneng.observability`. Tests may inspect
the structured payload through `caplog`.

### Final Trace Summary

Phase 6 adds a public `trace_summary` field to `FinalEvent`.

`trace_summary` is a small sanitized dictionary, not a full trace dump. It is
intended for Java-side debugging and production support correlation.

Allowed example keys:

```text
request_id
session_key
active_hermes_session_id
status
duration_ms
agent_mode
history_count
attachment_count
agent_step_count
citation_count
artifact_count
answer_chars
compression_used
compression_root_session_id
compression_active_session_id
deploy_env
deploy_image_ref
deploy_git_sha
deploy_build_id
```

`trace_summary` must not contain:

- `query.content`
- Java `history` message content
- `system_prompt.content`
- skill prompt body
- attachment text or `download_url`
- raw tool arguments
- raw tool results
- provider exception text or traceback
- API keys, bearer tokens, passwords, signed URLs, local filesystem paths

`trace_summary` should default to `{}` for compatibility when no trace context
is provided. Existing SSE event naming remains unchanged; the event name still
comes from the SSE `event:` line.

### Error And Cancellation Logging

Errors emitted after streaming starts still use SSE `error` events. Phase 6
does not change the Java error event contract.

Route instrumentation must record a sanitized failure log when:

- request validation fails before streaming.
- a duplicate request is already running.
- adapter raises or ends without a terminal event.
- client disconnect causes `CLIENT_STREAM_CANCELLED`.

Failure logs must carry the public `error_code` and `recoverable` flag, not raw
exception text.

## Non-Goals

Phase 6 does not:

- Implement Docker, compose, deployment scripts, rollback, or GitHub Actions.
- Modify Java code or require Java request changes.
- Add a Java-side cleanup endpoint.
- Add a new public session delete or clear API.
- Change the stable LingNeng SSE event names.
- Use Java `history` as Agent context.
- Persist raw attachment contents into session history.
- Replace Hermes compression internals or implement a new summarization engine.
- Require a live compression LLM provider in tests.
- Require live Redis, Milvus, MinIO, Nacos, MQ, object storage, web search, or
  AIGC services in tests.
- Delete Hermes CLI/TUI/Gateway/plugin functionality.

## Accepted Decisions

1. The LingNeng business session key remains the root key even when Hermes
   compression rotates the active transcript to a child session.
2. The active Hermes session id is an internal implementation detail used for
   SessionDB history loading and `AIAgent` construction.
3. Request idempotency remains keyed by the business root session key and
   `request_id`, not by the compression tip id.
4. Java `history` remains excluded from Agent context. Phase 6 may log only
   `history_count`.
5. Cleanup is a library boundary in Phase 6. Invocation by cron, CLI, startup,
   or deployment scripts is deferred.
6. Structured logs and `trace_summary` use sanitized counters, IDs, statuses,
   durations, and deployment metadata only.
7. `FinalEvent.trace_summary` defaults to `{}` so existing tests and clients
   that ignore the field continue to work.
8. Deployment metadata is optional and passive. Phase 6 may read it when present
   but must not create deployment assets.

## Open Decisions

No user decision is required before writing the Phase 6 implementation plan.

The following choices are implementation details for the plan:

- Exact method names for resolving the active Hermes session id.
- Whether cleanup directly issues SQL or wraps existing SessionDB prune helpers.
- Exact logging helper class/function names.
- Whether trace context is carried as a dataclass, Pydantic model, or plain
  sanitized dictionary.

## Module Boundaries

Expected new modules:

- `lingneng/session/cleanup.py`: cleanup result models and maintenance
  functions for SessionDB and run-store retention.
- `lingneng/observability/__init__.py`: observability package marker.
- `lingneng/observability/logging.py`: structured trace context builders,
  sanitizers, deploy metadata reader, and logging helpers.

Expected modified modules:

- `lingneng/session/hermes_session.py`: active Hermes session resolution and
  compression-aware history loading.
- `lingneng/runtime/hermes_adapter.py`: build `AIAgent` against the active
  Hermes session id; produce trace summary fields for final events.
- `lingneng/api/routes.py`: structured logs around request reservation,
  replay/duplicate handling, streaming terminal events, errors, and
  cancellation.
- `lingneng/session/run_store.py`: cleanup support for idempotency records if
  existing `cleanup_older_than()` is not sufficient for Phase 6 tests.
- `lingneng/schemas/chat_events.py`: add `FinalEvent.trace_summary`.
- `lingneng/config/settings.py`: expose any new non-secret observability or
  deployment metadata settings only if the plan chooses settings over direct
  environment reads.

Expected new tests:

- `tests/lingneng/session/test_long_conversation_compression.py`
- `tests/lingneng/session/test_cleanup.py`
- `tests/lingneng/observability/test_trace_logging.py`

## Test Strategy

Phase 6 must add focused tests for:

- Resolving active Hermes session id from a root session after compression.
- Loading conversation history from the compression tip, not from Java
  `history`.
- Building `AIAgent` with the active Hermes session id after compression.
- Keeping `LingNengRunStore` idempotency on the root business session key.
- Cleanup retention for non-archived sessions, archived sessions, and run-store
  idempotency records.
- Cleanup logs containing counts and cutoffs but no message content.
- Structured route logs containing required IDs, status, counts, and duration.
- Structured route logs excluding Java `history`, system prompt, attachment
  text, secrets, signed URLs, local paths, raw tool args, and raw tool output.
- `FinalEvent.trace_summary` defaults to `{}` and carries sanitized summary data
  on live and replayed successful runs.
- Phase 5 artifact/RAG/attachment behavior remains intact.

Expected Phase 6 verification:

```bash
uv run --extra dev python -m pytest tests/lingneng/session/test_long_conversation_compression.py tests/lingneng/session/test_cleanup.py tests/lingneng/observability/test_trace_logging.py -q
uv run --extra dev python -m pytest tests/lingneng -q
uv run --extra dev python -m ruff check lingneng tests/lingneng model_tools.py tools/registry.py
/Users/rotas/Documents/work/hailun/LingNengAI/.venv/bin/python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_tool_artifact_events.py -q
git diff --check HEAD~5..HEAD
```

## Acceptance Criteria

Phase 6 is complete when:

1. A LingNeng conversation whose Hermes transcript was compressed continues
   from the active compression tip on the next Java request.
2. Java `history` is still excluded from Hermes Agent context even in long
   conversation tests.
3. The business root session key remains the idempotency key for repeated
   `request_id` replay.
4. Cleanup can remove stale non-archived sessions, stale archived sessions, and
   stale run-store records using settings-driven retention values.
5. Cleanup logs counts and cutoff metadata without logging message content.
6. Structured route logs include the required non-secret run identifiers,
   status, counts, durations, and optional deployment metadata.
7. `FinalEvent.trace_summary` exists, defaults to `{}`, and carries only safe
   summary fields when trace context is available.
8. Error and cancellation paths log sanitized public failure information without
   leaking raw exceptions.
9. Full LingNeng regression tests, ruff, relevant old LingNengAI contract tests,
   and diff whitespace checks pass.

## User Confirmations Needed Before Phase Plan

None. Phase 6 follows the master roadmap, keeps deployment work deferred to
Phase 7, and does not change Java-facing request requirements.

## Spec Self-Review

- Scope coverage: long-session compression recovery, cleanup retention, logs,
  and final trace summary are all covered.
- Non-goal check: Docker, compose, deploy scripts, GitHub Actions, Java changes,
  and new public session APIs remain excluded.
- Contract consistency: Java keeps the same `/internal/agent/chat/stream`
  request path and SSE event names. `FinalEvent.trace_summary` is additive and
  defaults to `{}`.
- Security check: logs and trace summary explicitly exclude history content,
  prompt content, attachment text, raw tool data, secrets, signed URLs, and
  local filesystem paths.
- Execution readiness: no user confirmation is needed before writing the Phase
  6 implementation plan.
