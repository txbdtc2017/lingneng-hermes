from __future__ import annotations

from fastapi import FastAPI

from lingneng.api.routes import register_routes
from lingneng.config.settings import LingNengSettings
from lingneng.runtime.agent_adapter import AgentRunAdapter
from lingneng.runtime.fake_agent import FakeAgentRunAdapter
from lingneng.session.run_store import LingNengRunStore


def _default_adapter(settings: LingNengSettings) -> AgentRunAdapter:
    if settings.agent_mode == "fake":
        return FakeAgentRunAdapter()
    if settings.agent_mode == "hermes":
        from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter

        return HermesAgentRunAdapter(settings=settings)
    raise ValueError(f"Unsupported LingNeng agent mode: {settings.agent_mode}")


def create_app(
    settings: LingNengSettings | None = None,
    adapter: AgentRunAdapter | None = None,
    run_store: LingNengRunStore | None = None,
) -> FastAPI:
    resolved_settings = settings or LingNengSettings.from_env()
    resolved_adapter = adapter or _default_adapter(resolved_settings)
    resolved_store = run_store or LingNengRunStore(
        resolved_settings.runtime_dir / "runs.sqlite3",
        settings=resolved_settings,
    )

    app = FastAPI(title="LingNeng Hermes API")
    app.state.lingneng_settings = resolved_settings
    app.state.lingneng_adapter = resolved_adapter
    app.state.lingneng_run_store = resolved_store
    register_routes(app, resolved_settings, resolved_adapter, resolved_store)
    return app
