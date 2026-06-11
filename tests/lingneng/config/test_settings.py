from pathlib import Path

import pytest
from pydantic import ValidationError

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
            "LINGNENG_SKILL_READ_MAX_CHARS": "13000",
            "LINGNENG_SKILL_RESOURCE_MAX_CHARS": "14000",
            "LINGNENG_SKILL_RESOURCE_MAX_BYTES": "300000",
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
    assert settings.skill_read_max_chars == 13000
    assert settings.skill_resource_max_chars == 14000
    assert settings.skill_resource_max_bytes == 300000


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


def test_phase_2_settings_include_session_db_path(tmp_path):
    settings = LingNengSettings.from_env(
        {"LINGNENG_RUNTIME_DIR": str(tmp_path / "runtime")}
    )
    direct_settings = LingNengSettings(runtime_dir=tmp_path / "direct-runtime")

    assert settings.agent_mode == "fake"
    assert settings.session_db_path == tmp_path / "runtime" / "sessions.sqlite3"
    assert (
        direct_settings.session_db_path
        == tmp_path / "direct-runtime" / "sessions.sqlite3"
    )


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


def test_skill_and_rag_settings_defaults_are_safe(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_INTERNAL_API_KEY": "key",
        }
    )

    assert settings.skill_roots == []
    assert settings.skill_excerpt_max_chars == 4000
    assert settings.skill_prompt_max_chars == 12000
    assert settings.skill_read_max_chars == 12000
    assert settings.skill_resource_max_chars == 12000
    assert settings.skill_resource_max_bytes == 262144
    assert settings.rag_endpoint == ""
    assert settings.rag_api_key == ""
    assert settings.rag_timeout_seconds == 5.0
    assert settings.rag_default_top_k == 5
    assert settings.rag_max_top_k == 20
    assert settings.rag_context_max_chars == 6000


def test_phase_5_artifact_generation_and_attachment_settings_defaults(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_INTERNAL_API_KEY": "key",
        }
    )

    assert settings.artifact_public_base_url == ""
    assert settings.artifact_url_allowed_hosts == []
    assert settings.tool_result_max_chars == 6000
    assert settings.document_max_content_chars == 20000
    assert settings.image_max_count == 4
    assert settings.generation_timeout_seconds == 300.0
    assert settings.web_search_default_top_k == 5
    assert settings.web_search_max_top_k == 10
    assert settings.attachment_allowed_hosts == []
    assert settings.attachment_max_files == 5
    assert settings.attachment_max_total_bytes == 52428800
    assert settings.attachment_max_file_bytes == 20971520
    assert settings.attachment_max_image_bytes == 10485760
    assert settings.attachment_timeout_seconds == 30.0
    assert settings.attachment_context_max_chars == 6000


def test_skill_roots_parse_json_comma_and_newline(tmp_path):
    first = tmp_path / "employees"
    second = tmp_path / "tasks"
    json_settings = LingNengSettings.from_env(
        {
            "LINGNENG_SKILL_ROOTS": f'["{first}", "{second}"]',
        }
    )
    comma_settings = LingNengSettings.from_env(
        {
            "LINGNENG_SKILL_ROOTS": f"{first},{second}",
        }
    )
    newline_settings = LingNengSettings.from_env(
        {
            "LINGNENG_SKILL_ROOTS": f"{first}\n{second}",
        }
    )

    assert json_settings.skill_roots == [first, second]
    assert comma_settings.skill_roots == [first, second]
    assert newline_settings.skill_roots == [first, second]


def test_phase_5_string_list_settings_parse_json_comma_and_newline():
    first = "files.example.test"
    second = "cdn.example.test"

    json_settings = LingNengSettings.from_env(
        {"LINGNENG_ARTIFACT_URL_ALLOWED_HOSTS": f'["{first}", "{second}"]'}
    )
    comma_settings = LingNengSettings.from_env(
        {"LINGNENG_ATTACHMENT_ALLOWED_HOSTS": f"{first},{second}"}
    )
    newline_settings = LingNengSettings.from_env(
        {"LINGNENG_ATTACHMENT_ALLOWED_HOSTS": f"{first}\n{second}"}
    )

    assert json_settings.artifact_url_allowed_hosts == [first, second]
    assert comma_settings.attachment_allowed_hosts == [first, second]
    assert newline_settings.attachment_allowed_hosts == [first, second]


def test_ready_summary_hides_rag_api_key(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_INTERNAL_API_KEY": "key",
            "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
            "LINGNENG_RAG_API_KEY": "secret-rag-key",
        }
    )

    summary = settings.ready_summary()

    assert summary["rag_configured"] is True
    assert "rag_api_key" not in summary
    assert "secret-rag-key" not in repr(summary)


def test_ready_summary_reports_phase_5_non_secret_counts(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_INTERNAL_API_KEY": "key",
            "LINGNENG_ARTIFACT_URL_ALLOWED_HOSTS": "files.example.test",
            "LINGNENG_ATTACHMENT_ALLOWED_HOSTS": "files.example.test,cdn.example.test",
        }
    )

    summary = settings.ready_summary()

    assert summary["artifact_url_allow_list_count"] == 1
    assert summary["attachment_host_allow_list_count"] == 2
    assert "api_key" not in summary
    assert "secret" not in repr(summary).lower()


@pytest.mark.parametrize(
    ("env_name", "invalid_value"),
    [
        ("LINGNENG_SKILL_EXCERPT_MAX_CHARS", "499"),
        ("LINGNENG_SKILL_PROMPT_MAX_CHARS", "999"),
        ("LINGNENG_SKILL_READ_MAX_CHARS", "999"),
        ("LINGNENG_SKILL_RESOURCE_MAX_CHARS", "999"),
        ("LINGNENG_SKILL_RESOURCE_MAX_BYTES", "1023"),
        ("LINGNENG_RAG_TIMEOUT_SECONDS", "0.09"),
        ("LINGNENG_RAG_DEFAULT_TOP_K", "0"),
        ("LINGNENG_RAG_MAX_TOP_K", "0"),
        ("LINGNENG_RAG_CONTEXT_MAX_CHARS", "499"),
    ],
)
def test_skill_and_rag_settings_reject_values_below_spec_minimums(
    env_name, invalid_value
):
    with pytest.raises(ValidationError):
        LingNengSettings.from_env({env_name: invalid_value})


@pytest.mark.parametrize(
    ("env_name", "invalid_value"),
    [
        ("LINGNENG_TOOL_RESULT_MAX_CHARS", "499"),
        ("LINGNENG_DOCUMENT_MAX_CONTENT_CHARS", "999"),
        ("LINGNENG_IMAGE_MAX_COUNT", "0"),
        ("LINGNENG_GENERATION_TIMEOUT_SECONDS", "0.99"),
        ("LINGNENG_WEB_SEARCH_DEFAULT_TOP_K", "0"),
        ("LINGNENG_WEB_SEARCH_MAX_TOP_K", "0"),
        ("LINGNENG_ATTACHMENT_MAX_FILES", "-1"),
        ("LINGNENG_ATTACHMENT_MAX_TOTAL_BYTES", "-1"),
        ("LINGNENG_ATTACHMENT_MAX_FILE_BYTES", "-1"),
        ("LINGNENG_ATTACHMENT_MAX_IMAGE_BYTES", "-1"),
        ("LINGNENG_ATTACHMENT_TIMEOUT_SECONDS", "0.09"),
        ("LINGNENG_ATTACHMENT_CONTEXT_MAX_CHARS", "499"),
    ],
)
def test_phase_5_settings_reject_values_below_spec_minimums(
    env_name, invalid_value
):
    with pytest.raises(ValidationError):
        LingNengSettings.from_env({env_name: invalid_value})
