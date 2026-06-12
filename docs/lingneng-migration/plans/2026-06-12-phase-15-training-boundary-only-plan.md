# Phase 15 Training Boundary-Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record and enforce the Phase 15 boundary-only decision: old LingNengAI remains the owner of training/indexing, while Hermes continues to query the old RAG service through the external `retrieve_rag` provider.

**Architecture:** Do not add a Hermes training worker, MQ consumer, embedding pipeline, vector indexer, or training runtime store. Add explicit training ownership settings and readiness fields, add compatibility tests proving RAG query remains independent from training mode, and add durable docs/tests that make the boundary visible after context compaction.

**Tech Stack:** Python 3.11-3.13, Pydantic v2, httpx mock transport, pytest, uv, ruff, ty.

---

## Approved Spec

This plan implements the `boundary_only` path from:

```text
docs/lingneng-migration/specs/2026-06-12-phase-15-training-rag-ingestion-migration-spec.md
```

Required durable context was reloaded before writing this plan:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-12-phase-15-training-rag-ingestion-migration-spec.md`

## Confirmed User Decision

The user selected option `1`, which is the `boundary_only` branch from the Phase
15 spec.

Locked decisions for this plan:

- Old LingNengAI remains the training/indexing owner for now.
- Hermes must not implement a second training worker in Phase 15.
- Hermes chat-time `retrieve_rag` keeps querying the configured external RAG
  endpoint; that endpoint may be backed by the old LingNengAI service.
- `LINGNENG_TRAINING_MODE` supports only `old_service` and `disabled` in this
  phase. The value `hermes` is intentionally rejected until a later
  full-migration spec/plan is approved.
- Phase 15 remains code/test/docs only. It does not add Docker, compose,
  GitHub Actions, server rollout, MQ consumers, vector providers, or embedding
  providers.

## Scope

Implement:

- explicit `training_mode` settings with `old_service` default;
- readiness summary fields that expose ownership and worker-disabled status
  without exposing endpoints, keys, URLs, file names, or task payloads;
- focused tests proving `retrieve_rag` still works when training mode is
  `old_service` or `disabled`;
- durable boundary decision documentation;
- repository guard tests proving no Hermes-side training pipeline package was
  introduced in Phase 15 and no old `app.*` runtime import was added.

Do not implement:

- `lingneng/training/` runtime package;
- training task schemas, MQ consumers, or worker APIs;
- training runtime DB/store;
- file download/parse/chunk/embed/index/activate pipeline;
- vector-store or embedding provider code;
- Java chat/SSE contract changes;
- deployment or CI/CD changes;
- old LingNengAI `app.*` imports.

## File Map

Modify:

- `lingneng/config/settings.py`
  - Add `TrainingMode = Literal["old_service", "disabled"]`.
  - Add `training_mode` field and env parsing from `LINGNENG_TRAINING_MODE`.
  - Add readiness summary keys: `training_mode`, `training_owner`,
    `training_worker_enabled`, and `training_query_source`.
- `tests/lingneng/config/test_settings.py`
  - Add settings/default/env/validation/ready-summary tests.
- `tests/lingneng/tools/test_retrieve_rag.py`
  - Add tests proving RAG query behavior is unchanged in both training modes.

Create:

- `docs/lingneng-migration/specs/2026-06-12-phase-15-training-boundary-decision.md`
  - Durable ownership decision record.
- `tests/lingneng/training/test_training_boundary.py`
  - Boundary and import guard tests.

Avoid modifying:

- `run_agent.py`
- `model_tools.py`
- `toolsets.py`
- `lingneng/runtime/hermes_adapter.py` unless an existing test demonstrates a
  real boundary bug
- old `/Users/rotas/Documents/work/hailun/LingNengAI` files

## Task 15.1: Add Training Boundary Settings

**Files:**
- Modify: `lingneng/config/settings.py`
- Modify: `tests/lingneng/config/test_settings.py`

- [ ] **Step 1: Add failing default and env tests**

Append to `tests/lingneng/config/test_settings.py`:

```python
def test_phase_15_training_boundary_settings_default_to_old_service(tmp_path):
    settings = LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})

    assert settings.training_mode == "old_service"
    assert settings.training_worker_enabled is False
    assert settings.training_owner == "old_lingnengai"
    assert settings.training_query_source == "external_rag_provider"


def test_phase_15_training_boundary_settings_can_disable_training(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_TRAINING_MODE": "disabled",
        }
    )

    assert settings.training_mode == "disabled"
    assert settings.training_worker_enabled is False
    assert settings.training_owner == "disabled"
    assert settings.training_query_source == "external_rag_provider"
```

- [ ] **Step 2: Add failing validation and ready-summary tests**

Append to `tests/lingneng/config/test_settings.py`:

```python
def test_phase_15_training_boundary_rejects_hermes_mode_until_full_migration():
    with pytest.raises(ValidationError):
        LingNengSettings.from_env({"LINGNENG_TRAINING_MODE": "hermes"})


def test_phase_15_training_ready_summary_is_secret_safe(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve?token=secret-token",
            "LINGNENG_RAG_API_KEY": "secret-rag-key",
            "LINGNENG_TRAINING_MODE": "old_service",
        }
    )

    summary = settings.ready_summary()

    assert summary["training_mode"] == "old_service"
    assert summary["training_owner"] == "old_lingnengai"
    assert summary["training_worker_enabled"] is False
    assert summary["training_query_source"] == "external_rag_provider"
    dumped = repr(summary)
    assert "secret-rag-key" not in dumped
    assert "secret-token" not in dumped
    assert "rag.example.test" not in dumped
    assert "rag_endpoint" not in summary
```

- [ ] **Step 3: Run failing settings tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/config/test_settings.py::test_phase_15_training_boundary_settings_default_to_old_service \
  tests/lingneng/config/test_settings.py::test_phase_15_training_boundary_settings_can_disable_training \
  tests/lingneng/config/test_settings.py::test_phase_15_training_boundary_rejects_hermes_mode_until_full_migration \
  tests/lingneng/config/test_settings.py::test_phase_15_training_ready_summary_is_secret_safe \
  -q
```

Expected: fail because `training_mode`, `training_worker_enabled`,
`training_owner`, and `training_query_source` do not exist yet.

- [ ] **Step 4: Implement settings**

In `lingneng/config/settings.py`, update the mode declarations near
`AgentMode`:

```python
AgentMode = Literal["fake", "hermes"]
TrainingMode = Literal["old_service", "disabled"]
```

Add this field to `LingNengSettings` after `agent_mode`:

```python
    training_mode: TrainingMode = "old_service"
```

Parse the env var in `from_env()` immediately after `agent_mode=...`:

```python
            training_mode=source.get("LINGNENG_TRAINING_MODE", "old_service"),
```

Add these properties before `ready_summary()`:

```python
    @property
    def training_worker_enabled(self) -> bool:
        return False

    @property
    def training_owner(self) -> str:
        if self.training_mode == "old_service":
            return "old_lingnengai"
        return "disabled"

    @property
    def training_query_source(self) -> str:
        return "external_rag_provider"
```

Add these keys to `ready_summary()`:

```python
            "training_mode": self.training_mode,
            "training_owner": self.training_owner,
            "training_worker_enabled": self.training_worker_enabled,
            "training_query_source": self.training_query_source,
```

- [ ] **Step 5: Run focused settings verification**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/config/test_settings.py -q
uv run --extra dev python -m ruff check \
  lingneng/config/settings.py \
  tests/lingneng/config/test_settings.py
```

Expected: all selected tests pass and ruff reports no errors.

- [ ] **Step 6: Commit and push**

```bash
git add lingneng/config/settings.py tests/lingneng/config/test_settings.py
git commit -m "feat: 增加培训边界配置"
git push origin dev
```

Rollback: revert this commit to remove the Phase 15 settings. Java chat stream
and Phase 14 RAG query behavior should remain unchanged because no runtime
adapter or tool handler should depend on the new setting.

## Task 15.2: Prove RAG Query Is Independent From Training Mode

**Files:**
- Modify: `tests/lingneng/tools/test_retrieve_rag.py`

- [ ] **Step 1: Add an old-service compatibility test**

Append to `tests/lingneng/tools/test_retrieve_rag.py`:

```python
def test_retrieve_rag_keeps_querying_external_provider_when_training_owner_is_old_service(
    tmp_path,
):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "context": "旧培训服务已经入库的知识。",
                "citations": [{"chunk_id": "chunk-old", "score": 0.9}],
            },
        )

    settings_obj = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_TRAINING_MODE": "old_service",
            "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
        }
    )
    provider = HttpRagProvider(
        settings_obj,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.retrieve(
        RagRetrieveRequest(
            query="培训后的知识能查吗",
            tenant_id="tenant-a",
            user_id="user-a",
            employee_type="marketing_content_creator",
            conversation_id="conv-a",
            session_key="tenant-a:user-a:emp-001:conv-a",
            request_id="req-001",
            top_k=3,
            filters={},
        )
    )

    assert settings_obj.training_owner == "old_lingnengai"
    assert settings_obj.training_worker_enabled is False
    assert captured["body"]["query"] == "培训后的知识能查吗"
    assert captured["body"]["tenant_id"] == "tenant-a"
    assert "training_mode" not in captured["body"]
    assert "training_owner" not in captured["body"]
    assert result.status == "hit"
    assert result.context == "旧培训服务已经入库的知识。"
```

- [ ] **Step 2: Add a disabled-mode compatibility test**

Append to `tests/lingneng/tools/test_retrieve_rag.py`:

```python
def test_retrieve_rag_query_path_still_uses_external_provider_when_training_disabled(
    tmp_path,
):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "status": "empty",
                "context": "",
                "citations": [],
                "metadata": {"retrieval_status": "empty"},
            },
        )

    settings_obj = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_TRAINING_MODE": "disabled",
            "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
        }
    )
    provider = HttpRagProvider(
        settings_obj,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.retrieve(
        RagRetrieveRequest(
            query="没有新增培训时仍可查询已有知识",
            tenant_id="tenant-a",
            user_id="user-a",
            employee_type="marketing_content_creator",
            conversation_id="conv-a",
            session_key="tenant-a:user-a:emp-001:conv-a",
            request_id="req-001",
            top_k=3,
            filters={},
        )
    )

    assert settings_obj.training_owner == "disabled"
    assert settings_obj.training_worker_enabled is False
    assert captured["body"]["query"] == "没有新增培训时仍可查询已有知识"
    assert "training_mode" not in captured["body"]
    assert "training_owner" not in captured["body"]
    assert result.status == "empty"
```

- [ ] **Step 3: Run focused failing tests**

Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/tools/test_retrieve_rag.py::test_retrieve_rag_keeps_querying_external_provider_when_training_owner_is_old_service \
  tests/lingneng/tools/test_retrieve_rag.py::test_retrieve_rag_query_path_still_uses_external_provider_when_training_disabled \
  -q
```

Expected before Task 15.1 is implemented: fail because `LINGNENG_TRAINING_MODE`
is unknown to settings. Expected after Task 15.1: pass.

- [ ] **Step 4: Run focused RAG verification**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/tools/test_retrieve_rag.py -q
uv run --extra dev python -m ruff check tests/lingneng/tools/test_retrieve_rag.py
```

Expected: all RAG retrieval tests pass and ruff reports no errors.

- [ ] **Step 5: Commit and push**

```bash
git add tests/lingneng/tools/test_retrieve_rag.py
git commit -m "test: 固化培训边界下的 RAG 查询兼容"
git push origin dev
```

Rollback: revert this commit if the compatibility tests are incorrect. It should
not change runtime code.

## Task 15.3: Document And Guard The Boundary-Only Decision

**Files:**
- Create: `docs/lingneng-migration/specs/2026-06-12-phase-15-training-boundary-decision.md`
- Create: `tests/lingneng/training/test_training_boundary.py`

- [ ] **Step 1: Add the boundary decision document**

Create `docs/lingneng-migration/specs/2026-06-12-phase-15-training-boundary-decision.md`:

```markdown
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
```

- [ ] **Step 2: Add boundary guard tests**

Create `tests/lingneng/training/test_training_boundary.py`:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BOUNDARY_DOC = (
    ROOT
    / "docs"
    / "lingneng-migration"
    / "specs"
    / "2026-06-12-phase-15-training-boundary-decision.md"
)


def test_phase_15_boundary_decision_doc_records_old_service_ownership():
    text = BOUNDARY_DOC.read_text(encoding="utf-8")

    assert "boundary_only" in text
    assert "Old LingNengAI remains the owner" in text
    assert "LINGNENG_TRAINING_MODE=old_service" in text
    assert "LINGNENG_TRAINING_MODE=disabled" in text
    assert "LINGNENG_TRAINING_MODE=hermes" in text
    assert "intentionally unsupported" in text


def test_phase_15_does_not_add_hermes_training_pipeline_package():
    assert not (ROOT / "lingneng" / "training").exists()


def test_phase_15_runtime_does_not_import_old_lingnengai_app_modules():
    runtime_files = list((ROOT / "lingneng").rglob("*.py"))
    assert runtime_files

    offenders: list[str] = []
    forbidden_fragments = (
        "from app.",
        "import app.",
        "/Users/rotas/Documents/work/hailun/LingNengAI/app",
    )
    for path in runtime_files:
        text = path.read_text(encoding="utf-8")
        if any(fragment in text for fragment in forbidden_fragments):
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []
```

- [ ] **Step 3: Run failing boundary tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/training/test_training_boundary.py -q
```

Expected: fail until the decision document is created. After adding the document
and ensuring no `lingneng/training/` package exists, pass.

- [ ] **Step 4: Run boundary verification**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/training/test_training_boundary.py -q
uv run --extra dev python -m ruff check tests/lingneng/training/test_training_boundary.py
rg -n "from app\\.|import app\\.|/Users/rotas/Documents/work/hailun/LingNengAI/app" lingneng tests/lingneng || true
```

Expected:

- pytest passes;
- ruff reports no errors;
- old `app.*` scan prints no runtime import matches.

- [ ] **Step 5: Commit and push**

```bash
git add \
  docs/lingneng-migration/specs/2026-06-12-phase-15-training-boundary-decision.md \
  tests/lingneng/training/test_training_boundary.py
git commit -m "docs: 记录培训入库边界决策"
git push origin dev
```

Rollback: revert this commit to remove only the boundary doc and guard tests.

## Phase 15 Verification

After all tasks pass their reviews, run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/config/test_settings.py \
  tests/lingneng/tools/test_retrieve_rag.py \
  tests/lingneng/training/test_training_boundary.py \
  -q
uv run --extra dev python -m pytest tests/lingneng -q
uv run --extra dev python -m ruff check lingneng tests/lingneng
uv run --extra dev ty check lingneng tests/lingneng
rg -n "from app\\.|import app\\.|/Users/rotas/Documents/work/hailun/LingNengAI/app" lingneng tests/lingneng || true
git status --short --branch
```

Expected:

- focused tests pass;
- full `tests/lingneng` passes;
- ruff passes;
- ty passes or reports only pre-existing unrelated warnings that must be
  recorded before claiming completion;
- old `app.*` scan prints no runtime import matches;
- working tree is clean after commits and pushes.

## Acceptance Checklist

- [ ] Training ownership decision is documented.
- [ ] `LINGNENG_TRAINING_MODE=old_service|disabled` exists.
- [ ] `LINGNENG_TRAINING_MODE=hermes` is rejected until full migration.
- [ ] `ready_summary()` exposes mode, owner, query source, and worker-disabled
      status without secrets or endpoints.
- [ ] Hermes does not start or define a training worker.
- [ ] RAG query still uses the configured external provider in `old_service`
      and `disabled` modes.
- [ ] No duplicate training pipeline is added.
- [ ] No old `app.*` runtime import is added.

## Rollback

This phase is rollback-safe:

- Revert Task 15.1 to remove the explicit training mode settings.
- Revert Task 15.2 to remove compatibility tests only.
- Revert Task 15.3 to remove boundary docs and guard tests.
- Java chat streaming, SessionDB history, skills, routing, attachments,
  generation tools, and Phase 14 RAG provider hardening should remain unaffected
  because this phase does not change chat route execution or tool dispatch.

## Plan Self-Review

- Spec coverage: this plan implements only the `boundary_only` acceptance path
  from the Phase 15 spec: ownership docs, `old_service|disabled` mode,
  compatibility proof, and no duplicate training pipeline.
- Scope check: no task creates MQ consumers, vector/embedding providers,
  training store, training worker, deployment, CI/CD, or Java contract changes.
- Placeholder scan: no unresolved placeholder markers or unspecified tests
  remain in task steps.
- Type consistency: `TrainingMode`, `training_mode`, `training_owner`,
  `training_worker_enabled`, and `training_query_source` are introduced in Task
  15.1 and used consistently by later tests.
- Rollback check: each task has an independent commit and can be reverted
  without touching Phase 14 RAG query behavior.
