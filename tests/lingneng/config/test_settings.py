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
