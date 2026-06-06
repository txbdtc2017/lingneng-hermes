# Phase 6 Session Quality, Cleanup, And Observability Plan

> **Execution rule:** Phase 6 follows the approved migration sequence:
> `phase spec -> phase plan -> subagent-driven execution`.

## Status

Drafted on `dev` after Phase 6 spec commit `65c8a72f4`.

This plan implements:

- `docs/lingneng-migration/specs/2026-06-06-phase-6-session-quality-observability-spec.md`

Required durable context loaded before writing this plan:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-06-phase-6-session-quality-observability-spec.md`

Current known Phase 5/6 baseline:

- Branch: `dev`
- Phase 5 final runtime HEAD: `65a7132c6714bf56ee5494479f910d1dc3d9c910`
- Phase 6 spec HEAD: `65c8a72f4`
- Phase 5 final verification passed:
  - `uv run --extra dev python -m pytest tests/lingneng -q`
  - `uv run --extra dev python -m ruff check lingneng tests/lingneng model_tools.py tools/registry.py`
  - `/Users/rotas/Documents/work/hailun/LingNengAI/.venv/bin/python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_tool_artifact_events.py -q`

## Goal

Make long-lived LingNeng Java conversations reliable under Hermes-managed
conversation history by adding:

1. Compression-aware active Hermes session resolution.
2. Deterministic cleanup for stale LingNeng SessionDB sessions and run-store
   idempotency rows.
3. Structured, sanitized route logging.
4. Additive `FinalEvent.trace_summary` support for live and replayed successful
   SSE responses.

## Scope

Phase 6 covers only runtime quality and observability work:

- Resolve a LingNeng business root session key to the active Hermes compression
  tip before loading history and constructing `AIAgent`.
- Keep Java request `history` excluded from Agent context.
- Keep `LingNengRunStore` idempotency keyed by the business root session key
  and `request_id`.
- Add a library-only cleanup module; no cron, CLI, deployment script, or server
  startup invoker is added in this phase.
- Add sanitized structured logs around the Java-compatible chat stream route.
- Add sanitized `trace_summary` data to final events without changing SSE event
  names.

## Non-Goals

Phase 6 must not:

- Implement Docker, compose, deployment scripts, rollback, or GitHub Actions.
- Modify Java code or require Java request changes.
- Add a public Java-facing session clear/delete endpoint.
- Change LingNeng SSE event names.
- Merge Java `history` into Hermes context.
- Persist raw attachment contents, tool args, tool outputs, or provider errors
  into public trace output.
- Replace Hermes compression internals.
- Require live Redis, Milvus, MinIO, Nacos, MQ, object storage, web search,
  AIGC, or live LLM services in tests.
- Remove Hermes CLI/TUI/Gateway/plugin behavior.

## Decisions

- The LingNeng business session key remains the compression root and the
  idempotency key.
- The active Hermes session id is internal and may differ from the business
  session key after compression.
- Active session resolution order:
  1. `SessionDB.get_compression_tip(root_session_key)`
  2. `SessionDB.resolve_resume_session_id(root_session_key)`
  3. `root_session_key`
- Cleanup deletes only ended LingNeng sessions. Live old sessions are preserved.
- Cleanup should use `SessionDB.delete_sessions()` for selected ids so messages
  are removed with sessions and child sessions are handled by the existing
  SessionDB contract.
- Observability uses standard Python logging under `lingneng.observability`.
- `trace_summary` is a small sanitized dictionary, not a trace dump.
- Deployment metadata is passive and optional, read only when present in the
  environment.

## User Confirmations

No further user confirmation is required before Phase 6 execution. The Phase 6
spec has no open user decisions, keeps deployment deferred, and preserves Java
compatibility.

## Execution Sequence

Each task follows this loop:

1. Reload durable context and the Phase 6 spec/plan before starting.
2. Dispatch one implementation subagent for the task.
3. The implementation subagent writes failing tests first.
4. The implementation subagent implements only that task's scoped changes.
5. The implementation subagent runs the task verification command.
6. The main agent inspects the worktree and verification output.
7. Dispatch a spec-compliance reviewer subagent for the task.
8. Dispatch a code-quality reviewer subagent for the task.
9. Verify review feedback technically before applying it.
10. Fix valid findings and re-run task verification.
11. Commit with the task's Chinese conventional-prefix message.
12. Push `dev` only after verification passes.
13. Move to the next task only after task review is approved or findings are
    explicitly resolved.

After all tasks:

1. Run full Phase 6 verification.
2. Dispatch final Phase 6 spec-compliance review.
3. Dispatch final Phase 6 code-quality review.
4. Fix valid findings, re-run full verification, commit and push fixes.
5. Mark Phase 6 complete only when all acceptance criteria are met.

## File Map

Expected new files:

- `docs/lingneng-migration/plans/2026-06-06-phase-6-session-quality-observability-plan.md`
- `lingneng/session/cleanup.py`
- `lingneng/observability/__init__.py`
- `lingneng/observability/logging.py`
- `tests/lingneng/session/test_long_conversation_compression.py`
- `tests/lingneng/session/test_cleanup.py`
- `tests/lingneng/observability/test_trace_logging.py`

Expected modified files:

- `lingneng/session/hermes_session.py`
- `lingneng/runtime/hermes_adapter.py`
- `lingneng/api/routes.py`
- `lingneng/schemas/chat_events.py`
- `lingneng/session/run_store.py` if existing `cleanup_older_than()` needs a
  safer or more testable boundary.
- Existing LingNeng tests may be adjusted only when the Phase 6 public contract
  is additive and the old expectation is now incomplete.

Files that should remain untouched in Phase 6 unless a test proves a narrow
compatibility need:

- Java reference project under `/Users/rotas/Documents/work/hailun/LingNengAI`
- Docker, compose, deploy scripts, and `.github/workflows/`
- Hermes CLI/TUI/Gateway/plugin removals
- `run_agent.py`, `model_tools.py`, and `toolsets.py`

## Task 6.1: Compression-Aware LingNeng Session Loading

### Goal

Ensure a Java business conversation continues from the active Hermes
compression tip after Hermes rotates the underlying SessionDB session.

### Files

- Create: `tests/lingneng/session/test_long_conversation_compression.py`
- Modify: `lingneng/session/hermes_session.py`
- Modify: `lingneng/runtime/hermes_adapter.py`

### Test-First Work

Write focused failing tests for these scenarios:

- `LingNengHermesSessionStore.resolve_active_session_id(resolved)` returns the
  child compression tip when `SessionDB` contains:
  - root session id equals `resolved.session_key`
  - root has `end_reason="compression"`
  - child session has `parent_session_id=root`
  - child contains continuation messages
- `load_conversation_history(resolved)` reads messages from the active child
  session, not from the root key.
- Java `request.history` content is not passed to `AIAgent.run_conversation()`
  as `conversation_history`.
- `HermesAgentRunAdapter` constructs `AIAgent` with `session_id` equal to the
  active Hermes session id after compression.
- `LingNengRunStore.reserve_run()` still receives the root business session key
  from the route layer, so repeated `request_id` remains stable across
  compression.

Recommended deterministic test setup:

- Use an in-memory or temp-file `SessionDB`.
- Create a root LingNeng session with `source="lingneng"`.
- Append root messages that should not appear after compression.
- End the root with `end_reason="compression"`.
- Create a child session with `parent_session_id=root`.
- Append a synthetic compressed summary or continuation assistant message to
  the child.
- Use a fake `agent_cls` that records constructor kwargs and
  `run_conversation()` kwargs instead of calling a live LLM.

The assertion must prove:

- The fake agent sees the compressed summary or child continuation in
  `conversation_history`.
- The fake agent does not see a sentinel string from Java `history`.
- The fake agent constructor receives the active child session id.
- The original root key is still used by idempotency tests.

### Implementation Steps

1. Add `resolve_active_session_id()` to `LingNengHermesSessionStore`.
   - Accept `ResolvedSessionKey` or root session key string.
   - Resolve the root key from input.
   - Try `self.db.get_compression_tip(root_key)`.
   - If it returns a non-empty id, return it.
   - Else try `self.db.resolve_resume_session_id(root_key)`.
   - If that returns a non-empty id, return it.
   - Else return `root_key`.
   - Do not log message contents or DB rows on errors.
2. Add `load_conversation_history_for_session_id(session_id)` or a private
   helper so the public `load_conversation_history(resolved)` can delegate to
   the resolved active id.
3. Keep `ensure_session(resolved)` anchored on the root key. It should not
   create a new child when no compression lineage exists.
4. Modify `HermesAgentRunAdapter.stream()` so the worker thread resolves the
   active Hermes session id before loading history and building the agent.
5. Modify `_build_agent()` to accept `active_session_id` and pass that value as
   `session_id` to `AIAgent`.
6. Keep `run_id`, `request_id`, RAG context, skill prompt, attachment prompt,
   and idempotency behavior unchanged.
7. Do not pass Java `request.history` into `conversation_history`.

### Verification

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/session/test_long_conversation_compression.py -q
uv run --extra dev python -m pytest tests/lingneng/session/test_session_key_resolver.py tests/lingneng/runtime/test_hermes_adapter_config.py -q
uv run --extra dev python -m ruff check lingneng/session/hermes_session.py lingneng/runtime/hermes_adapter.py tests/lingneng/session/test_long_conversation_compression.py
```

Expected:

- New compression tests pass.
- Existing session-key and adapter tests still pass.
- Ruff passes.

### Review

Dispatch after implementation:

- Task 6.1 spec reviewer: verify root key, active tip, Java history exclusion,
  and idempotency boundaries match the Phase 6 spec.
- Task 6.1 quality reviewer: verify no broad Hermes core edits, no live LLM
  dependency, and no brittle timestamp assumptions.

### Commit

After review findings are resolved and verification passes:

```bash
git add lingneng/session/hermes_session.py lingneng/runtime/hermes_adapter.py tests/lingneng/session/test_long_conversation_compression.py
git commit -m "feat: 支持灵能长会话压缩"
git push origin dev
```

## Task 6.2: LingNeng Session And Run Cleanup

### Goal

Add a deterministic library boundary for stale LingNeng session and idempotency
cleanup without adding cron, CLI, startup hooks, deploy scripts, or public APIs.

### Files

- Create: `lingneng/session/cleanup.py`
- Create: `tests/lingneng/session/test_cleanup.py`
- Modify: `lingneng/session/run_store.py` only if existing cleanup support is
  insufficient.

### Test-First Work

Write failing tests for:

- Non-archived ended LingNeng sessions older than
  `settings.session_retention_days` are deleted.
- Recent non-archived ended LingNeng sessions are preserved.
- Old active LingNeng sessions with `ended_at IS NULL` are preserved.
- Archived LingNeng sessions older than
  `settings.archived_session_retention_days` are deleted.
- Recent archived LingNeng sessions are preserved.
- Non-LingNeng sessions are preserved.
- `LingNengRunStore` rows older than `settings.idempotency_retention_days` are
  deleted.
- Recent run-store rows are preserved.
- Cleanup returns structured counts.
- Cleanup logs counts and cutoff metadata but does not log message content.

Recommended test setup:

- Use temp SQLite files for both `SessionDB` and `LingNengRunStore`.
- Seed `SessionDB` through public methods where possible:
  - `create_session(..., source="lingneng")`
  - `append_message(...)`
  - `end_session(...)`
  - `set_session_archived(...)`
- Adjust `started_at`/`ended_at` with a minimal test helper that executes SQL
  on the test DB only.
- Seed old/recent run-store rows with `reserve_run()`, `mark_succeeded()`, and
  `force_update_created_at()`.
- Use `caplog` against `lingneng.observability` or the cleanup logger namespace.
- Put sentinel strings such as `SECRET_MESSAGE_SHOULD_NOT_LOG` in session
  messages and assert they never appear in logs.

### Implementation Steps

1. Create `lingneng/session/cleanup.py`.
2. Add a small result model, preferably a frozen dataclass:
   - `active_sessions_pruned`
   - `archived_sessions_pruned`
   - `run_records_pruned`
   - `session_retention_days`
   - `archived_session_retention_days`
   - `idempotency_retention_days`
   - cutoff timestamps as ISO strings or `datetime` values
3. Add `run_lingneng_cleanup(settings, session_db=None, run_store=None, logger=None)`.
4. Select stale non-archived sessions with explicit LingNeng semantics:
   - `source='lingneng'`
   - `archived=0`
   - `ended_at IS NOT NULL`
   - timestamp older than non-archived cutoff
5. Select stale archived sessions with:
   - `source='lingneng'`
   - `archived=1`
   - `ended_at IS NOT NULL`
   - timestamp older than archived cutoff
6. Use `SessionDB.delete_sessions(session_ids)` to delete selected ids.
7. Use `LingNengRunStore.cleanup_older_than(settings.idempotency_retention_days)`
   for run-store cleanup if it already satisfies tests.
8. Log only structured counts and cutoff values:
   - no message body
   - no history
   - no prompt
   - no raw tool output
   - no local absolute DB path if a path label is enough
9. Preserve compression chains within retention by selecting only individual
   ended sessions older than the appropriate cutoff. Do not attempt recursive
   deletion of child sessions.

### Verification

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/session/test_cleanup.py -q
uv run --extra dev python -m pytest tests/lingneng/session/test_run_store.py tests/lingneng/session/test_long_conversation_compression.py -q
uv run --extra dev python -m ruff check lingneng/session/cleanup.py lingneng/session/run_store.py tests/lingneng/session/test_cleanup.py
```

Expected:

- Cleanup tests pass.
- Existing run-store and compression tests pass.
- Ruff passes.

### Review

Dispatch after implementation:

- Task 6.2 spec reviewer: verify cleanup retention, no invoker, no Java API, and
  no secret/content logs.
- Task 6.2 quality reviewer: verify SQL selection is narrow, deletion uses
  SessionDB helpers, active sessions are preserved, and tests are deterministic.

### Commit

After review findings are resolved and verification passes:

```bash
git add lingneng/session/cleanup.py tests/lingneng/session/test_cleanup.py lingneng/session/run_store.py
git commit -m "feat: 增加灵能会话清理"
git push origin dev
```

If `lingneng/session/run_store.py` was not modified, omit it from `git add`.

## Task 6.3: Structured Logging And Final Trace Summary

### Goal

Add sanitized structured run logs and a safe `final.trace_summary` for both
live successful runs and idempotency replay.

### Files

- Create: `lingneng/observability/__init__.py`
- Create: `lingneng/observability/logging.py`
- Modify: `lingneng/api/routes.py`
- Modify: `lingneng/schemas/chat_events.py`
- Modify: `lingneng/runtime/hermes_adapter.py` only if trace counts cannot be
  computed cleanly in the route layer.
- Create: `tests/lingneng/observability/test_trace_logging.py`

### Test-First Work

Write failing tests for:

- `FinalEvent(...).trace_summary == {}` by default.
- Live `/internal/agent/chat/stream` success emits a `final` event whose data
  contains a `trace_summary` dictionary.
- Replayed successful `request_id` emits a `final` event with a
  `trace_summary` dictionary and does not call the adapter a second time.
- Structured logs include non-secret fields:
  - `event_name`
  - `request_id`
  - `run_id`
  - `tenant_id`
  - `user_id`
  - `conversation_id`
  - `session_key`
  - `employee_id`
  - `employee_type`
  - `status`
  - `duration_ms`
  - `agent_mode`
  - `history_count`
  - `attachment_count`
  - `agent_step_count`
  - `citation_count`
  - `artifact_count`
  - `answer_chars`
  - `active_hermes_session_id`
  - `compression_root_session_id`
  - `compression_active_session_id`
- Logs and `trace_summary` exclude sentinel secret/content strings from:
  - `query.content`
  - Java `history`
  - `system_prompt.content`
  - skill prompt/body
  - attachment extracted text
  - attachment `download_url`
  - raw tool args/results
  - provider exception text
  - bearer/API key/password-like strings
  - signed URLs
  - local absolute paths
- Failed adapter streams log a sanitized failure status and public
  `error_code`, without raw exception text.
- Duplicate running request logs `REQUEST_ALREADY_RUNNING` as a sanitized
  duplicate/failure event.
- Optional deployment metadata from environment appears when present:
  - `LINGNENG_DEPLOY_ENV`
  - `LINGNENG_IMAGE_REF`
  - `LINGNENG_GIT_SHA`
  - `LINGNENG_BUILD_ID`

Recommended test style:

- Use `TestClient` with the existing LingNeng API app factory or route
  registration helper used by current tests.
- Use a fake adapter that yields:
  - `RunStartedEvent`
  - one or more `AgentStepEvent`
  - optional `CitationDeltaEvent`/`ArtifactCreatedEvent`
  - `AnswerDeltaEvent`
  - `FinalEvent`
- Parse SSE frames with existing test helpers if available.
- Use `caplog` for `lingneng.observability`.
- Assert against structured `LogRecord` attributes or a stable
  `trace_payload` dict rather than fragile formatted log strings.

### Implementation Steps

1. Add `trace_summary: dict[str, Any] = Field(default_factory=dict)` to
   `FinalEvent`.
2. Create `lingneng/observability/logging.py` with:
   - safe allow-list of trace keys
   - `deploy_metadata_from_env()`
   - `build_trace_context(request, resolved, run_id, ...)`
   - `build_trace_summary(trace_context)`
   - `log_lingneng_event(event_name, trace_context, logger=None)`
   - value sanitizer for strings, mappings, lists, and unknown objects
3. Use allow-listing for public fields. Prefer dropping suspicious values over
   redacting into noisy public payloads.
4. Add route instrumentation in `lingneng/api/routes.py`:
   - request accepted after validation/session resolution/reservation
   - duplicate/replay branch
   - adapter stream started
   - adapter stream completed
   - adapter stream failed
   - client stream cancelled
5. Track stream counters in `_adapter_stream()`:
   - agent step count
   - citation count
   - artifact count
   - answer char count
   - terminal status
   - duration
6. Before yielding a live `FinalEvent`, replace it with
   `event.model_copy(update={"trace_summary": summary})`.
7. Before yielding a replayed `FinalEvent`, construct a trace summary from the
   stored record and request/resolved context.
8. Mark run-store success using the final event's answer/citations/artifacts.
   The run store does not need to persist trace summary in Phase 6.
9. Keep public error messages stable:
   - `RUNTIME_ERROR`
   - `REQUEST_ALREADY_RUNNING`
   - `CLIENT_STREAM_CANCELLED`
   - existing public messages
10. Never log raw exceptions from adapter failures. Log public error code,
    status, recoverable flag, and trace id if available.

### Verification

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/observability/test_trace_logging.py -q
uv run --extra dev python -m pytest tests/lingneng/api/test_chat_stream_contract.py tests/lingneng/schemas/test_chat_event_schema.py -q
uv run --extra dev python -m ruff check lingneng/observability lingneng/api/routes.py lingneng/schemas/chat_events.py tests/lingneng/observability/test_trace_logging.py
```

Expected:

- Observability tests pass.
- Existing chat stream and event schema tests pass.
- Ruff passes.

### Review

Dispatch after implementation:

- Task 6.3 spec reviewer: verify required log fields, `trace_summary`,
  live/replay coverage, and secret/content exclusions.
- Task 6.3 quality reviewer: verify sanitizer defaults closed, logs are
  structured, route instrumentation is not tangled with business logic, and
  error handling preserves terminal SSE semantics.

### Commit

After review findings are resolved and verification passes:

```bash
git add lingneng/observability lingneng/api/routes.py lingneng/schemas/chat_events.py tests/lingneng/observability/test_trace_logging.py
git commit -m "feat: 增加灵能运行追踪日志"
git push origin dev
```

Add `lingneng/runtime/hermes_adapter.py` only if Task 6.3 required adapter
changes.

## Task 6.4: Phase 6 Contract Regression And Final Verification

### Goal

Close Phase 6 with regression coverage that ties compression, cleanup,
observability, and existing LingNeng Java contracts together.

### Files

- Modify or add focused tests only if Task 6.1-6.3 coverage leaves a contract
  gap.
- Do not add deployment files.

### Test-First Work

Before adding any new code, inspect coverage from Tasks 6.1-6.3. Add a small
contract regression only if one of these is not already covered:

- Live final SSE frame includes safe `trace_summary`.
- Replayed successful final SSE frame includes safe `trace_summary`.
- `trace_summary` is additive and old Java event schema compatibility remains.
- Compression-aware active session loading does not change root-key
  idempotency.

If coverage is already complete, Task 6.4 is verification-only and should not
create a commit.

### Verification

Run the full Phase 6 command set:

```bash
uv run --extra dev python -m pytest tests/lingneng/session/test_long_conversation_compression.py tests/lingneng/session/test_cleanup.py tests/lingneng/observability/test_trace_logging.py -q
uv run --extra dev python -m pytest tests/lingneng -q
uv run --extra dev python -m ruff check lingneng tests/lingneng model_tools.py tools/registry.py
/Users/rotas/Documents/work/hailun/LingNengAI/.venv/bin/python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_tool_artifact_events.py -q
git diff --check HEAD~5..HEAD
```

If fewer or more than five Phase 6 commits exist, adjust the `git diff --check`
range to cover all Phase 6 commits from the Phase 6 spec commit through current
HEAD.

Expected:

- Focused Phase 6 tests pass.
- Full LingNeng regression suite passes.
- Ruff passes.
- LingNengAI reference contract tests pass.
- Whitespace check has no output.

### Final Review

Dispatch after full verification:

- Final Phase 6 spec reviewer:
  - Compare current code against the Phase 6 spec acceptance criteria.
  - Check no deployment/GitHub Actions work slipped into Phase 6.
  - Check Java `history` remains excluded.
  - Check live and replay `trace_summary` are safe.
- Final Phase 6 quality reviewer:
  - Review cross-task integration.
  - Check sanitizer and cleanup boundaries.
  - Check test quality and regression risk.
  - Check no unnecessary Hermes core churn.

Fix valid final review findings, then rerun the full Phase 6 verification
command set.

### Commit

If Task 6.4 adds tests or fixes:

```bash
git add <changed-files>
git commit -m "test: 增加灵能 Phase 6 回归验证"
git push origin dev
```

If Task 6.4 is verification-only, do not create an empty commit.

## Phase 6 Acceptance Checklist

- [ ] A LingNeng conversation whose Hermes transcript was compressed continues
      from the active compression tip on the next Java request.
- [ ] Java `history` remains excluded from Hermes Agent context.
- [ ] Business root session key remains the idempotency key for repeated
      `request_id` replay.
- [ ] Cleanup removes stale non-archived sessions, stale archived sessions, and
      stale run-store records using settings-driven retention values.
- [ ] Cleanup logs counts and cutoff metadata without message content.
- [ ] Structured route logs include required non-secret identifiers, statuses,
      counts, durations, and optional deployment metadata.
- [ ] `FinalEvent.trace_summary` exists, defaults to `{}`, and carries only safe
      summary fields when trace context is available.
- [ ] Error and cancellation paths log sanitized public failure information.
- [ ] Full LingNeng regression tests, ruff, relevant LingNengAI reference
      contract tests, and whitespace checks pass.
- [ ] Final spec-compliance and code-quality reviewers approve Phase 6.

## Rollback Notes

Task-level rollback should use normal git revert of the task commit, not manual
file resets:

- Revert Task 6.1 if active session resolution breaks normal LingNeng session
  continuation.
- Revert Task 6.2 if cleanup selection is too broad or deletes active/recent
  sessions.
- Revert Task 6.3 if route instrumentation changes SSE terminal semantics or
  leaks unsafe data.

Because Phase 6 adds no deploy assets and no Java API changes, rollback does not
require server or Java coordination in this phase.

## Plan Self-Review

- The plan implements only the approved Phase 6 spec.
- Deployment, compose, rollback scripts, and GitHub Actions remain deferred to
  Phase 7.
- Every task has a test-first path, implementation boundary, verification
  command, reviewer loop, and commit point.
- The active-session design keeps root-key idempotency separate from Hermes
  compression tip selection.
- Cleanup is library-only and explicitly preserves active sessions.
- Observability is allow-list based and rejects raw history, prompts,
  attachment data, tool payloads, secrets, signed URLs, and local paths.
