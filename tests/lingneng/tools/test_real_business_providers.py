from __future__ import annotations

from pathlib import Path

from lingneng.config.settings import LingNengSettings
from lingneng.tools.providers import build_lingneng_tool_providers


def settings(tmp_path: Path, **env_overrides: str) -> LingNengSettings:
    env = {"LINGNENG_RUNTIME_DIR": str(tmp_path)}
    env.update(env_overrides)
    return LingNengSettings.from_env(env)


def test_provider_factory_returns_none_for_incomplete_config(tmp_path):
    providers = build_lingneng_tool_providers(settings(tmp_path))

    assert providers.web_search is None
    assert providers.document_generation is None
    assert providers.image_generation is None
    assert providers.chart_visualization is None
