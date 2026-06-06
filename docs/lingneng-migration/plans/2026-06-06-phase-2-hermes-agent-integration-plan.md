# Phase 2 Hermes Agent Integration And Persistent Conversation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Phase 1 fake stream with a no-tool Hermes `AIAgent` runtime path that preserves the Java SSE contract, persists conversation state in Hermes `SessionDB`, and replays terminal idempotency results.

**Architecture:** Keep LingNeng-specific behavior inside the `lingneng/` namespace. Add a Hermes adapter that runs synchronous `AIAgent.run_conversation()` in a worker thread, bridges stream callbacks into async LingNeng SSE events, uses a LingNeng-owned `SessionDB` under `LINGNENG_RUNTIME_DIR`, and extends route-level duplicate handling to replay stored terminal output without invoking the adapter again.

**Tech Stack:** Python 3.11-3.13, FastAPI, Pydantic v2, SQLite, Hermes `AIAgent`, Hermes `SessionDB`, pytest, uv.

---

## Approved Inputs

- Master context: `LINGNENG_MIGRATION_CONTEXT.md`
- Master design: `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- Master roadmap: `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- Phase 1 spec: `docs/lingneng-migration/specs/2026-06-06-phase-1-java-compatible-api-mvp-spec.md`
- Phase 1 plan: `docs/lingneng-migration/plans/2026-06-06-phase-1-java-compatible-api-mvp-plan.md`
- Phase 2 spec: `docs/lingneng-migration/specs/2026-06-06-phase-2-hermes-agent-integration-spec.md`

## Execution Order

Execute tasks in this exact order:

1. Task 2.1 Settings and adapter mode selection
2. Task 2.2 LingNeng SessionDB adapter
3. Task 2.3 Hermes adapter construction
4. Task 2.4 Hermes answer stream bridge
5. Task 2.5 Terminal run replay
6. Task 2.6 No-tool route contract and phase verification

Each task must follow:

```text
reload durable context -> write failing tests -> run focused test and confirm expected failure -> implement -> run focused test -> run task review checks -> commit in Chinese -> push dev
```

Do not start Task N+1 until Task N is verified, committed, and pushed.

## User Confirmations Before Execution

No additional user confirmation is required before Phase 2 execution. The Phase
2 spec locks these decisions:

- Phase 2 is a no-tool Hermes conversation phase.
- `LINGNENG_AGENT_MODE=fake` remains the default.
- `LINGNENG_AGENT_MODE=hermes` selects `HermesAgentRunAdapter`.
- `AIAgent` receives `enabled_toolsets=[]` and
  `disabled_toolsets=["kanban"]`; the dedicated LingNeng business toolset
  remains Phase 3 work. The kanban disable guard strips worker tools that
  Hermes can inject when `HERMES_KANBAN_TASK` is present.
- The Hermes adapter clears inherited `HERMES_KANBAN_*` worker environment
  variables while constructing `AIAgent` and while executing
  `run_conversation()`, then restores the original values after the run. The
  lock covers the full LingNeng Hermes construction/run context because
  `os.environ` is process-global and concurrent restore can otherwise leak
  `HERMES_KANBAN_TASK` into another run.
- The Hermes adapter installs a LingNeng-only instance `_touch_activity`
  tracker so kanban heartbeat side effects do not run during Java API
  no-tool requests.
- `lingneng.session` exports `LingNengHermesSessionStore` lazily so fake-mode
  imports do not load `hermes_state`; direct
  `lingneng.session.hermes_session` imports remain supported.
- LingNeng SessionDB data defaults under `LINGNENG_RUNTIME_DIR`.
- Real model credentials are not required for tests.
- Docker, Compose, deployment scripts, GitHub Actions workflows, RAG, skills,
  artifacts, attachments, and business tools remain outside Phase 2.

## Shared Worker Rules

- Work in `/Users/rotas/Documents/work/hailun/demos/lingneng-hermes`.
- Do not use git worktrees.
- Do not modify Java code or `/Users/rotas/Documents/work/hailun/LingNengAI`.
- Do not modify `run_agent.py`, `agent/conversation_loop.py`,
  `model_tools.py`, `toolsets.py`, `hermes_state.py`,
  `gateway/platforms/api_server.py`, or `hermes_cli/web_server.py` in Phase 2.
- Keep edits scoped to `lingneng/`, `tests/lingneng/`, and this Phase 2 plan
  unless a test proves a generic Hermes extension point is missing.
- Use `uv run --extra dev python -m pytest` for repository-local pytest.
- Use `apply_patch` for manual edits.
- Keep secrets out of source and test output.
- No local service is required. Use `fastapi.testclient.TestClient`.
- If a local server is manually started for debugging, first run
  `lsof -nP -iTCP:18083 -sTCP:LISTEN` and do not kill unrelated processes.
- After each task, run `git diff --check` before commit.
- Commit messages are Chinese conventional-prefix messages listed per task.
- Push `origin dev` after each verified task commit.

## File Map

Runtime modules created or modified in Phase 2:

- `lingneng/config/settings.py`: add validated `agent_mode` values and
  `session_db_path`.
- `lingneng/api/app.py`: select fake or Hermes adapter by settings when no
  adapter is injected.
- `lingneng/api/routes.py`: replay stored terminal run state for duplicate
  requests.
- `lingneng/events/bridge.py`: add helper functions for replayed finals and
  public runtime errors if needed.
- `lingneng/session/run_store.py`: expose lookup by `(session_key, request_id)`
  or equivalent data already returned by `reserve_run`; preserve terminal
  answer/artifacts/error fields.
- `lingneng/session/__init__.py`: keep lightweight key exports eager and expose
  `LingNengHermesSessionStore` lazily through `__getattr__`.
- `lingneng/session/hermes_session.py`: construct LingNeng-owned `SessionDB`
  and convert stored rows into `conversation_history`.
- `lingneng/runtime/__init__.py`: export `HermesAgentRunAdapter`.
- `lingneng/runtime/agent_adapter.py`: keep the `AgentRunAdapter` protocol
  stable.
- `lingneng/runtime/hermes_adapter.py`: construct and run Hermes `AIAgent`,
  bridge sync callbacks to async LingNeng events, and map public failures.

Tests created or modified in Phase 2:

- `tests/lingneng/config/test_settings.py`
- `tests/lingneng/api/test_chat_stream_contract.py`
- `tests/lingneng/runtime/test_hermes_adapter_config.py`
- `tests/lingneng/runtime/test_hermes_answer_stream.py`
- `tests/lingneng/session/test_hermes_session_adapter.py`
- `tests/lingneng/api/test_chat_stream_idempotency.py`
- `tests/lingneng/contract/test_chat_stream_minimal.py`

## Shared Test Helpers

Reuse `full_payload()` from `tests/lingneng/schemas/test_chat_request_schema.py`
for Java request bodies.

Use this SSE parser shape in route and contract tests:

```python
def parse_sse(text: str) -> list[tuple[str, dict]]:
    frames = []
    for raw_frame in text.strip().split("\n\n"):
        lines = raw_frame.splitlines()
        if not lines or lines[0].startswith(":"):
            continue
        event_line = next(line for line in lines if line.startswith("event: "))
        data_line = next(line for line in lines if line.startswith("data: "))
        frames.append(
            (
                event_line.removeprefix("event: "),
                json.loads(data_line.removeprefix("data: ")),
            )
        )
    return frames
```

Use fake Hermes runners instead of real providers:

```python
class CapturingAgent:
    calls: list[dict] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.session_id = kwargs["session_id"]
        self.session_db = kwargs["session_db"]
        self.stream_delta_callback = kwargs.get("stream_delta_callback")
        CapturingAgent.calls.append(kwargs)

    def run_conversation(
        self,
        user_message: str,
        system_message: str | None = None,
        conversation_history: list[dict] | None = None,
        task_id: str | None = None,
        stream_callback=None,
        persist_user_message: str | None = None,
    ) -> dict:
        if self.stream_delta_callback:
            self.stream_delta_callback("你")
            self.stream_delta_callback("好")
        return {
            "final_response": "你好",
            "messages": [
                *(conversation_history or []),
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "你好"},
            ],
        }
```

## Review Checks For Every Task

Run these before each task commit:

```bash
git diff --check
rg -n "T[B]D|T[O]DO|t[o]do|fill[[:space:]]in|implement[[:space:]]later|place[h]older|待[补]充|待[定]|占[位]" lingneng tests/lingneng docs/lingneng-migration/plans/2026-06-06-phase-2-hermes-agent-integration-plan.md
```

Expected:

- `git diff --check` exits 0.
- The incomplete-marker scan exits 1 with no matches.

---

### Task 2.1: Settings And Adapter Mode Selection

**Files:**
- Modify: `lingneng/config/settings.py`
- Modify: `lingneng/api/app.py`
- Create: `tests/lingneng/runtime/test_hermes_adapter_config.py`
- Modify: `tests/lingneng/config/test_settings.py`
- Modify: `tests/lingneng/api/test_chat_stream_contract.py`

- [ ] **Step 1: Reload durable context**

Run:

```bash
sed -n '1,220p' LINGNENG_MIGRATION_CONTEXT.md
sed -n '1,360p' docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md
sed -n '1,520p' docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md
sed -n '1,460p' docs/lingneng-migration/specs/2026-06-06-phase-2-hermes-agent-integration-spec.md
```

Expected: files describe Phase 2 as no-tool Hermes adapter, SessionDB, and
replay work only.

- [ ] **Step 2: Write failing settings tests**

Add these tests to `tests/lingneng/config/test_settings.py`:

```python
import pytest
from pydantic import ValidationError


def test_phase_2_settings_include_session_db_path(tmp_path):
    settings = LingNengSettings.from_env(
        {"LINGNENG_RUNTIME_DIR": str(tmp_path / "runtime")}
    )

    assert settings.agent_mode == "fake"
    assert settings.session_db_path == tmp_path / "runtime" / "sessions.sqlite3"


def test_session_db_path_can_be_overridden(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path / "runtime"),
            "LINGNENG_SESSION_DB_PATH": str(tmp_path / "custom.sqlite3"),
        }
    )

    assert settings.session_db_path == tmp_path / "custom.sqlite3"


def test_agent_mode_accepts_hermes():
    settings = LingNengSettings.from_env({"LINGNENG_AGENT_MODE": "hermes"})

    assert settings.agent_mode == "hermes"


def test_unknown_agent_mode_is_rejected():
    with pytest.raises(ValidationError):
        LingNengSettings.from_env({"LINGNENG_AGENT_MODE": "unsafe"})
```

Expected initial failure: `session_db_path` does not exist and unknown
`agent_mode` is accepted.

- [ ] **Step 3: Write failing adapter selection tests**

Create `tests/lingneng/runtime/test_hermes_adapter_config.py` with:

```python
from lingneng.api.app import create_app
from lingneng.config.settings import LingNengSettings
from lingneng.runtime.fake_agent import FakeAgentRunAdapter


def settings(tmp_path, **overrides) -> LingNengSettings:
    env = {
        "LINGNENG_APP_ENV": "test",
        "LINGNENG_RUNTIME_DIR": str(tmp_path),
        "LINGNENG_INTERNAL_API_KEY": "key",
    }
    env.update(overrides)
    return LingNengSettings.from_env(env)


def test_create_app_uses_fake_adapter_by_default(tmp_path):
    app = create_app(settings=settings(tmp_path))

    assert isinstance(app.state.lingneng_adapter, FakeAgentRunAdapter)


def test_create_app_uses_hermes_adapter_for_hermes_mode(tmp_path):
    app = create_app(
        settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes")
    )

    assert app.state.lingneng_adapter.__class__.__name__ == "HermesAgentRunAdapter"
```

Expected initial failure: app state does not expose the selected adapter and
Hermes adapter does not exist.

- [ ] **Step 4: Run focused tests and confirm failure**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/config/test_settings.py tests/lingneng/runtime/test_hermes_adapter_config.py -q
```

Expected: FAIL with missing `session_db_path`, missing `HermesAgentRunAdapter`,
or missing `app.state.lingneng_adapter`.

- [ ] **Step 5: Implement settings and app selection**

Modify `lingneng/config/settings.py`:

```python
from typing import Literal

from pydantic import model_validator


AgentMode = Literal["fake", "hermes"]


class LingNengSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_env: str = "dev"
    api_host: str = "127.0.0.1"
    api_port: int = 18083
    runtime_dir: Path = Path(".runtime/lingneng")
    session_db_path: Path | None = None
    agent_mode: AgentMode = "fake"
    internal_api_key: str = Field(default="", repr=False)
    allow_insecure_local: bool = False
    session_retention_days: int = 90
    archived_session_retention_days: int = 180
    idempotency_retention_days: int = 7
    heartbeat_interval_seconds: float = 15.0

    @model_validator(mode="after")
    def _default_session_db_path(self) -> "LingNengSettings":
        if self.session_db_path is None:
            self.session_db_path = self.runtime_dir / "sessions.sqlite3"
        return self

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "LingNengSettings":
        source = os.environ if env is None else env
        runtime_dir = Path(source.get("LINGNENG_RUNTIME_DIR", ".runtime/lingneng"))
        session_db_value = source.get("LINGNENG_SESSION_DB_PATH")
        return cls(
            app_env=source.get("LINGNENG_APP_ENV", "dev"),
            api_host=source.get("LINGNENG_API_HOST", "127.0.0.1"),
            api_port=int(source.get("LINGNENG_API_PORT", "18083")),
            runtime_dir=runtime_dir,
            session_db_path=Path(session_db_value)
            if session_db_value
            else runtime_dir / "sessions.sqlite3",
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
```

Modify `ready_summary()` only if needed:

```python
def ready_summary(self) -> dict[str, object]:
    return {
        "status": "ready" if self.is_chat_configuration_ready else "not_ready",
        "app_env": self.app_env,
        "agent_mode": self.agent_mode,
        "runtime_dir": str(self.runtime_dir),
        "session_db_path": str(self.session_db_path),
        "auth_required": self.auth_required,
    }
```

Create a temporary minimal `lingneng/runtime/hermes_adapter.py` so app selection
can import it. The full adapter behavior lands in later tasks:

```python
from __future__ import annotations

from collections.abc import AsyncIterator

from lingneng.config.settings import LingNengSettings
from lingneng.runtime.agent_adapter import LingNengStreamEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import ResolvedSessionKey


class HermesAgentRunAdapter:
    def __init__(self, settings: LingNengSettings, **_kwargs) -> None:
        self.settings = settings

    async def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[LingNengStreamEvent]:
        raise RuntimeError("Hermes adapter is not configured")
```

Modify `lingneng/api/app.py`:

```python
def _default_adapter(settings: LingNengSettings) -> AgentRunAdapter:
    if settings.agent_mode == "fake":
        return FakeAgentRunAdapter()
    if settings.agent_mode == "hermes":
        from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
        return HermesAgentRunAdapter(settings=settings)
    raise ValueError(f"Unsupported LingNeng agent mode: {settings.agent_mode}")


def create_app(...):
    resolved_settings = settings or LingNengSettings.from_env()
    resolved_adapter = adapter or _default_adapter(resolved_settings)
    ...
    app = FastAPI(title="LingNeng Hermes API")
    app.state.lingneng_settings = resolved_settings
    app.state.lingneng_adapter = resolved_adapter
    app.state.lingneng_run_store = resolved_store
    register_routes(app, resolved_settings, resolved_adapter, resolved_store)
    return app
```

- [ ] **Step 6: Run focused tests and confirm pass**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/config/test_settings.py tests/lingneng/runtime/test_hermes_adapter_config.py -q
```

Expected: PASS.

- [ ] **Step 7: Run Phase 1 route compatibility test**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/api/test_chat_stream_contract.py -q
```

Expected: PASS. Fake mode remains unchanged.

- [ ] **Step 8: Review, commit, and push**

Run:

```bash
git diff --check
rg -n "T[B]D|T[O]DO|t[o]do|fill[[:space:]]in|implement[[:space:]]later|place[h]older|待[补]充|待[定]|占[位]" lingneng tests/lingneng docs/lingneng-migration/plans/2026-06-06-phase-2-hermes-agent-integration-plan.md
git status --short
git add lingneng/config/settings.py lingneng/api/app.py lingneng/runtime/hermes_adapter.py tests/lingneng/config/test_settings.py tests/lingneng/runtime/test_hermes_adapter_config.py tests/lingneng/api/test_chat_stream_contract.py
git commit -m "feat: 增加灵能 Hermes 模式配置"
git push origin dev
```

Rollback: revert this commit if mode selection breaks fake-mode route tests.

---

### Task 2.2: LingNeng SessionDB Adapter

**Files:**
- Create: `lingneng/session/hermes_session.py`
- Modify: `lingneng/session/__init__.py`
- Create: `tests/lingneng/session/test_hermes_session_adapter.py`

- [ ] **Step 1: Reload durable context**

Run the reload commands from Task 2.1 Step 1. Confirm the spec requires
SessionDB under `LINGNENG_RUNTIME_DIR` and Java `history` exclusion.

- [ ] **Step 2: Write failing SessionDB adapter tests**

Create `tests/lingneng/session/test_hermes_session_adapter.py`:

```python
from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.hermes_session import LingNengHermesSessionStore
from lingneng.session.keys import resolve_session_key
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def settings(tmp_path) -> LingNengSettings:
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_INTERNAL_API_KEY": "key",
        }
    )


def resolved_from(payload: dict):
    return resolve_session_key(ChatStreamRequest.model_validate(payload))


def test_session_db_path_is_lingneng_runtime_dir(tmp_path):
    store = LingNengHermesSessionStore(settings(tmp_path))

    assert store.db.db_path == tmp_path / "sessions.sqlite3"


def test_loads_existing_hermes_messages_as_conversation_history(tmp_path):
    store = LingNengHermesSessionStore(settings(tmp_path))
    resolved = resolved_from(full_payload())
    store.db.ensure_session(resolved.session_key, source="lingneng")
    store.db.append_message(
        session_id=resolved.session_key,
        role="user",
        content="上一轮问题",
    )
    store.db.append_message(
        session_id=resolved.session_key,
        role="assistant",
        content="上一轮回答",
    )

    history = store.load_conversation_history(resolved)

    assert history == [
        {"role": "user", "content": "上一轮问题"},
        {"role": "assistant", "content": "上一轮回答"},
    ]


def test_same_conversation_reuses_same_session_key(tmp_path):
    store = LingNengHermesSessionStore(settings(tmp_path))
    first = resolved_from(full_payload())
    second = resolved_from(full_payload())

    store.ensure_session(first)
    store.ensure_session(second)

    assert first.session_key == second.session_key
    assert store.db.get_session(first.session_key) is not None


def test_different_employee_gets_different_session_key(tmp_path):
    store = LingNengHermesSessionStore(settings(tmp_path))
    first_payload = full_payload()
    second_payload = full_payload()
    second_payload["employee"]["employee_id"] = "emp-002"
    first = resolved_from(first_payload)
    second = resolved_from(second_payload)

    store.ensure_session(first)
    store.ensure_session(second)

    assert first.session_key != second.session_key
    assert store.db.get_session(first.session_key) is not None
    assert store.db.get_session(second.session_key) is not None


def test_java_history_is_not_loaded_or_persisted(tmp_path):
    store = LingNengHermesSessionStore(settings(tmp_path))
    payload = full_payload()
    payload["history"].append(
        {"message_id": "h-3", "role": "user", "content": "Java 历史"}
    )
    resolved = resolved_from(payload)

    store.ensure_session(resolved)
    history = store.load_conversation_history(resolved)

    assert history == []
    assert store.db.get_messages(resolved.session_key) == []
```

Expected initial failure: `lingneng.session.hermes_session` does not exist.

- [ ] **Step 3: Run focused test and confirm failure**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/session/test_hermes_session_adapter.py -q
```

Expected: FAIL with missing module.

- [ ] **Step 4: Implement SessionDB adapter**

Create `lingneng/session/hermes_session.py`:

```python
from __future__ import annotations

from typing import Any

from hermes_state import SessionDB

from lingneng.config.settings import LingNengSettings
from lingneng.session.keys import ResolvedSessionKey


class LingNengHermesSessionStore:
    def __init__(
        self,
        settings: LingNengSettings,
        db: SessionDB | None = None,
    ) -> None:
        self.settings = settings
        self.db = db or SessionDB(db_path=settings.session_db_path)

    def ensure_session(self, resolved: ResolvedSessionKey) -> str:
        return self.db.ensure_session(
            resolved.session_key,
            source="lingneng",
            user_id=resolved.user_id,
        )

    def load_conversation_history(
        self,
        resolved: ResolvedSessionKey,
    ) -> list[dict[str, Any]]:
        rows = self.db.get_messages(resolved.session_key)
        history: list[dict[str, Any]] = []
        for row in rows:
            message = self._row_to_message(row)
            if message is not None:
                history.append(message)
        return history

    def _row_to_message(self, row: dict[str, Any]) -> dict[str, Any] | None:
        role = row.get("role")
        if role not in {"user", "assistant", "tool"}:
            return None
        message: dict[str, Any] = {"role": role, "content": row.get("content")}
        if row.get("tool_call_id"):
            message["tool_call_id"] = row["tool_call_id"]
        if row.get("tool_calls"):
            message["tool_calls"] = row["tool_calls"]
        if row.get("tool_name"):
            message["tool_name"] = row["tool_name"]
        if row.get("finish_reason"):
            message["finish_reason"] = row["finish_reason"]
        return message
```

Modify `lingneng/session/__init__.py`:

```python
from typing import TYPE_CHECKING, Any

from lingneng.session.keys import ResolvedSessionKey, resolve_session_key

if TYPE_CHECKING:
    from lingneng.session.hermes_session import LingNengHermesSessionStore

__all__ = [
    "LingNengHermesSessionStore",
    "ResolvedSessionKey",
    "resolve_session_key",
]


def __getattr__(name: str) -> Any:
    if name == "LingNengHermesSessionStore":
        from lingneng.session.hermes_session import LingNengHermesSessionStore

        return LingNengHermesSessionStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

- [ ] **Step 5: Run focused test and confirm pass**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/session/test_hermes_session_adapter.py -q
```

Expected: PASS.

- [ ] **Step 6: Run existing session tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/session -q
```

Expected: PASS.

- [ ] **Step 7: Review, commit, and push**

Run:

```bash
git diff --check
rg -n "T[B]D|T[O]DO|t[o]do|fill[[:space:]]in|implement[[:space:]]later|place[h]older|待[补]充|待[定]|占[位]" lingneng tests/lingneng docs/lingneng-migration/plans/2026-06-06-phase-2-hermes-agent-integration-plan.md
git status --short
git add lingneng/session/__init__.py lingneng/session/hermes_session.py tests/lingneng/session/test_hermes_session_adapter.py
git commit -m "feat: 连接灵能会话到 Hermes SessionDB"
git push origin dev
```

Rollback: revert this commit if SessionDB conversion breaks existing session
key or run store tests.

---

### Task 2.3: Hermes Adapter Construction

**Files:**
- Modify: `lingneng/runtime/hermes_adapter.py`
- Modify: `tests/lingneng/runtime/test_hermes_adapter_config.py`

- [ ] **Step 1: Reload durable context**

Run the reload commands from Task 2.1 Step 1. Confirm `enabled_toolsets=[]`
plus `disabled_toolsets=["kanban"]` is the accepted Phase 2 no-tool boundary,
and confirm the final review requirement to isolate inherited
`HERMES_KANBAN_*` worker environment and kanban heartbeat side effects. The
env-isolation lock must cover the full LingNeng Hermes construction/run
context.

- [ ] **Step 2: Extend failing adapter construction tests**

Append to `tests/lingneng/runtime/test_hermes_adapter_config.py`:

```python
import pytest

from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from tests.lingneng.schemas.test_chat_request_schema import full_payload


class CapturingAgent:
    calls: list[dict] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        CapturingAgent.calls.append(kwargs)

    def run_conversation(
        self,
        user_message,
        system_message=None,
        conversation_history=None,
        task_id=None,
        stream_callback=None,
        persist_user_message=None,
    ):
        self.run_args = {
            "user_message": user_message,
            "system_message": system_message,
            "conversation_history": conversation_history,
            "task_id": task_id,
            "persist_user_message": persist_user_message,
        }
        return {"final_response": "完成", "messages": []}


@pytest.mark.asyncio
async def test_hermes_adapter_constructs_agent_with_no_tool_lingneng_context(tmp_path):
    CapturingAgent.calls = []
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=CapturingAgent,
    )

    events = [event async for event in adapter.stream(request, resolved, "run-1")]

    kwargs = CapturingAgent.calls[0]
    assert kwargs["platform"] == "lingneng"
    assert kwargs["session_id"] == resolved.session_key
    assert kwargs["enabled_toolsets"] == []
    assert kwargs["disabled_toolsets"] == ["kanban"]
    assert kwargs["quiet_mode"] is True
    assert kwargs["skip_context_files"] is True
    assert kwargs["skip_memory"] is True
    assert kwargs["session_db"].db_path == tmp_path / "sessions.sqlite3"
    assert events[-1].answer == "完成"


@pytest.mark.asyncio
async def test_hermes_adapter_does_not_pass_java_history_to_conversation_history(tmp_path):
    CapturingAgent.calls = []
    payload = full_payload()
    payload["history"].append(
        {"message_id": "h-3", "role": "user", "content": "Java 历史"}
    )
    request = ChatStreamRequest.model_validate(payload)
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=CapturingAgent,
    )

    [event async for event in adapter.stream(request, resolved, "run-1")]

    agent = adapter._last_agent_for_tests
    assert agent.run_args["user_message"] == request.query.content
    assert agent.run_args["system_message"] == request.system_prompt.content
    assert agent.run_args["persist_user_message"] == request.query.content
    assert agent.run_args["conversation_history"] == []


@pytest.mark.asyncio
async def test_hermes_adapter_excludes_env_injected_kanban_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_KANBAN_TASK", "task-001")
    CapturingAgent.calls = []
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=CapturingAgent,
    )

    [event async for event in adapter.stream(request, resolved, "run-1")]

    from model_tools import get_tool_definitions

    kwargs = CapturingAgent.calls[0]
    definitions = get_tool_definitions(
        enabled_toolsets=kwargs["enabled_toolsets"],
        disabled_toolsets=kwargs.get("disabled_toolsets"),
        quiet_mode=True,
    )
    tool_names = [tool["function"]["name"] for tool in definitions]

    assert all(not name.startswith("kanban_") for name in tool_names)


class KanbanEnvProbeAgent:
    seen_in_init: str | None = None
    seen_in_run: str | None = None

    def __init__(self, **kwargs):
        import os

        KanbanEnvProbeAgent.seen_in_init = os.environ.get("HERMES_KANBAN_TASK")

    def run_conversation(self, *args, **kwargs):
        import os

        KanbanEnvProbeAgent.seen_in_run = os.environ.get("HERMES_KANBAN_TASK")
        return {"final_response": "完成", "messages": []}


class SideEffectingActivityAgent:
    def __init__(self, **kwargs):
        self._last_activity_ts = 0.0
        self._last_activity_desc = ""

    def _touch_activity(self, desc: str) -> None:
        raise AssertionError(f"kanban side effect inherited: {desc}")

    def run_conversation(self, *args, **kwargs):
        self._touch_activity("probe")
        return {"final_response": "完成", "messages": []}


@pytest.mark.asyncio
async def test_hermes_adapter_clears_kanban_worker_env_during_agent_run(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("HERMES_KANBAN_TASK", "task-001")
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=KanbanEnvProbeAgent,
    )

    [event async for event in adapter.stream(request, resolved, "run-1")]

    assert KanbanEnvProbeAgent.seen_in_init is None
    assert KanbanEnvProbeAgent.seen_in_run is None
    assert __import__("os").environ["HERMES_KANBAN_TASK"] == "task-001"


class ConcurrentKanbanEnvAgent:
    lock = threading.Lock()
    calls = 0
    first_started = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()
    check_second = threading.Event()
    second_seen_after_first: str | None = "unset"

    @classmethod
    def reset(cls) -> None:
        with cls.lock:
            cls.calls = 0
        cls.first_started = threading.Event()
        cls.release_first = threading.Event()
        cls.second_started = threading.Event()
        cls.check_second = threading.Event()
        cls.second_seen_after_first = "unset"

    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")

    def run_conversation(self, *args, **kwargs):
        import os

        with self.lock:
            type(self).calls += 1
            call_index = type(self).calls

        if call_index == 1:
            type(self).first_started.set()
            if not type(self).release_first.wait(timeout=5):
                raise AssertionError("first run was not released")
            return {"final_response": "first", "messages": []}

        type(self).second_started.set()
        if not type(self).check_second.wait(timeout=5):
            raise AssertionError("second run was not checked")
        type(self).second_seen_after_first = os.environ.get("HERMES_KANBAN_TASK")
        return {"final_response": "second", "messages": []}


@pytest.mark.asyncio
async def test_hermes_adapter_serializes_kanban_env_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_KANBAN_TASK", "task-001")
    ConcurrentKanbanEnvAgent.reset()
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    first_runtime_dir = tmp_path / "first"
    second_runtime_dir = tmp_path / "second"
    first_runtime_dir.mkdir()
    second_runtime_dir.mkdir()
    first_adapter = HermesAgentRunAdapter(
        settings=settings(first_runtime_dir, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=ConcurrentKanbanEnvAgent,
    )
    second_adapter = HermesAgentRunAdapter(
        settings=settings(second_runtime_dir, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=ConcurrentKanbanEnvAgent,
    )

    async def collect(adapter, run_id):
        return [event async for event in adapter.stream(request, resolved, run_id)]

    first_task = asyncio.create_task(collect(first_adapter, "run-1"))
    assert await asyncio.to_thread(ConcurrentKanbanEnvAgent.first_started.wait, 5)
    second_task = asyncio.create_task(collect(second_adapter, "run-2"))
    second_entered_before_release = await asyncio.to_thread(
        ConcurrentKanbanEnvAgent.second_started.wait,
        0.5,
    )
    assert second_entered_before_release is False
    ConcurrentKanbanEnvAgent.release_first.set()
    await first_task
    assert await asyncio.to_thread(ConcurrentKanbanEnvAgent.second_started.wait, 5)
    ConcurrentKanbanEnvAgent.check_second.set()
    await second_task

    assert ConcurrentKanbanEnvAgent.second_seen_after_first is None
    assert __import__("os").environ["HERMES_KANBAN_TASK"] == "task-001"


@pytest.mark.asyncio
async def test_hermes_adapter_installs_lingneng_activity_tracker(tmp_path):
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"),
        agent_cls=SideEffectingActivityAgent,
    )

    [event async for event in adapter.stream(request, resolved, "run-1")]

    agent = adapter._last_agent_for_tests
    assert agent._last_activity_desc == "probe"
    assert agent._last_activity_ts > 0.0
```

Expected initial failure: adapter does not accept `settings` or `agent_cls`,
does not construct `AIAgent`, has no test inspection hook, or does not strip
env-injected kanban tools from the no-tool boundary. The final review
regressions also fail until the adapter clears inherited `HERMES_KANBAN_*`
variables under a full-context lock during construction/run and replaces
kanban heartbeat activity tracking with a LingNeng-local tracker.

- [ ] **Step 3: Run focused test and confirm failure**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime/test_hermes_adapter_config.py -q
```

Expected: FAIL for missing adapter behavior.

- [ ] **Step 4: Implement Hermes adapter construction**

Replace `lingneng/runtime/hermes_adapter.py` with:

```python
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from run_agent import AIAgent

from lingneng.config.settings import LingNengSettings
from lingneng.events.bridge import answer_delta, final_answer, run_started
from lingneng.runtime.agent_adapter import LingNengStreamEvent
from lingneng.schemas.chat_events import ErrorEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.hermes_session import LingNengHermesSessionStore
from lingneng.session.keys import ResolvedSessionKey


class HermesAgentRunAdapter:
    def __init__(
        self,
        settings: LingNengSettings,
        agent_cls: type = AIAgent,
        session_store: LingNengHermesSessionStore | None = None,
    ) -> None:
        self.settings = settings
        self.agent_cls = agent_cls
        self.session_store = session_store or LingNengHermesSessionStore(settings)
        self._last_agent_for_tests: Any | None = None

    async def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[LingNengStreamEvent]:
        yield run_started(run_id=run_id, request_id=request.request_id)
        try:
            history = self.session_store.load_conversation_history(resolved_session)
            agent = self._build_agent(resolved_session)
            self._last_agent_for_tests = agent
            result = agent.run_conversation(
                request.query.content,
                system_message=request.system_prompt.content,
                conversation_history=history,
                task_id=run_id,
                persist_user_message=request.query.content,
            )
            final_text = _final_response_from_result(result)
            if final_text:
                yield answer_delta(text=final_text, sequence=1)
            yield final_answer(run_id=run_id, answer=final_text)
        except Exception:
            yield _public_runtime_error(run_id, request.request_id)

    def _build_agent(self, resolved_session: ResolvedSessionKey):
        return self.agent_cls(
            platform="lingneng",
            session_id=resolved_session.session_key,
            session_db=self.session_store.db,
            enabled_toolsets=[],
            disabled_toolsets=["kanban"],
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )


def _final_response_from_result(result: Any) -> str:
    if isinstance(result, dict):
        value = result.get("final_response")
        return value if isinstance(value, str) else ""
    return ""


def _public_runtime_error(run_id: str, request_id: str) -> ErrorEvent:
    return ErrorEvent(
        run_id=run_id,
        request_id=request_id,
        code="RUNTIME_ERROR",
        message="Agent runtime failed",
        trace_id=f"trace_{uuid.uuid4().hex}",
        recoverable=False,
    )
```

Modify `lingneng/runtime/__init__.py`:

```python
from lingneng.runtime.agent_adapter import AgentRunAdapter, LingNengStreamEvent
from lingneng.runtime.fake_agent import FakeAgentRunAdapter
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter

__all__ = [
    "AgentRunAdapter",
    "FakeAgentRunAdapter",
    "HermesAgentRunAdapter",
    "LingNengStreamEvent",
]
```

- [ ] **Step 5: Run focused test and confirm pass**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime/test_hermes_adapter_config.py -q
```

Expected: PASS.

- [ ] **Step 6: Run runtime tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime -q
```

Expected: PASS.

- [ ] **Step 7: Review, commit, and push**

Run:

```bash
git diff --check
rg -n "T[B]D|T[O]DO|t[o]do|fill[[:space:]]in|implement[[:space:]]later|place[h]older|待[补]充|待[定]|占[位]" lingneng tests/lingneng docs/lingneng-migration/plans/2026-06-06-phase-2-hermes-agent-integration-plan.md
git status --short
git add lingneng/runtime/__init__.py lingneng/runtime/hermes_adapter.py tests/lingneng/runtime/test_hermes_adapter_config.py
git commit -m "feat: 接入 Hermes Agent 适配器"
git push origin dev
```

Rollback: revert this commit if Hermes adapter construction breaks fake mode or
runtime protocol tests.

---

### Task 2.4: Hermes Answer Stream Bridge

**Files:**
- Modify: `lingneng/runtime/hermes_adapter.py`
- Modify: `lingneng/events/bridge.py`
- Create: `tests/lingneng/runtime/test_hermes_answer_stream.py`

- [ ] **Step 1: Reload durable context**

Run the reload commands from Task 2.1 Step 1. Confirm the spec requires a
worker thread or equivalent executor and ordered callback-to-SSE bridging.

- [ ] **Step 2: Write failing stream bridge tests**

Create `tests/lingneng/runtime/test_hermes_answer_stream.py`:

```python
import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.schemas.chat_events import AnswerDeltaEvent, ErrorEvent, FinalEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def settings(tmp_path) -> LingNengSettings:
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_AGENT_MODE": "hermes",
            "LINGNENG_INTERNAL_API_KEY": "key",
        }
    )


class StreamingAgent:
    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")

    def run_conversation(self, *args, **kwargs):
        self.stream_delta_callback("你")
        self.stream_delta_callback("好")
        return {"final_response": "你好", "messages": []}


class NonStreamingAgent:
    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")

    def run_conversation(self, *args, **kwargs):
        return {"final_response": "完成", "messages": []}


class FailingAgent:
    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")

    def run_conversation(self, *args, **kwargs):
        raise RuntimeError("private provider detail")


def request_and_session():
    request = ChatStreamRequest.model_validate(full_payload())
    return request, resolve_session_key(request)


@pytest.mark.asyncio
async def test_stream_callback_becomes_ordered_answer_delta_events(tmp_path):
    request, resolved = request_and_session()
    adapter = HermesAgentRunAdapter(settings(tmp_path), agent_cls=StreamingAgent)

    events = [event async for event in adapter.stream(request, resolved, "run-1")]
    deltas = [event for event in events if isinstance(event, AnswerDeltaEvent)]
    final = events[-1]

    assert [delta.text for delta in deltas] == ["你", "好"]
    assert [delta.sequence for delta in deltas] == [1, 2]
    assert isinstance(final, FinalEvent)
    assert final.answer == "你好"
    assert "".join(delta.text for delta in deltas) == final.answer


@pytest.mark.asyncio
async def test_final_answer_is_synthesized_as_delta_when_no_streaming_occurs(tmp_path):
    request, resolved = request_and_session()
    adapter = HermesAgentRunAdapter(settings(tmp_path), agent_cls=NonStreamingAgent)

    events = [event async for event in adapter.stream(request, resolved, "run-1")]
    deltas = [event for event in events if isinstance(event, AnswerDeltaEvent)]
    final = events[-1]

    assert [delta.text for delta in deltas] == ["完成"]
    assert isinstance(final, FinalEvent)
    assert final.answer == "完成"


@pytest.mark.asyncio
async def test_hermes_exception_maps_to_public_error(tmp_path):
    request, resolved = request_and_session()
    adapter = HermesAgentRunAdapter(settings(tmp_path), agent_cls=FailingAgent)

    events = [event async for event in adapter.stream(request, resolved, "run-1")]
    error = events[-1]

    assert isinstance(error, ErrorEvent)
    assert error.code == "RUNTIME_ERROR"
    assert error.message == "Agent runtime failed"
    assert error.recoverable is False
```

Expected initial failure: current adapter emits a synthesized delta after final
instead of preserving streamed callback deltas, or blocks the event loop.

- [ ] **Step 3: Run focused test and confirm failure**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime/test_hermes_answer_stream.py -q
```

Expected: FAIL until callback queue bridge exists.

- [ ] **Step 4: Implement async queue bridge**

Modify `lingneng/runtime/hermes_adapter.py`:

```python
import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class _ThreadResult:
    final_response: str = ""
    error: BaseException | None = None


async def stream(...):
    yield run_started(run_id=run_id, request_id=request.request_id)
    queue: asyncio.Queue[AnswerDeltaEvent | _ThreadResult] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    sequence = 0
    streamed_text: list[str] = []

    def on_delta(text: str) -> None:
        nonlocal sequence
        if not text:
            return
        sequence += 1
        streamed_text.append(text)
        loop.call_soon_threadsafe(
            queue.put_nowait,
            answer_delta(text=text, sequence=sequence),
        )

    def run_agent() -> _ThreadResult:
        try:
            history = self.session_store.load_conversation_history(resolved_session)
            agent = self._build_agent(resolved_session, stream_delta_callback=on_delta)
            self._last_agent_for_tests = agent
            result = agent.run_conversation(
                request.query.content,
                system_message=request.system_prompt.content,
                conversation_history=history,
                task_id=run_id,
                persist_user_message=request.query.content,
            )
            return _ThreadResult(final_response=_final_response_from_result(result))
        except BaseException as exc:
            return _ThreadResult(error=exc)

    task = asyncio.create_task(asyncio.to_thread(run_agent))
    while True:
        if task.done() and queue.empty():
            result = task.result()
            if result.error is not None:
                yield _public_runtime_error(run_id, request.request_id)
                return
            final_text = result.final_response
            if not streamed_text:
                sequence += 1
                yield answer_delta(text=final_text, sequence=sequence)
            yield final_answer(run_id=run_id, answer=final_text)
            return
        try:
            item = await asyncio.wait_for(queue.get(), timeout=0.05)
        except asyncio.TimeoutError:
            continue
        yield item
```

Update `_build_agent()` to accept callback:

```python
def _build_agent(self, resolved_session, stream_delta_callback=None):
    return self.agent_cls(
        platform="lingneng",
        session_id=resolved_session.session_key,
        session_db=self.session_store.db,
        enabled_toolsets=[],
        disabled_toolsets=["kanban"],
        quiet_mode=True,
        skip_context_files=True,
        skip_memory=True,
        stream_delta_callback=stream_delta_callback,
    )
```

Keep `_public_runtime_error()` public-safe and do not include exception text.

- [ ] **Step 5: Run focused test and confirm pass**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime/test_hermes_answer_stream.py -q
```

Expected: PASS.

- [ ] **Step 6: Run runtime tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/runtime -q
```

Expected: PASS.

- [ ] **Step 7: Review, commit, and push**

Run:

```bash
git diff --check
rg -n "T[B]D|T[O]DO|t[o]do|fill[[:space:]]in|implement[[:space:]]later|place[h]older|待[补]充|待[定]|占[位]" lingneng tests/lingneng docs/lingneng-migration/plans/2026-06-06-phase-2-hermes-agent-integration-plan.md
git status --short
git add lingneng/runtime/hermes_adapter.py lingneng/events/bridge.py tests/lingneng/runtime/test_hermes_answer_stream.py
git commit -m "feat: 桥接 Hermes 流式回答"
git push origin dev
```

Rollback: revert this commit if streaming bridge introduces duplicated deltas
or route tests regress.

---

### Task 2.5: Terminal Run Replay

**Files:**
- Modify: `lingneng/api/routes.py`
- Modify: `lingneng/session/run_store.py`
- Create: `tests/lingneng/api/test_chat_stream_idempotency.py`

- [ ] **Step 1: Reload durable context**

Run the reload commands from Task 2.1 Step 1. Confirm replay rules for
`running`, `succeeded`, and `failed`.

- [ ] **Step 2: Write failing idempotency replay tests**

Create `tests/lingneng/api/test_chat_stream_idempotency.py`:

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


INTERNAL_KEY = "key"


def settings(tmp_path) -> LingNengSettings:
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_INTERNAL_API_KEY": INTERNAL_KEY,
        }
    )


def parse_sse(text: str) -> list[tuple[str, dict]]:
    frames = []
    for raw_frame in text.strip().split("\n\n"):
        lines = raw_frame.splitlines()
        if not lines or lines[0].startswith(":"):
            continue
        event_line = next(line for line in lines if line.startswith("event: "))
        data_line = next(line for line in lines if line.startswith("data: "))
        frames.append(
            (
                event_line.removeprefix("event: "),
                json.loads(data_line.removeprefix("data: ")),
            )
        )
    return frames


class CountingSuccessAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[RunStartedEvent | AnswerDeltaEvent | FinalEvent]:
        self.calls += 1
        yield RunStartedEvent(run_id=run_id, request_id=request.request_id)
        yield AnswerDeltaEvent(text="完成", sequence=1)
        yield FinalEvent(
            run_id=run_id,
            status="succeeded",
            answer="完成",
            artifacts=[{"artifact_id": "a-1"}],
        )


class CountingFailureAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[ErrorEvent]:
        self.calls += 1
        yield ErrorEvent(
            run_id=run_id,
            request_id=request.request_id,
            code="RUNTIME_ERROR",
            message="Agent runtime failed",
            trace_id="trace-test",
            recoverable=False,
        )


def post(client: TestClient, payload: dict):
    return client.post(
        "/internal/agent/chat/stream",
        json=payload,
        headers={"X-Internal-Key": INTERNAL_KEY},
    )


def test_repeated_success_replays_stored_sse_without_adapter(tmp_path):
    adapter = CountingSuccessAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    app = create_app(settings=settings(tmp_path), adapter=adapter, run_store=store)
    client = TestClient(app)

    first = post(client, full_payload())
    second = post(client, full_payload())
    frames = parse_sse(second.text)

    assert first.status_code == 200
    assert second.status_code == 200
    assert [event for event, _ in frames] == ["run_started", "answer_delta", "final"]
    assert frames[1][1]["text"] == "完成"
    assert frames[2][1]["answer"] == "完成"
    assert frames[2][1]["artifacts"] == [{"artifact_id": "a-1"}]
    assert adapter.calls == 1


def test_repeated_failure_replays_stored_public_error_without_adapter(tmp_path):
    adapter = CountingFailureAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    app = create_app(settings=settings(tmp_path), adapter=adapter, run_store=store)
    client = TestClient(app)

    first = post(client, full_payload())
    second = post(client, full_payload())
    frames = parse_sse(second.text)

    assert first.status_code == 200
    assert second.status_code == 200
    assert [event for event, _ in frames] == ["error"]
    assert frames[0][1]["code"] == "RUNTIME_ERROR"
    assert frames[0][1]["message"] == "Agent runtime failed"
    assert adapter.calls == 1


def test_repeated_running_still_returns_running_error_without_adapter(tmp_path):
    adapter = CountingSuccessAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    store.reserve_run("tenant-a:user-a:emp-001:conv-a", "req-001")
    app = create_app(settings=settings(tmp_path), adapter=adapter, run_store=store)

    response = post(TestClient(app), full_payload())
    frames = parse_sse(response.text)

    assert [event for event, _ in frames] == ["error"]
    assert frames[0][1]["code"] == "REQUEST_ALREADY_RUNNING"
    assert adapter.calls == 0
```

Expected initial failure: repeated completed requests emit
`REQUEST_ALREADY_COMPLETED` instead of replayed terminal output.

- [ ] **Step 3: Run focused test and confirm failure**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/api/test_chat_stream_idempotency.py -q
```

Expected: FAIL for completed replay behavior.

- [ ] **Step 4: Implement run replay**

Modify `lingneng/api/routes.py` duplicate handling:

```python
if not reservation.created:
    stream = _replay_or_duplicate_stream(
        reservation.record,
        request.request_id,
    )
else:
    stream = _adapter_stream(...)
```

Add replay helper:

```python
async def _replay_or_duplicate_stream(
    record: RunRecord,
    request_id: str,
) -> AsyncIterator[str]:
    if record.status is RunStatus.RUNNING:
        yield _duplicate_error_frame(
            record.run_id,
            request_id,
            "REQUEST_ALREADY_RUNNING",
            "Request is already running",
        )
        return
    if record.status is RunStatus.SUCCEEDED:
        answer = record.answer or ""
        yield encode_sse("run_started", RunStartedEvent(record.run_id, request_id))
        yield encode_sse("answer_delta", AnswerDeltaEvent(text=answer, sequence=1))
        yield encode_sse(
            "final",
            FinalEvent(
                run_id=record.run_id,
                status="succeeded",
                answer=answer,
                artifacts=record.artifacts,
            ),
        )
        return
    yield encode_sse(
        "error",
        ErrorEvent(
            run_id=record.run_id,
            request_id=request_id,
            code=record.error_code or "RUNTIME_ERROR",
            message=record.error_message or "Agent runtime failed",
            trace_id=_new_trace_id(),
            recoverable=False,
        ),
    )
```

Keep `_duplicate_stream()` only if tests still call it directly; otherwise
replace it with the replay helper.

No database schema migration is required because Phase 1 already stores answer,
artifacts, error code, and error message.

- [ ] **Step 5: Run focused test and confirm pass**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/api/test_chat_stream_idempotency.py -q
```

Expected: PASS.

- [ ] **Step 6: Run API tests**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/api -q
```

Expected: PASS. Existing Phase 1 duplicate completed expectations may need to
be updated to replay behavior because Phase 2 intentionally changes completed
duplicate handling.

- [ ] **Step 7: Review, commit, and push**

Run:

```bash
git diff --check
rg -n "T[B]D|T[O]DO|t[o]do|fill[[:space:]]in|implement[[:space:]]later|place[h]older|待[补]充|待[定]|占[位]" lingneng tests/lingneng docs/lingneng-migration/plans/2026-06-06-phase-2-hermes-agent-integration-plan.md
git status --short
git add lingneng/api/routes.py lingneng/session/run_store.py tests/lingneng/api/test_chat_stream_contract.py tests/lingneng/api/test_chat_stream_idempotency.py
git commit -m "fix: 支持灵能终态请求重放"
git push origin dev
```

Rollback: revert this commit if duplicate running protection regresses or
stored errors leak private exception details.

---

### Task 2.6: No-Tool Route Contract And Phase Verification

**Files:**
- Create: `tests/lingneng/contract/test_chat_stream_minimal.py`
- Modify: `lingneng/runtime/hermes_adapter.py` only if contract test exposes a
  gap.

- [ ] **Step 1: Reload durable context**

Run the reload commands from Task 2.1 Step 1. Confirm this is the final Phase 2
contract slice and deployment remains out of scope.

- [ ] **Step 2: Write no-tool route contract test**

Create `tests/lingneng/contract/test_chat_stream_minimal.py`:

```python
import json

from fastapi.testclient import TestClient

from lingneng.api.app import create_app
from lingneng.config.settings import LingNengSettings
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from tests.lingneng.schemas.test_chat_request_schema import full_payload


INTERNAL_KEY = "key"


def parse_sse(text: str) -> list[tuple[str, dict]]:
    frames = []
    for raw_frame in text.strip().split("\n\n"):
        lines = raw_frame.splitlines()
        if not lines or lines[0].startswith(":"):
            continue
        event_line = next(line for line in lines if line.startswith("event: "))
        data_line = next(line for line in lines if line.startswith("data: "))
        frames.append(
            (
                event_line.removeprefix("event: "),
                json.loads(data_line.removeprefix("data: ")),
            )
        )
    return frames


class ContractAgent:
    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")

    def run_conversation(self, *args, **kwargs):
        self.stream_delta_callback("你")
        self.stream_delta_callback("好")
        return {"final_response": "你好", "messages": []}


def test_hermes_mode_no_tool_chat_stream_contract(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_AGENT_MODE": "hermes",
            "LINGNENG_INTERNAL_API_KEY": INTERNAL_KEY,
        }
    )
    adapter = HermesAgentRunAdapter(settings=settings, agent_cls=ContractAgent)
    app = create_app(settings=settings, adapter=adapter)
    response = TestClient(app).post(
        "/internal/agent/chat/stream",
        json=full_payload(),
        headers={"X-Internal-Key": INTERNAL_KEY},
    )

    frames = parse_sse(response.text)
    event_names = [event_name for event_name, _ in frames]
    deltas = [data["text"] for event_name, data in frames if event_name == "answer_delta"]
    final_payload = frames[-1][1]

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert event_names == ["run_started", "answer_delta", "answer_delta", "final"]
    assert "".join(deltas) == final_payload["answer"]
    assert final_payload["answer"] == "你好"
    assert "event" not in final_payload
```

Expected initial failure only if previous tasks missed route integration. If it
passes immediately, keep the test as the Phase 2 end-to-end guard.

- [ ] **Step 3: Run focused contract test**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/contract/test_chat_stream_minimal.py -q
```

Expected: PASS after Tasks 2.1 through 2.5.

- [ ] **Step 4: Run full Phase 2 verification**

Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/config tests/lingneng/schemas tests/lingneng/session tests/lingneng/api tests/lingneng/runtime tests/lingneng/contract -q
```

Expected: PASS.

Run:

```bash
/Users/rotas/Documents/work/hailun/LingNengAI/.venv/bin/python -m pytest /Users/rotas/Documents/work/hailun/LingNengAI/tests/contract/test_chat_events.py -q
```

Expected: PASS where the LingNengAI reference virtual environment is available.

Run:

```bash
uv run --extra dev python -m ruff check lingneng tests/lingneng
git diff --check
rg -n "T[B]D|T[O]DO|t[o]do|fill[[:space:]]in|implement[[:space:]]later|place[h]older|待[补]充|待[定]|占[位]" lingneng tests/lingneng docs/lingneng-migration/plans/2026-06-06-phase-2-hermes-agent-integration-plan.md
```

Expected:

- `ruff check` passes.
- `git diff --check` exits 0.
- The incomplete-marker scan exits 1 with no matches.

- [ ] **Step 5: Review, commit, and push**

Run:

```bash
git status --short
git add tests/lingneng/contract/test_chat_stream_minimal.py lingneng/runtime/hermes_adapter.py
git commit -m "test: 增加灵能 Hermes 最小对话合同测试"
git push origin dev
```

If `lingneng/runtime/hermes_adapter.py` was not changed in this task, omit it
from `git add`.

- [ ] **Step 6: Final Phase 2 review**

After the final task commit is pushed:

1. Re-run the full Phase 2 verification commands from Step 4 on the latest
   `HEAD`.
2. Dispatch a final code-review subagent over the Phase 2 implementation range.
3. Fix any critical or important findings with tests, commit, and push.
4. Re-run full verification on the latest `HEAD`.
5. Mark Phase 2 complete only after fresh verification and final review pass.

Rollback: revert this task commit if the contract test is wrong or forces a
behavior outside the Phase 2 spec.

## Phase 2 Completion Checklist

Phase 2 is complete only when:

- The Phase 2 spec acceptance criteria all map to implemented code and tests.
- `LINGNENG_AGENT_MODE=fake` still passes Phase 1 route tests.
- `LINGNENG_AGENT_MODE=hermes` selects `HermesAgentRunAdapter`.
- `HermesAgentRunAdapter` constructs `AIAgent` with no tools and LingNeng
  SessionDB.
- `HermesAgentRunAdapter` clears inherited `HERMES_KANBAN_*` worker environment
  during construction/run with a lock covering the entire context and restores
  it afterward.
- `HermesAgentRunAdapter` installs a LingNeng-only activity tracker so kanban
  heartbeat side effects do not run.
- Fake-mode imports do not load `hermes_state`, while
  `from lingneng.session import LingNengHermesSessionStore` still resolves.
- Java `history` is not passed to `AIAgent` and not persisted into SessionDB.
- Hermes deltas become ordered `answer_delta` SSE events.
- Non-streaming Hermes successful results synthesize one `answer_delta`, even
  when the final answer is empty.
- Completed success and failure duplicate requests replay stored terminal
  output without invoking the adapter; successful replay always emits one
  `answer_delta`, even when the stored answer is empty.
- Replayed requests do not append duplicate user messages.
- Phase-level pytest, reference contract, ruff, diff, and incomplete-marker
  checks pass.
- Final code review returns no required changes.
- All Phase 2 task commits are pushed to `origin/dev`.

## Next Phase Entry

Do not start Phase 3 implementation after Phase 2. First write a dedicated
Phase 3 spec in `docs/lingneng-migration/specs/`, then write a Phase 3 plan in
`docs/lingneng-migration/plans/`, then execute with subagents after review.
