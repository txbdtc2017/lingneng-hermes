# Phase 0 Contract Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce durable Java HTTP/SSE contract and GitHub workflow baseline documents before runtime implementation starts.

**Architecture:** This is a documentation-only phase. It reads the current LingNengAI request/event/schema references, records the externally visible contract in this Hermes fork, and records the GitHub branch/CI assumptions that later phases must follow.

**Tech Stack:** Markdown, LingNengAI Pydantic contract references, pytest contract tests, git.

---

## Approved Spec

This plan implements:

```text
docs/lingneng-migration/specs/2026-06-06-phase-0-contract-baseline-spec.md
```

## Scope

Phase 0 creates two baseline documents:

- `docs/lingneng-migration/specs/2026-06-06-lingneng-java-contract-baseline.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-github-workflow-baseline.md`

## Non-Goals

- Do not modify Java code.
- Do not create `lingneng/` runtime modules.
- Do not add API routes, toolsets, Docker assets, GitHub Actions workflows, or runtime tests in this phase.
- Do not change Hermes core files.
- Do not infer unobserved deployment details; record only accepted future boundaries and observed repository state.

## Decision Points Before Execution

There are no user-blocking decisions for Phase 0. If a command cannot run, record the exact command and failure output in the relevant baseline document.

## File Map

- `docs/lingneng-migration/specs/2026-06-06-lingneng-java-contract-baseline.md`: Java-facing request, session, SSE, heartbeat, event order, and reference test baseline.
- `docs/lingneng-migration/specs/2026-06-06-lingneng-github-workflow-baseline.md`: GitHub remote, branch flow, GitHub Actions target, and deferred deployment boundary.

## Required Context Reload

Before executing any task, read these files in order:

```bash
sed -n '1,260p' LINGNENG_MIGRATION_CONTEXT.md
sed -n '1,620p' docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md
sed -n '1,1050p' docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md
sed -n '1,260p' docs/lingneng-migration/specs/2026-06-06-phase-0-contract-baseline-spec.md
```

Expected: all files exist and confirm that Phase 0 is documentation-only.

---

## Task 0.1: Capture LingNeng Java Contract Baseline

**Files:**
- Create: `docs/lingneng-migration/specs/2026-06-06-lingneng-java-contract-baseline.md`
- Read: `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_request.py`
- Read: `/Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_events.py`
- Read: `/Users/rotas/Documents/work/hailun/LingNengAI/app/api/internal/chat_stream.py`
- Read: `/Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py`
- Read: `/Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_stream_event_order.py`

- [ ] **Step 1: Reload durable migration context**

Run:

```bash
sed -n '1,260p' LINGNENG_MIGRATION_CONTEXT.md
sed -n '1,620p' docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md
sed -n '1,1050p' docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md
sed -n '1,260p' docs/lingneng-migration/specs/2026-06-06-phase-0-contract-baseline-spec.md
```

Expected: the context confirms Java compatibility, Python-owned session history, `request_id` idempotency, and Phase 0 documentation-only scope.

- [ ] **Step 2: Read LingNengAI contract references**

Run:

```bash
sed -n '1,260p' /Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_request.py
sed -n '1,340p' /Users/rotas/Documents/work/hailun/LingNengAI/app/schemas/http/chat_events.py
sed -n '1,260p' /Users/rotas/Documents/work/hailun/LingNengAI/app/api/internal/chat_stream.py
sed -n '1,260p' /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py
sed -n '1,260p' /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_stream_event_order.py
```

Expected: the files show `ChatStreamRequest`, typed SSE event models, `encode_sse`, heartbeat behavior, and contract tests.

- [ ] **Step 3: Run the reference event contract test**

Run:

```bash
python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py -q
```

Expected: pass in the LingNengAI reference environment. If it fails because dependencies or imports are unavailable from this Hermes checkout, copy the exact command, exit status, and first relevant failure lines into the baseline document.

- [ ] **Step 4: Write the Java contract baseline document**

Create `docs/lingneng-migration/specs/2026-06-06-lingneng-java-contract-baseline.md` with these exact sections:

```markdown
# LingNeng Java Contract Baseline

## Source References

## HTTP Entrypoint

## Request Model Baseline

## Employee Identity Baseline

## Session And History Policy

## Attachment Baseline

## SSE Encoding Baseline

## Formal SSE Event Names

## Minimum Phase 1 Event Subset

## Event Payload Baseline

## Event Order Baseline

## Heartbeat Baseline

## Error Event Baseline

## Reference Test Result

## Phase 1 Implementation Notes
```

Fill the sections with these concrete facts from the references:

- Endpoint is `POST /internal/agent/chat/stream`.
- Response media type is `text/event-stream`.
- Request model accepts unknown extra fields through `ConfigDict(extra="ignore")`.
- Required top-level fields are `request_id`, `tenant_id`, `user_id`, `session_id`, `query`, `employee`, `system_prompt`, and `skill`.
- `conversation_id` is optional and accepts alias `conversationId`.
- `query` contains `message_id`, required `content`, and `content_type` defaulting to `text`.
- `employee` contains optional `employee_id`, required `employee_type`, and optional `display_name`.
- Employee types are `boss_assistant`, `operation_specialist`, `product_combo_advisor`, `marketing_planner`, `marketing_content_creator`, and `member_operator`.
- `system_prompt` contains `content` and optional `version`.
- `skill` contains `skill_id`, `skill_version`, `skill_hash`, and optional `inline`.
- `history` contains user/assistant messages, but LingNeng-Hermes must not merge Java `history` into Hermes Agent context.
- `history_options`, `attachments`, `runtime_context`, `stream_options`, `model_options`, `regenerate`, and `routing` are accepted structured fields.
- Attachment fields are `file_id`, `file_name`, `mime_type`, optional `size`, `download_url`, optional `download_url_expires_at`, and `usage` defaulting to `session_context`.
- SSE encoder format is `event: <event_name>\ndata: <json>\n\n` with `ensure_ascii=False`.
- Heartbeat frame is `: ping\n\n`.
- Heartbeat interval in the reference is `15.0` seconds.
- Formal P1 event names are `run_started`, `agent_step`, `route_result`, `route_suggestion`, `route_confirm_required`, `citation_delta`, `rag_context`, `artifact_created`, `answer_delta`, `final`, `compliance_block`, and `error`.
- Reference auxiliary event models also include `tool_started`, `tool_result`, and `console_debug`; they are not part of the formal LingNeng-Hermes P1 event name set unless a later phase explicitly adopts them.
- Minimum Phase 1 event subset is `run_started`, `answer_delta`, `final`, and `error`.
- `run_started` payload includes at least `run_id` and `request_id`.
- `answer_delta` payload includes `text` and optional `sequence`.
- `final` payload includes `run_id`, `status`, `answer`, optional `route`, `citations`, `artifacts`, `degradation_codes`, and `trace_summary`.
- `error` payload includes `code` and `message`; the total LingNeng-Hermes design requires future runtime errors to also carry `run_id`, `request_id`, `trace_id`, and `recoverable`.
- Event order baseline requires early progress before answer deltas when agent steps are enabled, answer deltas before final, exactly one final in successful streams, and joined `answer_delta.text` equals `final.answer` when final answer is non-empty.

- [ ] **Step 5: Validate text quality for the contract baseline**

Run:

```bash
rg -n "[T]BD|[T]ODO|fill[ ]in|implement[ ]later|待[补]充|待[定]|占[位]|Jenkins|Gitea" docs/lingneng-migration/specs/2026-06-06-lingneng-java-contract-baseline.md
grep -n '[[:blank:]]$' docs/lingneng-migration/specs/2026-06-06-lingneng-java-contract-baseline.md
```

Expected: both commands exit with no matches. If `rg` or `grep` exits `1` because no matches were found, that is a pass for these checks.

- [ ] **Step 6: Self-review against the Phase 0 spec**

Check that the baseline document records:

- Required request fields and notable optional fields.
- `conversation_id` and `conversationId` compatibility.
- Employee identity fields.
- Java `history` policy.
- Attachment fields.
- Formal event names and minimum Phase 1 subset.
- Event order, heartbeat, and SSE encoding.
- Reference test command and observed result.

Expected: every Phase 0 contract baseline requirement is covered.

- [ ] **Step 7: Commit and push Task 0.1**

Run:

```bash
git status --short
git add LINGNENG_MIGRATION_CONTEXT.md \
  docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md \
  docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md \
  docs/lingneng-migration/specs/2026-06-06-phase-0-contract-baseline-spec.md \
  docs/lingneng-migration/plans/2026-06-06-phase-0-contract-baseline-plan.md \
  docs/lingneng-migration/specs/2026-06-06-lingneng-java-contract-baseline.md
git commit -m "docs: 记录灵能 Java 接口基线"
git push origin dev
```

Expected: commit and push succeed only after the validation above passes.

---

## Task 0.2: Capture GitHub Workflow Baseline

**Files:**
- Create: `docs/lingneng-migration/specs/2026-06-06-lingneng-github-workflow-baseline.md`

- [ ] **Step 1: Reload durable migration context**

Run:

```bash
sed -n '1,260p' LINGNENG_MIGRATION_CONTEXT.md
sed -n '1,620p' docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md
sed -n '1,1050p' docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md
sed -n '1,260p' docs/lingneng-migration/specs/2026-06-06-phase-0-contract-baseline-spec.md
sed -n '1,360p' docs/lingneng-migration/plans/2026-06-06-phase-0-contract-baseline-plan.md
```

Expected: the context confirms GitHub Actions is the future CI/CD target and Docker/server deployment is deferred.

- [ ] **Step 2: Record observed git remote**

Run:

```bash
git remote -v
git status --short --branch
```

Expected: `origin` is observed from the current checkout. Record the exact `git remote -v` output in the baseline document.

- [ ] **Step 3: Write the GitHub workflow baseline document**

Create `docs/lingneng-migration/specs/2026-06-06-lingneng-github-workflow-baseline.md` with these exact sections:

```markdown
# LingNeng GitHub Workflow Baseline

## Repository Remote

## Branch Flow

## CI/CD Target

## Deferred Deployment Boundary

## Phase Execution Rules

## Secrets And Environment Boundary

## Observed Commands

## Phase 1 Planning Notes
```

Fill the sections with these concrete facts:

- The checkout is treated as GitHub-hosted.
- Observed remote is `git@github.com:txbdtc2017/lingneng-hermes.git` for both fetch and push when that is what `git remote -v` prints.
- Runtime implementation work happens on `dev`.
- Validation and promotion flow uses `test`.
- Future automation targets GitHub Actions.
- Jenkins and Gitea are not the target CI/CD surfaces for this repository.
- Docker image build, compose deployment, server deploy scripts, rollback, and GitHub Actions deployment workflows are deferred until the later deployment phase.
- Secrets must not be committed. Future GitHub Actions should use repository or environment secrets for LLM keys, Java internal keys, search keys, and image registry credentials.
- Every phase follows `phase spec -> phase plan -> subagent-driven execution`.
- After context compaction, reload `LINGNENG_MIGRATION_CONTEXT.md`, the total runtime design spec, and the master implementation plan before writing specs, plans, runtime code, verification, commits, or pushes.

- [ ] **Step 4: Validate text quality for the workflow baseline**

Run:

```bash
rg -n "[T]BD|[T]ODO|fill[ ]in|implement[ ]later|待[补]充|待[定]|占[位]" docs/lingneng-migration/specs/2026-06-06-lingneng-github-workflow-baseline.md
grep -n '[[:blank:]]$' docs/lingneng-migration/specs/2026-06-06-lingneng-github-workflow-baseline.md
```

Expected: both commands exit with no matches. If `rg` or `grep` exits `1` because no matches were found, that is a pass for these checks.

- [ ] **Step 5: Self-review against the Phase 0 spec**

Check that the baseline document records:

- GitHub-hosted repository assumption.
- Implementation on `dev`.
- Validation flow through `test`.
- GitHub Actions as future CI/CD target.
- Deployment work deferred.
- Observed `git remote -v` output.

Expected: every Phase 0 GitHub workflow baseline requirement is covered.

- [ ] **Step 6: Commit and push Task 0.2**

Run:

```bash
git status --short
git add docs/lingneng-migration/specs/2026-06-06-lingneng-github-workflow-baseline.md
git commit -m "docs: 记录灵能 GitHub 工作流基线"
git push origin dev
```

Expected: commit and push succeed only after the validation above passes.

---

## Phase 0 Final Verification

After Tasks 0.1 and 0.2 complete, run:

```bash
rg -n "[T]BD|[T]ODO|fill[ ]in|implement[ ]later|待[补]充|待[定]|占[位]" \
  docs/lingneng-migration/specs/2026-06-06-phase-0-contract-baseline-spec.md \
  docs/lingneng-migration/plans/2026-06-06-phase-0-contract-baseline-plan.md \
  docs/lingneng-migration/specs/2026-06-06-lingneng-java-contract-baseline.md \
  docs/lingneng-migration/specs/2026-06-06-lingneng-github-workflow-baseline.md
grep -n '[[:blank:]]$' \
  docs/lingneng-migration/specs/2026-06-06-phase-0-contract-baseline-spec.md \
  docs/lingneng-migration/plans/2026-06-06-phase-0-contract-baseline-plan.md \
  docs/lingneng-migration/specs/2026-06-06-lingneng-java-contract-baseline.md \
  docs/lingneng-migration/specs/2026-06-06-lingneng-github-workflow-baseline.md
rg -n "Jenkins|Gitea" \
  docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md \
  docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md \
  docs/lingneng-migration/specs/2026-06-06-phase-0-contract-baseline-spec.md \
  docs/lingneng-migration/plans/2026-06-06-phase-0-contract-baseline-plan.md \
  docs/lingneng-migration/specs/2026-06-06-lingneng-java-contract-baseline.md \
  docs/lingneng-migration/specs/2026-06-06-lingneng-github-workflow-baseline.md
git log --oneline -2
git status --short --branch
```

Expected:

- Unfinished-marker and trailing whitespace checks have no matches.
- Jenkins/Gitea references appear only where a baseline or plan instruction explicitly states they are not target CI/CD surfaces, or not at all.
- The last two commits are the Phase 0 task commits.
- The working tree is clean or contains only unrelated user changes.

## Rollback Notes

- To undo Task 0.1 only, revert the `docs: 记录灵能 Java 接口基线` commit.
- To undo Task 0.2 only, revert the `docs: 记录灵能 GitHub 工作流基线` commit.
- Do not use `git reset --hard`; preserve unrelated user changes.
