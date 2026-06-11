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


def test_route_settings_defaults(tmp_path):
    settings = LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})
    direct_settings = LingNengSettings(runtime_dir=tmp_path / "direct-runtime")

    assert settings.route_pending_db_path == tmp_path / "route_pending.sqlite3"
    assert settings.route_pending_ttl_seconds == 600
    assert settings.route_reason_max_chars == 300
    assert settings.route_reply_max_chars == 500
    assert direct_settings.route_pending_db_path == (
        tmp_path / "direct-runtime" / "route_pending.sqlite3"
    )


def test_route_settings_from_env(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path / "runtime"),
            "LINGNENG_ROUTE_PENDING_DB_PATH": str(tmp_path / "route.sqlite3"),
            "LINGNENG_ROUTE_PENDING_TTL_SECONDS": "120",
            "LINGNENG_ROUTE_REASON_MAX_CHARS": "80",
            "LINGNENG_ROUTE_REPLY_MAX_CHARS": "160",
        }
    )

    assert settings.route_pending_db_path == tmp_path / "route.sqlite3"
    assert settings.route_pending_ttl_seconds == 120
    assert settings.route_reason_max_chars == 80
    assert settings.route_reply_max_chars == 160


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


def test_phase_11_time_context_settings_defaults(tmp_path):
    settings = LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})

    assert settings.time_context_enabled is True
    assert settings.time_context_default_timezone == "Asia/Shanghai"
    assert settings.time_context_default_region == "CN"
    assert settings.time_context_max_events == 5
    assert settings.time_context_prompt_max_chars == 3000
    assert settings.prompt_section_max_chars == 8000
    assert settings.ready_summary()["time_context_enabled"] is True


def test_phase_11_time_context_settings_from_env(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path / "runtime"),
            "LINGNENG_TIME_CONTEXT_ENABLED": "false",
            "LINGNENG_TIME_CONTEXT_DEFAULT_TIMEZONE": "UTC",
            "LINGNENG_TIME_CONTEXT_DEFAULT_REGION": "CN",
            "LINGNENG_TIME_CONTEXT_MAX_EVENTS": "3",
            "LINGNENG_TIME_CONTEXT_PROMPT_MAX_CHARS": "1200",
            "LINGNENG_PROMPT_SECTION_MAX_CHARS": "2400",
        }
    )

    assert settings.time_context_enabled is False
    assert settings.time_context_default_timezone == "UTC"
    assert settings.time_context_default_region == "CN"
    assert settings.time_context_max_events == 3
    assert settings.time_context_prompt_max_chars == 1200
    assert settings.prompt_section_max_chars == 2400


def test_phase_12_provider_settings_defaults(tmp_path):
    settings = LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})

    assert settings.web_search_provider == ""
    assert settings.bocha_web_search_api_key == ""
    assert settings.bocha_web_search_base_url == "https://api.bochaai.com"
    assert settings.bocha_web_search_timeout_seconds == 30.0
    assert settings.document_provider == ""
    assert settings.java_agent_file_base_url == ""
    assert settings.java_agent_file_upload_path == "/ai/internal/agent-file/upload"
    assert settings.java_internal_key == ""
    assert settings.java_agent_file_upload_timeout_seconds == 120.0
    assert settings.image_provider == ""
    assert settings.aigc_image_base_url == ""
    assert settings.aigc_image_timeout_seconds == 30.0
    assert settings.aigc_result_store == ""
    assert settings.aigc_redis_url == ""
    assert settings.aigc_redis_key_prefix == "lingneng-agent"
    assert settings.aigc_result_ttl_seconds == 7200
    assert settings.aigc_result_wait_timeout_seconds == 300.0
    assert settings.aigc_result_poll_interval_seconds == 1.0
    assert settings.tool_artifact_max_calls_per_run == 3
    assert settings.web_search_max_calls_per_run == 12
    assert settings.duplicate_artifact_guard_enabled is True

    summary = settings.ready_summary()
    assert summary["web_search_configured"] is False
    assert summary["document_provider_configured"] is False
    assert summary["image_provider_configured"] is False
    assert summary["aigc_result_store_configured"] is False


def test_phase_12_provider_settings_from_env_are_secret_safe(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_WEB_SEARCH_PROVIDER": "bocha",
            "LINGNENG_BOCHA_WEB_SEARCH_API_KEY": "bocha-secret",
            "LINGNENG_BOCHA_WEB_SEARCH_BASE_URL": "https://bocha.example",
            "LINGNENG_BOCHA_WEB_SEARCH_TIMEOUT_SECONDS": "5.5",
            "LINGNENG_DOCUMENT_PROVIDER": "java_file",
            "LINGNENG_JAVA_AGENT_FILE_BASE_URL": "https://java-file.example",
            "LINGNENG_JAVA_AGENT_FILE_UPLOAD_PATH": "upload",
            "LINGNENG_JAVA_INTERNAL_KEY": "java-secret",
            "LINGNENG_JAVA_AGENT_FILE_UPLOAD_TIMEOUT_SECONDS": "33",
            "LINGNENG_IMAGE_PROVIDER": "aigc",
            "LINGNENG_AIGC_IMAGE_BASE_URL": "https://aigc.example",
            "LINGNENG_AIGC_IMAGE_TIMEOUT_SECONDS": "44",
            "LINGNENG_AIGC_RESULT_STORE": "redis",
            "LINGNENG_AIGC_REDIS_URL": "redis://:redis-secret@localhost:6379/0",
            "LINGNENG_AIGC_REDIS_KEY_PREFIX": "ln:test",
            "LINGNENG_AIGC_RESULT_TTL_SECONDS": "60",
            "LINGNENG_AIGC_RESULT_WAIT_TIMEOUT_SECONDS": "8",
            "LINGNENG_AIGC_RESULT_POLL_INTERVAL_SECONDS": "0.2",
            "LINGNENG_TOOL_ARTIFACT_MAX_CALLS_PER_RUN": "2",
            "LINGNENG_WEB_SEARCH_MAX_CALLS_PER_RUN": "4",
            "LINGNENG_DUPLICATE_ARTIFACT_GUARD_ENABLED": "false",
        }
    )

    assert settings.java_agent_file_upload_path == "/upload"
    assert settings.web_search_configured is True
    assert settings.document_provider_configured is True
    assert settings.image_provider_configured is True
    assert settings.aigc_result_store_configured is True
    assert settings.duplicate_artifact_guard_enabled is False

    dumped = repr(settings.ready_summary())
    assert "bocha-secret" not in dumped
    assert "java-secret" not in dumped
    assert "redis-secret" not in dumped


def test_phase_13_attachment_provider_settings_defaults(tmp_path):
    settings = LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})

    assert settings.attachment_provider == ""
    assert settings.attachment_http_endpoint == ""
    assert settings.attachment_http_api_key == ""
    assert settings.attachment_http_timeout_seconds == 30.0
    assert settings.attachment_http_max_response_bytes == 1048576
    assert settings.attachment_local_text_max_bytes == 2097152
    assert settings.attachment_local_text_max_chars_per_file == 12000
    assert settings.attachment_selected_chunk_limit == 4
    assert settings.attachment_chunk_size == 3000
    assert settings.attachment_chunk_overlap == 300
    assert settings.attachment_provider_configured is False
    assert settings.attachment_http_provider_configured is False
    assert settings.attachment_local_text_provider_configured is False

    summary = settings.ready_summary()
    assert summary["attachment_provider_configured"] is False
    assert summary["attachment_http_provider_configured"] is False
    assert summary["attachment_local_text_provider_configured"] is False


def test_phase_13_attachment_provider_settings_from_env_are_secret_safe(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_ATTACHMENT_PROVIDER": "http",
            "LINGNENG_ATTACHMENT_HTTP_ENDPOINT": "https://attachments.example/process",
            "LINGNENG_ATTACHMENT_HTTP_API_KEY": "attachment-secret",
            "LINGNENG_ATTACHMENT_HTTP_TIMEOUT_SECONDS": "9",
            "LINGNENG_ATTACHMENT_HTTP_MAX_RESPONSE_BYTES": "2048",
            "LINGNENG_ATTACHMENT_LOCAL_TEXT_MAX_BYTES": "1024",
            "LINGNENG_ATTACHMENT_LOCAL_TEXT_MAX_CHARS_PER_FILE": "1000",
            "LINGNENG_ATTACHMENT_SELECTED_CHUNK_LIMIT": "2",
            "LINGNENG_ATTACHMENT_CHUNK_SIZE": "700",
            "LINGNENG_ATTACHMENT_CHUNK_OVERLAP": "50",
        }
    )

    assert settings.attachment_provider_configured is True
    assert settings.attachment_http_provider_configured is True
    assert settings.attachment_local_text_provider_configured is False
    assert settings.attachment_http_timeout_seconds == 9.0
    assert settings.attachment_http_max_response_bytes == 2048
    assert settings.attachment_local_text_max_bytes == 1024
    assert settings.attachment_local_text_max_chars_per_file == 1000
    assert settings.attachment_selected_chunk_limit == 2
    assert settings.attachment_chunk_size == 700
    assert settings.attachment_chunk_overlap == 50
    assert "attachment-secret" not in repr(settings)
    assert "attachment-secret" not in repr(settings.ready_summary())


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


def test_phase_14_rag_hardening_settings_defaults(tmp_path):
    settings = LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})

    assert settings.rag_http_max_response_bytes == 1048576
    assert settings.rag_live_test_enabled is False
    assert settings.rag_live_test_query == ""

    summary = settings.ready_summary()
    assert summary["rag_configured"] is False
    assert summary["rag_http_max_response_bytes"] == 1048576
    assert summary["rag_live_test_enabled"] is False
    assert "rag_live_test_query" not in summary


def test_phase_14_rag_hardening_settings_from_env_are_secret_safe(tmp_path):
    settings = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve?token=url-token",
            "LINGNENG_RAG_API_KEY": "secret-rag-key",
            "LINGNENG_RAG_HTTP_MAX_RESPONSE_BYTES": "2048",
            "LINGNENG_RAG_LIVE_TEST_ENABLED": "true",
            "LINGNENG_RAG_LIVE_TEST_QUERY": "secret live query",
        }
    )

    assert settings.rag_http_max_response_bytes == 2048
    assert settings.rag_live_test_enabled is True
    assert settings.rag_live_test_query == "secret live query"

    dumped = repr(settings.ready_summary())
    assert "secret-rag-key" not in dumped
    assert "secret live query" not in dumped
    assert "url-token" not in dumped


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
        ("LINGNENG_RAG_HTTP_MAX_RESPONSE_BYTES", "1023"),
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
        ("LINGNENG_ROUTE_PENDING_TTL_SECONDS", "0"),
        ("LINGNENG_ROUTE_REASON_MAX_CHARS", "19"),
        ("LINGNENG_ROUTE_REPLY_MAX_CHARS", "19"),
    ],
)
def test_route_settings_reject_values_below_spec_minimums(
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
        ("LINGNENG_ATTACHMENT_HTTP_TIMEOUT_SECONDS", "0.09"),
        ("LINGNENG_ATTACHMENT_HTTP_MAX_RESPONSE_BYTES", "1023"),
        ("LINGNENG_ATTACHMENT_LOCAL_TEXT_MAX_BYTES", "0"),
        ("LINGNENG_ATTACHMENT_LOCAL_TEXT_MAX_CHARS_PER_FILE", "499"),
        ("LINGNENG_ATTACHMENT_SELECTED_CHUNK_LIMIT", "0"),
        ("LINGNENG_ATTACHMENT_CHUNK_SIZE", "499"),
        ("LINGNENG_ATTACHMENT_CHUNK_OVERLAP", "-1"),
        ("LINGNENG_TIME_CONTEXT_PROMPT_MAX_CHARS", "499"),
        ("LINGNENG_PROMPT_SECTION_MAX_CHARS", "499"),
    ],
)
def test_phase_5_settings_reject_values_below_spec_minimums(
    env_name, invalid_value
):
    with pytest.raises(ValidationError):
        LingNengSettings.from_env({env_name: invalid_value})
