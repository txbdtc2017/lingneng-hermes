# LingNeng Hermes Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement approved phase plans task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Java-compatible LingNeng Agent runtime on top of this Hermes fork without modifying Java code.

**Architecture:** Add a `lingneng/` namespace around Hermes core: FastAPI facade, Pydantic schemas, session/idempotency adapters, SSE bridge, AIAgent adapter, controlled toolset, and skill loader. Keep Hermes CLI/TUI/Gateway/plugins intact while the LingNeng API exposes only a business-safe surface.

**Tech Stack:** Python 3.11-3.13, FastAPI, Pydantic v2, SQLite, Hermes `AIAgent`, Hermes `SessionDB`, pytest, uv. Docker, Docker Compose, and GitHub Actions are deferred to the later deployment phase.

---

## Locked Assumptions

- Java code is not changed during this migration.
- The Java entrypoint remains `POST /internal/agent/chat/stream`.
- SSE response media type remains `text/event-stream`.
- Python owns Agent session history; Java `history` is accepted, counted, and traced, but never merged into Hermes conversation context.
- Session key format is `tenant_id:user_id:employee_id:conversation_id`, with `employee_type` fallback when `employee_id` is missing and `session_id` fallback only when `conversation_id` is missing.
- `request_id` is the idempotency key within a resolved session key.
- LingNeng API defaults to a dedicated safe toolset and excludes terminal, arbitrary filesystem, browser automation, code execution, and cross-channel messaging.
- The repository is hosted on GitHub. CI/CD planning targets GitHub Actions.
- Docker/server deployment remains a later requirement, but it is not part of the immediate runtime改造 path.
- Execution should happen on `dev` for implementation work and flow to `test` through the repo's normal branch process.

## Implementation Sequence

This document is the master roadmap. It is not the execution plan for every
phase in one pass. To prevent scope drift, missing decisions, and noisy partial
implementation, every phase must go through this gate sequence:

```text
phase spec -> phase plan -> subagent-driven execution
```

Execute the migration in this order:

1. Finish and verify Phase 0.
2. Before starting Phase 1, write a dedicated Phase 1 spec in
   `docs/lingneng-migration/specs/` with the filename format
   `YYYY-MM-DD-phase-1-<topic>-spec.md`.
3. Review and approve the Phase 1 spec.
4. Write a dedicated Phase 1 plan in
   `docs/lingneng-migration/plans/` with the filename format
   `YYYY-MM-DD-phase-1-<topic>-plan.md`.
5. Review and approve the Phase 1 plan before touching runtime code.
6. Execute Phase 1 task-by-task with `superpowers:subagent-driven-development`.
   After each task, run the task's verification, commit with a Chinese
   conventional-prefix message, and push only after verification passes.
7. After Phase 1 is complete, self-review it against the Phase 1 spec, Phase 1
   plan, and this master roadmap.
8. Repeat the same loop for Phase 2 through Phase 8: write one complete phase
   spec, review it, write one complete phase plan, review it, execute it with
   subagents, verify it, then move to the next phase.

Rules for each dedicated phase spec:

- It must define that phase's goal, scope, non-goals, accepted decisions,
  open decisions, data/API contracts, module boundaries, test strategy, and
  acceptance criteria.
- It must list all user confirmations needed before the phase plan is written.
- It must be reviewed and approved before the phase plan is written.

Rules for each dedicated phase plan:

- It must be self-contained for that phase: goal, scope, non-goals, decision
  points, file map, task breakdown, test commands, commit points, and rollback
  notes.
- It must explicitly reference the approved phase spec it implements.
- It must list any user confirmations needed before execution starts.
- It must not pull future deployment work into runtime改造 phases.
- It must not start Phase N+1 until Phase N is complete, explicitly deferred,
  or the user changes the order.

## Context Compaction Reload Rule

After every context compaction, resume, or handoff, reload the durable migration
context before doing more work:

1. `LINGNENG_MIGRATION_CONTEXT.md`
2. `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
3. `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`

This reload is required before writing a phase spec, writing a phase plan,
implementing runtime code, running verification, committing, or pushing.

## Reference Inputs

- Current spec: `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- Migration context: `LINGNENG_MIGRATION_CONTEXT.md`
- LingNengAI reference project: `/Users/rotas/Documents/work/hailun/LingNengAI`
- LingNengAI request schema reference: `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_request.py`
- LingNengAI event schema reference: `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_events.py`
- LingNengAI chat stream reference: `/Users/rotas/Documents/work/hailun/LingNengAI/app/api/internal/chat_stream.py`
- Future deployment reference: `/Users/rotas/Documents/work/hailun/LingNengAI/scripts/deploy-local-test.sh`
- Future server compose reference: `/Users/rotas/Documents/work/hailun/LingNengAI/deploy/local/docker-compose.agent-test.yml`

## File Structure Target

### New Runtime Modules

- `lingneng/__init__.py`: package marker and version helpers.
- `lingneng/api/__init__.py`: API package marker.
- `lingneng/api/app.py`: FastAPI app factory and router registration.
- `lingneng/api/routes.py`: `/internal/agent/chat/stream`, `/internal/agent/health`, `/internal/agent/ready`.
- `lingneng/api/server.py`: uvicorn CLI entrypoint for local server runs and later Docker reuse.
- `lingneng/api/auth.py`: internal request authentication.
- `lingneng/api/sse.py`: SSE frame encoding and heartbeat wrapper.
- `lingneng/config/__init__.py`: config package marker.
- `lingneng/config/settings.py`: environment-driven LingNeng runtime settings.
- `lingneng/schemas/__init__.py`: schema package marker.
- `lingneng/schemas/chat_request.py`: Java-compatible request models.
- `lingneng/schemas/chat_events.py`: Java-compatible SSE event models.
- `lingneng/session/__init__.py`: session package marker.
- `lingneng/session/keys.py`: session key resolver and degradation logging metadata.
- `lingneng/session/run_store.py`: SQLite idempotency and run state store.
- `lingneng/runtime/__init__.py`: runtime package marker.
- `lingneng/runtime/agent_adapter.py`: interface between API facade and Hermes `AIAgent`.
- `lingneng/runtime/fake_agent.py`: deterministic adapter for tests and local smoke runs.
- `lingneng/events/__init__.py`: event package marker.
- `lingneng/events/bridge.py`: adapter events to LingNeng SSE event models.
- `lingneng/tools/__init__.py`: tool package marker.
- `lingneng/tools/toolset.py`: dedicated LingNeng toolset registration.
- `lingneng/tools/stubs.py`: explicit non-production tool stubs for Phase 1 contract tests.
- `lingneng/skills/__init__.py`: skills package marker.
- `lingneng/skills/loader.py`: employee skill loading and progressive disclosure.

### Future Deployment Assets

- `deploy/lingneng/Dockerfile`: slim LingNeng-Hermes runtime image.
- `deploy/lingneng/docker-compose.yml`: server compose template.
- `deploy/lingneng/.env.example`: dev server environment template with no secrets.
- `deploy/lingneng/README.md`: server deployment runbook.
- `scripts/deploy-lingneng-local.sh`: image rollout, env rewrite, health checks, rollback.
- `scripts/lingneng-health-check.sh`: HTTP health/ready/SSE smoke helper.
- `.github/workflows/lingneng-runtime-ci.yml`: GitHub Actions test workflow.
- `.github/workflows/lingneng-runtime-image.yml`: GitHub Actions image build workflow.

### New Tests

- `tests/lingneng/schemas/test_chat_request_schema.py`
- `tests/lingneng/schemas/test_chat_event_schema.py`
- `tests/lingneng/session/test_session_key_resolver.py`
- `tests/lingneng/session/test_run_store.py`
- `tests/lingneng/api/test_sse_encoding.py`
- `tests/lingneng/api/test_chat_stream_contract.py`
- `tests/lingneng/runtime/test_agent_adapter_contract.py`
- `tests/lingneng/tools/test_toolset_policy.py`
- `tests/lingneng/deploy/test_lingneng_compose.py` (future deployment phase)
- `tests/lingneng/deploy/test_deploy_lingneng_local.py` (future deployment phase)

---

## Phase 0: Contract Baseline And Repo Guardrails

**Goal:** Freeze the external behavior to copy from LingNengAI before runtime code starts.

**Acceptance:** Contract tests can be written from a known request/event reference, and GitHub is the documented CI/CD target.

### Task 0.1: Capture LingNengAI Contract References

**Files:**
- Create: `docs/lingneng-migration/specs/2026-06-06-lingneng-java-contract-baseline.md`
- Read: `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_request.py`
- Read: `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_events.py`
- Read: `/Users/rotas/Documents/work/hailun/LingNengAI/app/api/internal/chat_stream.py`
- Read: `/Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py`
- Read: `/Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_stream_event_order.py`

- [ ] Record required request fields, optional fields, aliases, and ignored extras.
- [ ] Record formal SSE event names and the minimum Phase 1 event subset: `run_started`, `answer_delta`, `final`, `error`.
- [ ] Record heartbeat format `: ping\n\n`.
- [ ] Record event order requirements: `run_started` before answer events, `final` terminal, `error` terminal on failure.
- [ ] Run: `python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py -q`
- [ ] Expected: the reference contract tests pass in the LingNengAI checkout.
- [ ] Commit: `docs: 记录灵能 Java 接口基线`
- [ ] Push the active branch after the commit succeeds.

### Task 0.2: Confirm GitHub Branch And CI Assumptions

**Files:**
- Create: `docs/lingneng-migration/specs/2026-06-06-lingneng-github-workflow-baseline.md`

- [ ] Record that the repository is hosted on GitHub.
- [ ] Record that CI/CD automation should use GitHub Actions.
- [ ] Record intended branch flow: implementation on `dev`, validation on `test`, production stabilization through later release policy.
- [ ] Record that Docker/server deployment is deferred until after the runtime改造 phases.
- [ ] Run: `git remote -v`
- [ ] Expected: output shows the repository remote used for this checkout; if it is not the final GitHub remote, note that in the baseline doc instead of guessing.
- [ ] Commit: `docs: 记录灵能 GitHub 工作流基线`
- [ ] Push the active branch after the commit succeeds.

---

## Phase 1: Java-Compatible API MVP

**Goal:** Build the smallest LingNeng-Hermes API that Java can call without code changes.

**Acceptance:** Local tests pass, and a fake-agent SSE smoke test emits `run_started`, `answer_delta`, and `final`.

### Task 1.1: Add LingNeng Settings

**Files:**
- Create: `lingneng/__init__.py`
- Create: `lingneng/config/__init__.py`
- Create: `lingneng/config/settings.py`
- Test: `tests/lingneng/config/test_settings.py`

- [ ] Write failing tests for default settings:
  - `LINGNENG_API_HOST` defaults to `127.0.0.1` for local runtime safety.
  - `LINGNENG_API_PORT` defaults to `18083`.
  - `LINGNENG_RUNTIME_DIR` defaults to `.runtime/lingneng`.
  - `LINGNENG_SESSION_RETENTION_DAYS` defaults to `90`.
  - `LINGNENG_ARCHIVED_SESSION_RETENTION_DAYS` defaults to `180`.
  - `LINGNENG_IDEMPOTENCY_RETENTION_DAYS` defaults to `7`.
  - `LINGNENG_INTERNAL_API_KEY` defaults to an empty string and disables auth only for local/dev when explicit config allows it.
- [ ] Run: `python -m pytest tests/lingneng/config/test_settings.py -q`
- [ ] Expected: fail because `lingneng.config.settings` does not exist.
- [ ] Implement a `LingNengSettings` Pydantic model with `from_env()` and path normalization.
- [ ] Keep secrets in env only; do not add secret defaults to docs or code.
- [ ] Run: `python -m pytest tests/lingneng/config/test_settings.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 增加灵能运行配置`
- [ ] Push the active branch after the commit succeeds.

### Task 1.2: Add Java-Compatible Request Schemas

**Files:**
- Create: `lingneng/schemas/__init__.py`
- Create: `lingneng/schemas/chat_request.py`
- Test: `tests/lingneng/schemas/test_chat_request_schema.py`
- Reference: `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_request.py`

- [ ] Write failing schema tests that parse a full Java payload with:
  - `request_id`
  - `tenant_id`
  - `user_id`
  - `session_id`
  - `conversation_id`
  - `query.content`
  - `employee.employee_id`
  - `employee.employee_type`
  - `system_prompt.content`
  - `skill.skill_id`
  - `history`
  - `attachments`
  - `runtime_context`
  - `stream_options`
  - `model_options`
  - `regenerate`
  - `routing`
- [ ] Write a test that accepts `conversationId` as an alias for `conversation_id`.
- [ ] Write a test that ignores unknown Java fields through `ConfigDict(extra="ignore")`.
- [ ] Write a test that rejects empty `query.content`.
- [ ] Run: `python -m pytest tests/lingneng/schemas/test_chat_request_schema.py -q`
- [ ] Expected: fail because the schema module does not exist.
- [ ] Implement request models matching the LingNengAI reference.
- [ ] Keep `EmployeeType` limited to known LingNeng employee values.
- [ ] Run: `python -m pytest tests/lingneng/schemas/test_chat_request_schema.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 增加灵能请求协议模型`
- [ ] Push the active branch after the commit succeeds.

### Task 1.3: Add SSE Event Schemas And Encoder

**Files:**
- Create: `lingneng/schemas/chat_events.py`
- Create: `lingneng/api/__init__.py`
- Create: `lingneng/api/sse.py`
- Test: `tests/lingneng/schemas/test_chat_event_schema.py`
- Test: `tests/lingneng/api/test_sse_encoding.py`
- Reference: `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_events.py`
- Reference: `/Users/rotas/Documents/work/hailun/LingNengAI/app/api/internal/chat_stream.py`

- [ ] Write failing tests that assert the formal event names exactly include:
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
- [ ] Write failing tests for Phase 1 event payloads:
  - `RunStartedEvent(run_id, request_id)`
  - `AnswerDeltaEvent(text, sequence)`
  - `FinalEvent(run_id, status, answer, citations=[], artifacts=[])`
  - `ErrorEvent(run_id, request_id, code, message, trace_id, recoverable)`
- [ ] Write failing encoder tests:
  - `encode_sse("answer_delta", {"text": "你好"})` returns `event: answer_delta\ndata: {"text":"你好"}\n\n` with UTF-8-safe JSON.
  - `heartbeat_frame()` returns `: ping\n\n`.
- [ ] Run: `python -m pytest tests/lingneng/schemas/test_chat_event_schema.py tests/lingneng/api/test_sse_encoding.py -q`
- [ ] Expected: fail because event schema and SSE encoder do not exist.
- [ ] Implement Pydantic event models and SSE encoder.
- [ ] Ensure `data` JSON does not need an `event` field.
- [ ] Run: `python -m pytest tests/lingneng/schemas/test_chat_event_schema.py tests/lingneng/api/test_sse_encoding.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 增加灵能 SSE 协议模型`
- [ ] Push the active branch after the commit succeeds.

### Task 1.4: Add Session Key Resolver

**Files:**
- Create: `lingneng/session/__init__.py`
- Create: `lingneng/session/keys.py`
- Test: `tests/lingneng/session/test_session_key_resolver.py`

- [ ] Write failing tests for key resolution:
  - employee id present: `tenant:user:employee_id:conversation_id`
  - missing employee id: `tenant:user:employee_type:conversation_id`
  - missing conversation id: `tenant:user:employee_id:session_id`
  - missing conversation id emits degradation metadata with reason `conversation_id_missing`.
- [ ] Write a failing test that `history` size is counted in diagnostics but not returned as context messages.
- [ ] Run: `python -m pytest tests/lingneng/session/test_session_key_resolver.py -q`
- [ ] Expected: fail because resolver does not exist.
- [ ] Implement `ResolvedSessionKey` and `resolve_session_key(request)`.
- [ ] Include `tenant_id`, `user_id`, `conversation_id`, `session_id`, `employee_id`, `employee_type`, and `degraded` fields in the resolved object.
- [ ] Run: `python -m pytest tests/lingneng/session/test_session_key_resolver.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 增加灵能会话键解析`
- [ ] Push the active branch after the commit succeeds.

### Task 1.5: Add SQLite Run Store For Idempotency

**Files:**
- Create: `lingneng/session/run_store.py`
- Test: `tests/lingneng/session/test_run_store.py`

- [ ] Write failing tests for run store behavior:
  - first `request_id` in a session creates status `running`.
  - same `request_id` while running returns the existing run without creating another row.
  - completed run stores final answer and terminal status.
  - repeated completed request returns stored final result.
  - same `request_id` in a different session creates a separate run.
  - retention cleanup deletes rows older than configured days.
- [ ] Run: `python -m pytest tests/lingneng/session/test_run_store.py -q`
- [ ] Expected: fail because run store does not exist.
- [ ] Implement SQLite table `lingneng_runs` in a dedicated DB file under `LINGNENG_RUNTIME_DIR`.
- [ ] Use `(session_key, request_id)` as the unique idempotency boundary.
- [ ] Store `run_id`, `status`, `answer`, `error_code`, `error_message`, `artifacts_json`, `created_at`, `updated_at`, and `completed_at`.
- [ ] Run: `python -m pytest tests/lingneng/session/test_run_store.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 增加灵能请求幂等存储`
- [ ] Push the active branch after the commit succeeds.

### Task 1.6: Add Fake Agent Adapter And Event Bridge

**Files:**
- Create: `lingneng/runtime/__init__.py`
- Create: `lingneng/runtime/agent_adapter.py`
- Create: `lingneng/runtime/fake_agent.py`
- Create: `lingneng/events/__init__.py`
- Create: `lingneng/events/bridge.py`
- Test: `tests/lingneng/runtime/test_agent_adapter_contract.py`

- [ ] Write failing tests for the adapter protocol:
  - input contains parsed request and resolved session key.
  - output is an async iterator of LingNeng event models.
  - fake adapter emits `run_started`, one or more `answer_delta`, and `final`.
  - joined `answer_delta.text` equals `final.answer`.
- [ ] Run: `python -m pytest tests/lingneng/runtime/test_agent_adapter_contract.py -q`
- [ ] Expected: fail because adapter modules do not exist.
- [ ] Implement an `AgentRunAdapter` protocol with `stream(request, resolved_session)`.
- [ ] Implement `FakeAgentRunAdapter` for deterministic local tests.
- [ ] Implement bridge helpers that stamp `request_id`, `run_id`, sequence, and trace metadata.
- [ ] Run: `python -m pytest tests/lingneng/runtime/test_agent_adapter_contract.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 增加灵能 Agent 适配器接口`
- [ ] Push the active branch after the commit succeeds.

### Task 1.7: Add FastAPI App, Routes, Auth, Health, Ready

**Files:**
- Create: `lingneng/api/auth.py`
- Create: `lingneng/api/app.py`
- Create: `lingneng/api/routes.py`
- Create: `lingneng/api/server.py`
- Test: `tests/lingneng/api/test_chat_stream_contract.py`

- [ ] Write failing tests with `fastapi.testclient.TestClient`:
  - `GET /internal/agent/health` returns `{"status":"ok"}`.
  - `GET /internal/agent/ready` returns status and configuration summary without secrets.
  - `POST /internal/agent/chat/stream` returns `text/event-stream`.
  - stream contains `event: run_started`, `event: answer_delta`, and `event: final`.
  - missing/invalid internal key returns non-SSE HTTP error when auth is enabled.
- [ ] Run: `python -m pytest tests/lingneng/api/test_chat_stream_contract.py -q`
- [ ] Expected: fail because FastAPI app modules do not exist.
- [ ] Implement `create_app(settings=None, adapter=None, run_store=None)`.
- [ ] Implement auth using `X-Internal-Key` and `LINGNENG_INTERNAL_API_KEY`.
- [ ] Implement `/internal/agent/chat/stream` using `StreamingResponse`.
- [ ] Wrap stream with heartbeat every 15 seconds.
- [ ] Use `FakeAgentRunAdapter` when `LINGNENG_AGENT_MODE=fake`.
- [ ] Run: `python -m pytest tests/lingneng/api/test_chat_stream_contract.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 增加灵能 Java 兼容 API`
- [ ] Push the active branch after the commit succeeds.

## Phase 2: Hermes AIAgent Integration And Persistent Conversation

**Goal:** Replace fake responses with Hermes `AIAgent` while keeping the Java SSE contract stable.

**Acceptance:** The API can run a no-tool Hermes conversation, stream answer deltas when available, persist the session, and prevent duplicate appends for repeated `request_id`.

### Task 2.1: Add Hermes Adapter Construction

**Files:**
- Modify: `lingneng/runtime/agent_adapter.py`
- Create: `lingneng/runtime/hermes_adapter.py`
- Test: `tests/lingneng/runtime/test_hermes_adapter_config.py`

- [ ] Write failing tests that verify `HermesAgentRunAdapter` constructs `AIAgent` with:
  - `platform="lingneng"`
  - `session_id` equal to resolved session key
  - `enabled_toolsets=["lingneng"]`
  - high-risk default toolsets disabled
  - Java `history` not included in `conversation_history`
- [ ] Use dependency injection or monkeypatching so tests do not call a real model.
- [ ] Run: `python -m pytest tests/lingneng/runtime/test_hermes_adapter_config.py -q`
- [ ] Expected: fail because Hermes adapter does not exist.
- [ ] Implement Hermes adapter factory.
- [ ] Keep `run_agent.py` unchanged unless a missing callback extension is proven by tests.
- [ ] Run: `python -m pytest tests/lingneng/runtime/test_hermes_adapter_config.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 接入 Hermes Agent 适配器`
- [ ] Push the active branch after the commit succeeds.

### Task 2.2: Add Answer Delta Callback Bridge

**Files:**
- Modify: `lingneng/runtime/hermes_adapter.py`
- Modify: `lingneng/events/bridge.py`
- Test: `tests/lingneng/runtime/test_hermes_answer_stream.py`

- [ ] Write failing tests with a fake Hermes client that emits text chunks `["你", "好"]`.
- [ ] Assert SSE events include two `answer_delta` events with sequence `1` and `2`.
- [ ] Assert final answer equals `你好`.
- [ ] Run: `python -m pytest tests/lingneng/runtime/test_hermes_answer_stream.py -q`
- [ ] Expected: fail because callback bridge does not exist.
- [ ] Implement callback queue from Hermes streaming callbacks to LingNeng event models.
- [ ] Coalesce only when required by backpressure; do not duplicate deltas.
- [ ] Run: `python -m pytest tests/lingneng/runtime/test_hermes_answer_stream.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 桥接 Hermes 流式回答`
- [ ] Push the active branch after the commit succeeds.

### Task 2.3: Persist Conversation With Hermes SessionDB

**Files:**
- Create: `lingneng/session/hermes_session.py`
- Modify: `lingneng/runtime/hermes_adapter.py`
- Test: `tests/lingneng/session/test_hermes_session_adapter.py`

- [ ] Write failing tests that prove two requests with the same conversation id reuse the same Hermes session key.
- [ ] Write failing tests that prove a different employee id creates a different Hermes session key.
- [ ] Write failing tests that prove Java `history` messages are not appended to SessionDB.
- [ ] Run: `python -m pytest tests/lingneng/session/test_hermes_session_adapter.py -q`
- [ ] Expected: fail because adapter does not exist.
- [ ] Implement a thin wrapper around `SessionDB` for LingNeng session create/load/update.
- [ ] Use Hermes existing compression/session mechanics instead of adding a second message store.
- [ ] Run: `python -m pytest tests/lingneng/session/test_hermes_session_adapter.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 连接灵能会话到 Hermes SessionDB`
- [ ] Push the active branch after the commit succeeds.

### Task 2.4: Complete Idempotent Request Replay

**Files:**
- Modify: `lingneng/api/routes.py`
- Modify: `lingneng/session/run_store.py`
- Test: `tests/lingneng/api/test_chat_stream_idempotency.py`

- [ ] Write failing tests:
  - repeated completed `request_id` returns stored final SSE without invoking adapter.
  - repeated running `request_id` returns a deterministic `error` with code `REQUEST_ALREADY_RUNNING`.
  - failed run stores error state and repeated request returns the stored error event.
- [ ] Run: `python -m pytest tests/lingneng/api/test_chat_stream_idempotency.py -q`
- [ ] Expected: fail because route does not replay run store results.
- [ ] Implement route-level idempotency handling before appending user message or invoking `AIAgent`.
- [ ] Store final answer and terminal status after stream completion.
- [ ] Run: `python -m pytest tests/lingneng/api/test_chat_stream_idempotency.py -q`
- [ ] Expected: pass.
- [ ] Commit: `fix: 防止重复请求污染会话`
- [ ] Push the active branch after the commit succeeds.

### Task 2.5: Add No-Tool End-To-End Contract Test

**Files:**
- Create: `tests/lingneng/contract/test_chat_stream_minimal.py`

- [ ] Write a TestClient contract test using fake Hermes model injection.
- [ ] Assert event order: `run_started`, one or more `answer_delta`, `final`.
- [ ] Assert joined deltas equal `final.answer`.
- [ ] Assert response data JSON does not require an `event` field.
- [ ] Assert `Content-Type` starts with `text/event-stream`.
- [ ] Run: `python -m pytest tests/lingneng/contract/test_chat_stream_minimal.py -q`
- [ ] Expected: pass after Phase 2 tasks.
- [ ] Commit: `test: 增加灵能最小对话合同测试`
- [ ] Push the active branch after the commit succeeds.

---

## Phase 3: Dedicated LingNeng Toolset And Security Boundary

**Goal:** Provide a safe LingNeng toolset surface before business tools are migrated.

**Acceptance:** LingNeng API exposes only approved LingNeng tool schemas and never exposes Hermes high-risk defaults.

### Task 3.1: Register LingNeng Toolset Skeleton

**Files:**
- Create: `lingneng/tools/toolset.py`
- Create: `lingneng/tools/stubs.py`
- Modify: `toolsets.py`
- Test: `tests/lingneng/tools/test_toolset_policy.py`

- [ ] Write failing tests that assert toolset `lingneng` exists.
- [ ] Write failing tests that assert these tool names are present as disabled or stubbed business tools:
  - `retrieve_rag`
  - `list_skills`
  - `search_skills`
  - `read_skill`
  - `read_skill_resource`
  - `document_generation`
  - `image_generation`
  - `chart_visualization`
  - `web_search`
  - `read_workspace`
  - `write_workspace`
- [ ] Write failing tests that assert high-risk tools are absent from the LingNeng API toolset:
  - terminal execution
  - arbitrary local file access
  - browser automation
  - code execution
  - cross-channel messaging
- [ ] Run: `python -m pytest tests/lingneng/tools/test_toolset_policy.py -q`
- [ ] Expected: fail because LingNeng toolset does not exist.
- [ ] Register LingNeng tool schemas through existing Hermes registry/toolset mechanisms.
- [ ] Stub tools return JSON with `success=false`, `code="NOT_CONFIGURED"`, and an agent-safe message until the business implementation lands.
- [ ] Run: `python -m pytest tests/lingneng/tools/test_toolset_policy.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 增加灵能专用工具集`
- [ ] Push the active branch after the commit succeeds.

### Task 3.2: Map Tool Progress To `agent_step`

**Files:**
- Modify: `lingneng/events/bridge.py`
- Modify: `lingneng/runtime/hermes_adapter.py`
- Test: `tests/lingneng/events/test_agent_step_bridge.py`

- [ ] Write failing tests for tool start, success, skip, and failure progress.
- [ ] Assert public `agent_step` fields include `sequence`, `step_id`, `phase`, `status`, `title`, `short_text`, `summary`, and `refs`.
- [ ] Assert internal exception text is not leaked to public `agent_step`.
- [ ] Run: `python -m pytest tests/lingneng/events/test_agent_step_bridge.py -q`
- [ ] Expected: fail because tool progress bridge is incomplete.
- [ ] Implement tool progress mapping with safe public messages.
- [ ] Run: `python -m pytest tests/lingneng/events/test_agent_step_bridge.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 映射工具进度到灵能事件`
- [ ] Push the active branch after the commit succeeds.

---

## Phase 4: RAG And Skill Loader Minimum Migration

**Goal:** Move the first business intelligence capabilities onto Hermes without copying the old LangGraph runtime.

**Acceptance:** Employees get controlled base prompts and skill excerpts, and `retrieve_rag` can return Java-compatible RAG/citation events.

### Task 4.1: Implement Employee Skill Loader

**Files:**
- Create: `lingneng/skills/loader.py`
- Create: `lingneng/skills/models.py`
- Test: `tests/lingneng/skills/test_skill_loader.py`
- Reference: `/Users/rotas/Documents/work/hailun/LingNengAI/app/skills`

- [ ] Write failing tests for loading employee base skill by `employee_type`.
- [ ] Write failing tests for explicit `skill.skill_id` selection.
- [ ] Write failing tests that large skill resources are summarized or exposed through progressive disclosure, not injected wholesale.
- [ ] Write failing tests that `script_policy` remains metadata-only or stricter.
- [ ] Run: `python -m pytest tests/lingneng/skills/test_skill_loader.py -q`
- [ ] Expected: fail because skill loader does not exist.
- [ ] Implement loader models and prompt fragments.
- [ ] Wire skill loader output into `HermesAgentRunAdapter` system prompt construction.
- [ ] Run: `python -m pytest tests/lingneng/skills/test_skill_loader.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 增加数字员工技能加载`
- [ ] Push the active branch after the commit succeeds.

### Task 4.2: Implement RAG Tool Adapter

**Files:**
- Create: `lingneng/tools/rag.py`
- Modify: `lingneng/tools/toolset.py`
- Modify: `lingneng/events/bridge.py`
- Test: `tests/lingneng/tools/test_retrieve_rag.py`
- Test: `tests/lingneng/events/test_rag_events.py`

- [ ] Write failing tests for `retrieve_rag` request shape: query, tenant id, employee type, top k, filters.
- [ ] Write failing tests for empty RAG results emitting `rag_context` with status `empty`.
- [ ] Write failing tests for successful RAG results emitting `citation_delta` and `rag_context`.
- [ ] Run: `python -m pytest tests/lingneng/tools/test_retrieve_rag.py tests/lingneng/events/test_rag_events.py -q`
- [ ] Expected: fail because RAG adapter does not exist.
- [ ] Implement a provider interface that can call current LingNengAI RAG service or existing vector services through env-configured endpoints.
- [ ] Keep first implementation behind configuration so the Phase 1 no-tool API remains usable.
- [ ] Run: `python -m pytest tests/lingneng/tools/test_retrieve_rag.py tests/lingneng/events/test_rag_events.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 接入灵能 RAG 工具`
- [ ] Push the active branch after the commit succeeds.

### Task 4.3: Add RAG And Skill Contract Scenarios

**Files:**
- Create: `tests/lingneng/contract/test_rag_skill_chat_stream.py`

- [ ] Write a contract test where a marketing employee request loads a skill excerpt and one RAG hit.
- [ ] Assert stream includes `agent_step`, `citation_delta`, `rag_context`, `answer_delta`, and `final`.
- [ ] Assert `final.citations` contains the citation returned by RAG.
- [ ] Run: `python -m pytest tests/lingneng/contract/test_rag_skill_chat_stream.py -q`
- [ ] Expected: pass after Tasks 4.1 and 4.2.
- [ ] Commit: `test: 增加 RAG 与技能流式合同测试`
- [ ] Push the active branch after the commit succeeds.

---

## Phase 5: Artifacts, Attachments, And Business Generation Tools

**Goal:** Move document/image/chart/web/attachment capabilities behind Hermes tool calls.

**Acceptance:** Business tools can produce Java-compatible `artifact_created`, `agent_step`, and `final.artifacts` data without exposing unsafe generic tools.

### Task 5.1: Implement Artifact Model And Store Boundary

**Files:**
- Create: `lingneng/tools/artifacts.py`
- Modify: `lingneng/schemas/chat_events.py`
- Test: `tests/lingneng/tools/test_artifact_models.py`

- [ ] Write failing tests matching LingNengAI artifact fields: `artifact_id`, `artifact_type`, `source`, `file_name`, `mime_type`, `url`, `object_key`, `format`, `target_format`, `conversion_required`, `conversion_owner`.
- [ ] Assert external Java file object keys are accepted.
- [ ] Assert secrets and local filesystem paths are not exposed in public artifact events.
- [ ] Run: `python -m pytest tests/lingneng/tools/test_artifact_models.py -q`
- [ ] Expected: fail if artifact model is incomplete.
- [ ] Implement artifact schema and store abstraction.
- [ ] Run: `python -m pytest tests/lingneng/tools/test_artifact_models.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 增加灵能生成物模型`
- [ ] Push the active branch after the commit succeeds.

### Task 5.2: Implement Document, Image, Chart, And Web Search Tool Adapters

**Files:**
- Create: `lingneng/tools/document_generation.py`
- Create: `lingneng/tools/image_generation.py`
- Create: `lingneng/tools/chart_visualization.py`
- Create: `lingneng/tools/web_search.py`
- Modify: `lingneng/tools/toolset.py`
- Test: `tests/lingneng/tools/test_generation_tools.py`

- [ ] Write failing tests for each tool's schema and success/failure JSON result.
- [ ] Assert document/image/chart success returns artifact metadata.
- [ ] Assert web search success returns summarized sources and does not emit raw provider secrets.
- [ ] Assert each tool enforces per-run and per-tool call limits from settings.
- [ ] Run: `python -m pytest tests/lingneng/tools/test_generation_tools.py -q`
- [ ] Expected: fail because tool adapters do not exist.
- [ ] Implement provider interfaces backed by environment-configured LingNengAI/Java/AIGC services.
- [ ] Implement safe failure messages for provider errors.
- [ ] Run: `python -m pytest tests/lingneng/tools/test_generation_tools.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 接入灵能生成与搜索工具`
- [ ] Push the active branch after the commit succeeds.

### Task 5.3: Implement Attachment Understanding

**Files:**
- Create: `lingneng/tools/attachments.py`
- Modify: `lingneng/runtime/hermes_adapter.py`
- Test: `tests/lingneng/tools/test_attachments.py`

- [ ] Write failing tests for allowed download host checks.
- [ ] Write failing tests for file count, total bytes, image bytes, and timeout limits.
- [ ] Write failing tests that parsed attachment context is scoped to the current request.
- [ ] Write failing tests that direct attachment text is truncated to configured max chars.
- [ ] Run: `python -m pytest tests/lingneng/tools/test_attachments.py -q`
- [ ] Expected: fail because attachment tooling does not exist.
- [ ] Implement attachment download and parsing adapter interfaces.
- [ ] Reuse LingNengAI service contracts where available instead of re-creating converters.
- [ ] Run: `python -m pytest tests/lingneng/tools/test_attachments.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 增加灵能附件理解`
- [ ] Push the active branch after the commit succeeds.

### Task 5.4: Add Artifact Stream Contract Test

**Files:**
- Create: `tests/lingneng/contract/test_artifact_chat_stream.py`

- [ ] Write a contract test where a document tool call emits `agent_step`, `artifact_created`, and `final`.
- [ ] Assert `final.artifacts` contains the same artifact id emitted earlier.
- [ ] Assert tool failure emits public `agent_step` failure and still allows a degraded final answer when recoverable.
- [ ] Run: `python -m pytest tests/lingneng/contract/test_artifact_chat_stream.py -q`
- [ ] Expected: pass after Phase 5 tool adapters.
- [ ] Commit: `test: 增加生成物 SSE 合同测试`
- [ ] Push the active branch after the commit succeeds.

---

## Phase 6: Session Quality, Compression, Cleanup, And Observability

**Goal:** Make long-lived Java conversations reliable under Hermes-managed session history.

**Acceptance:** Long conversations compress and recover, stale sessions clean up, and logs/traces can diagnose a production run.

### Task 6.1: Long Conversation Compression Tests

**Files:**
- Create: `tests/lingneng/session/test_long_conversation_compression.py`
- Modify: `lingneng/session/hermes_session.py`
- Modify: `lingneng/runtime/hermes_adapter.py`

- [ ] Write failing tests that simulate a long conversation exceeding configured compression thresholds.
- [ ] Assert Hermes compression path is used rather than Java `history`.
- [ ] Assert compressed summary is available to the next turn.
- [ ] Run: `python -m pytest tests/lingneng/session/test_long_conversation_compression.py -q`
- [ ] Expected: fail until adapter exposes compression-friendly session behavior.
- [ ] Wire LingNeng sessions into Hermes existing compression mechanisms.
- [ ] Run: `python -m pytest tests/lingneng/session/test_long_conversation_compression.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 支持灵能长会话压缩`
- [ ] Push the active branch after the commit succeeds.

### Task 6.2: Add Session And Run Cleanup

**Files:**
- Create: `lingneng/session/cleanup.py`
- Test: `tests/lingneng/session/test_cleanup.py`

- [ ] Write failing tests for active session retention `90` days, archived retention `180` days, and idempotency retention `7` days.
- [ ] Write failing tests that cleanup logs counts but not message content.
- [ ] Run: `python -m pytest tests/lingneng/session/test_cleanup.py -q`
- [ ] Expected: fail because cleanup module does not exist.
- [ ] Implement cleanup functions callable by cron, CLI, or deployment maintenance script.
- [ ] Run: `python -m pytest tests/lingneng/session/test_cleanup.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 增加灵能会话清理`
- [ ] Push the active branch after the commit succeeds.

### Task 6.3: Add Structured Logging And Trace Summary

**Files:**
- Create: `lingneng/observability/__init__.py`
- Create: `lingneng/observability/logging.py`
- Modify: `lingneng/api/routes.py`
- Modify: `lingneng/schemas/chat_events.py`
- Test: `tests/lingneng/observability/test_trace_logging.py`

- [ ] Write failing tests that log records include `request_id`, `run_id`, `tenant_id`, `user_id`, `conversation_id`, `session_key`, employee identity, tool name, final status, and future deploy metadata when available.
- [ ] Write failing tests that full Java `history` content is not logged.
- [ ] Run: `python -m pytest tests/lingneng/observability/test_trace_logging.py -q`
- [ ] Expected: fail because structured logging is not wired.
- [ ] Implement logging helpers and route instrumentation.
- [ ] Add `trace_summary` data to `final` without leaking secrets.
- [ ] Run: `python -m pytest tests/lingneng/observability/test_trace_logging.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 增加灵能运行追踪日志`
- [ ] Push the active branch after the commit succeeds.

---

## Phase 7: Future Docker Deployment And GitHub Actions

**Goal:** Match LingNengAI's server deployment posture for LingNeng-Hermes after the runtime改造 is working.

**Acceptance:** GitHub Actions or a manually triggered equivalent can build, push, deploy, health-check, and roll back dev/test environments.

### Task 7.1: Add Docker And Compose MVP

**Files:**
- Create: `deploy/lingneng/Dockerfile`
- Create: `deploy/lingneng/docker-compose.yml`
- Create: `deploy/lingneng/.env.example`
- Create: `deploy/lingneng/README.md`
- Create: `scripts/lingneng-health-check.sh`
- Test: `tests/lingneng/deploy/test_lingneng_compose.py`

- [ ] Write failing tests that parse `deploy/lingneng/docker-compose.yml` and assert:
  - service `lingneng-hermes-api` exists.
  - service has no fixed `container_name`.
  - port mapping is `${LINGNENG_API_BIND_HOST:-127.0.0.1}:${LINGNENG_API_HOST_PORT:-18083}:${LINGNENG_API_PORT:-18083}`.
  - `data/runtime` and `logs` are mounted.
  - `LINGNENG_AGENT_MODE` defaults to `fake` in `.env.example` for smoke tests.
  - no secret value is non-empty in `.env.example`.
- [ ] Run: `python -m pytest tests/lingneng/deploy/test_lingneng_compose.py -q`
- [ ] Expected: fail because deploy assets do not exist.
- [ ] Implement slim Dockerfile with `uv sync --frozen --no-dev` and command `python -m lingneng.api.server`.
- [ ] Implement compose template with configurable image, bind host, port, runtime volume, and logs volume.
- [ ] Implement README with build, configure, start, health check, and stop commands.
- [ ] Implement `scripts/lingneng-health-check.sh` to check health, ready, and a fake SSE request.
- [ ] Run: `python -m pytest tests/lingneng/deploy/test_lingneng_compose.py -q`
- [ ] Expected: pass.
- [ ] Run: `docker compose --env-file deploy/lingneng/.env.example -f deploy/lingneng/docker-compose.yml config >/tmp/lingneng-compose-config.txt`
- [ ] Expected: command exits 0.
- [ ] Commit: `feat: 增加灵能 Docker 部署骨架`
- [ ] Push the active branch after the commit succeeds.

### Task 7.2: Add Deploy Script With Rollback

**Files:**
- Create: `scripts/deploy-lingneng-local.sh`
- Modify: `deploy/lingneng/.env.example`
- Test: `tests/lingneng/deploy/test_deploy_lingneng_local.py`
- Reference: `/Users/rotas/Documents/work/hailun/LingNengAI/scripts/deploy-local-test.sh`

- [ ] Write failing tests using a fake `docker` executable that records compose commands.
- [ ] Assert `IMAGE_REF` is required.
- [ ] Assert script creates deploy dir, copies compose file, creates `.env`, and writes `.deploy-meta`.
- [ ] Assert script writes dev/test isolation values: env, API port, Redis prefix, Milvus collection, MinIO bucket, RocketMQ topics/groups, Nacos service metadata.
- [ ] Assert failed health check restores previous `.env` and previous image ref.
- [ ] Run: `python -m pytest tests/lingneng/deploy/test_deploy_lingneng_local.py -q`
- [ ] Expected: fail because deploy script behavior is missing.
- [ ] Implement deployment script with `set -euo pipefail`.
- [ ] Implement `docker compose --env-file "$env_file" -f "$compose_file" -p "$project_name"` wrapper.
- [ ] Implement rollback and post-deploy checks.
- [ ] Run: `python -m pytest tests/lingneng/deploy/test_deploy_lingneng_local.py -q`
- [ ] Expected: pass.
- [ ] Commit: `feat: 增加灵能服务器部署脚本`
- [ ] Push the active branch after the commit succeeds.

### Task 7.3: Add Docker Build Smoke Test

**Files:**
- Create: `tests/lingneng/deploy/test_dockerfile.py`

- [ ] Write tests that assert `deploy/lingneng/Dockerfile`:
  - uses a pinned or bounded base/runtime strategy consistent with repo dependency policy.
  - copies `pyproject.toml` and `uv.lock` before source for layer caching.
  - runs `uv sync --frozen`.
  - starts `python -m lingneng.api.server`.
  - does not bake known secret env names with values.
- [ ] Run: `python -m pytest tests/lingneng/deploy/test_dockerfile.py -q`
- [ ] Expected: pass once Dockerfile is complete.
- [ ] Run: `docker build -f deploy/lingneng/Dockerfile -t lingneng-hermes:local-smoke .`
- [ ] Expected: image builds successfully.
- [ ] Commit: `test: 增加灵能镜像构建校验`
- [ ] Push the active branch after the commit succeeds.

### Task 7.4: Add GitHub Actions Workflow Plan

**Files:**
- Create: `.github/workflows/lingneng-runtime-ci.yml`
- Create: `.github/workflows/lingneng-runtime-image.yml`
- Create: `deploy/lingneng/github-actions/README.md`
- Test: `tests/lingneng/deploy/test_github_actions_assets.py`

- [ ] Write tests that assert GitHub Actions workflows do not include literal secrets.
- [ ] Assert CI workflow runs on pull requests and pushes to `dev` and `test`.
- [ ] Assert image workflow can be manually triggered with `workflow_dispatch`.
- [ ] Assert deploy credentials are referenced through GitHub secrets or protected environments.
- [ ] Assert optional dev/test deployment jobs are environment-gated, not automatic uncontrolled SSH.
- [ ] Run: `python -m pytest tests/lingneng/deploy/test_github_actions_assets.py -q`
- [ ] Expected: fail because GitHub Actions assets do not exist.
- [ ] Add GitHub Actions workflows and runbook.
- [ ] Run: `python -m pytest tests/lingneng/deploy/test_github_actions_assets.py -q`
- [ ] Expected: pass.
- [ ] Commit: `ci: 增加灵能 Hermes GitHub Actions`
- [ ] Push the active branch after the commit succeeds.

### Task 7.5: Server Smoke Run

**Files:**
- Modify: `deploy/lingneng/README.md`

- [ ] Preflight intended ports with `lsof -nP -iTCP:18083 -sTCP:LISTEN` and `lsof -nP -iTCP:18084 -sTCP:LISTEN`.
- [ ] If occupied by unrelated services, set alternate values in a local `.env` and record them in deployment notes.
- [ ] Run: `docker compose --env-file deploy/lingneng/.env.example -f deploy/lingneng/docker-compose.yml -p lingneng-hermes-smoke up -d --build`
- [ ] Run: `scripts/lingneng-health-check.sh http://127.0.0.1:18083`
- [ ] Expected: health, ready, and fake SSE smoke pass.
- [ ] Run: `docker compose --env-file deploy/lingneng/.env.example -f deploy/lingneng/docker-compose.yml -p lingneng-hermes-smoke down`
- [ ] Commit deployment runbook updates if the smoke run reveals command corrections: `docs: 更新灵能部署验证说明`
- [ ] Push the active branch after the commit succeeds.

---

## Phase 8: Java Integration, Regression Comparison, And Pruning Decision

**Goal:** Prove Java can consume LingNeng-Hermes and decide what Hermes features can be disabled after business validation.

**Acceptance:** Existing Java integration works without code changes, output quality is compared against LingNengAI, and pruning decisions are documented.

### Task 8.1: Java-Compatible Integration Script

**Files:**
- Create: `scripts/lingneng-chat-smoke.py`
- Test: `tests/lingneng/contract/test_chat_smoke_script.py`

- [ ] Write a test that runs the script against a TestClient-backed URL or local fake server.
- [ ] Assert script posts a Java-compatible JSON request.
- [ ] Assert script parses SSE frames and exits 0 only after `final`.
- [ ] Run: `python -m pytest tests/lingneng/contract/test_chat_smoke_script.py -q`
- [ ] Expected: fail because script does not exist.
- [ ] Implement smoke script with configurable URL, internal key, request id, tenant id, user id, conversation id, employee type, and query.
- [ ] Run: `python -m pytest tests/lingneng/contract/test_chat_smoke_script.py -q`
- [ ] Expected: pass.
- [ ] Commit: `test: 增加灵能 Java 调用冒烟脚本`
- [ ] Push the active branch after the commit succeeds.

### Task 8.2: Compare LingNengAI And LingNeng-Hermes Outputs

**Files:**
- Create: `docs/lingneng-migration/reports/2026-06-06-output-comparison-template.md`
- Create: `tests/lingneng/evals/test_comparison_fixture.py`

- [ ] Define comparison cases for boss assistant, operation specialist, marketing planner, marketing content creator, member operator, and product combo advisor.
- [ ] Include one no-tool case, one RAG case, one artifact case, one attachment case, and one long conversation case.
- [ ] Add a fixture format for request, LingNengAI output, LingNeng-Hermes output, event order, tool calls, citations, artifacts, and evaluator notes.
- [ ] Run: `python -m pytest tests/lingneng/evals/test_comparison_fixture.py -q`
- [ ] Expected: pass after fixture schema exists.
- [ ] Commit: `docs: 增加灵能输出对比模板`
- [ ] Push the active branch after the commit succeeds.

### Task 8.3: Document Feature Pruning Decision

**Files:**
- Create: `docs/lingneng-migration/specs/2026-06-06-hermes-feature-pruning-decision.md`

- [ ] List Hermes channels/features kept for LingNeng.
- [ ] List Hermes channels/features disabled by default for LingNeng API.
- [ ] List Hermes channels/features eligible for removal after production soak.
- [ ] Require evidence links to passing Java integration, Docker deployment, contract tests, and output comparison before any removal.
- [ ] Run: `python -m pytest tests/lingneng -q`
- [ ] Expected: all LingNeng tests pass.
- [ ] Commit: `docs: 明确 Hermes 功能裁剪决策`
- [ ] Push the active branch after the commit succeeds.

---

## Phase-Level Verification Matrix

| Phase | Required Verification |
| --- | --- |
| Phase 0 | Reference docs written; LingNengAI contract reference tests pass where runnable; GitHub workflow baseline recorded. |
| Phase 1 | `python -m pytest tests/lingneng/config tests/lingneng/schemas tests/lingneng/session tests/lingneng/api -q`. |
| Phase 2 | `python -m pytest tests/lingneng/runtime tests/lingneng/session tests/lingneng/contract/test_chat_stream_minimal.py -q`. |
| Phase 3 | `python -m pytest tests/lingneng/tools/test_toolset_policy.py tests/lingneng/events/test_agent_step_bridge.py -q`. |
| Phase 4 | `python -m pytest tests/lingneng/skills tests/lingneng/tools/test_retrieve_rag.py tests/lingneng/events/test_rag_events.py tests/lingneng/contract/test_rag_skill_chat_stream.py -q`. |
| Phase 5 | `python -m pytest tests/lingneng/tools/test_artifact_models.py tests/lingneng/tools/test_generation_tools.py tests/lingneng/tools/test_attachments.py tests/lingneng/contract/test_artifact_chat_stream.py -q`. |
| Phase 6 | `python -m pytest tests/lingneng/session/test_long_conversation_compression.py tests/lingneng/session/test_cleanup.py tests/lingneng/observability/test_trace_logging.py -q`. |
| Phase 7 | `python -m pytest tests/lingneng/deploy -q`; `docker build -f deploy/lingneng/Dockerfile -t lingneng-hermes:local-smoke .`; `scripts/lingneng-health-check.sh http://127.0.0.1:18083`. |
| Phase 8 | `python -m pytest tests/lingneng -q`; Java smoke script exits 0 against local or deployed dev/test environment. |

## Execution Notes

- Before starting any local service, identify intended ports and run `lsof -nP -iTCP:<port> -sTCP:LISTEN`.
- Do not kill unrelated processes to free a port.
- Use `scripts/run_tests.sh` for broader regression checks before merging Phase branches.
- Before executing any phase, write and review that phase's dedicated spec, then write and review that phase's dedicated plan; do not implement directly from this master roadmap.
- Execute approved phase plans with `superpowers:subagent-driven-development`; do not use inline execution for phase implementation unless the user explicitly changes this rule.
- Keep commits Chinese with standard prefixes, for example `feat: 增加灵能 Java 兼容 API`.
- Never push a task commit before that task's verification command passes.
- If a task requires a core Hermes edit, prove the extension point cannot support it first, keep the core diff minimal, and add a regression test around the core behavior.
