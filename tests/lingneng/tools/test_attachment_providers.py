from __future__ import annotations

from pathlib import Path

from lingneng.config.settings import LingNengSettings
from lingneng.tools.attachment_provider import (
    build_attachment_processing_provider,
)


def settings(tmp_path: Path, **overrides: str) -> LingNengSettings:
    env = {"LINGNENG_RUNTIME_DIR": str(tmp_path)}
    env.update(overrides)
    return LingNengSettings.from_env(env)


def test_attachment_provider_factory_returns_none_for_incomplete_config(tmp_path):
    assert build_attachment_processing_provider(settings(tmp_path)) is None
    assert (
        build_attachment_processing_provider(
            settings(
                tmp_path,
                LINGNENG_ATTACHMENT_PROVIDER="http",
                LINGNENG_ATTACHMENT_HTTP_ENDPOINT="",
            )
        )
        is None
    )


def test_attachment_provider_factory_builds_local_text_provider(tmp_path):
    provider = build_attachment_processing_provider(
        settings(tmp_path, LINGNENG_ATTACHMENT_PROVIDER="local_text")
    )

    assert provider.__class__.__name__ == "LocalTextAttachmentProcessingProvider"


def test_attachment_provider_factory_fail_closes_construction_errors(
    tmp_path,
    monkeypatch,
    caplog,
):
    import lingneng.tools.attachment_local_text_provider as local_provider_module

    class ExplodingProvider:
        def __init__(self, settings):
            del settings
            raise ValueError("https://secret.example?token=secret-token")

    monkeypatch.setattr(
        local_provider_module,
        "LocalTextAttachmentProcessingProvider",
        ExplodingProvider,
    )

    with caplog.at_level("WARNING", logger="lingneng.tools.attachment_provider"):
        provider = build_attachment_processing_provider(
            settings(tmp_path, LINGNENG_ATTACHMENT_PROVIDER="local_text")
        )

    assert provider is None
    assert "attachment local_text provider construction failed" in caplog.text
    assert "secret-token" not in caplog.text
    assert "https://secret.example" not in caplog.text
