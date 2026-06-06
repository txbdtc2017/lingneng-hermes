from __future__ import annotations

import secrets

from fastapi import HTTPException

from lingneng.config.settings import LingNengSettings


def ensure_chat_configuration_ready(settings: LingNengSettings) -> None:
    if not settings.is_chat_configuration_ready:
        raise HTTPException(
            status_code=503,
            detail="LingNeng chat API is not ready",
        )


def verify_internal_key(
    settings: LingNengSettings,
    x_internal_key: str | None,
) -> None:
    if not settings.auth_required:
        return
    if x_internal_key is None or not secrets.compare_digest(
        x_internal_key,
        settings.internal_api_key,
    ):
        raise HTTPException(status_code=401, detail="Invalid internal key")
