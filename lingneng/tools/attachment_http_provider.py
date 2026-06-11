from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import ValidationError

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import AttachmentPayload
from lingneng.tools.attachments import (
    AttachmentProcessingRequest,
    AttachmentProcessingResult,
    AttachmentWarning,
)


class HttpAttachmentProcessingProviderError(Exception):
    """Internal marker for sanitized HTTP provider failures."""


class HttpAttachmentProcessingProvider:
    @classmethod
    def from_settings(
        cls,
        settings: LingNengSettings,
    ) -> "HttpAttachmentProcessingProvider":
        return cls(
            endpoint=settings.attachment_http_endpoint,
            api_key=settings.attachment_http_api_key,
            timeout_seconds=settings.attachment_http_timeout_seconds,
            max_response_bytes=settings.attachment_http_max_response_bytes,
        )

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str = "",
        timeout_seconds: float = 30.0,
        max_response_bytes: int = 1048576,
        http_client: httpx.Client | None = None,
    ) -> None:
        clean_endpoint = endpoint.strip()
        if not clean_endpoint:
            raise HttpAttachmentProcessingProviderError("endpoint required")
        self.endpoint = clean_endpoint
        self.api_key = api_key.strip()
        self.timeout_seconds = max(0.1, float(timeout_seconds))
        self.max_response_bytes = max(1, int(max_response_bytes))
        self._http_client = http_client

    def process(
        self,
        request: AttachmentProcessingRequest,
    ) -> AttachmentProcessingResult:
        try:
            response = self._post(self._request_payload(request))
        except httpx.TimeoutException:
            return _failure("ATTACHMENT_PROVIDER_TIMEOUT")
        except Exception:
            return _failure("ATTACHMENT_PROVIDER_ERROR")

        content = response.content
        if len(content) > self.max_response_bytes:
            return _failure("ATTACHMENT_PROVIDER_INVALID_RESULT")
        if response.status_code < 200 or response.status_code >= 300:
            return _failure("ATTACHMENT_PROVIDER_ERROR")

        try:
            payload = json.loads(content.decode("utf-8"))
            return AttachmentProcessingResult.model_validate(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError):
            return _failure("ATTACHMENT_PROVIDER_INVALID_RESULT")

    def _request_payload(self, request: AttachmentProcessingRequest) -> dict[str, Any]:
        return {
            "request_id": request.request_id,
            "tenant_id": request.tenant_id,
            "user_id": request.user_id,
            "session_id": request.session_id,
            "conversation_id": request.conversation_id,
            "employee_type": request.employee_type,
            "timeout_seconds": request.timeout_seconds,
            "context_max_chars": request.context_max_chars,
            "limits": {
                "max_files": request.max_files,
                "max_total_bytes": request.max_total_bytes,
                "max_file_bytes": request.max_file_bytes,
                "max_image_bytes": request.max_image_bytes,
            },
            "attachments": [
                _attachment_payload(attachment) for attachment in request.attachments
            ],
        }

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self._http_client is not None:
            return self._http_client.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
        with httpx.Client(
            timeout=self.timeout_seconds,
            trust_env=False,
        ) as client:
            return client.post(self.endpoint, json=payload, headers=headers)


def _attachment_payload(attachment: AttachmentPayload) -> dict[str, Any]:
    return {
        "file_id": attachment.file_id,
        "file_name": attachment.file_name,
        "mime_type": attachment.mime_type,
        "size": attachment.size,
        "download_url": attachment.download_url,
        "download_url_expires_at": attachment.download_url_expires_at,
        "usage": attachment.usage,
    }


def _failure(code: str) -> AttachmentProcessingResult:
    return AttachmentProcessingResult(
        status="failed",
        context_text="",
        processed_count=0,
        failed_count=0,
        selected_count=0,
        warnings=[AttachmentWarning(code=code)],
        code=code,
    )
