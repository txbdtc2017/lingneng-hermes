# LingNeng Hermes Migration Context

This repository is the Hermes fork for the LingNeng AI runtime migration.
It is not a generic upstream Hermes-only checkout anymore.

## Required Reading For Codex

Before doing LingNeng-related work in this repository, read these files in order:

1. `AGENTS.md`
2. `LINGNENG_MIGRATION_CONTEXT.md`
3. `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
4. `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`

## Context Compaction Reload Rule

After every context compaction, resume, or handoff, reload at minimum:

1. `LINGNENG_MIGRATION_CONTEXT.md`
2. `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
3. `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`

Do this before writing a phase spec, writing a phase plan, implementing runtime
code, running verification, committing, or pushing. The total design spec and
master implementation plan are the durable source of truth after compaction.

Use `/Users/rotas/Documents/work/hailun/LingNengAI` only as the reference
implementation for current business contracts and behavior. Do not implement the
new runtime there.

## Current Decision

Use this Hermes fork as the new LingNeng Agent runtime base.

The migration direction is:

```text
LingNeng business capabilities -> Hermes runtime
```

Do not migrate only small pieces of Hermes core into the old LingNengAI service.
The value of Hermes is the complete runtime: `AIAgent`, tool orchestration,
SessionDB, streaming callbacks, toolsets, plugins, config, profiles, and tests.

## First-Stage Scope

Keep Hermes channels, CLI, TUI, Gateway, plugins, Cron, Kanban, desktop code, and
other upstream features in place for now.

First make LingNeng business run on top of Hermes. Only after the Java-compatible
business flow is working and verified should unused Hermes features be disabled
or removed.

## External Project Paths

- Target runtime repository:
  `/Users/rotas/Documents/work/hailun/demos/lingneng-hermes`
- Current LingNengAI reference implementation:
  `/Users/rotas/Documents/work/hailun/LingNengAI`
- Migration documents in this Hermes repository:
  `docs/lingneng-migration/`
- Approved design spec:
  `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- Master implementation plan:
  `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`

## Java Compatibility Constraints

Java code cannot be modified for this migration phase.

Hermes must expose a Java-compatible API:

```text
POST /internal/agent/chat/stream
Response: text/event-stream
```

The request contract should follow the current LingNengAI `ChatRequest` and
`agent-java-interface-contract-p1.md`. Important fields include:

- `request_id`
- `tenant_id`
- `user_id`
- `session_id`
- `conversation_id`
- `query`
- `employee`
- `system_prompt`
- `skill`
- `history`
- `attachments`
- `options`
- `stream_options`

Do not require Java to send a new agent session id. Do not require Java to call a
new clear/delete session endpoint.

## Session Decision

Python owns Agent session and conversation history.

Use Java `conversation_id` as the business conversation identifier. Build the
internal Hermes session key as:

```text
tenant_id:user_id:employee_id:conversation_id
```

If `employee_id` is missing, use:

```text
tenant_id:user_id:employee_type:conversation_id
```

If `conversation_id` is missing, fall back to `session_id` only for compatibility
and log the degradation:

```text
tenant_id:user_id:employee_id:session_id
```

Java `history` must not be used as Hermes Agent context. During migration, it may
be counted or traced for diagnostics, but it must not be merged into SessionDB.

Use `request_id` as the idempotency key. A repeated `request_id` in the same
session must not append the user message twice or start a duplicate Agent run.

## SSE Contract

Java should be able to keep consuming the same LingNeng P1 SSE event names:

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

The SSE `event:` line carries the event type. The JSON `data` does not need to
include an `event` field. Heartbeats should be SSE comment frames such as
`: ping`.

Map Hermes runtime signals to LingNeng SSE:

| Hermes signal | LingNeng SSE |
| --- | --- |
| Agent run starts | `run_started` |
| Text stream delta | `answer_delta` |
| Tool progress | `agent_step` |
| RAG context and citations | `rag_context` / `citation_delta` |
| Generated files/images/charts | `artifact_created` |
| Final response | `final` |
| Runtime or tool error | `error` |

## Target Module Shape

Prefer adding a `lingneng/` namespace instead of hardcoding LingNeng logic into
Hermes core files.

Suggested boundaries:

- `lingneng/api/`: Java-compatible HTTP/SSE facade.
- `lingneng/schemas/`: request, employee, attachment, and SSE schemas.
- `lingneng/session/`: session key resolver, idempotency, SessionDB adapter.
- `lingneng/events/`: Hermes callback to LingNeng SSE bridge.
- `lingneng/tools/`: business tool registration and execution.
- `lingneng/skills/`: digital employee skill loading and progressive disclosure.
- `lingneng/config/`: internal auth and business service settings.

Keep edits to `run_agent.py`, `model_tools.py`, `toolsets.py`, and
`gateway/platforms/api_server.py` minimal. Prefer existing Hermes extension
points, callbacks, registries, or mounted API routes.

## Tool Exposure Rules

The LingNeng Java API should use a dedicated LingNeng toolset.

Expected business tools include:

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
- request attachment parsing and understanding tools

Do not expose high-risk Hermes default tools to the Java business API by default,
including terminal, arbitrary local file access, browser automation, code
execution, cross-channel messaging, or unrelated platform tools.

## Documentation And Planning Rules

For this migration, durable specs and plans belong in this Hermes repository so
they travel with the runtime code:

```text
docs/lingneng-migration/specs/
docs/lingneng-migration/plans/
```

The old LingNengAI docs repository remains useful reference material, but it is
not the canonical place for new LingNeng-Hermes migration specs or plans.

The current approved spec is copied into this repository:

```text
docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md
```

Next expected step: write the implementation plan for Phase 1 in the docs
directory above before changing runtime code.

## Implementation Priorities

Plan the first implementation phase around these slices:

1. LingNeng API facade and request schemas.
2. Session key resolver and request idempotency store.
3. Hermes `AIAgent` adapter for Java stream requests.
4. SSE event bridge for `run_started`, `answer_delta`, `final`, and `error`.
5. Dedicated LingNeng toolset skeleton with high-risk tools excluded.
6. Contract tests against the LingNeng Java SSE expectations.

Only after Phase 1 works should Codex plan RAG, skill loader, artifact tools,
attachment understanding, and later Hermes feature pruning.
