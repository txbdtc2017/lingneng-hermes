from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeVar

from lingneng.config.settings import LingNengSettings
from lingneng.tools.attachments import AttachmentProcessingProvider


_LOGGER = logging.getLogger(__name__)
_ProviderT = TypeVar("_ProviderT")


def build_attachment_processing_provider(
    settings: LingNengSettings,
) -> AttachmentProcessingProvider | None:
    provider_name = settings.attachment_provider.strip().lower()
    if provider_name == "http":
        if not settings.attachment_http_endpoint.strip():
            return None
        from lingneng.tools.attachment_http_provider import (
            HttpAttachmentProcessingProvider,
        )

        return _construct_provider(
            "http",
            lambda: HttpAttachmentProcessingProvider.from_settings(settings),
        )
    if provider_name == "local_text":
        from lingneng.tools.attachment_local_text_provider import (
            LocalTextAttachmentProcessingProvider,
        )

        return _construct_provider(
            "local_text",
            lambda: LocalTextAttachmentProcessingProvider(settings),
        )
    return None


def _construct_provider(
    provider_name: str,
    factory: Callable[[], _ProviderT],
) -> _ProviderT | None:
    try:
        return factory()
    except Exception:
        _LOGGER.warning(
            "LingNeng attachment %s provider construction failed; provider disabled.",
            provider_name,
        )
        return None
