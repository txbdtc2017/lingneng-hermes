# Phase 14 RAG Provider Integration Hardening Spec

## Status

Drafted on `dev` after Phase 13 attachment-understanding providers completed
and verified.

Required durable context reloaded before writing this spec:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-11-lingneng-business-capability-hermes-migration-spec.md`

Reference implementation inspected for this phase:

- `/Users/rotas/Documents/work/hailun/LingNengAI/app/application/rag_application_service.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/rag/retrieval_service.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/rag/retrieval_types.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/rag/context_builder.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/rag/citation_builder.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/agent_harness/langchain_runtime.py`

Current Hermes-side implementation inspected:

- `lingneng/tools/rag.py`
- `lingneng/runtime/hermes_adapter.py`
- `lingneng/events/bridge.py`
- `lingneng/config/settings.py`
- `tests/lingneng/tools/test_retrieve_rag.py`
- `tests/lingneng/events/test_rag_events.py`
- `tests/lingneng/runtime/test_hermes_answer_stream.py`

## Goal

Make configured external RAG query safe enough for dev/test and server use while
training and indexing remain in the old LingNengAI project.

Phase 14 hardens the existing `retrieve_rag` tool boundary. It keeps RAG as a
normal Hermes tool, preserves Java-compatible `citation_delta` and
`rag_context` events, and makes the external HTTP provider fail closed under
timeouts, invalid responses, oversized responses, provider errors, and leaked
private data.

## Scope

Phase 14 includes:

1. Production-safe HTTP behavior for `HttpRagProvider`.
2. Provider response byte limits and deterministic response parsing.
3. Secret-safe error handling and public failure codes.
4. Canonical response normalization for both the Hermes `RagRetrieveResult`
   shape and the old LingNengAI retrieval shape.
5. Stronger public sanitization for RAG context, metadata, and citations.
6. Adapter-level provider construction hardening so broken RAG config does not
   abort the whole chat stream.
7. Optional live integration smoke tests behind explicit environment gates.
8. Focused contract tests proving `retrieve_rag` remains Java/SSE compatible.

## Non-Goals

Phase 14 does not:

- move old LingNengAI training ingestion into Hermes;
- implement embedding, vector search, BM25, RRF fusion, reranking, relevance
  gates, context building, or citation building inside Hermes;
- add training task APIs, MQ consumers, worker lifecycle, cancellation, or
  vector-store writes;
- import old `app.*` modules from `/Users/rotas/Documents/work/hailun/LingNengAI`;
- add a second pre-agent RAG router or force every request through RAG before
  the Hermes agent loop;
- change Java request or SSE contracts;
- make live RAG integration tests run by default in CI;
- add Docker, deployment, or CI/CD workflow changes.

## Accepted Decisions

1. **Query and training are separate.** Hermes may call an external RAG query
   endpoint. Old LingNengAI remains the owner of training, parsing, embedding,
   and indexing until Phase 15 or a later product decision.
2. **RAG remains a tool.** The current Hermes agent decides when to call
   `retrieve_rag`; Phase 14 does not add a parallel RAG-first answer path.
3. **HTTP provider is the short-term bridge.** `LINGNENG_RAG_ENDPOINT` points to
   a configured RAG query service. In dev/test this may be the old project or a
   compatibility wrapper around it.
4. **Provider failure is non-fatal.** RAG errors return a public failed tool
   result and may emit a failed `rag_context`, but they do not become adapter
   `ErrorEvent` unless the agent itself fails.
5. **No raw provider leakage.** Provider exceptions, endpoint URLs, bearer
   tokens, request payloads, raw query text inside metadata, local paths, signed
   URLs, and tracebacks must not appear in tool results, SSE events, logs, or
   final citation payloads.
6. **Live tests are opt-in.** Deterministic fake-client tests cover CI. Live
   integration checks require explicit environment flags and a configured
   endpoint/key.

## User Confirmations Before Phase 14 Plan

No additional user confirmation is required before the Phase 14 plan if these
decisions remain true:

- RAG query can keep calling an external endpoint, including old LingNengAI in
  dev/test.
- Training and indexing remain out of scope for this phase.
- Live RAG integration tests stay opt-in and disabled by default.
- The public Java/SSE contract remains unchanged.

If any of those decisions changes, update this spec before writing the plan.

## Existing RAG Surface To Preserve

`lingneng/tools/rag.py` already provides:

- `RagRequestContext`
- `RagRetrieveRequest`
- `RagRetrieveResult`
- `RagProvider`
- `HttpRagProvider`
- `build_rag_request_context(...)`
- `rag_request_context(...)`
- `retrieve_rag_handler(...)`

The dedicated LingNeng toolset already exposes `retrieve_rag`. The runtime
adapter builds `RagRequestContext` from the Java request and resolved Python
session, then enters `rag_request_context(...)` around the Hermes agent run.

Phase 14 must preserve the tool name and the public tool result shape:

```json
{
  "success": true,
  "tool_name": "retrieve_rag",
  "status": "hit",
  "context": "...",
  "citations": [],
  "metadata": {}
}
```

Failure results remain public and non-throwing:

```json
{
  "success": false,
  "tool_name": "retrieve_rag",
  "status": "failed",
  "code": "RAG_PROVIDER_ERROR",
  "message": "LingNeng RAG provider failed.",
  "context": "",
  "citations": [],
  "metadata": {"selected_count": 0, "citation_count": 0}
}
```

## Configuration

Existing settings stay:

```text
LINGNENG_RAG_ENDPOINT
LINGNENG_RAG_API_KEY
LINGNENG_RAG_TIMEOUT_SECONDS
LINGNENG_RAG_DEFAULT_TOP_K
LINGNENG_RAG_MAX_TOP_K
LINGNENG_RAG_CONTEXT_MAX_CHARS
```

Add:

```text
LINGNENG_RAG_HTTP_MAX_RESPONSE_BYTES
  Type: int
  Default: 1048576
  Minimum: 1024
  Meaning: maximum bytes read from the external RAG HTTP response before the
  provider returns RAG_PROVIDER_INVALID_RESULT.

LINGNENG_RAG_LIVE_TEST_ENABLED
  Type: bool
  Default: false
  Meaning: enables opt-in live RAG integration smoke tests.

LINGNENG_RAG_LIVE_TEST_QUERY
  Type: str
  Default: ""
  Meaning: query used only by opt-in live integration tests.
```

`ready_summary()` must remain secret-safe. It may expose booleans/counts only:

- `rag_configured`
- `rag_http_max_response_bytes`
- `rag_live_test_enabled`

It must not expose `LINGNENG_RAG_API_KEY`, the live test query, request payloads,
or endpoint query strings.

## HTTP Provider Contract

### Request

The provider sends the existing `RagRetrieveRequest` as JSON:

```json
{
  "query": "...",
  "tenant_id": "...",
  "user_id": "...",
  "employee_type": "...",
  "conversation_id": "...",
  "session_key": "...",
  "request_id": "...",
  "top_k": 5,
  "filters": {}
}
```

Rules:

- `query` is the direct tool argument from the model after local validation. It
  is sent to the provider but must never be echoed into public metadata on
  failure.
- `top_k` remains clamped by `rag_default_top_k` and `rag_max_top_k`.
- `filters` must be a bounded JSON object. Non-object filters become `{}`.
- Authorization uses `Authorization: Bearer <LINGNENG_RAG_API_KEY>` when a key
  is configured.
- The default HTTP client must use `trust_env=False` and `follow_redirects=False`.
- Provider code must not log request bodies or response bodies.

### Response

Canonical response shape:

```json
{
  "status": "hit",
  "context": "...",
  "citations": [],
  "metadata": {}
}
```

Accepted `status` values:

- `hit`
- `empty`
- `failed`

Old LingNengAI-compatible shape is also accepted:

```json
{
  "context": "...",
  "citations": [],
  "route_debug": {}
}
```

Normalization rules:

- If old shape has non-empty context or valid citations, derive `status="hit"`.
- If old shape has empty context and no citations, derive `status="empty"`.
- Map `route_debug` into public `metadata`.
- Ignore unknown response fields.
- Invalid JSON, invalid schema, invalid status, invalid citation list, or
  oversized response returns `RAG_PROVIDER_INVALID_RESULT`.
- Timeout returns `RAG_PROVIDER_TIMEOUT`.
- Network errors and non-2xx HTTP statuses return `RAG_PROVIDER_ERROR`.

## HTTP Safety

`HttpRagProvider` must:

- stream the response instead of reading `response.content` before enforcing the
  byte limit;
- return immediately on non-2xx status without reading the response body;
- pass a bounded chunk size to `response.iter_bytes(...)`;
- enforce `rag_http_max_response_bytes` before JSON parse;
- catch `httpx.TimeoutException` separately as `RAG_PROVIDER_TIMEOUT`;
- catch other provider/client exceptions as `RAG_PROVIDER_ERROR`;
- never include exception text, endpoint URLs, bearer tokens, local paths,
  signed URLs, raw request payloads, or raw response bodies in public results.

## Sanitization

RAG public data includes:

- `context`
- citation fields
- metadata values
- failed `message` and `context`
- downstream `citation_delta`, `rag_context`, and `final.citations`

Sanitization must cover:

- direct and percent-encoded API keys, bearer tokens, credentials, passwords,
  secrets, signed URL markers, and local paths;
- metadata keys containing `api_key`, `authorization`, `bearer`, `credential`,
  `password`, `passwd`, `secret`, `token`, `traceback`, `exception`, `history`,
  `request`, `payload`, `args`, `input`, or `query`;
- string values shaped like raw request/query/payload dumps;
- citation fields containing raw provider errors or private paths.

The sanitizer must still allow benign business text containing ordinary words
such as `request`, `query`, `input`, `token usage`, or `exception rate` when
they are not credential-shaped. Phase 14 should avoid repeating the earlier
over-sanitization problem fixed for attachment queries.

## Citation Contract

RAG citations must remain Java-compatible and safe:

```json
{
  "document_id": "doc-1",
  "source_file_id": "file-1",
  "source_file_name": "menu.pdf",
  "page_no": 2,
  "section_title": "套餐",
  "chunk_id": "chunk-1",
  "score": 0.9
}
```

Rules:

- Unknown citation fields are ignored before emitting SSE.
- Invalid citation items are dropped, not fatal.
- `score` must remain non-negative.
- Public string fields are bounded and sanitized.
- Duplicate citations are still deduped by `chunk_id` before final payloads.

## Adapter Boundary

`HermesAgentRunAdapter` currently uses:

```python
with rag_request_context(
    rag_context,
    provider=_build_rag_provider(self.settings),
):
    result = agent.run_conversation(...)
```

Phase 14 may add a helper around `_build_rag_provider(...)` so construction
failure is fail-closed and secret-safe, matching the Phase 12/13 provider
pattern. It must not change the existing toolset exposure, prompt section order,
or Java stream contract.

## Optional Live Integration Tests

Add deterministic tests with fake HTTP clients for all default verification.

Live tests may be added only if they are skipped unless all of these are true:

```text
LINGNENG_RAG_LIVE_TEST_ENABLED=true
LINGNENG_RAG_ENDPOINT is non-empty
LINGNENG_RAG_LIVE_TEST_QUERY is non-empty
```

If `LINGNENG_RAG_API_KEY` is required by the target service, it is provided by
the environment. Test output must never print the key, endpoint query string, or
raw response body.

The live test acceptance is a smoke check only:

- provider returns a valid public `retrieve_rag` result;
- result status is one of `hit`, `empty`, or `failed`;
- no secret strings are present in serialized public output.

## Test Strategy

Phase 14 should add or extend tests in:

- `tests/lingneng/config/test_settings.py`
- `tests/lingneng/tools/test_retrieve_rag.py`
- `tests/lingneng/events/test_rag_events.py`
- `tests/lingneng/runtime/test_hermes_adapter_config.py`
- optional: `tests/lingneng/integration/test_rag_provider_live.py`

Required coverage:

- settings defaults, env parsing, minimum validation, and secret-safe readiness;
- HTTP provider success request shape, Bearer auth, `trust_env=False`, and
  `follow_redirects=False`;
- response streaming byte limit, non-2xx no-body-read, timeout, invalid JSON,
  invalid schema, and old-shape normalization;
- public sanitization for context, citations, metadata, and failed results;
- benign business text containing `query`, `input`, `request`, `token usage`,
  and `exception rate` remains usable;
- adapter RAG provider construction failure degrades without `ErrorEvent`;
- existing `citation_delta`, `rag_context`, and final citation behavior remains
  compatible.

## Acceptance Criteria

Phase 14 is complete when:

1. `retrieve_rag` can call a configured external HTTP provider with bounded,
   secret-safe behavior.
2. Provider errors, invalid responses, oversized responses, and timeouts return
   public failed tool results instead of uncaught exceptions.
3. Old LingNengAI-compatible query response shape can be normalized without
   importing old `app.*` modules.
4. RAG context/citations/metadata remain Java-compatible and do not leak
   provider secrets or raw request data.
5. Live integration tests are opt-in and skipped by default.
6. Focused RAG tests, runtime adapter tests, `tests/lingneng`, ruff, and old
   `app.*` import boundary scans pass.

## Rollback

Phase 14 remains additive and fail-closed:

- Clear `LINGNENG_RAG_ENDPOINT` to disable the external provider.
- If the provider is broken or returns invalid data, `retrieve_rag` degrades to
  a public failed result and the chat stream continues.
- Reverting Phase 14 should not affect skills, attachments, generation tools,
  routing/handoff, SessionDB, or the Java stream endpoint.

## Spec Self-Review

- Scope check: this spec hardens query-time RAG provider integration only. It
  explicitly excludes training ingestion, vector indexing, reranking, workers,
  deployment, and Java changes.
- Contract check: request/response shapes preserve the existing
  `retrieve_rag`, citation, `rag_context`, and `final.citations` contracts.
- Safety check: provider errors, response size, HTTP status, timeout, secrets,
  signed URLs, local paths, raw request payloads, metadata, citations, and live
  tests all have explicit boundaries.
- Ambiguity check: live tests are opt-in, old LingNengAI response normalization
  is allowed, and full retrieval migration remains Phase 15 or later.
