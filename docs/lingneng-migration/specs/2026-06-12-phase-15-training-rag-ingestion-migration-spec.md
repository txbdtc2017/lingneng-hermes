# Phase 15 Training/RAG Ingestion Migration Spec

## Status

Drafted on `dev` after Phase 14 RAG provider integration hardening completed
and passed final verification.

Required durable context reloaded before writing this spec:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-11-lingneng-business-capability-hermes-migration-spec.md`
- `docs/lingneng-migration/specs/2026-06-12-phase-14-rag-provider-hardening-spec.md`

Reference implementation inspected for this phase:

- `/Users/rotas/Documents/work/hailun/LingNengAI/app/application/training_application_service.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/training/runtime_store.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/training/lifecycle_service.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/training/cancellation_service.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/domain/rag/ingestion_service.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/training/state.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/training/events.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/training/graph.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/graphs/training/nodes/*`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/mq/agent_task.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/mq/agent_task_result.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/workers/training_consumer.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/infra/vector_store/base.py`
- `/Users/rotas/Documents/work/hailun/LingNengAI/app/providers/embedding/base.py`

Current Hermes-side implementation inspected:

- `lingneng/tools/rag.py`
- `lingneng/runtime/hermes_adapter.py`
- `lingneng/config/settings.py`
- `lingneng/tools/attachments.py`
- `lingneng/tools/attachment_provider.py`
- `lingneng/tools/document_provider.py`
- `lingneng/tools/providers.py`
- `lingneng/events/bridge.py`
- `lingneng/session/run_store.py`
- `lingneng/observability/logging.py`

## Goal

Define the migration path for LingNeng training ingestion and RAG indexing from
the old LingNengAI service into this Hermes fork, without disrupting the already
working Java chat stream.

Phase 15 is about the worker/storage/indexing side of RAG, not the chat answer
loop. It must make an explicit product decision visible before execution:

```text
Do we retire the old LingNengAI training/indexing service now, or keep it as the
owner while Hermes only queries it?
```

If the product decision is to retire the old service, Phase 15 migrates the
training task contracts, lifecycle state, cancellation behavior, ingestion
pipeline, embedding/vector-store writes, activation/finalization, and task
result events into Hermes-native modules.

If the product decision is not to retire the old service yet, Phase 15 should
stop after documenting the compatibility boundary and should not implement a
parallel training worker.

## Scope

When full migration is approved, Phase 15 includes:

1. Java/MQ-compatible training task schemas for created and cancel-requested
   messages.
2. Java/MQ-compatible task result schemas for status, summary delta, completed,
   failed, and cancelled events.
3. A Hermes-side training runtime store with idempotency, terminal event retry,
   cancellation flags, and safe persistence.
4. A training lifecycle service that owns queued/running/cancelling/terminal
   transitions and emits task result messages through a provider boundary.
5. A training ingestion processor or graph with explicit stages:
   validation, skill snapshot loading, file download, parse/conversion, image
   understanding, scope filtering, cleaning, chunking, embedding, indexing,
   summary generation, activation, cancellation, and finalization.
6. Provider protocols for message bus, file download, office/PDF conversion,
   document parsing, image understanding, embedding, vector store, object
   storage, and summary generation.
7. RAG chunk and metadata models compatible with Phase 14 query/citation
   contracts.
8. Safe task output sanitization so result events never leak credentials,
   signed URLs, raw downloaded files, local paths, raw embeddings, or raw
   provider exceptions.
9. Deterministic in-memory/fake providers for tests and local validation.
10. Optional live integration tests for MQ/vector/embedding/storage providers
    behind explicit environment gates.

## Non-Goals

Phase 15 does not:

- change Java chat request or SSE contracts for `/internal/agent/chat/stream`;
- make RAG a pre-agent router or bypass the Hermes `AIAgent` loop;
- reintroduce Java `history` as Agent context;
- import old `app.*` modules from `/Users/rotas/Documents/work/hailun/LingNengAI`
  at runtime;
- require live Milvus, Redis, RocketMQ, MinIO, embedding, OCR, office conversion,
  or LLM services in default tests;
- expose training operations as normal chat tools to the Java chat endpoint;
- store raw downloaded files, raw attachment text, raw embeddings, or raw
  provider responses in Hermes SessionDB;
- replace Phase 14 external query provider behavior before the new indexer is
  validated;
- add Docker, CI/CD, deployment scripts, or server rollout changes.

## Accepted Decisions

1. **Training is not a chat-path feature.** The Java chat endpoint should keep
   working even if training ingestion is disabled or handled by the old service.
2. **The old service remains the safe fallback.** Until the product explicitly
   switches training ownership, old LingNengAI remains the training/indexing
   owner and Hermes `retrieve_rag` queries the configured endpoint.
3. **Runtime imports stay clean.** Old LingNengAI code is reference-only.
   Hermes modules must define their own schemas, protocols, processors, and
   tests.
4. **Provider boundaries are mandatory.** Vector store, embedding, MQ, object
   storage, conversion, OCR, parser, image understanding, and summary services
   are injected through protocols. Tests use fake providers by default.
5. **Idempotency is first-class.** `idempotency_key` on created/cancel messages
   is part of the public contract and must prevent duplicate work and duplicate
   terminal events.
6. **Cancellation is cooperative.** Cancellation is checked between expensive
   stages and before activation; already indexed chunks must be marked
   cancelled/ineffective if cancellation wins before activation.
7. **Activation is atomic at the task level.** Newly indexed chunks are written
   as `document_status="indexing"` and `effective=False`; only after successful
   embedding/indexing/summary should the task activate chunks and deactivate
   replaced active chunks for the same scope/source files.
8. **Public events are sanitized.** Task result events can include counts,
   warnings, public summaries, and stable error codes, but not secrets, signed
   URLs, raw files, raw request payloads, tracebacks, local paths, or raw
   embedding vectors.
9. **Phase 14 query path remains valid.** Full ingestion migration must not
   break the external HTTP RAG query provider or the safe failure behavior added
   in Phase 14.

## User Confirmations Before Phase 15 Plan

These confirmations are required before writing the Phase 15 implementation
plan:

1. **Training ownership decision.** Choose one:
   - `full_migration`: implement Hermes-native training ingestion/indexing and
     prepare to retire the old training service.
   - `boundary_only`: keep old LingNengAI as the training/indexing owner for now
     and only document or test the compatibility boundary in this repository.
2. **Provider target.** If `full_migration`, confirm whether the first
   executable plan should use deterministic in-memory/vector fake providers only,
   or should wire a real vector/embedding provider behind opt-in settings.
3. **MQ boundary.** Confirm whether Hermes should consume the same Java/MQ
   `agent.task.created` and `agent.task.cancel_requested` messages directly, or
   expose an internal Python worker API that another adapter can feed.
4. **Storage boundary.** Confirm whether raw downloaded files may be stored in a
   temporary runtime directory during processing, or must remain memory-only in
   the first implementation.
5. **Deployment boundary.** Confirm that Phase 15 remains code/test only and
   does not add worker Docker/compose/GitHub Actions deployment assets.

If these decisions are not confirmed, do not write the Phase 15 plan and do not
implement the worker. This prevents accidentally creating a second training
system beside the old one.

## Existing Contracts To Preserve

### Created Message

The old training intake contract is:

```json
{
  "schema_version": "1.0",
  "event_id": "evt-1",
  "event_type": "agent.task.created",
  "request_id": "req-1",
  "task_id": "task-1",
  "idempotency_key": "idem-1",
  "task_type": "training",
  "tenant_id": "tenant-a",
  "user_id": "user-a",
  "employee_id": "emp-1",
  "employee_type": "marketing_content_creator",
  "payload": {
    "skill_id": "training-summary-report",
    "skill_version": "1.0",
    "skill_hash": "sha256:...",
    "files": [
      {
        "file_id": "file-1",
        "file_name": "menu.pdf",
        "mime_type": "application/pdf",
        "size": 1024,
        "download_url": "https://files.example.test/menu.pdf",
        "download_url_expires_at": "2026-06-12T12:00:00Z"
      }
    ]
  },
  "produced_at": "2026-06-12T10:00:00Z"
}
```

Rules:

- `task_type` must be `training`.
- `payload.files` must be non-empty for actual processing.
- `download_url` is never echoed in public results.
- `skill_id`, `skill_version`, and `skill_hash` are recorded as a snapshot but
  must not become executable instructions.

### Cancel Requested Message

The old cancellation contract is:

```json
{
  "schema_version": "1.0",
  "event_id": "evt-cancel-1",
  "event_type": "agent.task.cancel_requested",
  "request_id": "req-cancel-1",
  "task_id": "task-1",
  "idempotency_key": "task-1:cancel",
  "task_type": "training",
  "tenant_id": "tenant-a",
  "user_id": "user-a",
  "employee_id": "emp-1",
  "employee_type": "marketing_content_creator",
  "reason": "user_cancelled",
  "requested_at": "2026-06-12T10:01:00Z"
}
```

If the idempotency key is omitted, Hermes should derive
`{task_id}:cancel` for compatibility.

### Result Events

Phase 15 must preserve these event names and public payload classes:

- `agent.task.status.changed`
- `agent.task.summary_delta`
- `agent.task.completed`
- `agent.task.failed`
- `agent.task.cancelled`

`status.changed` uses:

```text
status: queued | running | cancelling | succeeded | cancelled | failed
stage: validate | download | parse | image_understanding | cleaning |
       chunking | embedding | indexing | summarizing | activating |
       cancelling
progress: 0..100
message: public Chinese status text
```

Terminal events must be emitted at most once per terminal transition. If
publishing fails, the runtime store must record retry-needed state so the
terminal event can be retried without re-running the full task.

## Runtime State Model

Hermes should define a training runtime state equivalent to:

```text
task_id
request_id
tenant_id
user_id
employee_type
employee_id
runtime_status: queued | running | activating | cancelling
terminal_status: succeeded | failed | cancelled | null
cancel_requested
cancel_requested_at
terminal_event_emitted
retry_needed
pending_terminal_event
created_idempotency_keys
cancel_idempotency_keys
created_at
updated_at
terminal_at
```

Persistence requirements:

- The first implementation may use SQLite under `LINGNENG_RUNTIME_DIR`.
- Tests may use an in-memory store.
- `(idempotency_key -> task_id)` mapping must survive process restarts when
  using the persistent store.
- Terminal status must be compare-and-set protected so a task cannot complete
  and cancel simultaneously.
- Public state dumps must not include raw files, raw embeddings, provider
  exceptions, signed URLs, or local paths.

## Ingestion Pipeline

The full migration pipeline is:

1. `validate_task`
   - Validate schema, task type, required files, tenant/user/employee scope.
   - Fail with `NO_EFFECTIVE_KNOWLEDGE` if there are no files.
2. `load_skill_snapshot`
   - Record `skill_id`, `skill_version`, and `skill_hash`.
   - Do not inject skill text into the worker as trusted code.
3. `download_files`
   - Fetch each file through a file-download provider.
   - Enforce allowed hosts, max file count, per-file bytes, total bytes, and
     timeout settings.
   - Add `FILE_DOWNLOAD_FAILED` warnings per failed file.
4. `parse_files`
   - Parse office/PDF/text files through a parser/conversion provider.
   - Add `FILE_PARSE_FAILED` warnings per failed file.
5. `understand_images`
   - Process image files through an OCR/vision/image-understanding provider when
     enabled.
   - Skipped images must be counted and warned without failing the whole task.
6. `scope_filter`
   - Keep only content relevant to the task scope:
     tenant/user/employee_type/employee_id.
   - Deterministic filter first; LLM classification requires a later dedicated
     spec.
7. `clean_documents`
   - Trim blank lines, normalize text, drop empty elements.
   - Do not keep raw document text outside the pipeline state.
8. `chunk_documents`
   - Build layout-aware chunks with source file, page, section, and index
     metadata.
   - Fail with `ALL_FILES_FAILED` or `NO_EFFECTIVE_KNOWLEDGE` when appropriate.
9. `embed_chunks`
   - Batch through an embedding provider if configured.
   - Validate embedding count and dimension.
   - Fail with public codes for provider, count, or dimension errors.
10. `index_chunks_as_indexing`
    - Upsert chunks with `document_status="indexing"` and `effective=False`.
11. `summarize_training`
    - Produce public summary deltas and a final summary. Deterministic
      rule-based summary is acceptable by default; LLM summary is provider-gated.
12. `activate_knowledge`
    - Deactivate previous active chunks in the same scope/source files.
    - Mark current task chunks `document_status="active"` and `effective=True`.
13. `finalize_completed`
    - Emit completed terminal event with counts, public summary, structured
      result, and warnings.
14. `finalize_cancelled`
    - Mark task chunks cancelled/ineffective and emit cancelled terminal event.
15. `finalize_failed`
    - Mark task chunks failed/ineffective where possible and emit failed
      terminal event.

Cancellation must be checked after download, parse, image understanding,
chunking, embedding, indexing, and before activation.

## RAG Chunk And Metadata Contract

Phase 15 should define Hermes-owned chunk models compatible with Phase 14
citations:

```text
text
embedding
metadata:
  tenant_id
  user_id
  employee_type
  employee_id
  task_id
  document_id
  chunk_id
  source_file_id
  source_file_name
  content_type
  document_status: indexing | active | cancelled | failed
  effective
  page_no
  section_title
  chunk_index
  created_at
  updated_at
  embedding_model
  embedding_dim
  failed_reason
```

Rules:

- `chunk_id` must be stable within a task.
- `document_id` can be `{task_id}_{source_file_id}` unless a Java-provided
  document id is added later.
- `effective=True` is only allowed with `document_status="active"`.
- Query-time citations must not expose raw chunk text or raw embeddings.

## Provider Boundaries

Phase 15 should add protocols, not hard dependencies:

- `TrainingMessageBus`
  - `publish(topic, message)`
  - fake implementation records events for tests.
- `TrainingFileReader`
  - `read(training_file) -> bytes`
  - validates allowed hosts, size, timeout.
- `TrainingDocumentParser`
  - `parse_content(training_file, content) -> list[DocumentElement]`
  - may wrap existing attachment/document provider logic when compatible.
- `TrainingOfficeConverter`
  - converts office files to PDF/text through a configured Java/internal
    service when enabled.
- `TrainingImageUnderstandingProvider`
  - returns bounded public image summaries or skipped warnings.
- `TrainingEmbeddingProvider`
  - `embed_batch(texts) -> list[list[float]]`.
- `TrainingVectorStore`
  - `upsert_chunks`, `update_status_by_task`,
    `deactivate_previous_active_chunks`, and search methods needed by future
    full retrieval.
- `TrainingSummaryProvider`
  - deterministic summary by default; optional LLM summary behind settings.

Provider failures must map to public error codes and messages.

## Configuration

Phase 15 should add settings only when implementation is approved. Candidate
settings:

```text
LINGNENG_TRAINING_MODE=old_service|hermes|disabled
LINGNENG_TRAINING_RUNTIME_DB_PATH
LINGNENG_TRAINING_RESULT_TOPIC
LINGNENG_TRAINING_MAX_FILES
LINGNENG_TRAINING_MAX_FILE_BYTES
LINGNENG_TRAINING_MAX_TOTAL_BYTES
LINGNENG_TRAINING_DOWNLOAD_TIMEOUT_SECONDS
LINGNENG_TRAINING_ALLOWED_DOWNLOAD_HOSTS
LINGNENG_TRAINING_EMBEDDING_PROVIDER
LINGNENG_TRAINING_EMBEDDING_MODEL
LINGNENG_TRAINING_EMBEDDING_DIM
LINGNENG_TRAINING_EMBEDDING_BATCH_SIZE
LINGNENG_TRAINING_VECTOR_PROVIDER
LINGNENG_TRAINING_LIVE_TEST_ENABLED
```

`ready_summary()` may expose booleans, limits, provider names, and configured
mode. It must not expose API keys, endpoints with query strings, signed URLs,
download URLs, vector credentials, raw file names from live tasks, or live test
queries.

## Error Codes

Public terminal errors should include stable codes:

- `INVALID_TASK`
- `NO_EFFECTIVE_KNOWLEDGE`
- `ALL_FILES_FAILED`
- `FILE_DOWNLOAD_FAILED`
- `FILE_PARSE_FAILED`
- `EMBEDDING_PROVIDER_FAILED`
- `EMBEDDING_COUNT_MISMATCH`
- `EMBEDDING_DIMENSION_MISMATCH`
- `VECTOR_UPSERT_FAILED`
- `VECTOR_ACTIVATION_FAILED`
- `VECTOR_CANCELLATION_FAILED`
- `TRAINING_CANCELLED`
- `TRAINING_FAILED`

Provider exception text and tracebacks must not be returned.

## Observability

Logs and trace summaries should include:

- `task_id`
- `request_id`
- `tenant_id`
- `user_id`
- `employee_type`
- `employee_id`
- current stage
- runtime status
- terminal status
- counts: files, documents, images, chunks, warnings
- provider names

Logs and trace summaries must not include:

- download URLs
- signed URL query strings
- API keys or bearer tokens
- raw file bytes or raw extracted text
- raw embeddings
- provider exception text
- local temporary paths

## Test Strategy

Default tests must be deterministic and offline:

- schema tests for created/cancel/result events;
- runtime store tests for idempotency, terminal CAS, retry-needed state, and
  cancellation;
- lifecycle tests for running, completion, failure, cancellation, terminal
  retry, and duplicate messages;
- processor tests for partial download/parse failures, all-file failures, empty
  knowledge, chunking, embedding count/dimension failures, vector upsert
  failure, activation failure, cancellation before activation, and public
  result sanitization;
- event bridge tests for status progress order, summary deltas, and terminal
  events;
- provider boundary tests for allowed hosts, size/time limits, fake embeddings,
  fake vector store state transitions, and no secret leakage;
- import boundary scans proving no old `app.*` runtime import;
- regression tests proving Phase 14 `retrieve_rag` still works when
  `LINGNENG_TRAINING_MODE` is `old_service` or `disabled`.

Optional live integration tests may exist only if skipped unless explicit
environment gates are enabled for each provider.

## Acceptance Criteria

If `full_migration` is approved, Phase 15 is complete when:

1. Hermes has its own training task schemas and result event schemas compatible
   with the old Java/MQ contracts.
2. Hermes has a persistent runtime store with idempotency, cancellation, and
   terminal retry behavior.
3. A deterministic offline training processor can ingest fake files, produce
   chunks, index them into a fake vector store, activate them, summarize them,
   and emit result events.
4. Cancellation before activation marks indexed chunks ineffective and emits one
   cancelled terminal event.
5. Failures emit public stable error codes without leaking provider exception
   text or private data.
6. Phase 14 chat-time `retrieve_rag` behavior remains compatible and safe.
7. Focused training tests, `tests/lingneng`, ruff, ty for touched files, and old
   `app.*` import scans pass.

If `boundary_only` is selected, Phase 15 is complete when:

1. The training ownership decision is documented.
2. Hermes keeps `LINGNENG_TRAINING_MODE=old_service|disabled` and does not start
   a training worker.
3. Compatibility tests or docs prove chat-time RAG can keep querying the old
   service while training/indexing remain there.
4. No duplicate training pipeline is added.

## Rollback

Phase 15 must be rollback-safe:

- Set `LINGNENG_TRAINING_MODE=old_service` or `disabled` to stop Hermes-side
  training ingestion.
- Keep Phase 14 external RAG query settings working so chat can continue using
  the old RAG query endpoint.
- Do not delete old-service compatibility config until production has migrated
  training and indexing.
- Reverting Phase 15 should not affect Java chat streaming, skills, routing,
  attachments, generation tools, or Phase 14 RAG query hardening.

## Spec Self-Review

- Scope check: this spec covers training/RAG ingestion and indexing only; it
  does not modify chat SSE, Java chat request contracts, deployment, CI/CD, or
  Hermes core.
- Decision check: the spec explicitly blocks planning/execution until the user
  chooses `full_migration` or `boundary_only`.
- Contract check: old training created/cancel/result event contracts are
  preserved and rewritten as Hermes-owned schemas, not imported from old
  `app.*` modules.
- Safety check: idempotency, cancellation, activation, provider boundaries,
  secret-safe results, live test gates, and rollback have explicit boundaries.
- Ambiguity check: first executable implementation depends on the training
  ownership decision; no plan should be written until that is confirmed.
