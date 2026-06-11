from __future__ import annotations

from typing import Any

from lingneng.config.settings import LingNengSettings


class HttpAttachmentProcessingProvider:
    @classmethod
    def from_settings(
        cls,
        settings: LingNengSettings,
    ) -> "HttpAttachmentProcessingProvider":
        return cls(settings=settings)

    def __init__(
        self,
        *,
        settings: LingNengSettings,
        http_client: Any | None = None,
    ) -> None:
        self.settings = settings
        self.http_client = http_client
