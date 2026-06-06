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


class LingNengSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_env: str = "dev"
    api_host: str = "127.0.0.1"
    api_port: int = 18083
    runtime_dir: Path = Path(".runtime/lingneng")
    session_db_path: Path | None = None
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
    rag_endpoint: str = ""
    rag_api_key: str = Field(default="", repr=False)
    rag_timeout_seconds: float = Field(default=5.0, ge=0.1)
    rag_default_top_k: int = Field(default=5, ge=1)
    rag_max_top_k: int = Field(default=20, ge=1)
    rag_context_max_chars: int = Field(default=6000, ge=500)

    @model_validator(mode="after")
    def _default_session_db_path(self) -> "LingNengSettings":
        if self.session_db_path is None:
            self.session_db_path = self.runtime_dir / "sessions.sqlite3"
        return self

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "LingNengSettings":
        source = os.environ if env is None else env
        session_db_value = source.get("LINGNENG_SESSION_DB_PATH")
        return cls(
            app_env=source.get("LINGNENG_APP_ENV", "dev"),
            api_host=source.get("LINGNENG_API_HOST", "127.0.0.1"),
            api_port=int(source.get("LINGNENG_API_PORT", "18083")),
            runtime_dir=Path(
                source.get("LINGNENG_RUNTIME_DIR", ".runtime/lingneng")
            ),
            session_db_path=Path(session_db_value) if session_db_value else None,
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
            "auth_required": self.auth_required,
            "skill_root_count": len(self.skill_roots),
            "rag_configured": bool(self.rag_endpoint),
        }
