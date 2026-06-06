# Phase 1 Java-Compatible API MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the smallest Java-compatible LingNeng-Hermes HTTP/SSE API with fake-agent streaming, strict request/SSE contracts, session key resolution, and request idempotency.

**Architecture:** Add an isolated `lingneng/` package that owns config, schemas, session keys, run idempotency, fake runtime events, SSE encoding, FastAPI auth, and Java-compatible routes. Phase 1 deliberately avoids Hermes `AIAgent`, `SessionDB`, business tools, Docker, deployment scripts, and GitHub Actions workflow files.

**Tech Stack:** Python 3.11-3.13, Pydantic v2, FastAPI, Starlette `TestClient`, SQLite, pytest. Existing dependencies in `pyproject.toml` already include `pydantic==2.13.4`, `fastapi>=0.104.0,<1`, `uvicorn[standard]>=0.24.0,<1`, and dev pytest dependencies.

---

## Approved Inputs

- Master context: `LINGNENG_MIGRATION_CONTEXT.md`
- Master design: `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- Master roadmap: `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- Phase spec: `docs/lingneng-migration/specs/2026-06-06-phase-1-java-compatible-api-mvp-spec.md`
- Java baseline: `docs/lingneng-migration/specs/2026-06-06-lingneng-java-contract-baseline.md`
- GitHub baseline: `docs/lingneng-migration/specs/2026-06-06-lingneng-github-workflow-baseline.md`

## Execution Order

Execute tasks in this exact order:

1. Task 1.1 Settings
2. Task 1.2 Request schemas
3. Task 1.3 SSE event schemas and encoder
4. Task 1.4 Session key resolver
5. Task 1.5 SQLite run store
6. Task 1.6 Fake adapter and event bridge
7. Task 1.7 FastAPI app, routes, auth, health, ready, and phase verification

Each task must follow:

```text
reload durable context -> write failing tests -> run focused test and confirm expected failure -> implement -> run focused test -> run task review checks -> commit in Chinese -> push dev
```

Do not start Task N+1 until Task N is verified, committed, and pushed.

## User Confirmations Before Execution

No additional user confirmation is required before Phase 1 execution. The Phase 1 spec locks:

- `X-Internal-Key` as the internal auth header.
- `.runtime/lingneng` as the default runtime directory.
- `fake` as the default Phase 1 agent mode.
- FastAPI app remains independent of Hermes dashboard and gateway code.
- Deployment, Docker, GitHub Actions workflows, real Hermes `AIAgent`, tools, RAG, skills, and artifacts remain outside Phase 1.

## Shared Worker Rules

- Work in `/Users/rotas/Documents/work/hailun/demos/lingneng-hermes`.
- Do not use git worktrees.
- Do not modify Java code or `/Users/rotas/Documents/work/hailun/LingNengAI`.
- Do not edit `run_agent.py`, `model_tools.py`, `toolsets.py`, `hermes_state.py`, `gateway/platforms/api_server.py`, or `hermes_cli/web_server.py` in Phase 1.
- Run repository-local pytest commands through `uv run --extra dev python -m pytest`. If the first `uv run` needs to create the environment, allow it to sync the declared dev dependencies.
- Use `apply_patch` for manual edits.
- Keep secrets out of source. `ready` responses must never return `internal_api_key`.
- No local server is required. All route tests use `fastapi.testclient.TestClient`.
- If a local server is manually started for debugging, first run `lsof -nP -iTCP:18083 -sTCP:LISTEN` and do not kill unrelated processes.
- After each task, run `git diff --check` before commit.
- Commit messages are Chinese conventional-prefix messages listed per task.
- Push `origin dev` after each verified task commit.

## File Map

Runtime modules created in Phase 1:

- `lingneng/__init__.py`: package marker and Phase 1 runtime version string.
- `lingneng/config/__init__.py`: config package exports.
- `lingneng/config/settings.py`: environment-driven `LingNengSettings` and auth readiness helpers.
- `lingneng/schemas/__init__.py`: schema package exports.
- `lingneng/schemas/chat_request.py`: Java-compatible request Pydantic models.
- `lingneng/schemas/chat_events.py`: LingNeng SSE event Pydantic models.
- `lingneng/api/__init__.py`: API package marker.
- `lingneng/api/sse.py`: SSE frame encoder and heartbeat helper.
- `lingneng/api/auth.py`: `X-Internal-Key` validation and unsafe configuration checks.
- `lingneng/api/app.py`: `create_app(settings=None, adapter=None, run_store=None)`.
- `lingneng/api/routes.py`: health, ready, and stream route registration.
- `lingneng/api/server.py`: uvicorn entrypoint for local and future Docker reuse.
- `lingneng/session/__init__.py`: session package exports.
- `lingneng/session/keys.py`: `ResolvedSessionKey` and `resolve_session_key`.
- `lingneng/session/run_store.py`: SQLite `LingNengRunStore`.
- `lingneng/runtime/__init__.py`: runtime package exports.
- `lingneng/runtime/agent_adapter.py`: `AgentRunAdapter` protocol.
- `lingneng/runtime/fake_agent.py`: deterministic `FakeAgentRunAdapter`.
- `lingneng/events/__init__.py`: event package exports.
- `lingneng/events/bridge.py`: helper functions that stamp LingNeng event models.
- `pyproject.toml`: add `lingneng` and `lingneng.*` to setuptools package discovery.

Tests created in Phase 1:

- `tests/lingneng/config/test_settings.py`
- `tests/lingneng/config/test_packaging.py`
- `tests/lingneng/schemas/test_chat_request_schema.py`
- `tests/lingneng/schemas/test_chat_event_schema.py`
- `tests/lingneng/api/test_sse_encoding.py`
- `tests/lingneng/session/test_session_key_resolver.py`
- `tests/lingneng/session/test_run_store.py`
- `tests/lingneng/runtime/test_agent_adapter_contract.py`
- `tests/lingneng/api/test_chat_stream_contract.py`

## Shared Contract Values

Employee types:

```python
[
    "boss_assistant",
    "operation_specialist",
    "product_combo_advisor",
    "marketing_planner",
    "marketing_content_creator",
    "member_operator",
]
```

Formal SSE event names:

```python
[
    "run_started",
    "agent_step",
    "route_result",
    "route_suggestion",
    "route_confirm_required",
    "citation_delta",
    "rag_context",
    "artifact_created",
    "answer_delta",
    "final",
    "compliance_block",
    "error",
]
```

Shared Java payload shape for tests:

```python
def full_payload() -> dict:
    return {
        "request_id": "req-001",
        "tenant_id": "tenant-a",
        "user_id": "user-a",
        "session_id": "session-a",
        "conversation_id": "conv-a",
        "query": {
            "message_id": "msg-001",
            "content": "请生成一段会员运营文案",
            "content_type": "text",
        },
        "employee": {
            "employee_id": "emp-001",
            "employee_type": "marketing_content_creator",
            "display_name": "营销内容员工",
        },
        "system_prompt": {
            "content": "你是灵能营销内容员工。",
            "version": "v1",
        },
        "skill": {
            "skill_id": "skill-marketing-content",
            "skill_version": "2026-06-06",
            "skill_hash": "sha256-test",
            "inline": {"summary": "写作技能"},
        },
        "history": [
            {"message_id": "h-1", "role": "user", "content": "上一轮用户问题"},
            {"message_id": "h-2", "role": "assistant", "content": "上一轮回答"},
        ],
        "history_options": {
            "source": "java_payload",
            "max_history_tokens": 4096,
        },
        "attachments": [
            {
                "file_id": "file-001",
                "file_name": "brief.pdf",
                "mime_type": "application/pdf",
                "size": 1234,
                "download_url": "https://files.example.test/brief.pdf",
                "download_url_expires_at": "2026-06-07T00:00:00+08:00",
                "usage": "session_context",
            }
        ],
        "runtime_context": {
            "timezone": "Asia/Shanghai",
            "region": "CN",
        },
        "stream_options": {
            "include_agent_steps": True,
            "include_citations": True,
            "include_rag_context": False,
            "ignored_stream_option": "ignored",
        },
        "model_options": {
            "enable_internal_reasoning": False,
            "ignored_model_option": "ignored",
        },
        "regenerate": {
            "enabled": False,
            "from_message_id": None,
            "extra_instruction": None,
        },
        "routing": {
            "confirmed_employee_type": "marketing_content_creator",
            "confirmation_message_id": "confirm-001",
        },
        "unknown_java_field": "ignored",
    }
```

## Review Checks For Every Task

Run these before each task commit:

```bash
git diff --check
rg -n "T[B]D|T[O]DO|t[o]do|fill[[:space:]]in|implement[[:space:]]later|place[h]older|待[补]充|待[定]|占[位]" lingneng tests/lingneng docs/lingneng-migration/plans/2026-06-06-phase-1-java-compatible-api-mvp-plan.md
```

Expected:

- `git diff --check` exits 0.
- The `rg` command exits 1 with no matches.

---

### Task 1.1: Add LingNeng Settings

**Files:**
- Create: `lingneng/__init__.py`
- Create: `lingneng/config/__init__.py`
- Create: `lingneng/config/settings.py`
- Modify: `pyproject.toml`
- Create: `tests/lingneng/config/test_settings.py`
- Create: `tests/lingneng/config/test_packaging.py`

- [ ] **Step 1: Reload durable context**

Run:

```bash
sed -n '1,180p' LINGNENG_MIGRATION_CONTEXT.md
sed -n '1,220p' docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md
sed -n '1,430p' docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md
sed -n '1,560p' docs/lingneng-migration/specs/2026-06-06-phase-1-java-compatible-api-mvp-spec.md
```

Expected: files describe Phase 1 as fake-agent-only and no deployment work.

- [ ] **Step 2: Write failing settings tests**

Create `tests/lingneng/config/test_settings.py` with tests equivalent to:

```python
from pathlib import Path

from lingneng.config.settings import LingNengSettings


def test_default_settings_are_local_safe():
    settings = LingNengSettings.from_env({})

    assert settings.app_env == "dev"
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 18083
    assert settings.runtime_dir == Path(".runtime/lingneng")
    assert settings.agent_mode == "fake"
    assert settings.internal_api_key == ""
    assert settings.allow_insecure_local is False
    assert settings.session_retention_days == 90
    assert settings.archived_session_retention_days == 180
    assert settings.idempotency_retention_days == 7
    assert settings.heartbeat_interval_seconds == 15.0


def test_environment_overrides_are_parsed(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_API_HOST": "127.0.0.2",
            "LINGNENG_API_PORT": "18084",
            "LINGNENG_RUNTIME_DIR": str(tmp_path / "runtime"),
            "LINGNENG_AGENT_MODE": "fake",
            "LINGNENG_INTERNAL_API_KEY": "secret-value",
            "LINGNENG_ALLOW_INSECURE_LOCAL": "true",
            "LINGNENG_SESSION_RETENTION_DAYS": "91",
            "LINGNENG_ARCHIVED_SESSION_RETENTION_DAYS": "181",
            "LINGNENG_IDEMPOTENCY_RETENTION_DAYS": "8",
            "LINGNENG_HEARTBEAT_INTERVAL_SECONDS": "12.5",
        }
    )

    assert settings.app_env == "test"
    assert settings.api_host == "127.0.0.2"
    assert settings.api_port == 18084
    assert settings.runtime_dir == tmp_path / "runtime"
    assert settings.internal_api_key == "secret-value"
    assert settings.allow_insecure_local is True
    assert settings.session_retention_days == 91
    assert settings.archived_session_retention_days == 181
    assert settings.idempotency_retention_days == 8
    assert settings.heartbeat_interval_seconds == 12.5


def test_from_env_none_reads_process_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("LINGNENG_APP_ENV", "test")
    monkeypatch.setenv("LINGNENG_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("LINGNENG_INTERNAL_API_KEY", "secret")

    settings = LingNengSettings.from_env()

    assert settings.app_env == "test"
    assert settings.runtime_dir == tmp_path / "runtime"
    assert settings.internal_api_key == "secret"


def test_auth_readiness_boundaries():
    dev_unsafe = LingNengSettings.from_env({})
    dev_insecure_allowed = LingNengSettings.from_env(
        {"LINGNENG_ALLOW_INSECURE_LOCAL": "true"}
    )
    prod_missing_key = LingNengSettings.from_env(
        {"LINGNENG_APP_ENV": "prod", "LINGNENG_INTERNAL_API_KEY": ""}
    )
    prod_with_key = LingNengSettings.from_env(
        {"LINGNENG_APP_ENV": "prod", "LINGNENG_INTERNAL_API_KEY": "secret"}
    )

    assert dev_unsafe.is_local_like is True
    assert dev_unsafe.auth_required is False
    assert dev_unsafe.is_chat_configuration_ready is False
    assert dev_insecure_allowed.is_chat_configuration_ready is True
    assert prod_missing_key.is_local_like is False
    assert prod_missing_key.is_chat_configuration_ready is False
    assert prod_with_key.auth_required is True
    assert prod_with_key.is_chat_configuration_ready is True


def test_ready_summary_redacts_secret(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "prod",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_INTERNAL_API_KEY": "secret-value",
        }
    )

    summary = settings.ready_summary()

    assert summary["status"] == "ready"
    assert summary["app_env"] == "prod"
    assert summary["agent_mode"] == "fake"
    assert summary["runtime_dir"] == str(tmp_path)
    assert summary["auth_required"] is True
    assert "secret-value" not in repr(summary)
    assert "internal_api_key" not in summary
```

Create `tests/lingneng/config/test_packaging.py` with:

```python
import tomllib
from pathlib import Path


def test_lingneng_package_is_in_setuptools_find_include():
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    include = data["tool"]["setuptools"]["packages"]["find"]["include"]

    assert "lingneng" in include
    assert "lingneng.*" in include
```

- [ ] **Step 3: Run the focused test and confirm failure**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/config/test_settings.py tests/lingneng/config/test_packaging.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'lingneng'`, missing
`LingNengSettings`, or missing `lingneng` package discovery entries.

- [ ] **Step 4: Implement settings**

Create `lingneng/__init__.py`:

```python
"""LingNeng runtime facade for this Hermes fork."""

__all__ = ["__version__"]

__version__ = "0.1.0-phase1"
```

Create `lingneng/config/__init__.py`:

```python
"""Configuration helpers for LingNeng runtime modules."""

from lingneng.config.settings import LingNengSettings

__all__ = ["LingNengSettings"]
```

Create `lingneng/config/settings.py` with:

```python
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field


_LOCAL_ENVS = {"local", "dev", "test"}


def _bool_from_env(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class LingNengSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_env: str = "dev"
    api_host: str = "127.0.0.1"
    api_port: int = 18083
    runtime_dir: Path = Path(".runtime/lingneng")
    agent_mode: str = "fake"
    internal_api_key: str = Field(default="", repr=False)
    allow_insecure_local: bool = False
    session_retention_days: int = 90
    archived_session_retention_days: int = 180
    idempotency_retention_days: int = 7
    heartbeat_interval_seconds: float = 15.0

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None
    ) -> "LingNengSettings":
        source = os.environ if env is None else env
        return cls(
            app_env=source.get("LINGNENG_APP_ENV", "dev"),
            api_host=source.get("LINGNENG_API_HOST", "127.0.0.1"),
            api_port=int(source.get("LINGNENG_API_PORT", "18083")),
            runtime_dir=Path(
                source.get("LINGNENG_RUNTIME_DIR", ".runtime/lingneng")
            ),
            agent_mode=source.get("LINGNENG_AGENT_MODE", "fake"),
            internal_api_key=source.get("LINGNENG_INTERNAL_API_KEY", ""),
            allow_insecure_local=_bool_from_env(
                source.get("LINGNENG_ALLOW_INSECURE_LOCAL"), False
            ),
            session_retention_days=int(
                source.get("LINGNENG_SESSION_RETENTION_DAYS", "90")
            ),
            archived_session_retention_days=int(
                source.get("LINGNENG_ARCHIVED_SESSION_RETENTION_DAYS", "180")
            ),
            idempotency_retention_days=int(
                source.get("LINGNENG_IDEMPOTENCY_RETENTION_DAYS", "7")
            ),
            heartbeat_interval_seconds=float(
                source.get("LINGNENG_HEARTBEAT_INTERVAL_SECONDS", "15.0")
            ),
        )

    @property
    def is_local_like(self) -> bool:
        return self.app_env.lower() in _LOCAL_ENVS

    @property
    def auth_required(self) -> bool:
        return bool(self.internal_api_key)

    @property
    def is_chat_configuration_ready(self) -> bool:
        if self.internal_api_key:
            return True
        return self.is_local_like and self.allow_insecure_local

    def ready_summary(self) -> dict[str, object]:
        return {
            "status": "ready"
            if self.is_chat_configuration_ready
            else "not_ready",
            "app_env": self.app_env,
            "agent_mode": self.agent_mode,
            "runtime_dir": str(self.runtime_dir),
            "auth_required": self.auth_required,
        }
```

Modify `[tool.setuptools.packages.find].include` in `pyproject.toml` to preserve
all existing package names and append these two entries:

```toml
"lingneng"
"lingneng.*"
```

- [ ] **Step 5: Run the focused test and confirm pass**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/config/test_settings.py tests/lingneng/config/test_packaging.py -q
```

Expected: PASS.

- [ ] **Step 6: Review, commit, and push**

Run:

```bash
git diff --check
rg -n "T[B]D|T[O]DO|t[o]do|fill[[:space:]]in|implement[[:space:]]later|place[h]older|待[补]充|待[定]|占[位]" lingneng tests/lingneng docs/lingneng-migration/plans/2026-06-06-phase-1-java-compatible-api-mvp-plan.md
git status --short
git add pyproject.toml lingneng/__init__.py lingneng/config/__init__.py lingneng/config/settings.py tests/lingneng/config/test_settings.py tests/lingneng/config/test_packaging.py
git commit -m "feat: 增加灵能运行配置"
git push origin dev
```

Expected:

- `git diff --check` exits 0.
- `rg` exits 1 with no matches.
- Commit succeeds.
- Push updates `origin/dev`.

Rollback: revert this task commit if settings behavior blocks Task 1.2.

---

### Task 1.2: Add Java-Compatible Request Schemas

**Files:**
- Create: `lingneng/schemas/__init__.py`
- Create: `lingneng/schemas/chat_request.py`
- Create: `tests/lingneng/schemas/test_chat_request_schema.py`

- [ ] **Step 1: Reload durable context**

Run the same reload commands from Task 1.1 Step 1. Confirm Phase 1 still excludes real Hermes `AIAgent`.

- [ ] **Step 2: Write failing request schema tests**

Create `tests/lingneng/schemas/test_chat_request_schema.py` with:

```python
import pytest
from pydantic import ValidationError

from lingneng.schemas.chat_request import ChatStreamRequest, EmployeeType


def full_payload() -> dict:
    return {
        "request_id": "req-001",
        "tenant_id": "tenant-a",
        "user_id": "user-a",
        "session_id": "session-a",
        "conversation_id": "conv-a",
        "query": {
            "message_id": "msg-001",
            "content": "请生成一段会员运营文案",
            "content_type": "text",
        },
        "employee": {
            "employee_id": "emp-001",
            "employee_type": "marketing_content_creator",
            "display_name": "营销内容员工",
        },
        "system_prompt": {"content": "你是灵能营销内容员工。", "version": "v1"},
        "skill": {
            "skill_id": "skill-marketing-content",
            "skill_version": "2026-06-06",
            "skill_hash": "sha256-test",
            "inline": {"summary": "写作技能"},
        },
        "history": [
            {"message_id": "h-1", "role": "user", "content": "上一轮用户问题"},
            {"message_id": "h-2", "role": "assistant", "content": "上一轮回答"},
        ],
        "history_options": {"source": "java_payload", "max_history_tokens": 4096},
        "attachments": [
            {
                "file_id": "file-001",
                "file_name": "brief.pdf",
                "mime_type": "application/pdf",
                "size": 1234,
                "download_url": "https://files.example.test/brief.pdf",
                "download_url_expires_at": "2026-06-07T00:00:00+08:00",
                "usage": "session_context",
            }
        ],
        "runtime_context": {"timezone": "Asia/Shanghai", "region": "CN"},
        "stream_options": {
            "include_agent_steps": True,
            "include_citations": True,
            "include_rag_context": False,
            "ignored_stream_option": "ignored",
        },
        "model_options": {
            "enable_internal_reasoning": False,
            "ignored_model_option": "ignored",
        },
        "regenerate": {
            "enabled": False,
            "from_message_id": None,
            "extra_instruction": None,
        },
        "routing": {
            "confirmed_employee_type": "marketing_content_creator",
            "confirmation_message_id": "confirm-001",
        },
        "unknown_java_field": "ignored",
    }


def test_parses_full_java_payload():
    request = ChatStreamRequest.model_validate(full_payload())

    assert request.request_id == "req-001"
    assert request.tenant_id == "tenant-a"
    assert request.user_id == "user-a"
    assert request.session_id == "session-a"
    assert request.conversation_id == "conv-a"
    assert request.query.content == "请生成一段会员运营文案"
    assert request.query.content_type == "text"
    assert request.employee.employee_id == "emp-001"
    assert request.employee.employee_type is EmployeeType.MARKETING_CONTENT_CREATOR
    assert request.system_prompt.content == "你是灵能营销内容员工。"
    assert request.skill.skill_id == "skill-marketing-content"
    assert len(request.history) == 2
    assert request.history_options.max_history_tokens == 4096
    assert request.attachments[0].file_id == "file-001"
    assert request.runtime_context.timezone == "Asia/Shanghai"
    assert request.stream_options.include_agent_steps is True
    assert request.model_options.enable_internal_reasoning is False
    assert request.regenerate.enabled is False
    assert request.routing.confirmed_employee_type is EmployeeType.MARKETING_CONTENT_CREATOR
    assert not hasattr(request, "unknown_java_field")


def test_accepts_conversation_id_alias():
    payload = full_payload()
    payload.pop("conversation_id")
    payload["conversationId"] = "conv-alias"

    request = ChatStreamRequest.model_validate(payload)

    assert request.conversation_id == "conv-alias"


def test_defaults_for_structured_optional_fields():
    payload = full_payload()
    for key in [
        "history",
        "history_options",
        "attachments",
        "runtime_context",
        "stream_options",
        "model_options",
        "regenerate",
        "routing",
    ]:
        payload.pop(key)

    request = ChatStreamRequest.model_validate(payload)

    assert request.history == []
    assert request.history_options.source == "java_payload"
    assert request.history_options.max_history_tokens == 4096
    assert request.attachments == []
    assert request.runtime_context.timezone == "Asia/Shanghai"
    assert request.runtime_context.region == "CN"
    assert request.stream_options.include_citations is True
    assert request.stream_options.include_rag_context is False
    assert request.model_options.enable_internal_reasoning is False
    assert request.regenerate.enabled is False
    assert request.routing.confirmed_employee_type is None


@pytest.mark.parametrize("content", ["", "   "])
def test_rejects_empty_query_content(content):
    payload = full_payload()
    payload["query"]["content"] = content

    with pytest.raises(ValidationError):
        ChatStreamRequest.model_validate(payload)


def test_rejects_unknown_employee_type():
    payload = full_payload()
    payload["employee"]["employee_type"] = "unknown_employee"

    with pytest.raises(ValidationError):
        ChatStreamRequest.model_validate(payload)
```

- [ ] **Step 3: Run the focused test and confirm failure**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/schemas/test_chat_request_schema.py -q
```

Expected: FAIL with missing `lingneng.schemas.chat_request`.

- [ ] **Step 4: Implement request schemas**

Create `lingneng/schemas/__init__.py`:

```python
"""LingNeng Java-compatible request and event schemas."""
```

Create `lingneng/schemas/chat_request.py` with Pydantic v2 models:

```python
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EmployeeType(str, Enum):
    BOSS_ASSISTANT = "boss_assistant"
    OPERATION_SPECIALIST = "operation_specialist"
    PRODUCT_COMBO_ADVISOR = "product_combo_advisor"
    MARKETING_PLANNER = "marketing_planner"
    MARKETING_CONTENT_CREATOR = "marketing_content_creator"
    MEMBER_OPERATOR = "member_operator"


class QueryPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message_id: str | None = None
    content: str
    content_type: str = "text"

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query.content must not be empty")
        return value


class EmployeePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    employee_id: str | None = None
    employee_type: EmployeeType
    display_name: str | None = None


class SystemPromptPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str
    version: str | None = None


class SkillPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    skill_id: str
    skill_version: str
    skill_hash: str
    inline: dict[str, Any] | str | None = None


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message_id: str | None = None
    role: Literal["user", "assistant"]
    content: str


class HistoryOptions(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: str = "java_payload"
    max_history_tokens: int = 4096


class AttachmentPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    file_id: str
    file_name: str
    mime_type: str
    size: int | None = None
    download_url: str
    download_url_expires_at: str | None = None
    usage: str = "session_context"


class RuntimeContext(BaseModel):
    model_config = ConfigDict(extra="ignore")

    timezone: str = "Asia/Shanghai"
    region: str = "CN"


class StreamOptions(BaseModel):
    model_config = ConfigDict(extra="ignore")

    include_agent_steps: bool = True
    include_citations: bool = True
    include_rag_context: bool = False


class ModelOptions(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enable_internal_reasoning: bool = False


class RegenerateOptions(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    from_message_id: str | None = None
    extra_instruction: str | None = None


class RoutingOptions(BaseModel):
    model_config = ConfigDict(extra="ignore")

    confirmed_employee_type: EmployeeType | None = None
    confirmation_message_id: str | None = None


class ChatStreamRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    request_id: str
    tenant_id: str
    user_id: str
    session_id: str
    conversation_id: str | None = Field(default=None, alias="conversationId")
    query: QueryPayload
    employee: EmployeePayload
    system_prompt: SystemPromptPayload
    skill: SkillPayload
    history: list[HistoryMessage] = Field(default_factory=list)
    history_options: HistoryOptions = Field(default_factory=HistoryOptions)
    attachments: list[AttachmentPayload] = Field(default_factory=list)
    runtime_context: RuntimeContext = Field(default_factory=RuntimeContext)
    stream_options: StreamOptions = Field(default_factory=StreamOptions)
    model_options: ModelOptions = Field(default_factory=ModelOptions)
    regenerate: RegenerateOptions = Field(default_factory=RegenerateOptions)
    routing: RoutingOptions = Field(default_factory=RoutingOptions)
```

- [ ] **Step 5: Run the focused test and confirm pass**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/schemas/test_chat_request_schema.py -q
```

Expected: PASS.

- [ ] **Step 6: Review, commit, and push**

Run review checks from the shared section, then:

```bash
git add lingneng/schemas/__init__.py lingneng/schemas/chat_request.py tests/lingneng/schemas/test_chat_request_schema.py
git commit -m "feat: 增加灵能请求协议模型"
git push origin dev
```

Rollback: revert this task commit if schema parsing blocks Task 1.4.

---

### Task 1.3: Add SSE Event Schemas And Encoder

**Files:**
- Create: `lingneng/schemas/chat_events.py`
- Create: `lingneng/api/__init__.py`
- Create: `lingneng/api/sse.py`
- Create: `tests/lingneng/schemas/test_chat_event_schema.py`
- Create: `tests/lingneng/api/test_sse_encoding.py`

- [ ] **Step 1: Reload durable context**

Run the reload commands from Task 1.1 Step 1. Confirm the Java baseline SSE encoder uses `json.dumps(data, ensure_ascii=False)`.

- [ ] **Step 2: Write failing event schema tests**

Create `tests/lingneng/schemas/test_chat_event_schema.py` with:

```python
from lingneng.schemas.chat_events import (
    AnswerDeltaEvent,
    ErrorEvent,
    FINAL_STATUSES,
    FORMAL_EVENT_NAMES,
    FinalEvent,
    RunStartedEvent,
)


def test_formal_event_names_match_lingneng_p1_contract():
    assert FORMAL_EVENT_NAMES == [
        "run_started",
        "agent_step",
        "route_result",
        "route_suggestion",
        "route_confirm_required",
        "citation_delta",
        "rag_context",
        "artifact_created",
        "answer_delta",
        "final",
        "compliance_block",
        "error",
    ]


def test_phase_1_event_payloads_dump_without_event_field():
    started = RunStartedEvent(run_id="run-1", request_id="req-1")
    delta = AnswerDeltaEvent(text="你好", sequence=1)
    final = FinalEvent(run_id="run-1", status="succeeded", answer="你好")
    error = ErrorEvent(
        run_id="run-1",
        request_id="req-1",
        code="RUNTIME_ERROR",
        message="运行失败",
        trace_id="trace-1",
        recoverable=False,
    )

    assert started.model_dump() == {"run_id": "run-1", "request_id": "req-1"}
    assert delta.model_dump() == {"text": "你好", "sequence": 1}
    assert final.model_dump() == {
        "run_id": "run-1",
        "status": "succeeded",
        "answer": "你好",
        "citations": [],
        "artifacts": [],
    }
    assert error.model_dump() == {
        "run_id": "run-1",
        "request_id": "req-1",
        "code": "RUNTIME_ERROR",
        "message": "运行失败",
        "trace_id": "trace-1",
        "recoverable": False,
    }
    assert "event" not in final.model_dump()
    assert "tool_plan" not in final.model_dump()


def test_final_statuses_include_required_values():
    assert FINAL_STATUSES == {"succeeded", "degraded", "failed", "blocked"}
```

Create `tests/lingneng/api/test_sse_encoding.py` with:

```python
from lingneng.api.sse import encode_sse, heartbeat_frame


def test_encode_sse_uses_event_line_and_utf8_json():
    assert (
        encode_sse("answer_delta", {"text": "你好"})
        == 'event: answer_delta\ndata: {"text": "你好"}\n\n'
    )


def test_encode_sse_does_not_require_event_in_data():
    frame = encode_sse("final", {"answer": "完成"})

    assert frame.startswith("event: final\n")
    assert '"event"' not in frame


def test_heartbeat_frame_is_comment_ping():
    assert heartbeat_frame() == ": ping\n\n"
```

- [ ] **Step 3: Run the focused tests and confirm failure**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/schemas/test_chat_event_schema.py tests/lingneng/api/test_sse_encoding.py -q
```

Expected: FAIL with missing `lingneng.schemas.chat_events` or `lingneng.api.sse`.

- [ ] **Step 4: Implement event schemas and SSE encoder**

Create `lingneng/schemas/chat_events.py` with:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


FORMAL_EVENT_NAMES = [
    "run_started",
    "agent_step",
    "route_result",
    "route_suggestion",
    "route_confirm_required",
    "citation_delta",
    "rag_context",
    "artifact_created",
    "answer_delta",
    "final",
    "compliance_block",
    "error",
]

FINAL_STATUSES = {"succeeded", "degraded", "failed", "blocked"}
FinalStatus = Literal["succeeded", "degraded", "failed", "blocked"]


class RunStartedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    request_id: str


class AnswerDeltaEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    sequence: int


class FinalEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    status: FinalStatus
    answer: str
    citations: list[dict] = Field(default_factory=list)
    artifacts: list[dict] = Field(default_factory=list)


class ErrorEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    request_id: str
    code: str
    message: str
    trace_id: str
    recoverable: bool
```

Create `lingneng/api/__init__.py`:

```python
"""FastAPI facade for the LingNeng Java-compatible runtime."""
```

Create `lingneng/api/sse.py`:

```python
from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel

_DONE = object()


def _jsonable(data: Any) -> Any:
    if isinstance(data, BaseModel):
        return data.model_dump()
    return data


def encode_sse(event_name: str, data: Any) -> str:
    payload = json.dumps(_jsonable(data), ensure_ascii=False)
    return f"event: {event_name}\ndata: {payload}\n\n"


def heartbeat_frame() -> str:
    return ": ping\n\n"


async def with_heartbeats(
    source: AsyncIterator[str], interval_seconds: float
) -> AsyncIterator[str]:
    queue: asyncio.Queue[str | object] = asyncio.Queue()

    async def pump() -> None:
        try:
            async for frame in source:
                await queue.put(frame)
        finally:
            await queue.put(_DONE)

    task = asyncio.create_task(pump())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                yield heartbeat_frame()
                continue
            if item is _DONE:
                break
            yield item
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
```

- [ ] **Step 5: Run the focused tests and confirm pass**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/schemas/test_chat_event_schema.py tests/lingneng/api/test_sse_encoding.py -q
```

Expected: PASS.

- [ ] **Step 6: Review, commit, and push**

Run review checks, then:

```bash
git add lingneng/schemas/chat_events.py lingneng/api/__init__.py lingneng/api/sse.py tests/lingneng/schemas/test_chat_event_schema.py tests/lingneng/api/test_sse_encoding.py
git commit -m "feat: 增加灵能 SSE 协议模型"
git push origin dev
```

Rollback: revert this task commit if event model names or SSE encoding block route tests.

---

### Task 1.4: Add Session Key Resolver

**Files:**
- Create: `lingneng/session/__init__.py`
- Create: `lingneng/session/keys.py`
- Create: `tests/lingneng/session/test_session_key_resolver.py`

- [ ] **Step 1: Reload durable context**

Run the reload commands from Task 1.1 Step 1. Confirm Java `history` remains diagnostics-only.

- [ ] **Step 2: Write failing resolver tests**

Create `tests/lingneng/session/test_session_key_resolver.py` with:

```python
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def request_from(payload: dict) -> ChatStreamRequest:
    return ChatStreamRequest.model_validate(payload)


def test_resolves_with_employee_id_and_conversation_id():
    resolved = resolve_session_key(request_from(full_payload()))

    assert resolved.session_key == "tenant-a:user-a:emp-001:conv-a"
    assert resolved.degraded is False
    assert resolved.degradation_reason is None
    assert resolved.history_message_count == 2
    assert resolved.context_messages == []


def test_resolves_with_employee_type_when_employee_id_missing():
    payload = full_payload()
    payload["employee"].pop("employee_id")

    resolved = resolve_session_key(request_from(payload))

    assert resolved.session_key == "tenant-a:user-a:marketing_content_creator:conv-a"
    assert resolved.employee_id is None
    assert resolved.employee_type == "marketing_content_creator"


def test_falls_back_to_session_id_when_conversation_id_missing():
    payload = full_payload()
    payload.pop("conversation_id")

    resolved = resolve_session_key(request_from(payload))

    assert resolved.session_key == "tenant-a:user-a:emp-001:session-a"
    assert resolved.degraded is True
    assert resolved.degradation_reason == "conversation_id_missing"


def test_history_is_counted_but_not_returned_as_context():
    payload = full_payload()
    payload["history"].append(
        {"message_id": "h-3", "role": "user", "content": "不要进入上下文"}
    )

    resolved = resolve_session_key(request_from(payload))

    assert resolved.history_message_count == 3
    assert resolved.context_messages == []
```

- [ ] **Step 3: Run focused test and confirm failure**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/session/test_session_key_resolver.py -q
```

Expected: FAIL with missing `lingneng.session.keys`.

- [ ] **Step 4: Implement resolver**

Create `lingneng/session/__init__.py`:

```python
"""Session helpers for LingNeng Java-compatible requests."""
```

Create `lingneng/session/keys.py` with:

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from lingneng.schemas.chat_request import ChatStreamRequest


class ResolvedSessionKey(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_key: str
    tenant_id: str
    user_id: str
    conversation_id: str | None
    session_id: str
    employee_id: str | None
    employee_type: str
    degraded: bool = False
    degradation_reason: str | None = None
    history_message_count: int = 0
    context_messages: list[dict] = Field(default_factory=list)


def resolve_session_key(request: ChatStreamRequest) -> ResolvedSessionKey:
    employee_id = request.employee.employee_id
    employee_type = request.employee.employee_type.value
    employee_segment = employee_id or employee_type
    conversation_id = request.conversation_id
    degraded = False
    reason = None

    if conversation_id:
        business_session = conversation_id
    else:
        business_session = request.session_id
        degraded = True
        reason = "conversation_id_missing"

    return ResolvedSessionKey(
        session_key=(
            f"{request.tenant_id}:{request.user_id}:"
            f"{employee_segment}:{business_session}"
        ),
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        conversation_id=conversation_id,
        session_id=request.session_id,
        employee_id=employee_id,
        employee_type=employee_type,
        degraded=degraded,
        degradation_reason=reason,
        history_message_count=len(request.history),
        context_messages=[],
    )
```

- [ ] **Step 5: Run focused test and confirm pass**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/session/test_session_key_resolver.py -q
```

Expected: PASS.

- [ ] **Step 6: Review, commit, and push**

Run review checks, then:

```bash
git add lingneng/session/__init__.py lingneng/session/keys.py tests/lingneng/session/test_session_key_resolver.py
git commit -m "feat: 增加灵能会话键解析"
git push origin dev
```

Rollback: revert this task commit if route session resolution blocks Task 1.7.

---

### Task 1.5: Add SQLite Run Store For Idempotency

**Files:**
- Create: `lingneng/session/run_store.py`
- Create: `tests/lingneng/session/test_run_store.py`

- [ ] **Step 1: Reload durable context**

Run the reload commands from Task 1.1 Step 1. Confirm full completed-run SSE replay remains Phase 2.

- [ ] **Step 2: Write failing run store tests**

Create `tests/lingneng/session/test_run_store.py` with:

```python
from datetime import datetime, timedelta, timezone

from lingneng.session.run_store import LingNengRunStore, RunStatus


def test_first_request_creates_running_run(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")

    outcome = store.reserve_run("session-a", "req-1")

    assert outcome.created is True
    assert outcome.record.session_key == "session-a"
    assert outcome.record.request_id == "req-1"
    assert outcome.record.run_id.startswith("run_")
    assert outcome.record.status == RunStatus.RUNNING


def test_same_request_while_running_returns_existing_run(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    first = store.reserve_run("session-a", "req-1")
    second = store.reserve_run("session-a", "req-1")

    assert first.created is True
    assert second.created is False
    assert second.record.run_id == first.record.run_id
    assert store.count_runs() == 1


def test_completed_run_stores_final_answer_and_reuses_existing_state(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    first = store.reserve_run("session-a", "req-1")

    store.mark_succeeded(
        first.record.run_id,
        answer="完成",
        artifacts=[{"artifact_id": "artifact-1"}],
    )
    repeated = store.reserve_run("session-a", "req-1")

    assert repeated.created is False
    assert repeated.record.status == RunStatus.SUCCEEDED
    assert repeated.record.answer == "完成"
    assert repeated.record.artifacts == [{"artifact_id": "artifact-1"}]
    assert store.count_runs() == 1


def test_same_request_id_in_different_session_is_separate(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    first = store.reserve_run("session-a", "req-1")
    second = store.reserve_run("session-b", "req-1")

    assert first.created is True
    assert second.created is True
    assert first.record.run_id != second.record.run_id
    assert store.count_runs() == 2


def test_failed_run_stores_public_error(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    first = store.reserve_run("session-a", "req-1")

    store.mark_failed(first.record.run_id, "RUNTIME_ERROR", "运行失败")
    record = store.get_by_run_id(first.record.run_id)

    assert record.status == RunStatus.FAILED
    assert record.error_code == "RUNTIME_ERROR"
    assert record.error_message == "运行失败"


def test_cleanup_deletes_rows_older_than_retention(tmp_path):
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    old = datetime.now(timezone.utc) - timedelta(days=10)
    recent = datetime.now(timezone.utc) - timedelta(days=2)
    old_run = store.reserve_run("session-a", "old")
    recent_run = store.reserve_run("session-a", "recent")
    store.force_update_created_at(old_run.record.run_id, old)
    store.force_update_created_at(recent_run.record.run_id, recent)

    deleted = store.cleanup_older_than(days=7)

    assert deleted == 1
    assert store.get_by_run_id(old_run.record.run_id) is None
    assert store.get_by_run_id(recent_run.record.run_id) is not None
```

- [ ] **Step 3: Run focused test and confirm failure**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/session/test_run_store.py -q
```

Expected: FAIL with missing `lingneng.session.run_store`.

- [ ] **Step 4: Implement SQLite run store**

Create `lingneng/session/run_store.py` with:

```python
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class RunRecord:
    session_key: str
    request_id: str
    run_id: str
    status: RunStatus
    answer: str | None
    error_code: str | None
    error_message: str | None
    artifacts: list[dict]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True)
class ReserveRunResult:
    created: bool
    record: RunRecord


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_db_time(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def _from_db_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


class LingNengRunStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lingneng_runs (
                    session_key TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    run_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    answer TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    artifacts_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    PRIMARY KEY (session_key, request_id)
                )
                """
            )

    def reserve_run(self, session_key: str, request_id: str) -> ReserveRunResult:
        now = _now()
        run_id = f"run_{uuid.uuid4().hex}"
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO lingneng_runs (
                        session_key, request_id, run_id, status,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_key,
                        request_id,
                        run_id,
                        RunStatus.RUNNING.value,
                        _to_db_time(now),
                        _to_db_time(now),
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM lingneng_runs WHERE run_id = ?", (run_id,)
                ).fetchone()
                return ReserveRunResult(True, self._record_from_row(row))
            except sqlite3.IntegrityError:
                row = conn.execute(
                    """
                    SELECT * FROM lingneng_runs
                    WHERE session_key = ? AND request_id = ?
                    """,
                    (session_key, request_id),
                ).fetchone()
                return ReserveRunResult(False, self._record_from_row(row))

    def mark_succeeded(
        self, run_id: str, answer: str, artifacts: list[dict] | None = None
    ) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE lingneng_runs
                SET status = ?, answer = ?, artifacts_json = ?,
                    updated_at = ?, completed_at = ?
                WHERE run_id = ?
                """,
                (
                    RunStatus.SUCCEEDED.value,
                    answer,
                    json.dumps(artifacts or [], ensure_ascii=False),
                    _to_db_time(now),
                    _to_db_time(now),
                    run_id,
                ),
            )

    def mark_failed(self, run_id: str, error_code: str, error_message: str) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE lingneng_runs
                SET status = ?, error_code = ?, error_message = ?,
                    updated_at = ?, completed_at = ?
                WHERE run_id = ?
                """,
                (
                    RunStatus.FAILED.value,
                    error_code,
                    error_message,
                    _to_db_time(now),
                    _to_db_time(now),
                    run_id,
                ),
            )

    def get_by_run_id(self, run_id: str) -> RunRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM lingneng_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return self._record_from_row(row) if row else None

    def count_runs(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM lingneng_runs").fetchone()
        return int(row["count"])

    def cleanup_older_than(self, days: int) -> int:
        cutoff = _now() - timedelta(days=days)
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM lingneng_runs WHERE created_at < ?",
                (_to_db_time(cutoff),),
            )
            return cursor.rowcount

    def force_update_created_at(self, run_id: str, created_at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE lingneng_runs SET created_at = ? WHERE run_id = ?",
                (_to_db_time(created_at), run_id),
            )

    def _record_from_row(self, row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            session_key=row["session_key"],
            request_id=row["request_id"],
            run_id=row["run_id"],
            status=RunStatus(row["status"]),
            answer=row["answer"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            artifacts=json.loads(row["artifacts_json"] or "[]"),
            created_at=_from_db_time(row["created_at"]),
            updated_at=_from_db_time(row["updated_at"]),
            completed_at=_from_db_time(row["completed_at"]),
        )
```

- [ ] **Step 5: Run focused test and confirm pass**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/session/test_run_store.py -q
```

Expected: PASS.

- [ ] **Step 6: Review, commit, and push**

Run review checks, then:

```bash
git add lingneng/session/run_store.py tests/lingneng/session/test_run_store.py
git commit -m "feat: 增加灵能请求幂等存储"
git push origin dev
```

Rollback: revert this task commit if idempotency handling blocks Task 1.7.

---

### Task 1.6: Add Fake Agent Adapter And Event Bridge

**Files:**
- Create: `lingneng/runtime/__init__.py`
- Create: `lingneng/runtime/agent_adapter.py`
- Create: `lingneng/runtime/fake_agent.py`
- Create: `lingneng/events/__init__.py`
- Create: `lingneng/events/bridge.py`
- Create: `tests/lingneng/runtime/test_agent_adapter_contract.py`

- [ ] **Step 1: Reload durable context**

Run the reload commands from Task 1.1 Step 1. Confirm Phase 2 owns real Hermes `AIAgent` integration.

- [ ] **Step 2: Write failing adapter contract tests**

Create `tests/lingneng/runtime/test_agent_adapter_contract.py` with:

```python
import pytest

from lingneng.runtime.fake_agent import FakeAgentRunAdapter
from lingneng.schemas.chat_events import AnswerDeltaEvent, FinalEvent, RunStartedEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from tests.lingneng.schemas.test_chat_request_schema import full_payload


@pytest.mark.asyncio
async def test_fake_adapter_streams_minimum_phase_1_events():
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = FakeAgentRunAdapter(answer="你好，已完成。")

    events = [event async for event in adapter.stream(request, resolved, "run-test")]

    assert isinstance(events[0], RunStartedEvent)
    assert any(isinstance(event, AnswerDeltaEvent) for event in events)
    assert isinstance(events[-1], FinalEvent)
    assert events[0].request_id == "req-001"
    assert events[0].run_id == "run-test"
    assert events[0].run_id == events[-1].run_id
    assert events[-1].status == "succeeded"


@pytest.mark.asyncio
async def test_joined_deltas_equal_final_answer():
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = FakeAgentRunAdapter(answer="第一段第二段", chunk_size=2)

    events = [event async for event in adapter.stream(request, resolved, "run-test")]
    deltas = [event for event in events if isinstance(event, AnswerDeltaEvent)]
    final = events[-1]

    assert [delta.sequence for delta in deltas] == [1, 2, 3]
    assert "".join(delta.text for delta in deltas) == final.answer
```

- [ ] **Step 3: Run focused test and confirm failure**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime/test_agent_adapter_contract.py -q
```

Expected: FAIL with missing `lingneng.runtime.fake_agent`.

- [ ] **Step 4: Implement adapter protocol, bridge helpers, and fake adapter**

Create `lingneng/runtime/__init__.py`:

```python
"""Runtime adapters for LingNeng API execution."""
```

Create `lingneng/runtime/agent_adapter.py`:

```python
from __future__ import annotations

from typing import AsyncIterator, Protocol, Union

from lingneng.schemas.chat_events import AnswerDeltaEvent, ErrorEvent, FinalEvent, RunStartedEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import ResolvedSessionKey


LingNengStreamEvent = Union[RunStartedEvent, AnswerDeltaEvent, FinalEvent, ErrorEvent]


class AgentRunAdapter(Protocol):
    def stream(
        self, request: ChatStreamRequest, resolved_session: ResolvedSessionKey, run_id: str
    ) -> AsyncIterator[LingNengStreamEvent]:
        pass
```

Create `lingneng/events/__init__.py`:

```python
"""Event bridge helpers for LingNeng streaming."""
```

Create `lingneng/events/bridge.py`:

```python
from __future__ import annotations

from lingneng.schemas.chat_events import AnswerDeltaEvent, FinalEvent, RunStartedEvent


def run_started(run_id: str, request_id: str) -> RunStartedEvent:
    return RunStartedEvent(run_id=run_id, request_id=request_id)


def answer_delta(text: str, sequence: int) -> AnswerDeltaEvent:
    return AnswerDeltaEvent(text=text, sequence=sequence)


def final_answer(run_id: str, answer: str) -> FinalEvent:
    return FinalEvent(run_id=run_id, status="succeeded", answer=answer)
```

Create `lingneng/runtime/fake_agent.py`:

```python
from __future__ import annotations

from collections.abc import AsyncIterator

from lingneng.events.bridge import answer_delta, final_answer, run_started
from lingneng.runtime.agent_adapter import LingNengStreamEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import ResolvedSessionKey


class FakeAgentRunAdapter:
    def __init__(self, answer: str = "这是灵能 Hermes Phase 1 fake 回复。", chunk_size: int = 8) -> None:
        self.answer = answer
        self.chunk_size = chunk_size

    async def stream(
        self, request: ChatStreamRequest, resolved_session: ResolvedSessionKey, run_id: str
    ) -> AsyncIterator[LingNengStreamEvent]:
        yield run_started(run_id=run_id, request_id=request.request_id)

        sequence = 1
        for start in range(0, len(self.answer), self.chunk_size):
            yield answer_delta(self.answer[start : start + self.chunk_size], sequence)
            sequence += 1

        yield final_answer(run_id=run_id, answer=self.answer)
```

- [ ] **Step 5: Run focused test and confirm pass**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime/test_agent_adapter_contract.py -q
```

Expected: PASS.

- [ ] **Step 6: Review, commit, and push**

Run review checks, then:

```bash
git add lingneng/runtime/__init__.py lingneng/runtime/agent_adapter.py lingneng/runtime/fake_agent.py lingneng/events/__init__.py lingneng/events/bridge.py tests/lingneng/runtime/test_agent_adapter_contract.py
git commit -m "feat: 增加灵能 Agent 适配器接口"
git push origin dev
```

Rollback: revert this task commit if fake stream event generation blocks Task 1.7.

---

### Task 1.7: Add FastAPI App, Routes, Auth, Health, Ready

**Files:**
- Create: `lingneng/api/auth.py`
- Create: `lingneng/api/app.py`
- Create: `lingneng/api/routes.py`
- Create: `lingneng/api/server.py`
- Create: `tests/lingneng/api/test_chat_stream_contract.py`

- [ ] **Step 1: Reload durable context**

Run the reload commands from Task 1.1 Step 1. Confirm Docker and GitHub Actions files are deferred.

- [ ] **Step 2: Write failing route contract tests**

Create `tests/lingneng/api/test_chat_stream_contract.py` with:

```python
import json
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from lingneng.api.app import create_app
from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_events import AnswerDeltaEvent, ErrorEvent, FinalEvent, RunStartedEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import ResolvedSessionKey
from lingneng.session.run_store import LingNengRunStore
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def settings(tmp_path, **overrides):
    values = {
        "LINGNENG_APP_ENV": "test",
        "LINGNENG_RUNTIME_DIR": str(tmp_path),
        "LINGNENG_INTERNAL_API_KEY": "secret",
    }
    values.update(overrides)
    return LingNengSettings.from_env(values)


def client(tmp_path, **kwargs) -> TestClient:
    app = create_app(
        settings=settings(tmp_path, **kwargs),
        run_store=LingNengRunStore(tmp_path / "runs.sqlite3"),
    )
    return TestClient(app)


def post_stream(client: TestClient, payload: dict, key: str = "secret"):
    return client.post(
        "/internal/agent/chat/stream",
        json=payload,
        headers={"X-Internal-Key": key},
    )


def parse_sse(text: str) -> list[tuple[str, dict]]:
    frames = []
    for raw_frame in text.strip().split("\n\n"):
        lines = raw_frame.splitlines()
        event_line = next(line for line in lines if line.startswith("event: "))
        data_line = next(line for line in lines if line.startswith("data: "))
        frames.append(
            (
                event_line.removeprefix("event: "),
                json.loads(data_line.removeprefix("data: ")),
            )
        )
    return frames


def test_health_returns_ok(tmp_path):
    response = client(tmp_path).get("/internal/agent/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_non_secret_summary(tmp_path):
    response = client(tmp_path).get("/internal/agent/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["app_env"] == "test"
    assert body["agent_mode"] == "fake"
    assert body["auth_required"] is True
    assert "secret" not in repr(body)
    assert "internal_api_key" not in body


def test_ready_is_not_ready_for_production_like_empty_key(tmp_path):
    response = client(
        tmp_path,
        LINGNENG_APP_ENV="prod",
        LINGNENG_INTERNAL_API_KEY="",
    ).get("/internal/agent/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_ready"
    assert "internal_api_key" not in body


def test_chat_stream_success_with_configured_key(tmp_path):
    response = post_stream(client(tmp_path), full_payload())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = parse_sse(response.text)
    event_names = [event_name for event_name, data in frames]
    deltas = [data["text"] for event_name, data in frames if event_name == "answer_delta"]
    final_payload = frames[-1][1]

    assert event_names[0] == "run_started"
    assert "answer_delta" in event_names
    assert event_names[-1] == "final"
    assert "".join(deltas) == final_payload["answer"]


def test_missing_or_invalid_key_returns_non_sse_error(tmp_path):
    app_client = client(tmp_path)

    missing = app_client.post("/internal/agent/chat/stream", json=full_payload())
    invalid = post_stream(app_client, full_payload(), key="wrong")

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert "text/event-stream" not in missing.headers.get("content-type", "")


def test_local_like_empty_key_without_explicit_allow_returns_503(tmp_path):
    response = client(
        tmp_path,
        LINGNENG_INTERNAL_API_KEY="",
        LINGNENG_ALLOW_INSECURE_LOCAL="false",
    ).post("/internal/agent/chat/stream", json=full_payload())

    assert response.status_code == 503
    assert "text/event-stream" not in response.headers.get("content-type", "")


def test_production_like_empty_key_returns_503(tmp_path):
    response = client(
        tmp_path,
        LINGNENG_APP_ENV="prod",
        LINGNENG_INTERNAL_API_KEY="",
    ).post("/internal/agent/chat/stream", json=full_payload())

    assert response.status_code == 503
    assert "text/event-stream" not in response.headers.get("content-type", "")


class FailingAdapter:
    async def stream(
        self, request: ChatStreamRequest, resolved_session: ResolvedSessionKey, run_id: str
    ) -> AsyncIterator[RunStartedEvent | AnswerDeltaEvent]:
        yield RunStartedEvent(run_id=run_id, request_id=request.request_id)
        raise RuntimeError("private exception detail")


def test_adapter_failure_after_stream_start_returns_terminal_error(tmp_path):
    app = create_app(
        settings=settings(tmp_path),
        adapter=FailingAdapter(),
        run_store=LingNengRunStore(tmp_path / "runs.sqlite3"),
    )
    response = TestClient(app).post(
        "/internal/agent/chat/stream",
        json=full_payload(),
        headers={"X-Internal-Key": "secret"},
    )

    frames = parse_sse(response.text)
    error_frames = [
        data for event_name, data in frames if event_name == "error"
    ]

    assert response.status_code == 200
    assert [event_name for event_name, data in frames] == ["run_started", "error"]
    assert len(error_frames) == 1
    assert error_frames[0]["run_id"].startswith("run_")
    assert error_frames[0]["request_id"] == "req-001"
    assert error_frames[0]["code"] == "RUNTIME_ERROR"
    assert error_frames[0]["message"] == "Agent runtime failed"
    assert error_frames[0]["trace_id"].startswith("trace_")
    assert error_frames[0]["recoverable"] is False
    assert "private exception detail" not in response.text


class CountingFinalAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def stream(
        self, request: ChatStreamRequest, resolved_session: ResolvedSessionKey, run_id: str
    ) -> AsyncIterator[RunStartedEvent | AnswerDeltaEvent | FinalEvent]:
        self.calls += 1
        yield RunStartedEvent(run_id=run_id, request_id=request.request_id)
        yield AnswerDeltaEvent(text="完成", sequence=1)
        yield FinalEvent(run_id=run_id, status="succeeded", answer="完成")


def test_repeated_running_request_does_not_invoke_adapter(tmp_path):
    adapter = CountingFinalAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    store.reserve_run("tenant-a:user-a:emp-001:conv-a", "req-001")
    app = create_app(settings=settings(tmp_path), adapter=adapter, run_store=store)
    app_client = TestClient(app)

    response = post_stream(app_client, full_payload())

    assert response.status_code == 200
    assert "REQUEST_ALREADY_RUNNING" in response.text
    assert adapter.calls == 0


def test_repeated_completed_request_does_not_invoke_adapter(tmp_path):
    adapter = CountingFinalAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    app = create_app(settings=settings(tmp_path), adapter=adapter, run_store=store)
    app_client = TestClient(app)

    first = post_stream(app_client, full_payload())
    second = post_stream(app_client, full_payload())

    assert first.status_code == 200
    assert "event: final" in first.text
    assert second.status_code == 200
    assert "REQUEST_ALREADY_COMPLETED" in second.text
    assert adapter.calls == 1
```

- [ ] **Step 3: Run focused test and confirm failure**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/api/test_chat_stream_contract.py -q
```

Expected: FAIL with missing `lingneng.api.app`.

- [ ] **Step 4: Implement auth, app factory, routes, and server**

Create `lingneng/api/auth.py`:

```python
from __future__ import annotations

from fastapi import Header, HTTPException

from lingneng.config.settings import LingNengSettings


def ensure_chat_configuration_ready(settings: LingNengSettings) -> None:
    if not settings.is_chat_configuration_ready:
        raise HTTPException(status_code=503, detail="LingNeng chat API is not ready")


def verify_internal_key(
    settings: LingNengSettings, x_internal_key: str | None = Header(default=None)
) -> None:
    if not settings.auth_required:
        return
    if x_internal_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Invalid internal key")
```

Create `lingneng/api/app.py`:

```python
from __future__ import annotations

from fastapi import FastAPI

from lingneng.api.routes import register_routes
from lingneng.config.settings import LingNengSettings
from lingneng.runtime.agent_adapter import AgentRunAdapter
from lingneng.runtime.fake_agent import FakeAgentRunAdapter
from lingneng.session.run_store import LingNengRunStore


def create_app(
    settings: LingNengSettings | None = None,
    adapter: AgentRunAdapter | None = None,
    run_store: LingNengRunStore | None = None,
) -> FastAPI:
    resolved_settings = settings or LingNengSettings.from_env()
    resolved_adapter = adapter or FakeAgentRunAdapter()
    resolved_store = run_store or LingNengRunStore(
        resolved_settings.runtime_dir / "runs.sqlite3"
    )
    app = FastAPI(title="LingNeng Hermes API")
    register_routes(app, resolved_settings, resolved_adapter, resolved_store)
    return app
```

Create `lingneng/api/routes.py`. The implementation must:

- Register `GET /internal/agent/health`.
- Register `GET /internal/agent/ready`.
- Register `POST /internal/agent/chat/stream`.
- Parse `ChatStreamRequest` before session resolution.
- Call `ensure_chat_configuration_ready(settings)` before returning `StreamingResponse`.
- Call `verify_internal_key(settings, x_internal_key)` before returning `StreamingResponse`.
- Use `resolve_session_key(request)`.
- Call `run_store.reserve_run(resolved.session_key, request.request_id)` before adapter streaming.
- If existing status is `running`, return a stream with one `error` event code `REQUEST_ALREADY_RUNNING`.
- If existing status is `succeeded` or `failed`, return a stream with one `error` event code `REQUEST_ALREADY_COMPLETED`.
- For a fresh run, pass `reservation.record.run_id` into the adapter and stream adapter events with `encode_sse`.
- On `FinalEvent`, call `run_store.mark_succeeded(run_id, answer, artifacts)`.
- On `ErrorEvent`, call `run_store.mark_failed(run_id, code, message)`.
- On adapter exception, call `run_store.mark_failed(run_id, "RUNTIME_ERROR", "Agent runtime failed")` and stream one public `error`.
- Do not leak raw exception text.

Use this structure:

```python
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import FastAPI, Header
from fastapi.responses import StreamingResponse

from lingneng.api.auth import ensure_chat_configuration_ready, verify_internal_key
from lingneng.api.sse import encode_sse, with_heartbeats
from lingneng.config.settings import LingNengSettings
from lingneng.runtime.agent_adapter import AgentRunAdapter
from lingneng.schemas.chat_events import ErrorEvent, FinalEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from lingneng.session.run_store import LingNengRunStore, RunStatus


def register_routes(
    app: FastAPI,
    settings: LingNengSettings,
    adapter: AgentRunAdapter,
    run_store: LingNengRunStore,
) -> None:
    @app.get("/internal/agent/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/internal/agent/ready")
    def ready() -> dict[str, object]:
        return settings.ready_summary()

    @app.post("/internal/agent/chat/stream")
    async def chat_stream(
        request: ChatStreamRequest,
        x_internal_key: str | None = Header(default=None),
    ) -> StreamingResponse:
        ensure_chat_configuration_ready(settings)
        verify_internal_key(settings, x_internal_key)
        resolved = resolve_session_key(request)
        reservation = run_store.reserve_run(resolved.session_key, request.request_id)

        if not reservation.created:
            return StreamingResponse(
                with_heartbeats(
                    _duplicate_stream(
                        reservation.record.run_id,
                        request.request_id,
                        reservation.record.status,
                    ),
                    settings.heartbeat_interval_seconds,
                ),
                media_type="text/event-stream",
            )

        return StreamingResponse(
            with_heartbeats(
                _adapter_stream(
                    adapter,
                    run_store,
                    request,
                    resolved,
                    reservation.record.run_id,
                ),
                settings.heartbeat_interval_seconds,
            ),
            media_type="text/event-stream",
        )


async def _duplicate_stream(
    run_id: str, request_id: str, status: RunStatus
) -> AsyncIterator[str]:
    code = "REQUEST_ALREADY_RUNNING"
    message = "Request is already running"
    if status in {RunStatus.SUCCEEDED, RunStatus.FAILED}:
        code = "REQUEST_ALREADY_COMPLETED"
        message = "Request is already completed"
    yield encode_sse(
        "error",
        ErrorEvent(
            run_id=run_id,
            request_id=request_id,
            code=code,
            message=message,
            trace_id=f"trace_{uuid.uuid4().hex}",
            recoverable=True,
        ),
    )


async def _adapter_stream(
    adapter: AgentRunAdapter,
    run_store: LingNengRunStore,
    request: ChatStreamRequest,
    resolved,
    run_id: str,
) -> AsyncIterator[str]:
    current_run_id = run_id
    try:
        async for event in adapter.stream(request, resolved, run_id):
            if hasattr(event, "run_id"):
                current_run_id = event.run_id
            yield encode_sse(_event_name(event), event)
            if isinstance(event, FinalEvent):
                run_store.mark_succeeded(
                    event.run_id,
                    answer=event.answer,
                    artifacts=event.artifacts,
                )
            if isinstance(event, ErrorEvent):
                run_store.mark_failed(event.run_id, event.code, event.message)
                return
    except Exception:
        run_id = current_run_id or f"run_{uuid.uuid4().hex}"
        run_store.mark_failed(run_id, "RUNTIME_ERROR", "Agent runtime failed")
        yield encode_sse(
            "error",
            ErrorEvent(
                run_id=run_id,
                request_id=request.request_id,
                code="RUNTIME_ERROR",
                message="Agent runtime failed",
                trace_id=f"trace_{uuid.uuid4().hex}",
                recoverable=False,
            ),
        )


def _event_name(event) -> str:
    if event.__class__.__name__ == "RunStartedEvent":
        return "run_started"
    if event.__class__.__name__ == "AnswerDeltaEvent":
        return "answer_delta"
    if event.__class__.__name__ == "FinalEvent":
        return "final"
    if event.__class__.__name__ == "ErrorEvent":
        return "error"
    raise ValueError(f"Unsupported LingNeng event model: {event.__class__.__name__}")
```

Create `lingneng/api/server.py`:

```python
from __future__ import annotations

import uvicorn

from lingneng.api.app import create_app
from lingneng.config.settings import LingNengSettings


def main() -> None:
    settings = LingNengSettings.from_env()
    uvicorn.run(
        create_app(settings=settings),
        host=settings.api_host,
        port=settings.api_port,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run focused test and confirm pass**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/api/test_chat_stream_contract.py -q
```

Expected: PASS.

- [ ] **Step 6: Run Phase 1 verification matrix**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/config tests/lingneng/schemas tests/lingneng/session tests/lingneng/api tests/lingneng/runtime -q
/Users/rotas/Documents/work/hailun/LingNengAI/.venv/bin/python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py -q
```

Expected:

- LingNeng-Hermes Phase 1 test directories pass.
- LingNengAI reference contract reports `14 passed`.

- [ ] **Step 7: Review, commit, and push**

Run review checks, then:

```bash
git add lingneng/api/auth.py lingneng/api/app.py lingneng/api/routes.py lingneng/api/server.py tests/lingneng/api/test_chat_stream_contract.py
git commit -m "feat: 增加灵能 Java 兼容 API"
git push origin dev
```

Rollback: revert this task commit if route contract behavior needs redesign. Keep Tasks 1.1-1.6 unless their focused tests fail, because they are independent Phase 1 building blocks.

---

## Phase Completion Review

After Task 1.7 commit and push:

- [ ] Re-read `docs/lingneng-migration/specs/2026-06-06-phase-1-java-compatible-api-mvp-spec.md`.
- [ ] Re-read this plan.
- [ ] Confirm every acceptance criterion in the spec maps to a passing test or implemented file.
- [ ] Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/config tests/lingneng/schemas tests/lingneng/session tests/lingneng/api tests/lingneng/runtime -q
/Users/rotas/Documents/work/hailun/LingNengAI/.venv/bin/python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py -q
git status --short --branch
```

Expected:

- Phase 1 pytest command exits 0.
- Reference contract command reports `14 passed`.
- `git status --short --branch` shows `## dev`.

## Phase 2 Handoff

Phase 2 must start with a dedicated Phase 2 spec. Phase 2 may use `AgentRunAdapter`, `FakeAgentRunAdapter`, `ChatStreamRequest`, SSE event models, session key resolver, and `LingNengRunStore` from Phase 1. Phase 2 owns real Hermes `AIAgent`, Hermes `SessionDB`, completed-run replay, and callback-based answer streaming.
