from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field


_LOCAL_ENVS = {"local", "dev", "test"}


def _bool_from_env(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class LingNengSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_env: str = "dev"
    api_host: str = "127.0.0.1"
    api_port: int = 18083
    runtime_dir: Path = Path(".runtime/lingneng")
    agent_mode: str = "fake"
    internal_api_key: str = Field(default="", repr=False)
    allow_insecure_local: bool = False
    session_retention_days: int = 90
    archived_session_retention_days: int = 180
    idempotency_retention_days: int = 7
    heartbeat_interval_seconds: float = 15.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "LingNengSettings":
        source = os.environ if env is None else env
        return cls(
            app_env=source.get("LINGNENG_APP_ENV", "dev"),
            api_host=source.get("LINGNENG_API_HOST", "127.0.0.1"),
            api_port=int(source.get("LINGNENG_API_PORT", "18083")),
            runtime_dir=Path(
                source.get("LINGNENG_RUNTIME_DIR", ".runtime/lingneng")
            ),
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
            "auth_required": self.auth_required,
        }
