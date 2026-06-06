# Hermes Feature Pruning Decision For LingNeng

## Status

Decision status: decision gate only, documentation-only.

This document records the current LingNeng-Hermes feature pruning decision gate.
No removal is authorized in Phase 8. No Hermes feature, file, plugin, UI
surface, channel adapter, or deployment asset is deleted, moved, disabled
globally, or changed by this document.

The decision here is intentionally conservative: keep Hermes runtime capability
available while limiting what the LingNeng Java API exposes by default. Broad
removal requires a later approved spec and plan after the evidence gates below
are satisfied.

## Kept For LingNeng

The following Hermes and LingNeng-Hermes capabilities remain kept for LingNeng
because they are part of the runtime value or the Java-compatible business
contract:

- `AIAgent` runtime for the agent loop, tool orchestration, and model calls.
- `SessionDB` plus compression for Python-owned conversation history and long
  conversation continuity.
- LingNeng API facade for `POST /internal/agent/chat/stream` compatibility.
- LingNeng toolset and skills loader for controlled employee-specific business
  behavior.
- SSE bridge for `run_started`, `agent_step`, `answer_delta`, `final`, `error`,
  RAG, citation, and artifact events.
- observability and trace summary fields for request, run, session, tool, and
  terminal-status diagnostics.
- RAG/artifact/attachment business tools, including retrieval, generated
  artifact metadata, and current-request attachment understanding.

## Disabled By Default For LingNeng API

These capabilities remain in the Hermes repository, but the LingNeng Java API
surface must not expose them by default. This is an API exposure policy, not a
repository-wide removal instruction:

- terminal and shell tools.
- code execution tools.
- arbitrary filesystem access.
- browser automation.
- cross-channel messaging.
- unrelated platform adapters.
- non-LingNeng toolsets.

The LingNeng API should continue using the dedicated LingNeng toolset and
explicit allow-list behavior described by the migration design. Operators may
keep Hermes CLI, TUI, Gateway, desktop, plugins, Cron, Kanban, and other
upstream surfaces available for non-Java development workflows until a later
approved pruning plan says otherwise.

## Future Removal Candidates

The following areas may be evaluated later, after evidence exists and after a
separate approved spec and plan define exact file, packaging, and rollback
scope:

- unused platform/channel adapters for the server runtime image.
- unused UI surfaces in production deploy packaging.
- optional plugins not needed by LingNeng server.

Future evaluation should distinguish source-tree removal from production image
packaging. Some components may remain useful for development, diagnostics, or
upstream compatibility even if they are excluded from a minimal server runtime
image.

## Required Evidence Gates

Before any broad removal or global default-disable work outside the LingNeng API
boundary, the project must have reviewed evidence for all of these gates:

- Java smoke script pass, using `scripts/lingneng-chat-smoke.py` against a
  controlled LingNeng-Hermes-compatible endpoint.
- LingNeng contract tests pass for the Java-compatible request, SSE event, API,
  runtime, toolset, session, and observability contracts.
- Docker/server deployment validation from Phase 7, including server packaging,
  health, ready, and SSE smoke evidence from the later deployment phase.
- output comparison report based on
  `docs/lingneng-migration/reports/2026-06-06-output-comparison-fixture.json`
  and
  `docs/lingneng-migration/reports/2026-06-06-output-comparison-template.md`.
- production or test soak showing stable Java integration, session continuity,
  tool behavior, trace quality, and operational safety over repeated runs.

Phase 7 deployment evidence is still pending because deployment is deferred.
Status marker: Phase 7 deployment deferred. Docker, compose, and GitHub Actions
deployment work remains outside this Task 8.3 document and is not recorded here
as completed.

## Decision Boundary

This file is a pruning decision gate only. It authorizes documentation,
classification, and evidence tracking. It does not authorize code deletion,
runtime feature removal, global disablement, deployment changes, Docker or
compose assets, GitHub Actions workflows, Java project edits, or Hermes core
runtime edits.

Phase 8 keeps the first-stage migration policy intact: LingNeng business runs on
top of Hermes, the LingNeng Java API exposes only the dedicated safe business
surface, and feature pruning waits for validated integration, deployment,
comparison, and soak evidence.
