# Phase 2 Hermes Agent Integration And Persistent Conversation Spec

## Goal

Phase 2 replaces the Phase 1 fake Agent stream with a real Hermes `AIAgent`
adapter while preserving the Java-compatible HTTP/SSE contract created in
Phase 1.

The phase proves that LingNeng-Hermes can run a no-tool Hermes conversation,
stream or synthesize Java-compatible `answer_delta` events, persist conversation
state through Hermes `SessionDB`, and replay terminal idempotency results for
repeated `request_id` values without appending the same Java query twice.

## Scope

Phase 2 is limited to creating or modifying the following runtime modules and
tests:

- Modify `lingneng/config/settings.py`
- Modify `lingneng/api/app.py`
- Modify `lingneng/api/routes.py`
- Modify `lingneng/events/bridge.py`
- Modify `lingneng/session/run_store.py`
- Create `lingneng/session/hermes_session.py`
- Modify `lingneng/runtime/__init__.py`
- Modify `lingneng/runtime/agent_adapter.py`
- Create `lingneng/runtime/hermes_adapter.py`
- Create `tests/lingneng/runtime/test_hermes_adapter_config.py`
- Create `tests/lingneng/runtime/test_hermes_answer_stream.py`
- Create `tests/lingneng/session/test_hermes_session_adapter.py`
- Create `tests/lingneng/api/test_chat_stream_idempotency.py`
- Create `tests/lingneng/contract/test_chat_stream_minimal.py`
- Update existing focused Phase 1 tests only when the Phase 2 behavior
  intentionally changes a Phase 1 fake-mode expectation.

Expected implementation stays inside the `lingneng/` package except for using
Hermes public runtime classes and methods. Phase 2 must not require changes to
`run_agent.py`, `agent/conversation_loop.py`, `model_tools.py`, `toolsets.py`,
or `hermes_state.py`.

## Non-Goals

- Do not modify Java code.
- Do not change the Java request field names, response media type, SSE event
  names, heartbeat frame, auth header, health endpoint, or ready endpoint.
- Do not add Dockerfiles, Compose files, deployment scripts, deployment
  runbooks, or GitHub Actions workflows.
- Do not implement LingNeng business tools, RAG, skill loader, artifacts,
  attachment understanding, web search, document generation, image generation,
  chart generation, or tool progress mapping.
- Do not register the `lingneng` business toolset in this phase. Dedicated
  toolset registration and high-risk tool exclusion tests are Phase 3.
- Do not expose Hermes terminal, arbitrary filesystem, browser automation, code
  execution, cross-channel messaging, dashboard, gateway, or desktop surfaces
  through the Java API.
- Do not use Java `history` as Hermes conversation context.
- Do not require real LLM credentials, external model calls, network access, or
  LingNeng business services for Phase 2 automated tests.
- Do not solve hard cancellation of a running Hermes worker thread after an SSE
  client disconnects. Phase 2 must still mark the reserved run as failed on
  stream cancellation, matching Phase 1 behavior, but forcibly aborting the
  underlying provider call is out of scope.

## Required Inputs

Reload these durable files before writing the Phase 2 plan or implementation:

1. `LINGNENG_MIGRATION_CONTEXT.md`
2. `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
3. `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
4. `docs/lingneng-migration/specs/2026-06-06-lingneng-java-contract-baseline.md`
5. `docs/lingneng-migration/specs/2026-06-06-lingneng-github-workflow-baseline.md`
6. `docs/lingneng-migration/specs/2026-06-06-phase-1-java-compatible-api-mvp-spec.md`
7. `docs/lingneng-migration/plans/2026-06-06-phase-1-java-compatible-api-mvp-plan.md`

Use these Hermes files as implementation references:

- `run_agent.py`
- `agent/conversation_loop.py`
- `agent/agent_init.py`
- `hermes_state.py`
- `model_tools.py`
- `toolsets.py`

Use `/Users/rotas/Documents/work/hailun/LingNengAI` only as a read-only
contract reference. Do not implement there.

## Accepted Decisions

- The API entrypoint remains `POST /internal/agent/chat/stream`.
- The successful response media type remains `text/event-stream`.
- The default `LINGNENG_AGENT_MODE` remains `fake` so Phase 1 local smoke usage
  stays deterministic.
- Phase 2 adds `LINGNENG_AGENT_MODE=hermes` as the real Hermes runtime mode.
- `create_app(settings=None, adapter=None, run_store=None)` continues to allow
  dependency injection for tests.
- When no adapter is injected and `settings.agent_mode == "fake"`,
  `create_app()` constructs `FakeAgentRunAdapter`.
- When no adapter is injected and `settings.agent_mode == "hermes"`,
  `create_app()` constructs `HermesAgentRunAdapter`.
- Hermes conversations use `ResolvedSessionKey.session_key` as the Hermes
  `session_id`.
- LingNeng-Hermes must pass a dedicated `SessionDB` instance whose SQLite file
  lives under `LINGNENG_RUNTIME_DIR` by default, not the user's default Hermes
  profile DB.
- Phase 2 no-tool Hermes runs must construct `AIAgent` with
  `enabled_toolsets=[]`. This is the explicit no-tool mode and avoids
  accidentally exposing Hermes defaults before Phase 3 registers the dedicated
  LingNeng toolset.
- Phase 2 also defensively passes `disabled_toolsets=["kanban"]`. Hermes can
  inject kanban worker tools when `HERMES_KANBAN_TASK` is present, even with
  `enabled_toolsets=[]`, and the disabled-toolset subtraction is the guard that
  strips those env-injected tools from LingNeng no-tool runs.
- The Hermes adapter must also clear inherited `HERMES_KANBAN_*` worker
  environment variables while constructing `AIAgent` and while executing
  `run_conversation()`. Because `os.environ` is process-global, the env
  isolation lock must cover the entire LingNeng Hermes construction/run
  context, even when no kanban env key is currently present. The isolated keys
  include `HERMES_KANBAN_TASK`, `HERMES_KANBAN_BOARD`, `HERMES_KANBAN_DB`,
  `HERMES_KANBAN_WORKSPACE`, and `HERMES_KANBAN_WORKSPACES_ROOT`; original
  values must be restored after the LingNeng run finishes.
- The Hermes adapter must install a LingNeng-only instance activity tracker on
  the constructed agent so `_touch_activity(desc)` updates
  `_last_activity_ts` and `_last_activity_desc` without calling the kanban
  heartbeat bridge.
- The adapter must pass `platform="lingneng"`, `session_id` equal to the
  resolved session key, `session_db` set to the LingNeng SessionDB, and
  `quiet_mode=True`.
- The adapter must pass `skip_context_files=True` and `skip_memory=True` for
  Phase 2 no-tool contract stability. Business memory and skill context are
  later phases.
- Java `history` is counted in `ResolvedSessionKey` diagnostics only. It must
  never be converted into `conversation_history`, never be appended to
  `SessionDB`, and never be sent to `AIAgent`.
- Completed successful requests are replayed from the run store without invoking
  the adapter again.
- Completed failed requests are replayed from the run store as a terminal
  `error` event without invoking the adapter again.
- Replayed successful requests emit a minimal deterministic sequence:
  `run_started`, one `answer_delta` containing the stored final answer, and
  `final`. The `answer_delta` is required even when the stored final answer is
  an empty string. Fine-grained original delta replay remains out of scope
  unless it is already stored by the run store.
- Replayed failed requests emit a single terminal `error` event using the
  stored public error code and message.
- Running duplicates still emit `REQUEST_ALREADY_RUNNING` and do not invoke the
  adapter.
- Automated tests use fake Hermes classes, injected factories, or monkeypatches.
  They must not call a real model provider.
- `lingneng.session` must export `LingNengHermesSessionStore` lazily through
  `__getattr__`. Fake-mode imports such as `import lingneng.runtime` must not
  load `hermes_state` or `run_agent`, while direct imports from
  `lingneng.session.hermes_session` and lazy package imports from
  `lingneng.session` must both continue to work.

## User Confirmations Before Phase 2 Plan

No additional user confirmation is required before writing the Phase 2 plan.

These assumptions are locked for the plan unless the user changes them:

- Phase 2 is a no-tool Hermes conversation phase.
- The `lingneng` business toolset is not registered until Phase 3.
- SessionDB data defaults under `LINGNENG_RUNTIME_DIR`.
- Real provider credentials are not required for tests.
- Runtime mode remains explicitly selected by `LINGNENG_AGENT_MODE`.
- Docker/server deployment remains deferred.

If any of these assumptions must change, update this spec before writing or
executing the Phase 2 plan.

## Data Contracts

### Settings

`LingNengSettings` must continue to expose all Phase 1 fields and add or derive:

- `agent_mode`: accepted values are `fake` and `hermes`.
- `session_db_path`: defaults to `runtime_dir / "sessions.sqlite3"` and can be
  overridden by `LINGNENG_SESSION_DB_PATH`.

`ready_summary()` must remain non-secret. If it includes `session_db_path`, the
value must be a path string and must not include model API keys or internal API
keys.

Unknown `agent_mode` values must fail settings validation before `create_app()`
selects an adapter.

### Hermes Adapter Input

`HermesAgentRunAdapter.stream(request, resolved_session, run_id)` receives the
same parsed `ChatStreamRequest`, `ResolvedSessionKey`, and reserved `run_id`
contract as `FakeAgentRunAdapter`.

The adapter must build:

- `user_message` from `request.query.content`.
- `system_message` from `request.system_prompt.content`.
- `persist_user_message` from `request.query.content`.
- `conversation_history` from Hermes `SessionDB` rows for
  `resolved_session.session_key`.

The adapter must not use:

- Java `history` as `conversation_history`.
- Java `attachments` as model-visible context in this phase.
- Java `skill.inline` as a skill prompt in this phase.
- Hermes default toolsets.

### Hermes Adapter Output

The adapter must emit a LingNeng event stream:

1. `RunStartedEvent(run_id, request_id)`
2. Zero or more `AnswerDeltaEvent(text, sequence)` events as Hermes emits text
   through `stream_delta_callback`.
3. `FinalEvent(run_id, status="succeeded", answer=final_answer, citations=[],
   artifacts=[])` when Hermes returns a successful final response.
4. `ErrorEvent(run_id, request_id, code, message, trace_id, recoverable)` when
   Hermes raises or returns an unrecoverable error.

If Hermes returns successfully but no text deltas were delivered, the adapter
must synthesize one `answer_delta` containing the final answer before emitting
`final`, even when the final answer is an empty string. This keeps Java's
minimum event sequence stable.

If Hermes streams deltas and returns a final answer, the joined deltas should
equal the final answer in contract tests that use the fake Hermes runner. The
adapter must not duplicate deltas already delivered by the callback.

### Thread And Queue Contract

Hermes `run_conversation()` is synchronous while the API stream is async. The
Phase 2 adapter must bridge this without blocking the event loop:

- Run Hermes in a worker thread or equivalent executor.
- Use a thread-safe queue handoff from `stream_delta_callback` into the async
  generator.
- Preserve delta ordering.
- Assign monotonically increasing sequence values starting at `1`.
- Surface only public errors to Java.
- Do not leak raw provider exceptions, API keys, request payloads, or Java
  history content in SSE events.

### SessionDB Contract

Phase 2 uses Hermes `SessionDB` as the persistent conversation store.

The LingNeng session adapter must:

- Construct `SessionDB(db_path=settings.session_db_path)`.
- Load existing messages for `resolved_session.session_key` before the current
  turn.
- Convert stored rows into `conversation_history` entries compatible with
  `AIAgent.run_conversation()`.
- Preserve user, assistant, tool, tool_call_id, tool_calls, and tool_name fields
  when they exist and are needed by Hermes.
- Keep Java `history` out of SessionDB.
- Ensure two Java requests with the same tenant/user/employee/conversation key
  reuse the same Hermes session.
- Ensure a different employee id or employee type creates a different Hermes
  session even when `conversation_id` is the same.

`AIAgent` remains responsible for appending the current user message and final
assistant/tool messages to SessionDB through its existing persistence path.
LingNeng wrappers must avoid adding a second message store or manually
duplicating messages already persisted by Hermes.

### Run Store Replay Contract

The Phase 1 run store remains the idempotency boundary for
`(session_key, request_id)`.

Phase 2 must extend the replay behavior:

- `running`: return terminal `error` code `REQUEST_ALREADY_RUNNING`.
- `succeeded`: replay stored answer/artifacts without invoking the adapter.
- `failed`: replay stored public error without invoking the adapter.

Successful replay frame order:

1. `run_started`
2. `answer_delta`
3. `final`

Failed replay frame order:

1. `error`

The repeated request must not:

- create a new run id.
- invoke `AIAgent`.
- append the same Java query to SessionDB.
- emit internal exception details.

## Module Boundaries

### `lingneng/config`

Owns environment-driven mode and path settings. It must not import FastAPI or
Hermes `AIAgent`.

### `lingneng/session/hermes_session.py`

Owns SessionDB construction and conversion between stored Hermes rows and
`conversation_history`.

This module may import `hermes_state.SessionDB` but must not import FastAPI or
runtime adapter implementations.

### `lingneng/session/__init__.py`

Owns package-level session exports. `LingNengHermesSessionStore` must be a lazy
package export so importing fake-mode runtime modules does not load
`hermes_state`.

### `lingneng/runtime/hermes_adapter.py`

Owns Hermes `AIAgent` construction, sync-to-async stream bridging, public error
mapping, and no-tool conversation execution.

This module may import `run_agent.AIAgent`, `lingneng/session/hermes_session`,
and LingNeng event helpers. It must not import FastAPI route handlers.

### `lingneng/api`

Owns app construction, route-level adapter selection, idempotency reservation,
replay behavior, and SSE encoding. It must treat adapters through the
`AgentRunAdapter` protocol.

### `run_agent.py`, `agent/*`, `hermes_state.py`, `toolsets.py`, `model_tools.py`

These are Hermes core surfaces and must remain unchanged in Phase 2 unless a
failing test proves the existing public hooks cannot support the adapter. Any
such change must be small, generic, and not LingNeng-hardcoded.

## HTTP Behavior

### `GET /internal/agent/health`

Unchanged from Phase 1:

```json
{"status":"ok"}
```

### `GET /internal/agent/ready`

Unchanged auth semantics from Phase 1. The ready payload remains non-secret and
must still include at least:

- `status`
- `app_env`
- `agent_mode`
- `runtime_dir`
- `auth_required`

If the implementation adds `session_db_path`, it must be a path string and must
not include secret values.

### `POST /internal/agent/chat/stream`

Auth, config readiness, body validation, session key resolution, and pre-stream
HTTP error behavior remain unchanged from Phase 1.

When `agent_mode=fake`, behavior remains Phase 1 fake streaming.

When `agent_mode=hermes`, the route uses `HermesAgentRunAdapter` and must emit
at least:

1. `run_started`
2. one or more `answer_delta`
3. exactly one `final`

If Hermes fails after stream start, the route must emit one terminal `error`
event and mark the run failed. Raw exception details must not reach SSE output.

If the client disconnects after the run is reserved but before terminal output,
the run must not remain `running`. The existing Phase 1 cancellation behavior
must continue to mark the run as failed.

## Test Strategy

Phase 2 must remain test-first. Every implementation task must write the
failing test, confirm the expected failure, implement the minimum code, rerun
focused tests, then run task review checks before commit and push.

Required focused test commands:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime/test_hermes_adapter_config.py -q
uv run --extra dev python -m pytest tests/lingneng/runtime/test_hermes_answer_stream.py -q
uv run --extra dev python -m pytest tests/lingneng/session/test_hermes_session_adapter.py -q
uv run --extra dev python -m pytest tests/lingneng/api/test_chat_stream_idempotency.py -q
uv run --extra dev python -m pytest tests/lingneng/contract/test_chat_stream_minimal.py -q
```

Required phase-level verification:

```bash
uv run --extra dev python -m pytest tests/lingneng/config tests/lingneng/schemas tests/lingneng/session tests/lingneng/api tests/lingneng/runtime tests/lingneng/contract -q
```

Reference contract command:

```bash
/Users/rotas/Documents/work/hailun/LingNengAI/.venv/bin/python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py -q
```

Code hygiene commands:

```bash
uv run --extra dev python -m ruff check lingneng tests/lingneng
git diff --check
rg -n "T[B]D|T[O]DO|t[o]do|fill[[:space:]]in|implement[[:space:]]later|place[h]older|待[补]充|待[定]|占[位]" lingneng tests/lingneng docs/lingneng-migration/specs/2026-06-06-phase-2-hermes-agent-integration-spec.md
```

Expected:

- All focused and phase-level tests pass.
- The LingNengAI reference contract still passes where the reference virtual
  environment is available.
- `ruff check` passes.
- `git diff --check` exits 0.
- The incomplete-marker scan exits 1 with no matches.

No local server is required for Phase 2 verification. Tests must use
dependency injection and `fastapi.testclient.TestClient`.

## Acceptance Criteria

Phase 2 is complete when:

- Phase 1 Java request parsing, SSE encoding, auth, ready, health, session key,
  and fake mode behavior remain compatible.
- `LINGNENG_AGENT_MODE=hermes` is accepted and selects `HermesAgentRunAdapter`
  when no adapter is injected.
- Unknown agent modes are rejected by settings validation before chat starts.
- LingNeng SessionDB storage is isolated under `LINGNENG_RUNTIME_DIR` by default
  or through an explicit `LINGNENG_SESSION_DB_PATH` override.
- `HermesAgentRunAdapter` constructs `AIAgent` with `platform="lingneng"`.
- `HermesAgentRunAdapter` uses `resolved_session.session_key` as the Hermes
  `session_id`.
- `HermesAgentRunAdapter` passes a LingNeng-owned `SessionDB` into `AIAgent`.
- `HermesAgentRunAdapter` uses explicit no-tool configuration and does not
  expose Hermes default tools or env-injected kanban worker tools.
- `HermesAgentRunAdapter` clears inherited `HERMES_KANBAN_*` worker environment
  variables during `AIAgent` construction and `run_conversation()` under a lock
  that covers the whole context, then restores the original environment values.
- `HermesAgentRunAdapter` installs a LingNeng-only `_touch_activity` tracker so
  kanban heartbeat side effects do not run during LingNeng Java API requests.
- `import lingneng.runtime` in fake mode does not load `hermes_state` or
  `run_agent`, and `from lingneng.session import LingNengHermesSessionStore`
  still resolves lazily when the real SessionDB adapter is needed.
- Automated tests prove Java `history` is not passed as `conversation_history`
  and is not appended to SessionDB.
- Automated tests prove two turns with the same resolved LingNeng session reuse
  the same Hermes session key.
- Automated tests prove different employee identities produce different Hermes
  sessions for the same business `conversation_id`.
- Hermes stream deltas are converted to ordered `answer_delta` events.
- If Hermes does not stream deltas but returns successfully, the adapter
  synthesizes one `answer_delta`, including for an empty final answer.
- Joined deltas equal `final.answer` in the no-tool contract test.
- Successful Hermes output marks the run as `succeeded` and stores final answer
  and artifacts in the run store.
- Hermes exceptions after stream start mark the run as `failed`, emit one
  terminal public `error`, and do not leak raw exceptions.
- Repeated completed successful `request_id` values replay stored SSE output
  without invoking the adapter, including one `answer_delta` for empty stored
  answers.
- Repeated completed failed `request_id` values replay stored public error
  output without invoking the adapter.
- Repeated running `request_id` values still return `REQUEST_ALREADY_RUNNING`
  without invoking the adapter.
- Replayed requests do not append duplicate user messages to SessionDB.
- Phase-level pytest, reference contract, ruff, diff, and incomplete-marker checks
  pass.
- No Docker, Compose, deployment script, GitHub Actions workflow, RAG, skill
  loader, artifact, attachment, business toolset, or tool progress mapping work
  is included in this phase.

## Phase 3 Handoff

Phase 3 starts only after Phase 2 is verified, reviewed, committed, and pushed.
The Phase 3 spec must register a dedicated LingNeng toolset and prove the Java
API exposes only approved LingNeng tool schemas while keeping Hermes high-risk
default tools unavailable to the LingNeng Java entrypoint.
