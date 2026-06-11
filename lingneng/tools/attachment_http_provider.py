from __future__ import annotations

from typing import Any

from lingneng.config.settings import LingNengSettings
from lingneng.tools.attachments import (
    AttachmentProcessingRequest,
    AttachmentProcessingResult,
    AttachmentWarning,
)


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

    def process(
        self,
        request: AttachmentProcessingRequest,
    ) -> AttachmentProcessingResult:
        return AttachmentProcessingResult(
            status="skipped",
            context_text="",
            processed_count=0,
            failed_count=len(request.attachments),
            selected_count=0,
            warnings=[
                AttachmentWarning(code="ATTACHMENT_PROVIDER_NOT_CONFIGURED")
            ],
            code="ATTACHMENT_PROVIDER_NOT_CONFIGURED",
        )
