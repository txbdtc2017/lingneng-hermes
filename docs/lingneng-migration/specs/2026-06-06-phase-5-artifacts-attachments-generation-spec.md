# Phase 5 Artifacts, Attachments, And Business Generation Tools Spec

## Status

Drafted after Phase 4 completion on `dev`.

Required durable context reloaded before writing this spec:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`

Reference implementation inspected for this phase:

- `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/tools/artifact.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_events.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/artifacts/artifact_service.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/tools/tool_calling.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/tools/document_generation.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/tools/image_generation.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/tools/chart_visualization.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/tools/web_search.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/chat/nodes/attachment_processing.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/chat/nodes/direct_attachment_answer.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/tools/search_result_normalizer.py`

## Goal

Move LingNeng artifact-producing and request-attachment capabilities behind the
Hermes LingNeng toolset while preserving the Java-compatible SSE contract.

Phase 5 makes these capabilities real enough for deterministic local contract
tests:

1. Java-compatible artifact models and `artifact_created` events.
2. Real LingNeng handlers for `document_generation`, `image_generation`,
   `chart_visualization`, and a controlled LingNeng `web_search` tool.
3. Request-scoped attachment understanding that can add bounded current-request
   context before the Hermes agent runs.
4. Final artifact accumulation, dedupe, persistence, and idempotent replay.

## Scope

### Artifact Contract

Phase 5 adds a Hermes-side artifact model matching the current LingNengAI
Java-facing fields:

```text
Artifact:
  artifact_id: str
  artifact_type: "image" | "document"
  source: str
  file_name: str
  mime_type: str
  url: str
  object_key: str
  format: str | null
  target_format: str | null
  conversion_required: bool
  conversion_owner: str | null
```

`chart_visualization` produces an image artifact with
`source == "chart_visualization"` rather than adding a new public
`artifact_type`.

Phase 5 adds `ArtifactCreatedEvent` using the same public artifact fields.
As in earlier phases, the SSE `event:` line carries `artifact_created`; event
JSON must not include an `event` field.

`FinalEvent.artifacts` should become a validated list of artifacts. Existing
artifact replay from `LingNengRunStore` must keep working and should reject or
drop invalid artifact records rather than crashing the stream.

### Artifact Event Emission

Artifact events are derived from completed tool results from these tools:

- `document_generation`
- `image_generation`
- `chart_visualization`

The live stream order for a successful artifact-producing tool call is:

```text
agent_step completed -> artifact_created event(s) -> subsequent answer_delta/final
```

`final.artifacts` contains the deduped artifacts accumulated from completed
tool results. Dedupe key is `artifact_id`, preserving first-seen order.

Repeated completed `request_id` replay remains:

```text
run_started -> answer_delta -> final
```

Replay does not need to replay historical `agent_step` or `artifact_created`
events in Phase 5, but replayed `final.artifacts` must equal the stored live
final artifacts.

### Business Tool Adapters

Phase 5 replaces the Phase 3 stubs for:

- `document_generation`
- `image_generation`
- `chart_visualization`
- `web_search`

The remaining LingNeng business tools stay stubs unless explicitly listed in
this spec:

- `list_skills`
- `search_skills`
- `read_skill`
- `read_skill_resource`
- `read_workspace`
- `write_workspace`

`web_search` in Phase 5 is a LingNeng-controlled provider adapter. It must not
expose Hermes browser automation, arbitrary network automation, or high-risk
Hermes default tools.

All Phase 5 tool handlers return stable JSON with this public shape:

```text
success: bool
tool_name: str
status: "succeeded" | "failed" | "skipped"
summary: str
safe_output: dict
artifacts: list[Artifact]
metadata: dict
code: str | null
message: str | null
```

Public tool JSON must not contain raw provider exceptions, tracebacks, API keys,
bearer tokens, passwords, Java internal keys, signed upload credentials, local
absolute filesystem paths, raw request payloads, or raw attachment text beyond
the configured excerpt limits.

### Provider Interfaces

Phase 5 uses provider protocols and dependency injection, not live external
services in tests.

Document generation:

- Accepts a bounded title/content/instruction payload.
- Produces a PDF/document artifact through an env-configured or injected Java
  file/PDF provider.
- Public output may include source file name, source format, content length,
  artifact count, and hashes. It must not include full document body if it
  exceeds configured public-output limits.

Image generation:

- Accepts prompt, size, quality/style, and count.
- Count is clamped to configured bounds.
- Uses an injected AIGC provider and result store in tests.
- Partial success returns available artifacts plus safe public summary.
- Full failure returns safe failure JSON and no artifacts.

Chart visualization:

- Accepts instruction/title, chart type, and bounded data summary.
- Delegates to the image-generation provider boundary or a chart provider.
- Public artifact uses `artifact_type == "image"` and
  `source == "chart_visualization"`.

Web search:

- Accepts query, top_k, recency filter, and optional site filter.
- top_k is clamped to configured bounds.
- Returns normalized public web sources only: source id, title, URL, website,
  date, and snippet.
- Rejects URLs with credentials, invalid schemes, control characters, or
  whitespace in authority components.
- Does not emit artifacts.

### Attachment Understanding

Phase 5 adds request-scoped attachment understanding for
`request.attachments`.

The adapter must:

- Process only attachments from the current Java request.
- Never merge Java `history` or previous-turn attachment text into the current
  attachment context.
- Enforce allowed download host checks before using `download_url`.
- Enforce file count, total bytes, per-file bytes, image bytes, and total timeout
  limits.
- Truncate direct extracted text to configured maximum characters.
- Produce a bounded current-request attachment context that is added to the
  Hermes system prompt or pre-run context for this run only.
- Emit public `agent_step` progress for started/completed/failed/skipped
  attachment processing.
- Degrade safely when the attachment service is disabled, unavailable, times out,
  or returns malformed output.

Phase 5 does not make attachment contents persistent memory. If a future phase
needs persistent attachment summaries, it must add an explicit session policy.

### Configuration Contract

Add or extend `LingNengSettings` with non-secret settings for Phase 5:

```text
LINGNENG_ARTIFACT_PUBLIC_BASE_URL
  Type: str
  Default: ""
  Meaning: optional public URL prefix for locally stored artifacts.

LINGNENG_ARTIFACT_URL_ALLOWED_HOSTS
  Type: list[str]
  Default: []
  Meaning: optional allow-list for externally returned artifact URLs.

LINGNENG_TOOL_RESULT_MAX_CHARS
  Type: int
  Default: 6000
  Minimum: 500

LINGNENG_DOCUMENT_MAX_CONTENT_CHARS
  Type: int
  Default: 20000
  Minimum: 1000

LINGNENG_IMAGE_MAX_COUNT
  Type: int
  Default: 4
  Minimum: 1

LINGNENG_GENERATION_TIMEOUT_SECONDS
  Type: float
  Default: 300.0
  Minimum: 1.0

LINGNENG_WEB_SEARCH_DEFAULT_TOP_K
  Type: int
  Default: 5
  Minimum: 1

LINGNENG_WEB_SEARCH_MAX_TOP_K
  Type: int
  Default: 10
  Minimum: 1

LINGNENG_ATTACHMENT_ALLOWED_HOSTS
  Type: list[str]
  Default: []

LINGNENG_ATTACHMENT_MAX_FILES
  Type: int
  Default: 5
  Minimum: 0

LINGNENG_ATTACHMENT_MAX_TOTAL_BYTES
  Type: int
  Default: 52428800
  Minimum: 0

LINGNENG_ATTACHMENT_MAX_FILE_BYTES
  Type: int
  Default: 20971520
  Minimum: 0

LINGNENG_ATTACHMENT_MAX_IMAGE_BYTES
  Type: int
  Default: 10485760
  Minimum: 0

LINGNENG_ATTACHMENT_TIMEOUT_SECONDS
  Type: float
  Default: 30.0
  Minimum: 0.1

LINGNENG_ATTACHMENT_CONTEXT_MAX_CHARS
  Type: int
  Default: 6000
  Minimum: 500
```

Secrets for provider APIs remain env-only and must not appear in
`ready_summary()`.

`ready_summary()` may include non-secret booleans/counts such as
`artifact_url_allow_list_count`, `web_search_configured`, and
`attachment_host_allow_list_count`.

## Non-Goals

Phase 5 does not:

- Implement Docker, compose, deployment scripts, rollback, or GitHub Actions.
- Modify Java code or require Java request changes.
- Reintroduce the old LingNengAI LangGraph runtime.
- Expose Hermes terminal, filesystem, browser automation, code execution,
  delegation, cross-channel messaging, Kanban, or unrelated default tools.
- Make `list_skills`, `search_skills`, `read_skill`, `read_skill_resource`,
  `read_workspace`, or `write_workspace` real tools.
- Persist raw attachment contents into Hermes SessionDB.
- Implement full Excel direct-answer behavior from LingNengAI. A provider may
  return a bounded attachment context in Phase 5; direct attachment answer
  requires a separate future spec if product requirements need it.
- Require live Java file service, AIGC service, web search provider, object
  storage, or attachment parser in tests.
- Add artifact conversion workers. Phase 5 may mark
  `conversion_required=true` and `conversion_owner="java"` where compatible.

## Accepted Decisions

1. Artifact public fields match the current LingNengAI `Artifact` model.
2. `chart_visualization` returns image artifacts, not a new public artifact type.
3. `web_search` is added as a controlled LingNeng tool only; Hermes generic web
   or browser tools remain excluded from the Java API.
4. Generation providers are injected or env-configured behind protocols; tests
   use fake providers and make no live calls.
5. Attachment understanding is current-request scoped and bounded; it is not
   stored as durable session memory in Phase 5.
6. Artifact replay persists only final artifacts. Historical `artifact_created`
   events are not replayed for repeated completed `request_id` in Phase 5.
7. Tool failures are public, sanitized tool results. They should not break the
   no-tool fake API path or unrelated LingNeng tools.
8. Existing Phase 4 RAG and skill behavior must remain unchanged except for
   shared event/model types needed for artifact support.

## Open Decisions

No user decision is required before writing the Phase 5 implementation plan.

The following choices are intentionally implementation details for the plan:

- Whether document, image, chart, web search, and attachment provider injection
  uses one shared context manager or per-tool context managers.
- Whether local fake artifact storage uses in-memory provider state or files
  under `LINGNENG_RUNTIME_DIR` for tests.
- Exact internal names for provider protocol classes.

## Module Boundaries

Expected new modules:

- `lingneng/tools/artifacts.py`: artifact model helpers, public sanitization,
  URL/object-key validation, artifact dedupe.
- `lingneng/tools/generation.py` or separate modules:
  `document_generation.py`, `image_generation.py`, `chart_visualization.py`,
  `web_search.py`: provider protocols and tool handlers.
- `lingneng/tools/attachments.py`: attachment context models, provider
  protocols, bounded current-request context builder.

Expected modified modules:

- `lingneng/config/settings.py`: Phase 5 settings and non-secret readiness
  summary.
- `lingneng/schemas/chat_events.py`: `Artifact` and `ArtifactCreatedEvent`;
  `FinalEvent.artifacts` validation.
- `lingneng/events/bridge.py`: artifact extraction, dedupe, final answer helper.
- `lingneng/runtime/agent_adapter.py`: stream event union includes
  `ArtifactCreatedEvent`.
- `lingneng/runtime/hermes_adapter.py`: request-scoped attachment context,
  generation provider contexts, artifact event emission and final accumulation.
- `lingneng/api/routes.py`: event name routing and artifact replay.
- `lingneng/session/run_store.py`: keep artifact persistence compatible and
  validate/sanitize records.
- `lingneng/tools/stubs.py` and `lingneng/tools/toolset.py`: move Phase 5 real
  tools out of the stub list and add controlled `web_search`.

## Test Strategy

Phase 5 must add focused tests for:

- Artifact schema/event payloads and path/secret sanitization.
- Artifact dedupe by `artifact_id`.
- Tool result shape and safe failure for document/image/chart/web search.
- Provider injection without live services.
- Per-call/per-run limits and top_k/count clamping.
- Attachment allowed host, size, timeout, and current-request scoping.
- Hermes adapter stream order for artifact events:
  `agent_step` completion before `artifact_created`, then answer/final.
- Idempotent replay of `final.artifacts`.
- Contract scenario for document artifact stream.
- Regression that Phase 4 RAG/skill tests still pass.

Expected verification for the Phase 5 plan:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_artifact_models.py tests/lingneng/tools/test_generation_tools.py tests/lingneng/tools/test_attachments.py tests/lingneng/contract/test_artifact_chat_stream.py -q
uv run --extra dev python -m pytest tests/lingneng -q
uv run --extra dev python -m ruff check lingneng tests/lingneng
/Users/rotas/Documents/work/hailun/LingNengAI/.venv/bin/python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_tool_artifact_events.py -q
```

## Acceptance Criteria

Phase 5 is complete when:

1. Java-compatible `Artifact` and `ArtifactCreatedEvent` models exist and dump
   without an `event` JSON field in LingNeng-Hermes SSE payloads.
2. `document_generation`, `image_generation`, `chart_visualization`, and
   controlled LingNeng `web_search` handlers are real provider-backed handlers
   with no live dependencies in tests.
3. Other non-Phase-5 LingNeng tools remain stubs.
4. Artifact-producing tool completion emits `artifact_created` after the public
   `agent_step` completion event.
5. `final.artifacts` contains deduped artifacts when artifacts were produced.
6. Repeated completed `request_id` replays stored `final.artifacts`.
7. Attachment processing can add bounded current-request context and public
   progress without storing raw attachment content in session history.
8. No provider secret, raw exception, traceback, local absolute path, signed
   credential, or raw oversized attachment/document content appears in public
   SSE/tool output.
9. Full LingNeng regression tests, ruff, and relevant old LingNengAI artifact
   event contract tests pass.

## User Confirmations Needed Before Phase Plan

None. Phase 5 follows the master roadmap and keeps deployment work deferred.

## Spec Self-Review

- Scope coverage: artifact models, generation tools, web search, attachment
  understanding, event bridge, final persistence, and replay are covered.
- Non-goal check: deployment, GitHub Actions, Java changes, workspace tools, and
  full Excel direct-answer behavior remain excluded.
- Contract consistency: artifact fields match the current LingNengAI
  `Artifact` model; `artifact_created` uses the SSE event line rather than an
  `event` JSON field in this Hermes runtime.
- Security check: public outputs must strip provider secrets, bearer tokens,
  local filesystem paths, raw request payloads, and oversized content.
- Execution readiness: no user confirmation is needed before writing the Phase 5
  implementation plan.
