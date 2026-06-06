from __future__ import annotations

import json
from typing import Any

import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.tools.attachments import (
    AttachmentProcessingResult,
    attachment_processing_context,
    build_attachment_prompt_context,
)
from tests.lingneng.schemas.test_chat_request_schema import full_payload


class FakeAttachmentProvider:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.requests = []

    def process(self, request):
        self.requests.append(request)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def settings(tmp_path, **overrides) -> LingNengSettings:
    env = {
        "LINGNENG_RUNTIME_DIR": str(tmp_path),
        "LINGNENG_ATTACHMENT_ALLOWED_HOSTS": "files.example.test",
        "LINGNENG_ATTACHMENT_MAX_FILES": "2",
        "LINGNENG_ATTACHMENT_MAX_TOTAL_BYTES": "1000",
        "LINGNENG_ATTACHMENT_MAX_FILE_BYTES": "800",
        "LINGNENG_ATTACHMENT_MAX_IMAGE_BYTES": "500",
        "LINGNENG_ATTACHMENT_TIMEOUT_SECONDS": "0.1",
        "LINGNENG_ATTACHMENT_CONTEXT_MAX_CHARS": "500",
    }
    env.update(overrides)
    return LingNengSettings.from_env(env)


def attachment(**overrides) -> dict[str, Any]:
    value: dict[str, Any] = {
        "file_id": "file-1",
        "file_name": "menu.pdf",
        "mime_type": "application/pdf",
        "size": 100,
        "download_url": "https://files.example.test/menu.pdf",
        "usage": "session_context",
    }
    value.update(overrides)
    return value


def request_with_attachments(*attachments: dict[str, Any]) -> ChatStreamRequest:
    payload = full_payload()
    payload["attachments"] = list(attachments)
    payload["history"] = [
        {
            "message_id": "h-history",
            "role": "user",
            "content": "history content marker",
        }
    ]
    return ChatStreamRequest.model_validate(payload)


def warning_codes(result) -> set[str]:
    return {warning.code for warning in result.warnings}


def prompt_body(prompt_text: str) -> str:
    return prompt_text.split("\n\n", 1)[1]


def test_attachment_context_uses_current_request_only(tmp_path):
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(
            context_text="当前附件摘要",
            processed_count=1,
            failed_count=0,
            selected_count=1,
        )
    )
    first_request = request_with_attachments(attachment(file_id="file-current"))
    second_request = request_with_attachments(attachment(file_id="file-next"))

    with attachment_processing_context(provider=provider):
        first = build_attachment_prompt_context(settings(tmp_path), first_request)
        second = build_attachment_prompt_context(settings(tmp_path), second_request)

    assert "## LingNeng Current Request Attachments" in first.prompt_text
    assert "当前附件摘要" in first.prompt_text
    assert "history content marker" not in first.prompt_text
    assert [req.attachments[0].file_id for req in provider.requests] == [
        "file-current",
        "file-next",
    ]
    assert not hasattr(provider.requests[0], "history")
    assert second.selected_count == 1


def test_attachment_rejects_unallowed_host(tmp_path):
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(context_text="must not run", processed_count=1)
    )

    with attachment_processing_context(provider=provider):
        result = build_attachment_prompt_context(
            settings(tmp_path),
            request_with_attachments(
                attachment(download_url="https://evil.example.test/menu.pdf")
            ),
        )

    assert result.prompt_text == ""
    assert result.status == "skipped"
    assert "ATTACHMENT_HOST_NOT_ALLOWED" in warning_codes(result)
    assert provider.requests == []


def test_attachment_file_count_limit_skips_provider(tmp_path):
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(context_text="must not run", processed_count=2)
    )

    with attachment_processing_context(provider=provider):
        result = build_attachment_prompt_context(
            settings(tmp_path, LINGNENG_ATTACHMENT_MAX_FILES="1"),
            request_with_attachments(
                attachment(file_id="file-1"),
                attachment(file_id="file-2"),
            ),
        )

    assert result.prompt_text == ""
    assert result.status == "skipped"
    assert "ATTACHMENT_MAX_FILES_EXCEEDED" in warning_codes(result)
    assert provider.requests == []


def test_attachment_total_bytes_limit_skips_provider(tmp_path):
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(context_text="must not run", processed_count=2)
    )

    with attachment_processing_context(provider=provider):
        result = build_attachment_prompt_context(
            settings(tmp_path),
            request_with_attachments(
                attachment(file_id="file-1", size=600),
                attachment(file_id="file-2", size=500),
            ),
        )

    assert result.prompt_text == ""
    assert result.status == "skipped"
    assert "ATTACHMENT_TOTAL_BYTES_EXCEEDED" in warning_codes(result)
    assert provider.requests == []


def test_attachment_per_file_bytes_limit_skips_provider(tmp_path):
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(context_text="must not run", processed_count=1)
    )

    with attachment_processing_context(provider=provider):
        result = build_attachment_prompt_context(
            settings(tmp_path),
            request_with_attachments(attachment(file_id="large-file", size=801)),
        )

    assert result.prompt_text == ""
    assert result.status == "skipped"
    assert "ATTACHMENT_FILE_TOO_LARGE" in warning_codes(result)
    assert provider.requests == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"file_name": "photo.png", "mime_type": "image/png"},
        {"file_name": "photo.jpg", "mime_type": "application/octet-stream"},
    ],
)
def test_attachment_image_bytes_limit_uses_mime_type_or_suffix(tmp_path, overrides):
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(context_text="must not run", processed_count=1)
    )

    with attachment_processing_context(provider=provider):
        result = build_attachment_prompt_context(
            settings(tmp_path),
            request_with_attachments(attachment(size=501, **overrides)),
        )

    assert result.prompt_text == ""
    assert result.status == "skipped"
    assert "ATTACHMENT_IMAGE_TOO_LARGE" in warning_codes(result)
    assert provider.requests == []


def test_attachment_provider_exception_degrades_without_private_leaks(tmp_path):
    provider = FakeAttachmentProvider(
        RuntimeError("traceback secret-token /Users/rotas/private")
    )

    with attachment_processing_context(provider=provider):
        result = build_attachment_prompt_context(
            settings(tmp_path),
            request_with_attachments(attachment()),
        )

    dumped = json.dumps([warning.model_dump() for warning in result.warnings])
    assert result.prompt_text == ""
    assert result.status == "failed"
    assert "ATTACHMENT_PROVIDER_ERROR" in warning_codes(result)
    assert "secret-token" not in dumped
    assert "/Users/rotas" not in dumped
    assert "traceback" not in dumped.lower()


def test_attachment_timeout_like_provider_result_degrades_safely(tmp_path):
    provider = FakeAttachmentProvider(
        {
            "status": "timeout",
            "context_text": "secret-token /Users/rotas/private",
            "message": "raw timeout traceback",
            "selected_count": 1,
        }
    )

    with attachment_processing_context(provider=provider):
        result = build_attachment_prompt_context(
            settings(tmp_path),
            request_with_attachments(attachment()),
        )

    dumped = json.dumps(result.model_dump(), ensure_ascii=False)
    assert result.prompt_text == ""
    assert result.status == "failed"
    assert "ATTACHMENT_PROVIDER_TIMEOUT" in warning_codes(result)
    assert "secret-token" not in dumped
    assert "/Users/rotas" not in dumped
    assert "traceback" not in dumped.lower()


def test_attachment_context_truncates_to_configured_max_chars(tmp_path):
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(
            context_text="A" * 700,
            selected_count=1,
            processed_count=1,
        )
    )

    with attachment_processing_context(provider=provider):
        result = build_attachment_prompt_context(
            settings(tmp_path, LINGNENG_ATTACHMENT_CONTEXT_MAX_CHARS="500"),
            request_with_attachments(attachment()),
        )

    assert result.status == "succeeded"
    assert len(prompt_body(result.prompt_text)) == 500
    assert "ATTACHMENT_CONTEXT_TRUNCATED" in warning_codes(result)


def test_attachment_history_content_never_enters_prompt_or_provider_request(tmp_path):
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(
            context_text="当前附件摘要",
            selected_count=1,
            processed_count=1,
        )
    )
    request = request_with_attachments(attachment())

    with attachment_processing_context(provider=provider):
        result = build_attachment_prompt_context(settings(tmp_path), request)

    assert "history content marker" not in result.prompt_text
    assert not hasattr(provider.requests[0], "history")
