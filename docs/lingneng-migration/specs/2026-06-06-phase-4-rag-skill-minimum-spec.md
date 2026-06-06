# Phase 4 RAG And Skill Loader Minimum Spec

## Status

Drafted for implementation on `dev` after Phase 3 completion.

Required durable context reloaded before writing this spec:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`

Reference implementation inspected for this phase:

- `/Users/rotas/Documents/work/hailun/LingNengAI/app/skills`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/skills`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/rag/citation.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_events.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/chat/nodes/business_agent.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/chat/nodes/finalize.py`

## Goal

Move the first LingNeng business-intelligence capabilities onto the Hermes
runtime without copying the old LangGraph runtime:

1. Load controlled employee base skill fragments and an optional explicitly
   selected local skill package into the Hermes system prompt.
2. Replace the Phase 3 `retrieve_rag` stub with a bounded LingNeng RAG adapter.
3. Emit Java-compatible `citation_delta`, `rag_context`, and `final.citations`
   data from RAG tool results.

## Scope

### Employee Skill Loader

Phase 4 adds `lingneng/skills/` models and a loader for OpenSkill-style
packages stored under configured roots. A package is a directory containing
`SKILL.md` with YAML front matter and a Markdown body.

The loader must support:

- Loading employee base skill by `request.employee.employee_type`.
- Mapping known employee types to base package names:
  - `boss_assistant` -> `employee-boss-assistant`
  - `operation_specialist` -> `employee-operation-specialist`
  - `product_combo_advisor` -> `employee-product-combo-advisor`
  - `marketing_planner` -> `employee-marketing-planner`
  - `marketing_content_creator` -> `employee-marketing-content-creator`
  - `member_operator` -> `employee-member-operator`
- Selecting one explicit skill only when `request.skill.skill_id` matches a
  configured local package name exactly.
- Skipping selected skill injection when `skill_id` is unknown. The runtime must
  never treat Java `skill.inline` as trusted prompt content.
- Exposing large package bodies as bounded prompt excerpts, not full unbounded
  content.
- Exposing resource metadata only in prompt fragments. Resource file contents
  are not injected in Phase 4.
- Enforcing `metadata.lingneng.script_policy == "metadata_only"` for all loaded
  packages. Any looser or unknown script policy is rejected for this runtime.

The loader should follow the old LingNengAI package shape but remain a new
Hermes-side implementation. It may reuse the same concepts and field names; it
must not import `app.domain.skills` from the old repository at runtime.

### RAG Tool Adapter

Phase 4 replaces only the `retrieve_rag` tool handler. The remaining LingNeng
business tools stay Phase 3 stubs:

- `list_skills`
- `search_skills`
- `read_skill`
- `read_skill_resource`
- `document_generation`
- `image_generation`
- `chart_visualization`
- `read_workspace`
- `write_workspace`

The RAG adapter must:

- Build the RAG request from tool arguments plus current Java request context.
- Include `query`, `tenant_id`, `user_id`, `employee_type`, `conversation_id`,
  `session_key`, `request_id`, `top_k`, and `filters` in the normalized request.
- Clamp `top_k` to configured bounds.
- Return a stable JSON result with no raw provider exception, secret, traceback,
  or input echo.
- Support no-live-dependency tests through provider injection.
- Support a future HTTP provider through env-configured endpoint and API key,
  without making live network calls in the test suite.

### RAG And Citation Events

Phase 4 adds the formal payload models for:

- `Citation`
- `CitationDeltaEvent`
- `RagContextEvent`

These models must match the current Java-compatible LingNeng P1 fields:

```text
Citation:
  document_id: str
  source_file_id: str
  source_file_name: str
  page_no: int | null
  section_title: str | null
  chunk_id: str
  score: float >= 0

RagContextEvent:
  context: str
  citations: list[Citation]
  status: "hit" | "empty" | "failed"
  metadata: dict
```

The SSE `event:` line carries the event name. Event JSON still must not include
an `event` field.

RAG event emission is derived from `retrieve_rag` tool completion results:

- If `stream_options.include_citations` is true, each valid citation emits one
  `citation_delta`.
- If `stream_options.include_citations` is false, no `citation_delta` is emitted
  and `final.citations` is empty.
- If `stream_options.include_rag_context` is true, the bridge emits
  `rag_context` for `hit`, `empty`, and sanitized `failed` RAG results.
- If `stream_options.include_rag_context` is false, no `rag_context` is emitted.
- `rag_context.status == "empty"` is emitted for a successful RAG call with no
  citations and no context, when `include_rag_context` is true.
- `rag_context.status == "failed"` may be emitted only with a public sanitized
  context/message and no provider internals.
- Live stream order for a successful RAG call is:
  `agent_step` completion, then RAG-specific events, then later answer/final
  events.

### Final Citations And Idempotent Replay

The Hermes adapter must accumulate citations from completed `retrieve_rag` calls
and pass them into `FinalEvent` when `stream_options.include_citations` is true.
Duplicate citations are deduplicated by `chunk_id` while preserving first-seen
order.

`LingNengRunStore` must persist final citations for completed runs. A repeated
completed `request_id` should replay:

```text
run_started -> answer_delta -> final
```

Replay does not need to replay historical `agent_step`, `citation_delta`, or
`rag_context` events in Phase 4, but replayed `final.citations` must equal the
stored live final citations.

## Non-Goals

Phase 4 does not:

- Implement Docker, compose, deployment scripts, rollback, or GitHub Actions.
- Modify Java code or require Java request changes.
- Copy the old LingNengAI LangGraph runtime.
- Trust or inject `request.skill.inline`.
- Make `list_skills`, `search_skills`, `read_skill`, or
  `read_skill_resource` real public tools.
- Implement document/image/chart generation, web search, workspace persistence,
  attachment understanding, or artifact storage.
- Add dynamic employee routing.
- Expose Hermes terminal, filesystem, browser, code execution, delegation,
  cross-channel messaging, Kanban, or unrelated default tools.
- Require live Milvus, Redis, object storage, Nacos, or external RAG services in
  tests.

## Accepted Decisions

1. `LINGNENG_SKILL_ROOTS` is the only way to enable real local skill packages in
   Phase 4. The runtime must not hardcode the old sibling checkout path as a
   production default.
2. The old path `/Users/rotas/Documents/work/hailun/LingNengAI/app/skills` may
   be used manually in local/dev env config for migration comparison, but it is
   not a baked runtime dependency.
3. Missing skill roots, missing employee base package, or unknown
   `skill.skill_id` degrade to prompt construction with Java `system_prompt`
   only. They must not fail the chat request.
4. Skill package validation errors are recorded as public degradation metadata
   for tests/logging, but the Phase 4 stream does not add new degradation SSE
   event types.
5. RAG is a normal Hermes tool, not pre-retrieval injected context. The model
   decides to call `retrieve_rag` based on tool schema and skill/system prompt
   guidance.
6. Request-scoped RAG context uses Python `contextvars`. Hermes tool worker
   threads already propagate contextvars via `tools.thread_context`.
7. Provider-not-configured is a tool failure result with code
   `NOT_CONFIGURED`. It should remain safe and should not break the no-tool fake
   API path.
8. `include_citations` controls both `citation_delta` and `final.citations`, as
   in the current LingNengAI finalize behavior.
9. `include_rag_context` controls `rag_context` only. It does not suppress
   internal citation accumulation when `include_citations` is true.

## Configuration Contract

Add the following settings to `LingNengSettings`:

```text
LINGNENG_SKILL_ROOTS
  Type: list[Path]
  Default: []
  Parse: JSON list, comma-separated string, or newline-separated string.

LINGNENG_SKILL_EXCERPT_MAX_CHARS
  Type: int
  Default: 4000
  Minimum: 500

LINGNENG_SKILL_PROMPT_MAX_CHARS
  Type: int
  Default: 12000
  Minimum: 1000

LINGNENG_RAG_ENDPOINT
  Type: str
  Default: ""
  Meaning: empty disables the default HTTP provider.

LINGNENG_RAG_API_KEY
  Type: secret str
  Default: ""
  Meaning: optional bearer token for the configured RAG endpoint.

LINGNENG_RAG_TIMEOUT_SECONDS
  Type: float
  Default: 5.0
  Minimum: 0.1

LINGNENG_RAG_DEFAULT_TOP_K
  Type: int
  Default: 5
  Minimum: 1

LINGNENG_RAG_MAX_TOP_K
  Type: int
  Default: 20
  Minimum: 1

LINGNENG_RAG_CONTEXT_MAX_CHARS
  Type: int
  Default: 6000
  Minimum: 500
```

`ready_summary()` may include non-secret counts/flags such as skill root count
and whether a RAG endpoint is configured. It must not include API keys or
endpoint credentials.

## Skill Package Contract

The loader accepts package roots in either of these forms:

```text
<root>/SKILL.md
<root>/<package>/SKILL.md
<root>/<category>/<package>/SKILL.md
```

The front matter must contain:

```yaml
name: lower-kebab-package-name
description: human readable description
version: 1.0.0
metadata:
  lingneng:
    schema_version: "1.0"
    kind: employee_base | task | capability | infrastructure
    source: python | imported | generated
    status: active | draft | deprecated | disabled
    user_visible: true | false
    script_policy: metadata_only
```

Employee base packages additionally require:

```yaml
metadata:
  lingneng:
    employee_type: marketing_content_creator
    display_name: 内容创意师
```

The package directory name must match `name`. Disabled, deprecated, or draft
packages are not injected by default.

Allowed resource directories:

- `references/`
- `templates/`
- `examples/`
- `assets/`

Resources outside those directories, absolute paths, `..` path traversal, and
non-package files are rejected.

## Prompt Fragment Contract

`HermesAgentRunAdapter` should build one system message from these ordered
parts:

1. Java `request.system_prompt.content`.
2. A bounded LingNeng employee base fragment, if loaded.
3. A bounded selected skill fragment, if `request.skill.skill_id` matched a
   configured package.
4. Minimal RAG/tool guidance telling the model to use `retrieve_rag` for
   internal learned business knowledge that requires factual support.

Prompt fragments must include package name, kind, version, description, selected
body excerpt, resource manifest, and degradation warnings. They must not include
raw Java `history`, Java `skill.inline`, provider secrets, local absolute paths,
or raw resource file contents.

## RAG Tool Result Contract

`retrieve_rag` returns a JSON string. The public normalized success shape is:

```json
{
  "success": true,
  "tool_name": "retrieve_rag",
  "status": "hit",
  "context": "bounded context text",
  "citations": [
    {
      "document_id": "doc-1",
      "source_file_id": "file-1",
      "source_file_name": "menu.pdf",
      "page_no": 2,
      "section_title": "套餐规则",
      "chunk_id": "chunk-1",
      "score": 0.91
    }
  ],
  "metadata": {
    "selected_count": 1,
    "citation_count": 1,
    "duration_ms": 12
  }
}
```

Successful empty result:

```json
{
  "success": true,
  "tool_name": "retrieve_rag",
  "status": "empty",
  "context": "",
  "citations": [],
  "metadata": {
    "selected_count": 0,
    "citation_count": 0
  }
}
```

Safe failure result:

```json
{
  "success": false,
  "tool_name": "retrieve_rag",
  "code": "NOT_CONFIGURED",
  "status": "failed",
  "message": "LingNeng RAG provider is not configured."
}
```

Tool results must not contain raw request payloads, Java history, bearer tokens,
provider tracebacks, local filesystem paths, or unbounded provider responses.

## Module Boundaries

Create:

- `lingneng/skills/models.py`: skill metadata, resource, package, fragment, and
  error models.
- `lingneng/skills/loader.py`: package discovery, parsing, validation,
  employee-base resolution, explicit skill resolution, and prompt fragment
  building.
- `lingneng/tools/rag.py`: request context, provider protocol, default provider,
  result normalization, handler, and test injection helpers.

Modify:

- `lingneng/config/settings.py`: skill and RAG settings.
- `lingneng/runtime/hermes_adapter.py`: prompt construction, request-scoped RAG
  context, RAG event extraction, final citation accumulation.
- `lingneng/runtime/agent_adapter.py`: include new event model types.
- `lingneng/events/bridge.py`: citation/rag event helpers and final answer
  citations parameter.
- `lingneng/schemas/chat_events.py`: citation and RAG context event models.
- `lingneng/api/routes.py`: event-name routing and persisted final citations.
- `lingneng/session/run_store.py`: citation persistence for completed run replay.
- `lingneng/tools/toolset.py`: register real `retrieve_rag` handler while
  keeping other LingNeng tools as stubs.
- `lingneng/tools/stubs.py`: keep `retrieve_rag` schema in approved tool list but
  stop registering its stub handler when replaced by the real adapter.

Do not modify Hermes core files unless a small extension is unavoidable. Current
inspection shows Phase 4 can use existing Hermes tool callbacks and contextvar
thread propagation.

## Error Handling And Safety

- Skill load errors degrade prompt enrichment and continue the chat request.
- RAG provider errors return safe tool failure JSON.
- Public SSE events must not expose raw exceptions, tracebacks, API keys,
  bearer tokens, Java payloads, local paths, or prompt internals.
- Invalid citation payloads from a provider are ignored or converted to safe
  failure; they must not crash the stream.
- `include_agent_steps=false` is already accepted in the request schema but
  Phase 4 does not change Phase 3 step emission behavior. This can be tightened
  in a later stream-options phase.
- The dedicated `lingneng` toolset must remain the only toolset used by
  `HermesAgentRunAdapter`.

## Test Strategy

Use TDD per task. Tests must not require live external services.

Required tests:

- `tests/lingneng/skills/test_skill_loader.py`
  - Loads employee base skill by `employee_type`.
  - Selects explicit skill by exact package name.
  - Skips unknown Java `skill_id` and ignores `skill.inline`.
  - Truncates large skill bodies/resources to configured bounds.
  - Rejects or skips non-`metadata_only` script policies.
  - Produces prompt fragments without absolute package paths.

- `tests/lingneng/tools/test_retrieve_rag.py`
  - Builds normalized RAG request with tenant/user/employee/session context.
  - Clamps `top_k`.
  - Returns empty success result for provider empty hits.
  - Returns safe `NOT_CONFIGURED` result when no provider endpoint/injected
    provider exists.
  - Does not echo secrets or raw provider exceptions.

- `tests/lingneng/events/test_rag_events.py`
  - Adds `CitationDeltaEvent` and `RagContextEvent` models without `event`
    fields.
  - Extracts citation and RAG context events from `retrieve_rag` result JSON.
  - Honors `include_citations` and `include_rag_context`.
  - Emits `rag_context` with status `empty`.
  - Deduplicates final citations by `chunk_id`.

- `tests/lingneng/api/test_chat_stream_idempotency.py`
  - Persists and replays `final.citations` for completed repeated requests.

- `tests/lingneng/contract/test_rag_skill_chat_stream.py`
  - Configures temporary skill roots.
  - Uses a marketing employee request with a matching selected skill id.
  - Uses a deterministic agent/test provider to produce one RAG hit.
  - Asserts stream includes `agent_step`, `citation_delta`, `rag_context`,
    `answer_delta`, and `final`.
  - Asserts `final.citations` contains the RAG citation.
  - Asserts the agent received employee base and selected skill fragments in
    `system_message`.

Regression commands:

```bash
uv run --extra dev python -m pytest tests/lingneng/skills/test_skill_loader.py -q
uv run --extra dev python -m pytest tests/lingneng/tools/test_retrieve_rag.py tests/lingneng/events/test_rag_events.py -q
uv run --extra dev python -m pytest tests/lingneng/contract/test_rag_skill_chat_stream.py -q
uv run --extra dev python -m pytest tests/lingneng/config tests/lingneng/schemas tests/lingneng/session tests/lingneng/api tests/lingneng/runtime tests/lingneng/tools tests/lingneng/events tests/lingneng/contract -q
uv run --extra dev python -m ruff check lingneng tests/lingneng
/Users/rotas/Documents/work/hailun/LingNengAI/.venv/bin/python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py -q
```

## Acceptance Criteria

Phase 4 is complete when:

1. A Hermes-mode LingNeng request can construct a system prompt containing Java
   system prompt text plus bounded employee base guidance from configured skill
   roots.
2. A request with `skill.skill_id` matching a configured package injects only a
   bounded selected-skill excerpt.
3. A request with unknown `skill.skill_id` still runs and does not inject
   `skill.inline`.
4. `retrieve_rag` is registered as the real LingNeng handler while all other
   non-RAG business tools remain safe Phase 3 stubs.
5. A successful RAG hit can emit `citation_delta`, optional `rag_context`, and
   final citations compatible with current LingNeng P1 fields.
6. A successful empty RAG result can emit `rag_context.status == "empty"` when
   requested.
7. Completed-run idempotent replay preserves `final.citations`.
8. The LingNeng safe toolset boundary from Phase 3 still passes.
9. All Phase 4 tests and LingNengAI reference contract tests pass.

## User Confirmations Needed Before Phase 4 Plan

No new user confirmation is needed before writing the Phase 4 plan because the
previously approved master sequence already selected Phase 4 and this spec keeps
deployment out of scope.

Two implementation choices are now explicitly locked by this spec:

1. `LINGNENG_SKILL_ROOTS` enables skill packages; no production hardcode to the
   old sibling checkout.
2. `skill.inline` is never trusted as prompt content.

If either choice needs to change, this spec must be revised before the plan is
written.

## Self-Review

- Placeholder scan: no TBD/TODO placeholders remain.
- Scope check: the spec covers only Phase 4 skill loading, RAG adapter, RAG SSE
  events, and final citation replay. Deployment and artifact work are excluded.
- Consistency check: event gating follows the current LingNengAI behavior:
  `include_citations` gates citation deltas and final citations;
  `include_rag_context` gates RAG context events only.
- Boundary check: the implementation path uses `lingneng/` modules and existing
  Hermes callbacks/contextvars, with no expected Hermes core edits.
