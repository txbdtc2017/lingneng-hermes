from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator


_LOCAL_ENVS = {"local", "dev", "test"}
AgentMode = Literal["fake", "hermes"]


def _bool_from_env(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _path_list_from_env(value: str | None) -> list[Path]:
    if value is None:
        return []
    stripped = value.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        parsed = json.loads(stripped)
        if not isinstance(parsed, list):
            raise ValueError("LINGNENG_SKILL_ROOTS JSON value must be a list")
        return [Path(str(item).strip()) for item in parsed if str(item).strip()]
    normalized = stripped.replace("\n", ",")
    return [Path(part.strip()) for part in normalized.split(",") if part.strip()]


def _str_list_from_env(value: str | None) -> list[str]:
    if value is None:
        return []
    stripped = value.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        parsed = json.loads(stripped)
        if not isinstance(parsed, list):
            raise ValueError("JSON list setting value must be a list")
        return [str(item).strip() for item in parsed if str(item).strip()]
    normalized = stripped.replace("\n", ",")
    return [part.strip() for part in normalized.split(",") if part.strip()]


class LingNengSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_env: str = "dev"
    api_host: str = "127.0.0.1"
    api_port: int = 18083
    runtime_dir: Path = Path(".runtime/lingneng")
    session_db_path: Path | None = None
    route_pending_db_path: Path | None = None
    agent_mode: AgentMode = "fake"
    internal_api_key: str = Field(default="", repr=False)
    allow_insecure_local: bool = False
    session_retention_days: int = 90
    archived_session_retention_days: int = 180
    idempotency_retention_days: int = 7
    heartbeat_interval_seconds: float = 15.0
    skill_roots: list[Path] = Field(default_factory=list)
    skill_excerpt_max_chars: int = Field(default=4000, ge=500)
    skill_prompt_max_chars: int = Field(default=12000, ge=1000)
    skill_read_max_chars: int = Field(default=12000, ge=1000)
    skill_resource_max_chars: int = Field(default=12000, ge=1000)
    skill_resource_max_bytes: int = Field(default=262144, ge=1024)
    route_pending_ttl_seconds: int = Field(default=600, ge=1)
    route_reason_max_chars: int = Field(default=300, ge=20)
    route_reply_max_chars: int = Field(default=500, ge=20)
    rag_endpoint: str = ""
    rag_api_key: str = Field(default="", repr=False)
    rag_timeout_seconds: float = Field(default=5.0, ge=0.1)
    rag_default_top_k: int = Field(default=5, ge=1)
    rag_max_top_k: int = Field(default=20, ge=1)
    rag_context_max_chars: int = Field(default=6000, ge=500)
    artifact_public_base_url: str = ""
    artifact_url_allowed_hosts: list[str] = Field(default_factory=list)
    tool_result_max_chars: int = Field(default=6000, ge=500)
    document_max_content_chars: int = Field(default=20000, ge=1000)
    image_max_count: int = Field(default=4, ge=1)
    generation_timeout_seconds: float = Field(default=300.0, ge=1.0)
    web_search_default_top_k: int = Field(default=5, ge=1)
    web_search_max_top_k: int = Field(default=10, ge=1)
    attachment_allowed_hosts: list[str] = Field(default_factory=list)
    attachment_max_files: int = Field(default=5, ge=0)
    attachment_max_total_bytes: int = Field(default=52428800, ge=0)
    attachment_max_file_bytes: int = Field(default=20971520, ge=0)
    attachment_max_image_bytes: int = Field(default=10485760, ge=0)
    attachment_timeout_seconds: float = Field(default=30.0, ge=0.1)
    attachment_context_max_chars: int = Field(default=6000, ge=500)
    attachment_provider: str = ""
    attachment_http_endpoint: str = ""
    attachment_http_api_key: str = Field(default="", repr=False)
    attachment_http_timeout_seconds: float = Field(default=30.0, ge=0.1)
    attachment_http_max_response_bytes: int = Field(default=1048576, ge=1024)
    attachment_local_text_max_bytes: int = Field(default=2097152, ge=1)
    attachment_local_text_max_chars_per_file: int = Field(default=12000, ge=500)
    attachment_selected_chunk_limit: int = Field(default=4, ge=1)
    attachment_chunk_size: int = Field(default=3000, ge=500)
    attachment_chunk_overlap: int = Field(default=300, ge=0)
    time_context_enabled: bool = True
    time_context_default_timezone: str = "Asia/Shanghai"
    time_context_default_region: str = "CN"
    time_context_max_events: int = Field(default=5, ge=0)
    time_context_prompt_max_chars: int = Field(default=3000, ge=500)
    prompt_section_max_chars: int = Field(default=8000, ge=500)
    web_search_provider: str = ""
    bocha_web_search_api_key: str = Field(default="", repr=False)
    bocha_web_search_base_url: str = "https://api.bochaai.com"
    bocha_web_search_timeout_seconds: float = Field(default=30.0, ge=0.1)
    document_provider: str = ""
    java_agent_file_base_url: str = ""
    java_agent_file_upload_path: str = "/ai/internal/agent-file/upload"
    java_internal_key: str = Field(default="", repr=False)
    java_agent_file_upload_timeout_seconds: float = Field(default=120.0, ge=0.1)
    image_provider: str = ""
    aigc_image_base_url: str = ""
    aigc_image_timeout_seconds: float = Field(default=30.0, ge=0.1)
    aigc_result_store: str = ""
    aigc_redis_url: str = Field(default="", repr=False)
    aigc_redis_key_prefix: str = "lingneng-agent"
    aigc_result_ttl_seconds: int = Field(default=7200, ge=1)
    aigc_result_wait_timeout_seconds: float = Field(default=300.0, ge=0.1)
    aigc_result_poll_interval_seconds: float = Field(default=1.0, ge=0.01)
    tool_artifact_max_calls_per_run: int = Field(default=3, ge=1)
    web_search_max_calls_per_run: int = Field(default=12, ge=1)
    duplicate_artifact_guard_enabled: bool = True

    @model_validator(mode="after")
    def _default_storage_paths(self) -> "LingNengSettings":
        if self.session_db_path is None:
            self.session_db_path = self.runtime_dir / "sessions.sqlite3"
        if self.route_pending_db_path is None:
            self.route_pending_db_path = self.runtime_dir / "route_pending.sqlite3"
        upload_path = self.java_agent_file_upload_path.strip()
        if not upload_path:
            upload_path = "/"
        elif not upload_path.startswith("/"):
            upload_path = f"/{upload_path}"
        self.java_agent_file_upload_path = upload_path
        return self

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "LingNengSettings":
        source = os.environ if env is None else env
        session_db_value = source.get("LINGNENG_SESSION_DB_PATH")
        route_pending_value = source.get("LINGNENG_ROUTE_PENDING_DB_PATH")
        return cls(
            app_env=source.get("LINGNENG_APP_ENV", "dev"),
            api_host=source.get("LINGNENG_API_HOST", "127.0.0.1"),
            api_port=int(source.get("LINGNENG_API_PORT", "18083")),
            runtime_dir=Path(
                source.get("LINGNENG_RUNTIME_DIR", ".runtime/lingneng")
            ),
            session_db_path=Path(session_db_value) if session_db_value else None,
            route_pending_db_path=Path(route_pending_value)
            if route_pending_value
            else None,
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
            skill_roots=_path_list_from_env(source.get("LINGNENG_SKILL_ROOTS")),
            skill_excerpt_max_chars=int(
                source.get("LINGNENG_SKILL_EXCERPT_MAX_CHARS", "4000")
            ),
            skill_prompt_max_chars=int(
                source.get("LINGNENG_SKILL_PROMPT_MAX_CHARS", "12000")
            ),
            skill_read_max_chars=int(
                source.get("LINGNENG_SKILL_READ_MAX_CHARS", "12000")
            ),
            skill_resource_max_chars=int(
                source.get("LINGNENG_SKILL_RESOURCE_MAX_CHARS", "12000")
            ),
            skill_resource_max_bytes=int(
                source.get("LINGNENG_SKILL_RESOURCE_MAX_BYTES", "262144")
            ),
            route_pending_ttl_seconds=int(
                source.get("LINGNENG_ROUTE_PENDING_TTL_SECONDS", "600")
            ),
            route_reason_max_chars=int(
                source.get("LINGNENG_ROUTE_REASON_MAX_CHARS", "300")
            ),
            route_reply_max_chars=int(
                source.get("LINGNENG_ROUTE_REPLY_MAX_CHARS", "500")
            ),
            rag_endpoint=source.get("LINGNENG_RAG_ENDPOINT", ""),
            rag_api_key=source.get("LINGNENG_RAG_API_KEY", ""),
            rag_timeout_seconds=float(
                source.get("LINGNENG_RAG_TIMEOUT_SECONDS", "5.0")
            ),
            rag_default_top_k=int(source.get("LINGNENG_RAG_DEFAULT_TOP_K", "5")),
            rag_max_top_k=int(source.get("LINGNENG_RAG_MAX_TOP_K", "20")),
            rag_context_max_chars=int(
                source.get("LINGNENG_RAG_CONTEXT_MAX_CHARS", "6000")
            ),
            artifact_public_base_url=source.get(
                "LINGNENG_ARTIFACT_PUBLIC_BASE_URL", ""
            ),
            artifact_url_allowed_hosts=_str_list_from_env(
                source.get("LINGNENG_ARTIFACT_URL_ALLOWED_HOSTS")
            ),
            tool_result_max_chars=int(
                source.get("LINGNENG_TOOL_RESULT_MAX_CHARS", "6000")
            ),
            document_max_content_chars=int(
                source.get("LINGNENG_DOCUMENT_MAX_CONTENT_CHARS", "20000")
            ),
            image_max_count=int(source.get("LINGNENG_IMAGE_MAX_COUNT", "4")),
            generation_timeout_seconds=float(
                source.get("LINGNENG_GENERATION_TIMEOUT_SECONDS", "300.0")
            ),
            web_search_default_top_k=int(
                source.get("LINGNENG_WEB_SEARCH_DEFAULT_TOP_K", "5")
            ),
            web_search_max_top_k=int(
                source.get("LINGNENG_WEB_SEARCH_MAX_TOP_K", "10")
            ),
            attachment_allowed_hosts=_str_list_from_env(
                source.get("LINGNENG_ATTACHMENT_ALLOWED_HOSTS")
            ),
            attachment_max_files=int(
                source.get("LINGNENG_ATTACHMENT_MAX_FILES", "5")
            ),
            attachment_max_total_bytes=int(
                source.get("LINGNENG_ATTACHMENT_MAX_TOTAL_BYTES", "52428800")
            ),
            attachment_max_file_bytes=int(
                source.get("LINGNENG_ATTACHMENT_MAX_FILE_BYTES", "20971520")
            ),
            attachment_max_image_bytes=int(
                source.get("LINGNENG_ATTACHMENT_MAX_IMAGE_BYTES", "10485760")
            ),
            attachment_timeout_seconds=float(
                source.get("LINGNENG_ATTACHMENT_TIMEOUT_SECONDS", "30.0")
            ),
            attachment_context_max_chars=int(
                source.get("LINGNENG_ATTACHMENT_CONTEXT_MAX_CHARS", "6000")
            ),
            attachment_provider=source.get("LINGNENG_ATTACHMENT_PROVIDER", ""),
            attachment_http_endpoint=source.get(
                "LINGNENG_ATTACHMENT_HTTP_ENDPOINT", ""
            ),
            attachment_http_api_key=source.get(
                "LINGNENG_ATTACHMENT_HTTP_API_KEY", ""
            ),
            attachment_http_timeout_seconds=float(
                source.get("LINGNENG_ATTACHMENT_HTTP_TIMEOUT_SECONDS", "30.0")
            ),
            attachment_http_max_response_bytes=int(
                source.get("LINGNENG_ATTACHMENT_HTTP_MAX_RESPONSE_BYTES", "1048576")
            ),
            attachment_local_text_max_bytes=int(
                source.get("LINGNENG_ATTACHMENT_LOCAL_TEXT_MAX_BYTES", "2097152")
            ),
            attachment_local_text_max_chars_per_file=int(
                source.get(
                    "LINGNENG_ATTACHMENT_LOCAL_TEXT_MAX_CHARS_PER_FILE", "12000"
                )
            ),
            attachment_selected_chunk_limit=int(
                source.get("LINGNENG_ATTACHMENT_SELECTED_CHUNK_LIMIT", "4")
            ),
            attachment_chunk_size=int(
                source.get("LINGNENG_ATTACHMENT_CHUNK_SIZE", "3000")
            ),
            attachment_chunk_overlap=int(
                source.get("LINGNENG_ATTACHMENT_CHUNK_OVERLAP", "300")
            ),
            time_context_enabled=_bool_from_env(
                source.get("LINGNENG_TIME_CONTEXT_ENABLED"), True
            ),
            time_context_default_timezone=source.get(
                "LINGNENG_TIME_CONTEXT_DEFAULT_TIMEZONE", "Asia/Shanghai"
            ),
            time_context_default_region=source.get(
                "LINGNENG_TIME_CONTEXT_DEFAULT_REGION", "CN"
            ),
            time_context_max_events=int(
                source.get("LINGNENG_TIME_CONTEXT_MAX_EVENTS", "5")
            ),
            time_context_prompt_max_chars=int(
                source.get("LINGNENG_TIME_CONTEXT_PROMPT_MAX_CHARS", "3000")
            ),
            prompt_section_max_chars=int(
                source.get("LINGNENG_PROMPT_SECTION_MAX_CHARS", "8000")
            ),
            web_search_provider=source.get("LINGNENG_WEB_SEARCH_PROVIDER", ""),
            bocha_web_search_api_key=source.get(
                "LINGNENG_BOCHA_WEB_SEARCH_API_KEY", ""
            ),
            bocha_web_search_base_url=source.get(
                "LINGNENG_BOCHA_WEB_SEARCH_BASE_URL", "https://api.bochaai.com"
            ),
            bocha_web_search_timeout_seconds=float(
                source.get("LINGNENG_BOCHA_WEB_SEARCH_TIMEOUT_SECONDS", "30.0")
            ),
            document_provider=source.get("LINGNENG_DOCUMENT_PROVIDER", ""),
            java_agent_file_base_url=source.get(
                "LINGNENG_JAVA_AGENT_FILE_BASE_URL", ""
            ),
            java_agent_file_upload_path=source.get(
                "LINGNENG_JAVA_AGENT_FILE_UPLOAD_PATH",
                "/ai/internal/agent-file/upload",
            ),
            java_internal_key=source.get("LINGNENG_JAVA_INTERNAL_KEY", ""),
            java_agent_file_upload_timeout_seconds=float(
                source.get("LINGNENG_JAVA_AGENT_FILE_UPLOAD_TIMEOUT_SECONDS", "120.0")
            ),
            image_provider=source.get("LINGNENG_IMAGE_PROVIDER", ""),
            aigc_image_base_url=source.get("LINGNENG_AIGC_IMAGE_BASE_URL", ""),
            aigc_image_timeout_seconds=float(
                source.get("LINGNENG_AIGC_IMAGE_TIMEOUT_SECONDS", "30.0")
            ),
            aigc_result_store=source.get("LINGNENG_AIGC_RESULT_STORE", ""),
            aigc_redis_url=source.get("LINGNENG_AIGC_REDIS_URL", ""),
            aigc_redis_key_prefix=source.get(
                "LINGNENG_AIGC_REDIS_KEY_PREFIX", "lingneng-agent"
            ),
            aigc_result_ttl_seconds=int(
                source.get("LINGNENG_AIGC_RESULT_TTL_SECONDS", "7200")
            ),
            aigc_result_wait_timeout_seconds=float(
                source.get("LINGNENG_AIGC_RESULT_WAIT_TIMEOUT_SECONDS", "300.0")
            ),
            aigc_result_poll_interval_seconds=float(
                source.get("LINGNENG_AIGC_RESULT_POLL_INTERVAL_SECONDS", "1.0")
            ),
            tool_artifact_max_calls_per_run=int(
                source.get("LINGNENG_TOOL_ARTIFACT_MAX_CALLS_PER_RUN", "3")
            ),
            web_search_max_calls_per_run=int(
                source.get("LINGNENG_WEB_SEARCH_MAX_CALLS_PER_RUN", "12")
            ),
            duplicate_artifact_guard_enabled=_bool_from_env(
                source.get("LINGNENG_DUPLICATE_ARTIFACT_GUARD_ENABLED"), True
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

    @property
    def web_search_configured(self) -> bool:
        return (
            self.web_search_provider.strip().lower() == "bocha"
            and bool(self.bocha_web_search_api_key.strip())
        )

    @property
    def document_provider_configured(self) -> bool:
        return (
            self.document_provider.strip().lower() == "java_file"
            and bool(self.java_agent_file_base_url.strip())
            and bool(self.java_internal_key.strip())
        )

    @property
    def image_provider_configured(self) -> bool:
        return (
            self.image_provider.strip().lower() == "aigc"
            and bool(self.aigc_image_base_url.strip())
            and self.aigc_result_store.strip().lower() == "redis"
            and bool(self.aigc_redis_url.strip())
        )

    @property
    def aigc_result_store_configured(self) -> bool:
        return (
            self.aigc_result_store.strip().lower() == "redis"
            and bool(self.aigc_redis_url.strip())
        )

    @property
    def attachment_http_provider_configured(self) -> bool:
        return (
            self.attachment_provider.strip().lower() == "http"
            and bool(self.attachment_http_endpoint.strip())
        )

    @property
    def attachment_local_text_provider_configured(self) -> bool:
        return self.attachment_provider.strip().lower() == "local_text"

    @property
    def attachment_provider_configured(self) -> bool:
        return (
            self.attachment_http_provider_configured
            or self.attachment_local_text_provider_configured
        )

    def ready_summary(self) -> dict[str, object]:
        return {
            "status": "ready"
            if self.is_chat_configuration_ready
            else "not_ready",
            "app_env": self.app_env,
            "agent_mode": self.agent_mode,
            "runtime_dir": str(self.runtime_dir),
            "session_db_path": str(self.session_db_path),
            "route_pending_db_path": str(self.route_pending_db_path),
            "auth_required": self.auth_required,
            "skill_root_count": len(self.skill_roots),
            "rag_configured": bool(self.rag_endpoint),
            "artifact_url_allow_list_count": len(self.artifact_url_allowed_hosts),
            "attachment_host_allow_list_count": len(self.attachment_allowed_hosts),
            "time_context_enabled": self.time_context_enabled,
            "web_search_configured": self.web_search_configured,
            "document_provider_configured": self.document_provider_configured,
            "image_provider_configured": self.image_provider_configured,
            "aigc_result_store_configured": self.aigc_result_store_configured,
            "attachment_provider_configured": self.attachment_provider_configured,
            "attachment_http_provider_configured": (
                self.attachment_http_provider_configured
            ),
            "attachment_local_text_provider_configured": (
                self.attachment_local_text_provider_configured
            ),
        }
