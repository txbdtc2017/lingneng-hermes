# Phase 1 Java-Compatible API MVP Spec

## Goal

Phase 1 builds the smallest Java-compatible LingNeng-Hermes HTTP/SSE surface
inside this Hermes fork. It proves that Java can call the expected endpoint and
consume LingNeng-format SSE frames without changing Java code.

Phase 1 deliberately uses a deterministic fake Agent adapter for the route
smoke path. Real Hermes `AIAgent` execution, persistent conversation replay,
and callback-based streaming are Phase 2 work. This keeps the first runtime
slice focused on contract stability before model, session-history, and tool
loop behavior are introduced.

## Scope

Phase 1 may create the following runtime modules and tests:

- `lingneng/__init__.py`
- `lingneng/config/__init__.py`
- `lingneng/config/settings.py`
- `lingneng/schemas/__init__.py`
- `lingneng/schemas/chat_request.py`
- `lingneng/schemas/chat_events.py`
- `lingneng/api/__init__.py`
- `lingneng/api/sse.py`
- `lingneng/api/auth.py`
- `lingneng/api/app.py`
- `lingneng/api/routes.py`
- `lingneng/api/server.py`
- `lingneng/session/__init__.py`
- `lingneng/session/keys.py`
- `lingneng/session/run_store.py`
- `lingneng/runtime/__init__.py`
- `lingneng/runtime/agent_adapter.py`
- `lingneng/runtime/fake_agent.py`
- `lingneng/events/__init__.py`
- `lingneng/events/bridge.py`
- `pyproject.toml` package discovery entries for `lingneng` and `lingneng.*`
- `tests/lingneng/config/test_settings.py`
- `tests/lingneng/config/test_packaging.py`
- `tests/lingneng/schemas/test_chat_request_schema.py`
- `tests/lingneng/schemas/test_chat_event_schema.py`
- `tests/lingneng/api/test_sse_encoding.py`
- `tests/lingneng/session/test_session_key_resolver.py`
- `tests/lingneng/session/test_run_store.py`
- `tests/lingneng/runtime/test_agent_adapter_contract.py`
- `tests/lingneng/api/test_chat_stream_contract.py`

The phase should keep edits to existing Hermes core files at zero unless a
test proves no isolated `lingneng/` module can satisfy the contract. Expected
implementation does not require changes to `run_agent.py`, `model_tools.py`,
`toolsets.py`, `hermes_state.py`, or `gateway/platforms/api_server.py`.

## Non-Goals

- Do not modify Java code.
- Do not implement real Hermes `AIAgent` execution in this phase.
- Do not connect the endpoint to Hermes `SessionDB` conversation history.
- Do not implement full completed-request SSE replay; Phase 1 must still
  reserve/check `(session_key, request_id)` before invoking the fake adapter so
  a repeated request cannot start a duplicate run.
- Do not implement the LingNeng business toolset, RAG, skill loader, artifacts,
  attachment understanding, web search, document generation, image generation,
  or chart generation.
- Do not add Dockerfiles, Compose files, deployment scripts, GitHub Actions
  workflows, or server rollout logic.
- Do not expose Hermes dashboard, gateway, terminal, browser automation,
  arbitrary filesystem access, code execution, or cross-channel messaging
  through the LingNeng Java API.

## Required Inputs

Reload these durable files before writing the Phase 1 plan or implementation:

1. `LINGNENG_MIGRATION_CONTEXT.md`
2. `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
3. `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
4. `docs/lingneng-migration/specs/2026-06-06-lingneng-java-contract-baseline.md`
5. `docs/lingneng-migration/specs/2026-06-06-lingneng-github-workflow-baseline.md`

Use these LingNengAI reference files only as read-only contract sources:

- `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_request.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_events.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/api/internal/chat_stream.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_stream_event_order.py`

## Accepted Decisions

- The endpoint is `POST /internal/agent/chat/stream`.
- The successful stream media type is `text/event-stream`.
- The health endpoint is `GET /internal/agent/health`.
- The readiness endpoint is `GET /internal/agent/ready`.
- The default local API host is `127.0.0.1`.
- The default local API port is `18083`.
- The default runtime directory is `.runtime/lingneng`.
- The default Agent mode for Phase 1 route tests is `fake`.
- The internal auth header is `X-Internal-Key`.
- When `LINGNENG_INTERNAL_API_KEY` is non-empty, chat requests must present a
  matching `X-Internal-Key`.
- When `LINGNENG_INTERNAL_API_KEY` is empty, auth may be disabled only for
  `local`, `dev`, or `test` mode when `LINGNENG_ALLOW_INSECURE_LOCAL=true`.
- Production-like environments are any `app_env` values outside
  `local`, `dev`, and `test`.
- Production-like environments with an empty `LINGNENG_INTERNAL_API_KEY` must
  report `/internal/agent/ready` as not ready and must return non-SSE HTTP 503
  from `/internal/agent/chat/stream` before stream start.
- Request unknown fields are ignored at the Java boundary.
- `conversation_id` accepts both `conversation_id` and `conversationId`.
- Java `history` is accepted and counted for diagnostics but is never returned
  as Agent context and is never persisted as Hermes conversation history in
  Phase 1.
- `request_id` is the idempotency key inside a resolved LingNeng session.
- Full completed-run SSE replay is deferred to Phase 2, but the route must
  already reserve/check `(session_key, request_id)` before invoking the fake
  adapter and must not start a second adapter run for a repeated request.
- Phase 1 uses deterministic fake Agent output so contract tests do not require
  LLM keys, network access, external business services, or Hermes tool loops.
- Future CI/CD is GitHub Actions, but Phase 1 does not add workflow files.
- Docker/server deployment remains deferred.

## Open Decisions

Phase 1 has no user-blocking open decisions before the Phase 1 plan. The
following assumptions are locked for the plan unless the user changes them:

- Use `X-Internal-Key` as the Java internal auth header.
- Use `.runtime/lingneng` for local run-store state in tests and local runs.
- Keep the FastAPI app independent from `hermes_cli/web_server.py`.
- Start with fake Agent mode and leave real Hermes `AIAgent` streaming to
  Phase 2.

If any of these assumptions must change, update this spec before writing or
executing the Phase 1 plan.

## Data Contracts

### Settings

`LingNengSettings` must expose at least:

- `app_env`: defaults to `dev`.
- `api_host`: defaults to `127.0.0.1`.
- `api_port`: defaults to `18083`.
- `runtime_dir`: defaults to `.runtime/lingneng` and is normalized to a `Path`.
- `agent_mode`: defaults to `fake`.
- `internal_api_key`: defaults to an empty string.
- `allow_insecure_local`: defaults to `false`.
- `session_retention_days`: defaults to `90`.
- `archived_session_retention_days`: defaults to `180`.
- `idempotency_retention_days`: defaults to `7`.
- `heartbeat_interval_seconds`: defaults to `15.0`.

Settings must not expose secret values through `ready` responses or logs.

`app_env` values `local`, `dev`, and `test` are local-like environments.
Every other value is production-like for auth readiness checks.

### Request

`ChatStreamRequest` must match the Phase 0 Java contract baseline:

- Required top-level fields:
  - `request_id`
  - `tenant_id`
  - `user_id`
  - `session_id`
  - `query`
  - `employee`
  - `system_prompt`
  - `skill`
- Optional top-level `conversation_id` with alias `conversationId`.
- `query` fields:
  - `message_id`: optional string.
  - `content`: required string that rejects empty or whitespace-only text.
  - `content_type`: defaults to `text`.
- `system_prompt` fields:
  - `content`: required string.
  - `version`: optional string.
- `skill` fields:
  - `skill_id`: required string.
  - `skill_version`: required string.
  - `skill_hash`: required string.
  - `inline`: optional object, string, or null.
- Employee types are limited to:
  - `boss_assistant`
  - `operation_specialist`
  - `product_combo_advisor`
  - `marketing_planner`
  - `marketing_content_creator`
  - `member_operator`
- `history` is a list of messages:
  - `message_id`: optional string.
  - `role`: `user` or `assistant`.
  - `content`: required string.
- `history_options` defaults:
  - `source`: `java_payload`.
  - `max_history_tokens`: `4096`.
- `attachments` is a list of attachment objects:
  - `file_id`: required string.
  - `file_name`: required string.
  - `mime_type`: required string.
  - `size`: optional integer.
  - `download_url`: required string.
  - `download_url_expires_at`: optional string.
  - `usage`: defaults to `session_context`.
- `runtime_context` defaults:
  - `timezone`: `Asia/Shanghai`.
  - `region`: `CN`.
- `stream_options` defaults:
  - `include_agent_steps`: `true`.
  - `include_citations`: `true`.
  - `include_rag_context`: `false`.
  - unknown option fields are ignored.
- `model_options` defaults:
  - `enable_internal_reasoning`: `false`.
  - unknown option fields are ignored.
- `regenerate` defaults:
  - `enabled`: `false`.
  - `from_message_id`: optional string.
  - `extra_instruction`: optional string.
- `routing` accepts:
  - `confirmed_employee_type`: optional known employee type.
  - `confirmation_message_id`: optional string.
- `history`, `history_options`, `attachments`, `runtime_context`,
  `stream_options`, `model_options`, `regenerate`, and `routing` must parse.
- Extra Java fields must be ignored with Pydantic v2 `ConfigDict(extra="ignore")`.

History diagnostics may record presence, count, and coarse metadata, but must
not log the full Java `history` content.

### Session Key

Session key resolution must produce:

- `tenant_id:user_id:employee_id:conversation_id` when `employee_id` and
  `conversation_id` are present.
- `tenant_id:user_id:employee_type:conversation_id` when `employee_id` is
  missing.
- `tenant_id:user_id:employee_id:session_id` when `conversation_id` is missing.

When falling back from `conversation_id` to `session_id`, the resolved object
must record degradation metadata with reason `conversation_id_missing`.

The resolver must expose diagnostics that count Java `history` but must not
produce any context message list from Java `history`.

### Run Store

The SQLite run store must use a dedicated database file under
`LINGNENG_RUNTIME_DIR`. It must have a unique boundary on
`(session_key, request_id)`.

Each run record must store at least:

- `session_key`
- `request_id`
- `run_id`
- `status`
- `answer`
- `error_code`
- `error_message`
- `artifacts_json`
- `created_at`
- `updated_at`
- `completed_at`

Phase 1 statuses are:

- `running`
- `succeeded`
- `failed`

The store must support retention cleanup by configured idempotency retention
days.

The chat route must reserve/check the run store before invoking the adapter:

- First request for `(session_key, request_id)` creates or reserves a `running`
  run and invokes the adapter.
- Repeated request for an already `running` run must not invoke the adapter and
  must return a deterministic terminal `error` SSE event with code
  `REQUEST_ALREADY_RUNNING`.
- Repeated request for an already completed run must not invoke the adapter.
  Phase 1 may return a deterministic terminal `error` SSE event with code
  `REQUEST_ALREADY_COMPLETED`; full completed-run SSE replay remains Phase 2.

### SSE Events

The formal event name set remains:

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

Phase 1 route smoke tests must emit at least:

- `run_started`
- `answer_delta`
- `final`

Phase 1 route tests must verify streamed errors after stream start:

- adapter/runtime failure emits exactly one terminal `error` event.
- streamed `error` includes `run_id`, `request_id`, `code`, `message`,
  `trace_id`, and `recoverable`.
- streamed `error` does not emit `final` after the failure.

Minimum Phase 1 payloads:

- `RunStartedEvent(run_id, request_id)`
- `AnswerDeltaEvent(text, sequence)`
- `FinalEvent(run_id, status, answer, citations=[], artifacts=[])`
- `ErrorEvent(run_id, request_id, code, message, trace_id, recoverable)`

`FinalEvent.status` must allow:

- `succeeded`
- `degraded`
- `failed`
- `blocked`

`FinalEvent` must not include a `tool_plan` field.

### SSE Encoding

`encode_sse(event_name, data)` must produce:

```text
event: <event_name>
data: <json>

```

The encoded JSON must use UTF-8 readable output equivalent to
`json.dumps(..., ensure_ascii=False)`.

The `data` JSON does not need an `event` property. The SSE `event:` line is the
event type source of truth.

The heartbeat frame must be exactly:

```text
: ping

```

The exact string is `: ping\n\n`.

## Module Boundaries

### `lingneng/config`

Owns environment-driven settings and secret redaction. It must not import
FastAPI or Hermes `AIAgent`.

### `lingneng/schemas`

Owns Java request models and LingNeng SSE event models. It must not import
route handlers, runtime adapters, or database stores.

### `lingneng/session`

Owns session key resolution and the Phase 1 run store. It must not depend on
FastAPI or the fake Agent adapter.

### `lingneng/events`

Owns conversion between adapter events and LingNeng SSE event models. In Phase
1 this is intentionally small and mostly stamps run/request/sequence metadata
for fake events.

### `lingneng/runtime`

Owns the `AgentRunAdapter` protocol and `FakeAgentRunAdapter`. The protocol
must let Phase 2 replace fake output with Hermes `AIAgent` output without
changing the API route contract.

### `lingneng/api`

Owns FastAPI app creation, auth, route handlers, SSE encoding, heartbeat
wrapping, and uvicorn entrypoint. `create_app(settings=None, adapter=None,
run_store=None)` must allow tests to inject settings, fake adapters, and
temporary run stores.

The API module may import `lingneng/config`, `lingneng/schemas`,
`lingneng/session`, `lingneng/events`, and `lingneng/runtime`. It must not
import Hermes dashboard app state.

## HTTP Behavior

### `GET /internal/agent/health`

Returns:

```json
{"status":"ok"}
```

This endpoint must not require internal auth and must not expose secrets.

### `GET /internal/agent/ready`

Returns a JSON readiness summary without secret values. The response must
include at least:

- `status`
- `app_env`
- `agent_mode`
- `runtime_dir`
- `auth_required`

If production-like settings are insecure, `ready` must report a not-ready
status without returning the configured secret.

### `POST /internal/agent/chat/stream`

When auth is enabled and the key is missing or invalid, return a non-SSE HTTP
error.

When `app_env` is production-like and `internal_api_key` is empty, return
non-SSE HTTP 503 before stream start. The response must not include a secret
value.

When `app_env` is `local`, `dev`, or `test`, `internal_api_key` is empty, and
`allow_insecure_local` is not true, return a non-SSE HTTP 503 before stream
start. This is an unsafe configuration error, not a streamed business error.

When auth succeeds and the request is valid, return `text/event-stream`.

In fake Agent mode, the stream must emit:

1. `run_started`
2. one or more `answer_delta`
3. exactly one `final`

The concatenated `answer_delta.text` values must equal `final.answer`.

Business/runtime exceptions after stream start must be represented as `error`
events when possible. Request validation and auth failures before stream start
remain normal HTTP errors.

The route must reserve/check `(session_key, request_id)` before invoking its
adapter. Repeated running or completed request ids must not start a second
adapter run.

## Test Strategy

Phase 1 must be test-first. Each plan task should write the relevant failing
test first, confirm the expected failure, implement the minimum code, then
confirm the test passes.

Required focused test commands:

```bash
uv run --extra dev python -m pytest tests/lingneng/config/test_settings.py -q
uv run --extra dev python -m pytest tests/lingneng/config/test_packaging.py -q
uv run --extra dev python -m pytest tests/lingneng/schemas/test_chat_request_schema.py -q
uv run --extra dev python -m pytest tests/lingneng/schemas/test_chat_event_schema.py tests/lingneng/api/test_sse_encoding.py -q
uv run --extra dev python -m pytest tests/lingneng/session/test_session_key_resolver.py -q
uv run --extra dev python -m pytest tests/lingneng/session/test_run_store.py -q
uv run --extra dev python -m pytest tests/lingneng/runtime/test_agent_adapter_contract.py -q
uv run --extra dev python -m pytest tests/lingneng/api/test_chat_stream_contract.py -q
```

`tests/lingneng/api/test_chat_stream_contract.py` must include route-level
assertions for:

- successful fake stream event order.
- missing/invalid auth.
- production-like missing internal key returns non-SSE HTTP 503 before stream
  start.
- adapter/runtime failure after stream start producing terminal `error`.
- repeated running `request_id` not invoking the adapter again.
- repeated completed `request_id` not invoking the adapter again.

Required phase-level verification:

```bash
uv run --extra dev python -m pytest tests/lingneng/config tests/lingneng/schemas tests/lingneng/session tests/lingneng/api tests/lingneng/runtime -q
```

Reference contract command:

```bash
/Users/rotas/Documents/work/hailun/LingNengAI/.venv/bin/python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py -q
```

No local service needs to be started for Phase 1 verification; FastAPI route
tests should use `fastapi.testclient.TestClient`. If a local server is started
manually, port preflight must check `18083` before binding.

## Acceptance Criteria

Phase 1 is complete when:

- `lingneng/` package modules listed in scope exist.
- `pyproject.toml` package discovery includes `lingneng` and `lingneng.*` so
  installed builds include the new runtime package.
- Settings parse defaults and environment overrides without leaking secrets.
- Java-compatible request schema parses the full current payload shape.
- `conversationId` and `conversation_id` both populate `conversation_id`.
- Unknown Java request fields are ignored.
- Empty `query.content` is rejected.
- Java `history` shape parses, but full history content is not logged.
- SSE event models include the full formal event name set.
- `FinalEvent` does not include `tool_plan`.
- SSE encoder emits Java-compatible `event:` and `data:` frames with UTF-8
  readable JSON.
- Heartbeat frame is exactly `: ping\n\n`.
- Session key resolver follows the accepted tenant/user/employee/conversation
  rules and records degradation metadata for `conversation_id` fallback.
- Java `history` is counted for diagnostics but not converted to Agent context.
- Run store enforces uniqueness on `(session_key, request_id)`.
- Chat stream route checks/reserves `(session_key, request_id)` before invoking
  the adapter.
- Repeated running and repeated completed `request_id` values do not invoke a
  second adapter run.
- Fake Agent adapter emits `run_started`, `answer_delta`, and `final`.
- Chat stream route returns `text/event-stream` and emits the minimum Phase 1
  event sequence with joined deltas equal to final answer.
- Adapter/runtime failure after stream start emits one terminal `error` event
  with `run_id`, `request_id`, `code`, `message`, `trace_id`, and
  `recoverable`, and does not emit `final`.
- Health and ready endpoints return non-secret JSON.
- Auth rejects missing or invalid `X-Internal-Key` when auth is enabled.
- Production-like missing-key configuration reports `ready.status` as not ready
  and chat returns non-SSE HTTP 503 before stream start.
- Phase-level pytest command passes.
- LingNengAI reference contract command still passes where the reference
  virtual environment is available.
- No Docker, Compose, deployment script, GitHub Actions workflow, real Hermes
  `AIAgent` adapter, RAG, skill loader, artifact tool, or business toolset work
  is included in this phase.

## Phase 2 Handoff

Phase 2 starts only after Phase 1 is verified, committed, and pushed. The Phase
2 spec must use Phase 1's adapter protocol and replace `FakeAgentRunAdapter`
with a Hermes `AIAgent` adapter while keeping the Java request, SSE encoding,
session key, and route contracts stable.
