# Phase 12 Real Business Tool Providers Spec

## Status

Drafted on `dev` after Phase 11 completion.

Required durable context reloaded before writing this spec:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-11-lingneng-business-capability-hermes-migration-spec.md`

Reference implementation inspected for this phase:

- `/Users/rotas/Documents/work/hailun/LingNengAI/app/application/provider_factory.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/providers/web_search/bocha.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/tools/web_search.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/tools/document_generation.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/tools/image_generation.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/tools/chart_visualization.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/artifacts/artifact_service.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/providers/image_generation/aigc_http.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/aigc/material_result_store.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/aigc/runtime_config.py`

Current Hermes-side implementation inspected:

- `lingneng/tools/document_generation.py`
- `lingneng/tools/image_generation.py`
- `lingneng/tools/chart_visualization.py`
- `lingneng/tools/web_search.py`
- `lingneng/tools/artifacts.py`
- `lingneng/tools/toolset.py`
- `lingneng/runtime/hermes_adapter.py`
- `lingneng/config/settings.py`
- `tests/lingneng/tools/test_generation_tools.py`
- `tests/lingneng/events/test_artifact_events.py`
- `tests/lingneng/contract/test_artifact_chat_stream.py`

## Goal

Wire LingNeng's real business provider boundaries into the Hermes LingNeng
toolset so `LINGNENG_AGENT_MODE=hermes` can use configured services for:

1. Bocha-compatible public web search.
2. Java file/PDF-backed document generation.
3. AIGC-backed image generation.
4. Chart visualization through the image-generation provider boundary.
5. Java-compatible artifact construction, validation, duplicate protection,
   public result bounding, and per-run tool limits.

Phase 12 upgrades the Phase 5 provider protocols from injected test fakes to
environment-configured default providers. It does not replace the Hermes agent
loop, add a second router, or import the old LingNengAI runtime.

## Scope

### Existing Foundation To Keep

Phase 12 must keep these existing Phase 5/11 behaviors:

- Public tool envelopes stay:

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

- `artifact_created` events and `final.artifacts` continue to be derived from
  sanitized tool results.
- Artifact URL validation, host allow-lists, secret stripping, local-path
  rejection, output truncation, and `artifact_id` dedupe remain mandatory.
- Missing providers return `NOT_CONFIGURED` instead of old fake behavior.
- Non-LingNeng Hermes web search must not be overridden by the LingNeng
  `web_search` context override.
- Time context and trusted/untrusted prompt sections from Phase 11 remain
  unchanged.

### Provider Configuration

Add explicit LingNeng settings for real providers. Secret values remain in
environment variables only.

Web search:

```text
LINGNENG_WEB_SEARCH_PROVIDER
  Type: str
  Default: ""
  Meaning: empty disables the default provider; "bocha" enables the Bocha
  compatible provider.

LINGNENG_BOCHA_WEB_SEARCH_API_KEY
  Type: secret str
  Default: ""
  Meaning: required when provider is "bocha".

LINGNENG_BOCHA_WEB_SEARCH_BASE_URL
  Type: str
  Default: "https://api.bochaai.com"

LINGNENG_BOCHA_WEB_SEARCH_TIMEOUT_SECONDS
  Type: float
  Default: 30.0
  Minimum: 0.1
```

Document generation:

```text
LINGNENG_DOCUMENT_PROVIDER
  Type: str
  Default: ""
  Meaning: empty disables the default provider; "java_file" enables Java
  markdown-to-PDF upload.

LINGNENG_JAVA_AGENT_FILE_BASE_URL
  Type: str
  Default: ""

LINGNENG_JAVA_AGENT_FILE_UPLOAD_PATH
  Type: str
  Default: "/ai/internal/agent-file/upload"

LINGNENG_JAVA_INTERNAL_KEY
  Type: secret str
  Default: ""

LINGNENG_JAVA_AGENT_FILE_UPLOAD_TIMEOUT_SECONDS
  Type: float
  Default: 120.0
  Minimum: 0.1
```

Image and chart generation:

```text
LINGNENG_IMAGE_PROVIDER
  Type: str
  Default: ""
  Meaning: empty disables the default provider; "aigc" enables AIGC text-to-image.

LINGNENG_AIGC_IMAGE_BASE_URL
  Type: str
  Default: ""
  Meaning: may be either the base URL or the full /api/aigc/image/text2img URL.

LINGNENG_AIGC_IMAGE_TIMEOUT_SECONDS
  Type: float
  Default: 30.0
  Minimum: 0.1

LINGNENG_AIGC_RESULT_STORE
  Type: str
  Default: ""
  Meaning: empty disables waiting for AIGC material results; "redis" enables
  Redis-backed result polling.

LINGNENG_AIGC_REDIS_URL
  Type: secret-capable str
  Default: ""

LINGNENG_AIGC_REDIS_KEY_PREFIX
  Type: str
  Default: "lingneng-agent"

LINGNENG_AIGC_RESULT_TTL_SECONDS
  Type: int
  Default: 7200
  Minimum: 1

LINGNENG_AIGC_RESULT_WAIT_TIMEOUT_SECONDS
  Type: float
  Default: 300.0
  Minimum: 0.1

LINGNENG_AIGC_RESULT_POLL_INTERVAL_SECONDS
  Type: float
  Default: 1.0
  Minimum: 0.01
```

Tool guardrails:

```text
LINGNENG_TOOL_ARTIFACT_MAX_CALLS_PER_RUN
  Type: int
  Default: 3
  Minimum: 1
  Meaning: maximum successful or attempted calls per artifact-producing tool in
  one agent run.

LINGNENG_WEB_SEARCH_MAX_CALLS_PER_RUN
  Type: int
  Default: 12
  Minimum: 1

LINGNENG_DUPLICATE_ARTIFACT_GUARD_ENABLED
  Type: bool
  Default: true
  Meaning: suppress duplicate generation attempts with the same normalized tool
  input within one agent run.
```

`ready_summary()` must expose boolean status only, never secret values:

- `web_search_configured`
- `document_provider_configured`
- `image_provider_configured`
- `aigc_result_store_configured`

### Provider Factory

Add a Hermes-native LingNeng provider factory under `lingneng/tools/`.

The factory is responsible for:

- returning `None` when a provider is disabled or incomplete;
- validating supported provider names;
- constructing configured providers from `LingNengSettings`;
- not importing old `app.*` modules from the sibling LingNengAI checkout;
- exposing small focused constructors so tests can assert each branch without
  starting a live service.

Runtime wiring must happen in `HermesAgentRunAdapter.stream()` around the agent
run, beside the existing RAG, skill, handoff, and LingNeng web-search contexts.
The adapter should enter contexts for configured providers:

```text
document_generation_context(settings, provider=document_provider)
image_generation_context(settings, provider=image_provider)
chart_visualization_context(settings, provider=chart_provider)
web_search_context(settings, provider=web_search_provider)
tool_limit_context(...)
```

Fake-agent mode must not be changed. It remains deterministic for contract
tests and local smoke runs.

### Web Search Provider

Implement a synchronous Hermes provider wrapper compatible with
`lingneng.tools.web_search.WebSearchProvider`.

The Bocha-compatible provider must:

- call `POST {base_url}/v1/web-search`;
- send `Authorization: Bearer <key>`;
- send JSON fields `query`, `freshness`, `summary`, and `count`;
- map `recency_filter` as:
  - empty/unknown -> `noLimit`
  - `week` -> `oneWeek`
  - `month` -> `oneMonth`
  - `semiyear` -> `oneYear`
  - `year` -> `oneYear`
- ignore `site_filter` unless a future provider supports it safely;
- normalize known Bocha response shapes into `WebSearchResult.sources`;
- raise internal exceptions on HTTP/provider failure and let the handler return
  the existing sanitized `WEB_SEARCH_PROVIDER_ERROR` envelope.

The provider must not leak raw provider payloads, request headers, API keys, or
tracebacks into tool output.

### Document Provider And Artifact Service

Implement a Hermes-native document provider compatible with
`DocumentGenerationProvider`.

The provider must:

- treat the request `content` as the complete document body to convert;
- accept legacy-compatible content aliases through the existing handler only if
  the handler already supports them;
- build bounded Markdown source with one title heading when the body has no H1;
- produce a safe source file name and PDF file name;
- upload Markdown to the configured Java file/PDF service;
- create a Java-compatible external document artifact:
  - `artifact_type == "document"`
  - `source == "document_generation"`
  - `mime_type == "application/pdf"`
  - `format == "pdf"`
  - `target_format == "pdf"`
  - `conversion_required == false`
  - `conversion_owner == null`
  - `object_key == "external/java-agent-file/<artifact_id>"`
- include only safe public metadata such as source format, file name, content
  length, content hash, and artifact count.

The Java file client must:

- call the configured base URL + upload path;
- include the configured Java internal key using the current Java internal
  header convention if one exists in old LingNengAI, otherwise use a documented
  `X-Internal-Key` header for this Hermes provider;
- send Markdown and file name in a format covered by tests;
- accept common response shapes containing a public URL in `url`, `data.url`,
  `download_url`, or `data.download_url`;
- fail safely if the response has no valid public URL.

Phase 12 does not add local PDF conversion or office conversion fallback.

### Image Provider

Implement a Hermes-native image provider compatible with
`ImageGenerationProvider`.

The provider must:

- submit one AIGC text-to-image task per requested image;
- clamp count through existing handler settings;
- normalize size and quality defaults before calling AIGC;
- wait for a terminal task result through the configured AIGC result store;
- return partial success when some tasks produce valid image URLs;
- create external image artifacts:
  - `artifact_type == "image"`
  - `source == "image_generation"`
  - `object_key == "external/aigc-image/<task_id>/<index>"`
  - `format` inferred from URL suffix (`png`, `jpg`, `webp`, default `png`);
- return safe public metadata: requested count, succeeded count, failed count,
  task ids, size, quality, and artifact count;
- avoid exposing raw prompts beyond existing public output limits.

If AIGC submit is configured but result polling is not configured, the provider
factory must return `None` so the tool reports `NOT_CONFIGURED`. Returning task
ids without artifacts is not sufficient for Phase 12.

### AIGC Result Store

Add a small result-store abstraction for image generation.

The Redis-backed implementation must preserve the old key shape:

```text
<prefix>:aigc:image_task:<task_id>
```

Expected terminal payload fields:

```text
task_id: str
task_type: str
status: str
msg: str | null
material_urls: list[str]
```

`wait()` must poll until a non-`pending` result or timeout. Timeout and malformed
payloads become provider failures; the handler surfaces sanitized public failure
JSON.

If adding the Redis client dependency is necessary, it must follow this repo's
dependency policy and be exact-pinned with lockfile regeneration. If the plan can
implement Redis access without a new runtime dependency, that is acceptable, but
tests must still avoid a live Redis service.

### Chart Provider

Implement chart visualization by reusing the configured image provider.

The chart provider must:

- build a bounded chart prompt from title, chart type, instruction, and data
  summary;
- never pass raw unbounded table/file contents to the image provider;
- call the image provider with count 1 unless the caller supplied a clamped
  count that the existing handler accepts;
- rewrite artifacts to:
  - `artifact_type == "image"`
  - `source == "chart_visualization"`
  - file name based on sanitized title and index;
- preserve partial success semantics inherited from image generation.

### Tool Limits And Duplicate Guard

Phase 12 adds deterministic per-run guards for expensive tools. These guards are
not a new router and not an LLM-based admission classifier.

Apply guards to:

- `document_generation`
- `image_generation`
- `chart_visualization`
- `web_search`

Required behavior:

- count attempts by tool name within the current agent run;
- return a safe skipped envelope when a call exceeds the configured max;
- when duplicate guard is enabled, normalize public tool args and suppress a
  duplicate expensive call in the same run;
- duplicate suppression should preserve first result only indirectly through
  normal session/tool output; it must not replay raw provider payloads;
- guard state must be request/run scoped and must not bleed across concurrent
  sessions.

Guard failure codes:

```text
TOOL_CALL_LIMIT_EXCEEDED
DUPLICATE_TOOL_CALL_SUPPRESSED
```

Existing public sanitization rules apply to these guard envelopes.

### Observability

Extend sanitized runtime trace/ready output only with summary booleans and
counts:

- provider configured booleans in ready summary;
- tool result metadata may include `source_count`, `artifact_count`,
  `succeeded_count`, `failed_count`, `limit`, and `duplicate_suppressed`;
- final event trace may include generated artifact count and search source count
  only if that data is already public and sanitized.

Do not log or emit:

- API keys
- Java internal keys
- Redis URLs with credentials
- raw provider response bodies
- stack traces in SSE/tool output
- full generated document body
- raw image prompt beyond bounded public fields

## Non-Goals

Phase 12 does not:

- implement attachment parsing/OCR/vision providers; that is Phase 13;
- harden external RAG beyond the existing query adapter; that is Phase 14;
- migrate training/indexing/worker ingestion; that is Phase 15;
- add CI/CD, compose, deployment scripts, or server rollout changes;
- modify Java code or require Java request/stream changes;
- import or execute old LingNengAI `app.*` modules at runtime;
- rebuild old LingNengAI LangGraph nodes, route graph, or tool admission LLM;
- add browser automation, terminal execution, arbitrary filesystem access, or
  high-risk Hermes tools to the Java API;
- require live Bocha, Java file service, AIGC, Redis, or old LingNengAI in
  automated unit/contract tests.

## Accepted Decisions

1. Hermes remains the runtime owner. Old LingNengAI is a behavior reference, not
   an imported dependency.
2. Provider wiring is explicit and environment-driven. Missing or incomplete
   configuration returns `NOT_CONFIGURED`.
3. Fake-agent mode stays fake. Real providers are only wired for Hermes mode and
   direct handler tests with configured contexts.
4. Web search uses the Bocha-compatible contract first. Other providers require
   a future spec or a small extension to the provider factory.
5. Document generation uses Java file/PDF upload first. No local PDF renderer is
   added in this phase.
6. Image generation requires both AIGC submit and result polling before it is
   considered configured.
7. Chart visualization reuses the image provider with a bounded chart prompt.
8. Tool limits and duplicate guard are deterministic run-scoped guards, not a
   second routing/tool framework.
9. Automated tests use mock HTTP transports, fake result stores, and injected
   providers. Live integration tests are optional and skipped unless explicitly
   configured.

## Open Decisions

No user decision is required before the Phase 12 plan.

Implementation may choose one of two Redis result-store approaches during the
plan, as long as tests are deterministic and dependency policy is respected:

- exact-pin the official Redis Python client and regenerate `uv.lock`;
- define a tiny injectable Redis-like protocol and keep the concrete live Redis
  adapter optional/fail-closed when the package is unavailable.

## Data Contracts

### Public Artifact

Phase 12 continues to use the existing `Artifact` schema:

```text
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

### Provider Failure Envelope

Provider failures must return sanitized JSON:

```json
{
  "success": false,
  "tool_name": "image_generation",
  "status": "failed",
  "summary": "Image generation provider failed.",
  "safe_output": {},
  "artifacts": [],
  "metadata": {},
  "code": "IMAGE_GENERATION_PROVIDER_ERROR",
  "message": "LingNeng image generation provider failed."
}
```

### Guard Skip Envelope

Tool limits and duplicate suppression return sanitized skipped JSON:

```json
{
  "success": false,
  "tool_name": "web_search",
  "status": "skipped",
  "summary": "Tool call was skipped by LingNeng run guard.",
  "safe_output": {
    "reason": "limit_exceeded"
  },
  "artifacts": [],
  "metadata": {
    "limit": 12
  },
  "code": "TOOL_CALL_LIMIT_EXCEEDED",
  "message": "LingNeng web_search call limit was reached for this run."
}
```

## Module Boundaries

Expected files to add or modify:

- `lingneng/config/settings.py`: provider and guard settings plus ready summary.
- `lingneng/tools/providers.py`: provider factory and configured-provider
  construction.
- `lingneng/tools/web_search_provider.py`: Bocha-compatible web search adapter.
- `lingneng/tools/document_provider.py`: Java file/PDF document provider and
  artifact construction helpers.
- `lingneng/tools/image_provider.py`: AIGC submit/result polling provider and
  external image artifact helpers.
- `lingneng/tools/chart_provider.py`: chart provider backed by image provider.
- `lingneng/tools/limits.py`: request/run-scoped call limit and duplicate guard.
- `lingneng/tools/document_generation.py`, `image_generation.py`,
  `chart_visualization.py`, `web_search.py`: minimal hook points for guard
  envelopes if the guard is applied inside handlers.
- `lingneng/runtime/hermes_adapter.py`: enter provider/guard contexts around the
  Hermes agent run.
- `tests/lingneng/config/test_settings.py`: provider settings.
- `tests/lingneng/tools/test_real_business_providers.py`: provider adapter unit
  tests with fake transports/stores.
- `tests/lingneng/tools/test_generation_tool_guards.py`: per-run limits and
  duplicate guard.
- `tests/lingneng/runtime/test_hermes_adapter_config.py`: runtime context wiring.
- `tests/lingneng/contract/test_artifact_chat_stream.py`: configured provider
  artifact event/final artifact contract when needed.

The plan may split files differently if it preserves these responsibilities and
keeps each module focused.

## Test Strategy

Focused tests:

- settings parse defaults, provider env vars, secret-safe ready summary;
- provider factory returns `None` for incomplete config and concrete providers
  for complete config;
- Bocha provider sends the expected request and normalizes known response
  shapes using `httpx.MockTransport`;
- Java file provider builds Markdown, uploads it, extracts public URL response
  shapes, and creates a sanitized document artifact;
- AIGC provider submits tasks, waits through an injected result store, returns
  partial success, and fails safely on timeout/malformed results;
- chart provider delegates through image provider and rewrites artifact source;
- guard context enforces call limits and duplicate suppression per run while
  preserving isolation across contexts;
- Hermes adapter enters configured provider contexts in Hermes mode;
- public tool output, `artifact_created`, and `final.artifacts` remain free of
  secrets, local paths, and tracebacks.

Regression tests:

- existing Phase 5 generation tests still pass;
- existing artifact event tests still pass;
- existing Hermes web search isolation tests still pass;
- full `tests/lingneng` suite passes before implementation commits are pushed.

Optional live tests:

- may be added behind explicit environment flags such as
  `LINGNENG_LIVE_PROVIDER_TESTS=1`;
- must be skipped by default;
- must never require old LingNengAI service checkout imports.

## Acceptance Criteria

Phase 12 is complete when:

1. `LINGNENG_AGENT_MODE=hermes` can wire configured web search, document,
   image, and chart providers into the LingNeng tool contexts.
2. Missing or incomplete provider config still returns `NOT_CONFIGURED` safe
   results and does not use fake providers.
3. Bocha-compatible search, Java file/PDF document generation, AIGC image
   generation, and chart-via-image provider behavior are covered by deterministic
   tests.
4. Artifact-producing tools return validated public artifacts, emit
   `artifact_created`, accumulate `final.artifacts`, and preserve idempotent
   replay.
5. Per-run tool call limits and duplicate suppression are implemented for
   expensive tools without shared-state leakage across requests.
6. Public outputs and logs do not leak provider secrets, raw provider responses,
   tracebacks, local paths, raw document bodies, or Java history.
7. Non-LingNeng Hermes tool surfaces are unaffected, especially the default
   Hermes `web_search` tool.
8. No runtime import from `/Users/rotas/Documents/work/hailun/LingNengAI/app` or
   `app.*` is introduced.
9. Focused Phase 12 tests, the broader LingNeng test suite, and lint pass before
   each implementation commit is pushed.

## Rollback

Provider wiring is additive. Rollback can disable all real providers by clearing
the provider settings:

- `LINGNENG_WEB_SEARCH_PROVIDER`
- `LINGNENG_DOCUMENT_PROVIDER`
- `LINGNENG_IMAGE_PROVIDER`
- `LINGNENG_AIGC_RESULT_STORE`

With these empty, tools must return the same safe `NOT_CONFIGURED` envelopes as
before Phase 12. If a specific provider is faulty, clear only that provider's
setting and leave the rest enabled.

## Spec Self-Review

- Placeholder scan: no unresolved markers or incomplete placeholders remain.
- Scope check: Phase 12 excludes attachments, RAG hardening, training ingestion,
  CI/CD, and deployment.
- Consistency check: the spec builds on existing Phase 5 handlers and Phase 11
  prompt hardening rather than replacing them.
- Ambiguity check: missing config behavior, provider names, guard behavior, and
  live-test boundaries are explicit.
