from lingneng.api.app import create_app
from lingneng.config.settings import LingNengSettings
from lingneng.runtime.fake_agent import FakeAgentRunAdapter
from lingneng.session.run_store import LingNengRunStore


def settings(tmp_path, **overrides) -> LingNengSettings:
    env = {
        "LINGNENG_APP_ENV": "test",
        "LINGNENG_RUNTIME_DIR": str(tmp_path),
        "LINGNENG_INTERNAL_API_KEY": "key",
    }
    env.update(overrides)
    return LingNengSettings.from_env(env)


def test_create_app_uses_fake_adapter_by_default(tmp_path):
    resolved_settings = settings(tmp_path)

    app = create_app(settings=resolved_settings)

    assert app.state.lingneng_settings is resolved_settings
    assert isinstance(app.state.lingneng_adapter, FakeAgentRunAdapter)
    assert isinstance(app.state.lingneng_run_store, LingNengRunStore)


def test_create_app_uses_hermes_adapter_for_hermes_mode(tmp_path):
    app = create_app(settings=settings(tmp_path, LINGNENG_AGENT_MODE="hermes"))

    assert app.state.lingneng_adapter.__class__.__name__ == "HermesAgentRunAdapter"
