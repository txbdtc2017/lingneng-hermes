# Phase 15 Training Boundary Decision

## Decision

Phase 15 uses the `boundary_only` path.

Old LingNengAI remains the owner of:

- training task intake;
- file download, parsing, cleaning, chunking, embedding, and vector indexing;
- training task cancellation;
- training task status/result events;
- activation/deactivation of indexed knowledge.

LingNeng-Hermes remains the owner of:

- Java-compatible chat streaming;
- Hermes-managed conversation history;
- LingNeng skill/tool runtime;
- chat-time `retrieve_rag` calls through the configured external RAG endpoint;
- RAG result sanitization and SSE citation/context events.

## Runtime Modes

`LINGNENG_TRAINING_MODE=old_service` means training and indexing stay in the old
LingNengAI service. Hermes may still call `LINGNENG_RAG_ENDPOINT` at chat time.

`LINGNENG_TRAINING_MODE=disabled` means Hermes does not own or start training
ingestion. Existing RAG query configuration remains a separate chat-time setting.

`LINGNENG_TRAINING_MODE=hermes` is intentionally unsupported in this phase. It
requires a later full-migration spec and plan before any Hermes-side worker,
embedding provider, vector store, or MQ consumer is added.

## Non-Goals

Phase 15 boundary-only does not add:

- `lingneng/training/` runtime package;
- training schemas or MQ consumers;
- training runtime DB/store;
- file download/parse/chunk/embed/index/activate pipeline;
- embedding or vector providers;
- deployment, compose, GitHub Actions, or server rollout changes.

## Compatibility Contract

The chat-time RAG contract remains:

```text
Hermes retrieve_rag tool -> configured external HTTP RAG provider
```

The external provider may be the old LingNengAI dev/test RAG service. Hermes
must not import old `app.*` modules and must not know whether the queried
knowledge was indexed by the old service or by a future replacement.

## Rollback

Set `LINGNENG_TRAINING_MODE=old_service` to keep using the old service as the
training/indexing owner. Set `LINGNENG_TRAINING_MODE=disabled` to make the
training boundary explicitly inactive. Reverting this decision document and the
boundary settings must not affect Java chat streaming or Phase 14 RAG query
hardening.
