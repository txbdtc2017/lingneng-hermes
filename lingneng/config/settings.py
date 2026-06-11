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
    time_context_enabled: bool = True
    time_context_default_timezone: str = "Asia/Shanghai"
    time_context_default_region: str = "CN"
    time_context_max_events: int = Field(default=5, ge=0)
    time_context_prompt_max_chars: int = Field(default=3000, ge=500)
    prompt_section_max_chars: int = Field(default=8000, ge=500)

    @model_validator(mode="after")
    def _default_storage_paths(self) -> "LingNengSettings":
        if self.session_db_path is None:
            self.session_db_path = self.runtime_dir / "sessions.sqlite3"
        if self.route_pending_db_path is None:
            self.route_pending_db_path = self.runtime_dir / "route_pending.sqlite3"
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
        }
