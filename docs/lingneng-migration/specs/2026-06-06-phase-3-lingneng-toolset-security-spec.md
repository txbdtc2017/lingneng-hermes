# Phase 3 Dedicated LingNeng Toolset And Security Boundary Spec

## Goal

Phase 3 introduces the first LingNeng business tool surface on top of Hermes
without migrating the real business implementations yet.

The phase proves that the Java-compatible LingNeng API can run Hermes with a
dedicated `lingneng` toolset, expose only approved LingNeng tool schemas, keep
Hermes high-risk default tools out of Java requests, and translate Hermes tool
progress callbacks into public LingNeng `agent_step` SSE events.

## Scope

Phase 3 is limited to these runtime modules and tests:

- Modify `toolsets.py`
- Modify `lingneng/schemas/chat_events.py`
- Modify `lingneng/events/bridge.py`
- Modify `lingneng/runtime/hermes_adapter.py`
- Create `lingneng/tools/__init__.py`
- Create `lingneng/tools/stubs.py`
- Create `lingneng/tools/toolset.py`
- Create `tests/lingneng/tools/test_toolset_policy.py`
- Create `tests/lingneng/events/test_agent_step_bridge.py`
- Modify focused Phase 2 Hermes adapter tests only when the Phase 3 enabled
  toolset changes their expected adapter construction arguments.

Expected implementation should stay inside the `lingneng/` package except for
one minimal `toolsets.py` addition that makes `lingneng` a first-class Hermes
toolset name.

## Non-Goals

- Do not modify Java code.
- Do not change the Java request schema, endpoint path, auth header, heartbeat
  frame, health endpoint, ready endpoint, or successful SSE media type.
- Do not add Dockerfiles, Compose files, deployment scripts, deployment
  runbooks, or GitHub Actions workflows.
- Do not implement real RAG, skill loading, artifact generation, attachment
  understanding, web search, document generation, image generation, or chart
  generation behavior.
- Do not call LingNengAI business services, vector databases, MinIO, Redis,
  Milvus, Nacos, search services, or model providers in automated tests.
- Do not expose Hermes terminal, arbitrary filesystem, browser automation, code
  execution, delegation, cross-channel messaging, dashboard, gateway, desktop,
  kanban worker lifecycle tools, or other personal-agent surfaces through the
  Java API.
- Do not remove Hermes CLI, TUI, Gateway, desktop, Cron, Kanban, plugin, or
  default tool behavior for non-LingNeng entrypoints.
- Do not add a second tool execution framework. Use Hermes registry/toolset and
  callback mechanisms.

## Required Inputs

Reload these durable files before writing the Phase 3 plan or implementation:

1. `LINGNENG_MIGRATION_CONTEXT.md`
2. `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
3. `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
4. `docs/lingneng-migration/specs/2026-06-06-lingneng-java-contract-baseline.md`
5. `docs/lingneng-migration/specs/2026-06-06-lingneng-github-workflow-baseline.md`
6. `docs/lingneng-migration/specs/2026-06-06-phase-1-java-compatible-api-mvp-spec.md`
7. `docs/lingneng-migration/plans/2026-06-06-phase-1-java-compatible-api-mvp-plan.md`
8. `docs/lingneng-migration/specs/2026-06-06-phase-2-hermes-agent-integration-spec.md`
9. `docs/lingneng-migration/plans/2026-06-06-phase-2-hermes-agent-integration-plan.md`

Use these Hermes files as implementation references:

- `toolsets.py`
- `tools/registry.py`
- `model_tools.py`
- `agent/tool_executor.py`
- `run_agent.py`

Use `/Users/rotas/Documents/work/hailun/LingNengAI` only as a read-only
contract reference. Do not implement there.

## Accepted Decisions

- Phase 3 changes the real Hermes adapter from explicit no-tool mode to the
  dedicated LingNeng business toolset: `enabled_toolsets=["lingneng"]`.
- The adapter must keep `disabled_toolsets=["kanban"]`.
- The adapter must keep `platform="lingneng"`, `session_id` equal to the
  resolved LingNeng session key, `quiet_mode=True`, `skip_context_files=True`,
  and `skip_memory=True`.
- The `lingneng` toolset contains only approved LingNeng tool names.
- Phase 3 tools are explicit non-production stubs. They return JSON with
  `success=false`, `code="NOT_CONFIGURED"`, a stable `tool_name`, and an
  agent-safe `message`.
- Stub responses must not include Python tracebacks, secret values, raw request
  payloads, local filesystem paths outside the configured runtime directory, or
  Java `history` content.
- Stub tools may be callable by Hermes during Phase 3, but they must clearly
  report that the business backend is not configured yet. Real behavior lands
  in later phases.
- `toolsets.py` may add a static `lingneng` entry. It must not include Hermes
  default toolsets or compose from broader Hermes toolsets.
- `lingneng/tools/toolset.py` owns registration side effects for LingNeng stub
  tools through `tools.registry.registry.register(...)`.
- Importing `lingneng.tools.toolset` registers the LingNeng stub tools.
- `HermesAgentRunAdapter` may import the LingNeng toolset module as part of
  constructing the real LingNeng runtime path so tests and local usage do not
  depend on unrelated Hermes startup side effects.
- Fake mode remains deterministic and must not need to import `run_agent`,
  `hermes_state`, or LingNeng tools.
- `AgentStepEvent` is added to the formal LingNeng event model surface for
  public tool progress.
- `agent_step` events are emitted from Hermes tool callbacks, not by parsing
  provider text.
- The public `agent_step` event must not expose raw tool arguments by default.
  It may expose sanitized titles, short text, summary text, and refs.
- Failed tool results are mapped to public failure summaries. Internal
  exception details are not emitted to Java.

## User Confirmations Before Phase 3 Plan

No additional user confirmation is required before writing the Phase 3 plan.

These assumptions are locked for the plan unless the user changes them:

- Phase 3 registers stub tools only.
- Phase 3 enables the dedicated `lingneng` toolset for Hermes-mode Java API
  calls.
- Business implementations for RAG, skills, artifacts, web search, attachments,
  and generation tools remain Phase 4 or later.
- Docker/server deployment remains deferred.
- Tests must not call real model providers or external LingNeng business
  services.

If any of these assumptions must change, update this spec before writing or
executing the Phase 3 plan.

## Data Contracts

### Approved LingNeng Tool Names

The `lingneng` toolset must expose exactly these Phase 3 business tool names:

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

Each tool schema must be a valid OpenAI function schema with:

- `name`
- `description`
- `parameters.type == "object"`
- `parameters.properties`
- `parameters.additionalProperties == false`

The schemas should be intentionally small and stable. Phase 3 only needs enough
arguments for the model to express intent safely:

- `retrieve_rag`: `query`, optional `top_k`, optional `filters`
- `list_skills`: optional `employee_type`
- `search_skills`: `query`, optional `employee_type`
- `read_skill`: `skill_id`
- `read_skill_resource`: `skill_id`, `resource_id`
- `document_generation`: `instruction`, optional `format`
- `image_generation`: `prompt`, optional `style`
- `chart_visualization`: `instruction`, optional `data`
- `web_search`: `query`, optional `limit`
- `read_workspace`: `path`, optional `purpose`
- `write_workspace`: `path`, `content`, optional `purpose`

These argument names are a Phase 3 contract for stubs and tests. Later phases
may add optional fields but should avoid renaming these fields.

### Stub Result

Every Phase 3 stub handler must return a JSON string whose decoded object
contains:

- `success`: `false`
- `code`: `"NOT_CONFIGURED"`
- `tool_name`: the invoked LingNeng tool name
- `message`: a short agent-safe explanation that the LingNeng business backend
  is not configured in this phase

The decoded object may include:

- `phase`: `"phase_3_stub"`

The decoded object must not include:

- `args`
- `request`
- `payload`
- `history`
- `traceback`
- `exception`
- `api_key`
- `token`
- `secret`

### Toolset Resolution Contract

`validate_toolset("lingneng")` must return `True`.

`resolve_toolset("lingneng")` must return the approved LingNeng tool names and
must not include high-risk Hermes tool names.

`get_tool_definitions(enabled_toolsets=["lingneng"], disabled_toolsets=["kanban"],
quiet_mode=True)` must return only LingNeng tool schemas that pass registry
availability checks.

The LingNeng toolset must not expose any of these high-risk names:

- `terminal`
- `process`
- `read_file`
- `write_file`
- `patch`
- `search_files`
- `browser_navigate`
- `browser_snapshot`
- `browser_click`
- `browser_type`
- `browser_scroll`
- `browser_back`
- `browser_press`
- `browser_get_images`
- `browser_vision`
- `browser_console`
- `browser_cdp`
- `browser_dialog`
- `execute_code`
- `delegate_task`
- `send_message`
- `kanban_show`
- `kanban_list`
- `kanban_complete`
- `kanban_block`
- `kanban_heartbeat`
- `kanban_comment`
- `kanban_create`
- `kanban_link`
- `kanban_unblock`

The LingNeng business `web_search`, `read_workspace`, and `write_workspace`
names are allowed because they are LingNeng-controlled stubs in this phase.
They must not dispatch to Hermes default web/file tools until later phases
explicitly define safe business adapters.

### Agent Adapter Tool Configuration

For Hermes mode in Phase 3, `HermesAgentRunAdapter` must construct `AIAgent`
with:

- `enabled_toolsets=["lingneng"]`
- `disabled_toolsets=["kanban"]`
- `platform="lingneng"`
- `session_id=resolved_session.session_key`
- `session_db` equal to the LingNeng-owned SessionDB
- `quiet_mode=True`
- `skip_context_files=True`
- `skip_memory=True`

It must continue to:

- Clear inherited `HERMES_KANBAN_*` worker environment variables with a lock
  covering the full construction/run context.
- Install the LingNeng-only activity tracker to avoid kanban heartbeat side
  effects.
- Keep Java `history` out of `conversation_history`.
- Emit `run_started`, ordered `answer_delta`, `final`, and `error` as defined
  in Phase 2.

### `agent_step` Event Contract

Add `AgentStepEvent` to `lingneng/schemas/chat_events.py`.

The public payload fields are:

- `sequence`: integer starting at `1` within a LingNeng run's tool-progress
  event stream
- `step_id`: stable string id for this public step
- `phase`: one of `"tool"`
- `status`: one of `"started"`, `"succeeded"`, `"skipped"`, `"failed"`
- `title`: short display title
- `short_text`: one-line public progress text
- `summary`: optional longer public summary
- `refs`: list of reference objects, defaulting to an empty list

`AgentStepEvent` must forbid unknown fields.

Tool names may be used in `title` and `short_text` after being sanitized for
public display. Raw arguments and raw tool results must not be emitted as refs.

### Tool Progress Mapping

Phase 3 maps Hermes callbacks to public `agent_step` events:

- `tool.started` progress callback becomes `status="started"`.
- `tool.completed` with `is_error=false` becomes `status="succeeded"`.
- `tool.completed` with `is_error=true` becomes `status="failed"`.
- A skipped or blocked tool result, when represented by helper input or future
  callback data, becomes `status="skipped"`.

The bridge must expose pure helper functions so tests can exercise mapping
without running a real provider:

- `agent_step_started(sequence, tool_name, preview=None)`
- `agent_step_completed(sequence, tool_name, duration=None, is_error=False, result=None)`
- `agent_step_skipped(sequence, tool_name, reason=None)`

`HermesAgentRunAdapter.stream()` must bridge these events from synchronous
Hermes callbacks into the same async event queue used for answer deltas while
preserving per-callback order.

Tool progress events and answer delta events share a single output stream but
do not share sequence counters. `AnswerDeltaEvent.sequence` remains the answer
delta counter. `AgentStepEvent.sequence` is the tool-progress counter.

## Module Boundaries

### `lingneng/tools/stubs.py`

Owns Phase 3 stub handler implementations and schema-building helpers. It may
import `json` and lightweight typing utilities. It must not import FastAPI,
`run_agent.AIAgent`, `model_tools`, `hermes_state`, network clients, or
LingNengAI reference project modules.

### `lingneng/tools/toolset.py`

Owns LingNeng tool registration into the Hermes registry. It may import
`tools.registry.registry` and `lingneng.tools.stubs`. It must not import
FastAPI route handlers or runtime adapters.

### `toolsets.py`

Owns the static `lingneng` toolset entry. Phase 3 may add one entry with direct
LingNeng tool names and no `includes`.

### `lingneng/events/bridge.py`

Owns pure conversion helpers from LingNeng runtime signals and Hermes tool
callbacks to LingNeng event models.

### `lingneng/runtime/hermes_adapter.py`

Owns wiring of `AIAgent` callbacks to the async LingNeng stream. It may import
`lingneng.tools.toolset` for registration before constructing `AIAgent`.

### Hermes Core

`run_agent.py`, `agent/tool_executor.py`, `model_tools.py`, and
`tools/registry.py` must remain unchanged unless a failing test proves the
existing callback/registry surfaces cannot support Phase 3. Any such change
must be generic, minimal, and not LingNeng-hardcoded.

## HTTP And SSE Behavior

The route remains:

```text
POST /internal/agent/chat/stream
Response: text/event-stream
```

Successful no-tool answers keep the Phase 2 minimum:

1. `run_started`
2. one or more `answer_delta`
3. `final`

When Hermes emits tool progress callbacks, `agent_step` events may appear after
`run_started` and before terminal `final` or `error`.

The route-level idempotency replay behavior remains Phase 2 behavior:

- `running`: one terminal `error` with `REQUEST_ALREADY_RUNNING`
- `succeeded`: `run_started`, one `answer_delta`, `final`
- `failed`: one terminal `error`

Phase 3 does not persist or replay fine-grained historical `agent_step` events
for completed requests. That requires storing progress history and remains out
of scope.

## Test Strategy

Tests must not call real model providers or external business services.

Required focused tests:

- `tests/lingneng/tools/test_toolset_policy.py`
  - `lingneng` toolset validates.
  - `resolve_toolset("lingneng")` returns approved LingNeng tool names.
  - `get_tool_definitions(enabled_toolsets=["lingneng"],
    disabled_toolsets=["kanban"], quiet_mode=True)` exposes only LingNeng
    schemas.
  - High-risk Hermes tool names are absent.
  - Every Phase 3 stub handler returns the stable `NOT_CONFIGURED` JSON shape.
  - Importing `lingneng.tools.toolset` is enough to register the stubs.
- `tests/lingneng/events/test_agent_step_bridge.py`
  - Started, succeeded, skipped, and failed tool progress map to `agent_step`.
  - Public fields include `sequence`, `step_id`, `phase`, `status`, `title`,
    `short_text`, `summary`, and `refs`.
  - Failed tool progress does not leak internal exception text.
- Existing adapter tests update the expected Hermes `AIAgent` arguments from
  `enabled_toolsets=[]` to `enabled_toolsets=["lingneng"]`.

Required phase verification:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_toolset_policy.py tests/lingneng/events/test_agent_step_bridge.py -q
uv run --extra dev python -m pytest tests/lingneng/config tests/lingneng/schemas tests/lingneng/session tests/lingneng/api tests/lingneng/runtime tests/lingneng/tools tests/lingneng/events tests/lingneng/contract -q
/Users/rotas/Documents/work/hailun/LingNengAI/.venv/bin/python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py -q
uv run --extra dev python -m ruff check lingneng tests/lingneng
git diff --check
```

The incomplete-marker scan must also be run against Phase 3 code, tests, and
docs before commits.

## Acceptance Criteria

- Dedicated Phase 3 spec and plan exist in `docs/lingneng-migration/`.
- The master roadmap order is preserved: phase spec, phase plan,
  subagent-driven execution.
- `lingneng` is a valid Hermes toolset.
- The LingNeng API Hermes adapter uses `enabled_toolsets=["lingneng"]`.
- All approved Phase 3 LingNeng tool names are registered and resolvable.
- LingNeng business tools return explicit `NOT_CONFIGURED` stub results.
- High-risk Hermes tools are absent from the LingNeng tool definitions used by
  the Java API.
- `agent_step` is a formal event model and can be emitted by the adapter from
  Hermes tool progress callbacks.
- Public `agent_step` errors do not leak raw exception text or secrets.
- Phase 1 and Phase 2 request/session/idempotency/SSE contracts continue to
  pass.
- No deployment, RAG, skills, artifact, attachment, or real business backend
  implementation is added in Phase 3.
- Phase 3 changes are committed and pushed to `dev` only after verification
  passes.
