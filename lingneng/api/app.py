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
