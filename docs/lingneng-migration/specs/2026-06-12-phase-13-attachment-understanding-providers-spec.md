# Phase 13 Attachment Understanding Providers Spec

## Status

Drafted on `dev` after Phase 12 real business tool providers completed.

Required durable context reloaded before writing this spec:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-11-lingneng-business-capability-hermes-migration-spec.md`
- `docs/lingneng-migration/specs/2026-06-11-phase-12-real-business-tool-providers-spec.md`

Reference implementation inspected for this phase:

- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/chat_attachments/models.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/chat_attachments/service.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/chat_attachments/retrieval.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/chat_attachments/sanitization.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/chat_attachments/summarizer.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/chat/nodes/attachment_processing.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/chat/nodes/direct_attachment_answer.py`

Current Hermes-side implementation inspected:

- `lingneng/tools/attachments.py`
- `lingneng/runtime/hermes_adapter.py`
- `lingneng/config/settings.py`
- `tests/lingneng/tools/test_attachments.py`
- `tests/lingneng/runtime/test_hermes_adapter_config.py`

## Goal

Wire real LingNeng attachment-understanding provider boundaries into the Hermes
LingNeng runtime so Java request attachments can become bounded, current-turn
context for the Hermes agent.

Phase 13 upgrades the existing attachment safety shell from manually injected
test providers to configured providers while preserving the Phase 5/11 contract:

- only current request attachments are processed;
- Java `history` attachment text is never merged;
- raw attachment body text is never persisted into SessionDB by default;
- attachment context is injected as request-scoped untrusted prompt context;
- `attachment_processing` emits public `agent_step` progress;
- provider failures, timeouts, unsupported files, and unsafe input degrade
  safely without blocking the chat run.

## Scope

Phase 13 implements attachment understanding for chat-time context only.

It includes:

1. Attachment provider settings and secret-safe readiness summary fields.
2. A provider factory integrated with `HermesAgentRunAdapter`.
3. A configured external HTTP attachment-processing provider for deployments
   where an old LingNengAI-compatible or Java-side service owns parsing.
4. A small Hermes-native local text provider for safe direct text formats:
   `.txt`, `.md`, `.markdown`, `.csv`, and declared `text/*` where content is
   UTF-8 decodable.
5. Provider protocol boundaries for PDF/Office conversion, image vision, and
   Excel analysis so later work can add clients without changing the public
   attachment shell.
6. Response normalization from provider-specific per-file results into the
   existing `AttachmentProcessingResult`.
7. Strong sanitization and redaction for metadata, URLs, prompt body text,
   provider warnings, and logs.
8. Runtime wiring so `LINGNENG_AGENT_MODE=hermes` uses configured providers
   instead of relying on external `attachment_processing_context(...)` in tests.
9. Deterministic tests with fake HTTP/download/parser/vision clients. No live
   attachment service is required by CI.

## Non-Goals

Phase 13 does not:

- import old `app.*` modules from `/Users/rotas/Documents/work/hailun/LingNengAI`;
- reintroduce the old LangGraph `attachment_processing` node;
- reintroduce the old `direct_attachment_answer` node as a parallel answer path;
- add full in-Hermes PDF parsing, Office conversion, Excel analysis, OCR, or
  image vision clients backed by live services;
- add training ingestion, vector indexing, or persistent attachment memory;
- add RAG retrieval hardening beyond the current query provider;
- add deployment, CI/CD, Docker changes, or Java code changes;
- expose arbitrary filesystem reads or local upload paths to the Java API;
- persist downloaded attachment bytes or raw extracted text into SessionDB.

## Accepted Decisions

1. **Attachment context is prompt input, not memory.** The processed context is
   request-scoped and only appears in the current turn's ephemeral prompt.
2. **Provider construction is fail-closed.** Missing or broken configured
   providers must degrade to `ATTACHMENT_PROVIDER_NOT_CONFIGURED` or a sanitized
   provider failure, not adapter-level `RUNTIME_ERROR`.
3. **HTTP provider is the production bridge for rich parsing.** Phase 13 can
   call a configured external attachment-processing service when enabled. This
   allows dev/test to reuse old LingNengAI-compatible parsing while Hermes owns
   the chat runtime.
4. **Local provider is intentionally narrow.** Hermes-native local parsing in
   this phase is limited to safe text/CSV-like files using the standard library.
   PDF, Office, Excel direct answers, OCR, and vision remain explicit provider
   boundaries.
5. **No direct-answer shortcut.** Excel or attachment direct-answer behavior
   from old LingNengAI can be represented as context and/or normal Hermes
   answering later. Phase 13 does not bypass `AIAgent`.
6. **No raw provider leakage.** Provider exceptions, raw payloads, signed URLs,
   local paths, tokens, and body text must not appear in public SSE events,
   prompt warnings, logs, or ready summaries.
7. **Current request only.** Attachment providers receive only sanitized
   `request.attachments` from the current Java request, plus request metadata
   needed for correlation. They do not receive Java `history`.
8. **Step events remain adapter-owned.** `HermesAgentRunAdapter` continues to
   emit `attachment_processing` started/completed/skipped/failed events around
   prompt context building. Providers return structured status; they do not emit
   SSE events directly.

## User Confirmations Before Phase 13 Plan

No additional user confirmation is required before the Phase 13 plan if these
decisions remain true:

- Rich PDF/Office/OCR/Excel handling can be bridged through a configured
  external HTTP provider in this phase.
- The local provider may be limited to text/Markdown/CSV-style files.
- Excel direct-answer graph behavior stays out of scope; Hermes still produces
  the final answer through the normal agent loop.
- Live service tests stay disabled unless explicitly enabled later.

If any of those decisions change, update this spec before writing the plan.

## Existing Attachment Shell To Preserve

`lingneng/tools/attachments.py` already provides:

- `AttachmentProcessingProvider` protocol.
- `AttachmentProcessingRequest`.
- `AttachmentProcessingResult`.
- `AttachmentPromptContext`.
- `attachment_processing_context(provider=...)`.
- current-request selection and size/host checks.
- context timeout wrapper.
- prompt text sanitization.
- public warnings.
- `build_attachment_prompt_context(settings, request)`.

Phase 13 must keep this public surface compatible unless the plan explicitly
adds backward-compatible fields.

The existing adapter behavior remains:

```text
attachments present
  -> emit agent_step started: attachment_processing
  -> build bounded AttachmentPromptContext
  -> emit completed/skipped/failed agent_step
  -> inject prompt_text under request-scoped untrusted context
  -> run Hermes AIAgent
```

## Provider Configuration

Add explicit settings. Secret values remain environment-only and must never
appear in `ready_summary()`.

```text
LINGNENG_ATTACHMENT_PROVIDER
  Type: str
  Default: ""
  Meaning: empty disables default provider; "http" enables external HTTP
  provider; "local_text" enables the narrow local text/CSV provider.

LINGNENG_ATTACHMENT_HTTP_ENDPOINT
  Type: str
  Default: ""
  Meaning: full URL for an external attachment-processing service.

LINGNENG_ATTACHMENT_HTTP_API_KEY
  Type: secret str
  Default: ""
  Meaning: optional bearer token or internal key for the HTTP provider.

LINGNENG_ATTACHMENT_HTTP_TIMEOUT_SECONDS
  Type: float
  Default: 30.0
  Minimum: 0.1

LINGNENG_ATTACHMENT_HTTP_MAX_RESPONSE_BYTES
  Type: int
  Default: 1048576
  Minimum: 1024

LINGNENG_ATTACHMENT_LOCAL_TEXT_MAX_BYTES
  Type: int
  Default: 2097152
  Minimum: 1

LINGNENG_ATTACHMENT_LOCAL_TEXT_MAX_CHARS_PER_FILE
  Type: int
  Default: 12000
  Minimum: 500

LINGNENG_ATTACHMENT_SELECTED_CHUNK_LIMIT
  Type: int
  Default: 4
  Minimum: 1

LINGNENG_ATTACHMENT_CHUNK_SIZE
  Type: int
  Default: 3000
  Minimum: 500

LINGNENG_ATTACHMENT_CHUNK_OVERLAP
  Type: int
  Default: 300
  Minimum: 0
```

`ready_summary()` must expose booleans/counts only:

- `attachment_provider_configured`
- `attachment_http_provider_configured`
- `attachment_local_text_provider_configured`
- existing `attachment_host_allow_list_count`

## Provider Factory

Add `lingneng/tools/attachment_provider.py` or equivalent focused modules and a
factory such as:

```python
def build_attachment_processing_provider(
    settings: LingNengSettings,
) -> AttachmentProcessingProvider | None: ...
```

The factory must:

- return `None` for disabled or incomplete config;
- support `http` and `local_text`;
- fail closed on provider construction errors with secret-free warnings;
- avoid importing old `app.*` modules;
- be easy to monkeypatch in tests;
- integrate with `HermesAgentRunAdapter` so tests no longer need to wrap runtime
  calls in `attachment_processing_context(...)` for configured providers.

`HermesAgentRunAdapter.stream()` should build the attachment provider near the
other Phase 12 providers and enter:

```python
attachment_processing_context(provider=attachment_provider)
```

around the existing attachment prompt flow. Provider construction failure must
not prevent skill, handoff, RAG, or ordinary chat from running.

## External HTTP Attachment Provider

The HTTP provider is the rich parsing bridge for Phase 13.

### Request

The provider sends a bounded JSON payload to `LINGNENG_ATTACHMENT_HTTP_ENDPOINT`:

```json
{
  "request_id": "...",
  "tenant_id": "...",
  "user_id": "...",
  "session_id": "...",
  "conversation_id": "...",
  "employee_type": "...",
  "timeout_seconds": 30.0,
  "context_max_chars": 6000,
  "limits": {
    "max_files": 5,
    "max_total_bytes": 52428800,
    "max_file_bytes": 20971520,
    "max_image_bytes": 10485760
  },
  "attachments": [
    {
      "file_id": "...",
      "file_name": "...",
      "mime_type": "...",
      "size": 123,
      "download_url": "https://allowed.example/file.pdf",
      "usage": "session_context"
    }
  ]
}
```

The provider must:

- use sync `httpx.Client` or injected test client;
- set `trust_env=False` when constructing its own client;
- use `Authorization: Bearer <key>` or `X-Internal-Key` consistently with the
  configured auth mode chosen in the plan;
- enforce `LINGNENG_ATTACHMENT_HTTP_MAX_RESPONSE_BYTES`;
- reject non-JSON, non-2xx, oversized, or schema-invalid responses;
- normalize response fields into `AttachmentProcessingResult`;
- never expose raw HTTP errors, response bodies, endpoint URLs, or API keys.

### Response

Accepted response shape should be small and provider-neutral:

```json
{
  "status": "succeeded",
  "context_text": "bounded markdown/text summary",
  "processed_count": 1,
  "failed_count": 0,
  "selected_count": 1,
  "warnings": [
    {"code": "ATTACHMENT_CONTEXT_TRUNCATED", "file_id": "file-1"}
  ],
  "files": [
    {
      "file_id": "file-1",
      "file_name": "menu.pdf",
      "status": "processed",
      "mode": "pdf_text",
      "text_char_count": 1200,
      "chunk_count": 2,
      "processed_chunk_count": 1,
      "summary": "..."
    }
  ]
}
```

`files` may be retained in metadata for tests or future observability, but it
must not be injected into the prompt unless transformed into safe bounded
`context_text`.

## Local Text Attachment Provider

The local provider supports only safe text-like attachments. It should:

- download only from already selected/sanitized URLs in the request;
- use allowed hosts inherited from the existing attachment selection;
- use `httpx.Client(..., follow_redirects=False, trust_env=False)`;
- enforce `Content-Length` and streamed byte limits;
- reject private/local redirect targets by disabling redirects;
- support UTF-8 with BOM handling and fallback replacement only if safe;
- support:
  - `.txt`
  - `.md`
  - `.markdown`
  - `.csv`
  - declared `text/plain`, `text/markdown`, `text/csv`
- parse CSV with the standard library into bounded markdown-ish rows or a safe
  text table summary;
- chunk text using deterministic chunk size and overlap settings;
- select relevant chunks using lexical overlap with `request.query.content`
  when that query is made available through the request context; if the query
  is not available to the provider request in Phase 13, use file order;
- build a bounded context section per file:

```text
### file-name.ext
类型: text/csv
内容摘要/片段:
- ...
```

Because `AttachmentProcessingRequest` currently does not include the query text,
Phase 13 may add a bounded `query` field if needed. That field must come from
the current request only.

## PDF, Office, Image, And Excel Boundaries

Phase 13 does not need to implement live parsing for these file classes, but it
must define explicit extension points:

- `AttachmentDocumentParser` for PDF/document bytes -> text.
- `AttachmentOfficeConverter` for Office/Markdown -> PDF URL or bytes.
- `AttachmentVisionProvider` for image URL/bytes -> safe description.
- `AttachmentExcelAnalyzer` for one Excel file + query -> analysis context.

If not configured, unsupported rich files should return public skipped/failed
warnings, not raw exceptions.

Supported warning codes can reuse existing public warning behavior by mapping
provider-specific failures to:

- `ATTACHMENT_PROVIDER_NOT_CONFIGURED`
- `ATTACHMENT_PROVIDER_ERROR`
- `ATTACHMENT_PROVIDER_TIMEOUT`
- `ATTACHMENT_PROVIDER_INVALID_RESULT`
- `ATTACHMENT_FILE_TOO_LARGE`
- `ATTACHMENT_IMAGE_TOO_LARGE`
- `ATTACHMENT_URL_INVALID`
- `ATTACHMENT_HOST_NOT_ALLOWED`

Add new public codes only if the plan shows a concrete Java-facing need.

## Sanitization And Public Output Rules

All provider output must pass through existing or stronger sanitization before
prompt injection:

- remove control characters;
- reject or redact tokens, credentials, authorization headers, bearer strings,
  signed URLs, local paths, tracebacks, exception names, raw payload markers, and
  internal hostnames;
- redact download URLs and sensitive hostnames from body text;
- bound prompt context with `settings.attachment_context_max_chars`;
- include only safe `file_id`, `file_name`, counts, modes, and warning codes in
  public structures;
- never log attachment body text or provider response payloads.

Provider warnings returned from HTTP/local providers must be normalized through
the existing public warning allow-list. Unknown warning codes map to
`ATTACHMENT_PROVIDER_ERROR`.

## Runtime And SSE Behavior

`HermesAgentRunAdapter` behavior after Phase 13:

- No attachments: no attachment provider construction is required unless cheap.
- Attachments present but provider disabled: emit started then skipped
  `attachment_processing` agent steps; prompt gets no attachment section.
- Attachments selected and provider succeeds: emit started then completed;
  prompt gets `## LingNeng Current Request Attachments` under the existing
  request-scoped untrusted context.
- Provider timeout or failure: emit started then failed; chat continues without
  attachment context.
- Unsafe URLs/hosts/sizes: provider is not called for rejected files; step
  result is skipped or failed based on selected files and warning state.

No new SSE event names are required in Phase 13. The existing `agent_step`
contract is enough.

## Tests

Phase 13 must add or update tests covering:

- settings defaults and env parsing;
- secret-safe `ready_summary()`;
- provider factory returns `None` for incomplete config;
- provider construction failures fail closed and do not block adapter runs;
- HTTP provider request shape, auth header, timeout, `trust_env=False`, response
  normalization, max response byte enforcement, sanitized errors;
- local text provider download byte limits, unsupported file types, CSV/text
  context formatting, chunk selection, context truncation;
- URL/host/size protections continue to run before provider calls;
- provider output containing tokens, local paths, signed URLs, tracebacks, or
  old raw payload markers is removed from prompt/public output;
- `HermesAgentRunAdapter` uses configured attachment provider without test-only
  outer context;
- attachment context still appears only in current ephemeral prompt and is not
  persisted into SessionDB;
- attachment started/completed/skipped/failed step ordering remains stable;
- no old `app.*` imports from the sibling LingNengAI checkout.

Suggested focused suites:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/config/test_settings.py \
  tests/lingneng/tools/test_attachments.py \
  tests/lingneng/tools/test_attachment_providers.py \
  tests/lingneng/runtime/test_hermes_adapter_config.py \
  -q
uv run --extra dev python -m ruff check \
  lingneng/tools/attachments.py \
  lingneng/tools/attachment_provider.py \
  lingneng/runtime/hermes_adapter.py \
  tests/lingneng/tools/test_attachments.py \
  tests/lingneng/tools/test_attachment_providers.py \
  tests/lingneng/runtime/test_hermes_adapter_config.py
rg -n "from app\\.|import app\\.|/Users/rotas/Documents/work/hailun/LingNengAI/app" \
  lingneng tests/lingneng || true
```

## Acceptance Criteria

Phase 13 is complete when:

1. `LingNengSettings` exposes configured attachment provider settings with
   secret-safe readiness booleans.
2. A provider factory builds `http` or `local_text` providers and returns `None`
   for disabled/incomplete/broken config without blocking adapter runs.
3. `HermesAgentRunAdapter` enters `attachment_processing_context` with the
   configured provider around the existing attachment prompt flow.
4. The HTTP provider sends the expected bounded request, authenticates safely,
   enforces response limits, and normalizes/sanitizes provider responses.
5. The local text provider can process safe text/Markdown/CSV attachments from
   allowed hosts with byte limits and deterministic context output.
6. Unsupported PDF/Office/image/Excel cases fail or skip through public warning
   codes unless an explicit provider boundary is configured.
7. Attachment prompt context remains current-turn only and untrusted.
8. Raw attachment bytes/text, signed URLs, secrets, local paths, provider
   tracebacks, and old raw payloads do not appear in public output, logs, or
   persisted session prompts.
9. `attachment_processing` agent step behavior remains Java-compatible.
10. Focused Phase 13 tests, broader `tests/lingneng`, ruff, and old `app.*`
    import scan pass before completion.

## Rollback Notes

Phase 13 is additive and fail-closed:

- Clear `LINGNENG_ATTACHMENT_PROVIDER` to disable configured attachment
  processing.
- Clear `LINGNENG_ATTACHMENT_HTTP_ENDPOINT` or key values to disable the HTTP
  provider.
- Use `local_text` only when deployments explicitly want narrow text/CSV
  parsing in Hermes.
- Revert the Phase 13 provider/factory commits to return to the Phase 5 safety
  shell; Java stream contract remains intact.

## Spec Self-Review

- Scope check: Phase 13 is limited to chat-time attachment understanding
  providers and runtime wiring. It excludes RAG hardening, training ingestion,
  deployment, Java changes, and old graph direct-answer behavior.
- Architecture check: It keeps Hermes `AIAgent` as the only chat loop and uses
  provider protocols plus `attachment_processing_context`.
- Safety check: It preserves current-request-only processing, host/size/timeout
  limits, untrusted prompt placement, no raw persistence, and secret-free logs.
- Implementation check: The spec supports a realistic first delivery through an
  HTTP provider and narrow local text provider without requiring unavailable
  parser dependencies.
- Testability check: Every provider path can be tested with fake clients and
  no live services.
