from __future__ import annotations

from contextvars import ContextVar
import json
import time
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


_ATTACHMENT_CONTEXTVAR = ContextVar("attachment_test_contextvar", default="unset")


class FakeAttachmentProvider:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.requests = []

    def process(self, request):
        self.requests.append(request)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class SleepingAttachmentProvider:
    def __init__(self, sleep_seconds: float) -> None:
        self.sleep_seconds = sleep_seconds
        self.requests = []

    def process(self, request):
        self.requests.append(request)
        time.sleep(self.sleep_seconds)
        return AttachmentProcessingResult(
            context_text="secret-token /Users/rotas/private",
            selected_count=1,
            processed_count=1,
        )


class ContextReadingProvider:
    def __init__(self) -> None:
        self.context_value = None
        self.requests = []

    def process(self, request):
        self.requests.append(request)
        self.context_value = _ATTACHMENT_CONTEXTVAR.get()
        return AttachmentProcessingResult(
            context_text=f"context={self.context_value}",
            selected_count=1,
            processed_count=1,
        )


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


@pytest.mark.parametrize(
    "context_text",
    [
        "api%5Fkey%3Dabc123",
        "Bearer%20abc123",
        "%2FUsers%2Frotas%2Fsecret.pdf",
    ],
)
def test_attachment_prompt_text_percent_decodes_before_secret_checks(
    tmp_path,
    context_text,
):
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(
            context_text=context_text,
            processed_count=1,
            failed_count=0,
            selected_count=1,
        )
    )

    with attachment_processing_context(provider=provider):
        result = build_attachment_prompt_context(
            settings(tmp_path),
            request_with_attachments(attachment()),
        )

    assert result.prompt_text == ""
    dumped = json.dumps(result.model_dump(), ensure_ascii=False).lower()
    assert "api%5fkey" not in dumped
    assert "bearer%20" not in dumped
    assert "%2fusers%2frotas" not in dumped
    assert "abc123" not in dumped
    assert "/users/rotas" not in dumped


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


def test_attachment_rejects_when_allowed_hosts_not_configured(tmp_path):
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(context_text="must not run", processed_count=1)
    )

    with attachment_processing_context(provider=provider):
        result = build_attachment_prompt_context(
            settings(tmp_path, LINGNENG_ATTACHMENT_ALLOWED_HOSTS=""),
            request_with_attachments(attachment()),
        )

    assert result.prompt_text == ""
    assert result.status == "skipped"
    assert "ATTACHMENT_ALLOWED_HOSTS_NOT_CONFIGURED" in warning_codes(result)
    assert provider.requests == []


@pytest.mark.parametrize(
    "url,allowed_hosts",
    [
        ("http://169.254.169.254/latest/meta-data", "169.254.169.254"),
        ("http://127.0.0.1/file.pdf", "127.0.0.1"),
        ("http://localhost/file.pdf", "localhost"),
        ("http://10.1.2.3/file.pdf", "10.1.2.3"),
        ("http://172.16.0.1/file.pdf", "172.16.0.1"),
        ("http://192.168.1.1/file.pdf", "192.168.1.1"),
        ("http://[::1]/file.pdf", "::1"),
    ],
)
def test_attachment_rejects_private_or_local_hosts_even_when_allowlisted(
    tmp_path,
    url,
    allowed_hosts,
):
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(context_text="must not run", processed_count=1)
    )

    with attachment_processing_context(provider=provider):
        result = build_attachment_prompt_context(
            settings(tmp_path, LINGNENG_ATTACHMENT_ALLOWED_HOSTS=allowed_hosts),
            request_with_attachments(attachment(download_url=url)),
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


@pytest.mark.parametrize(
    "size,expected_code",
    [
        (None, "ATTACHMENT_SIZE_UNKNOWN"),
        (-1, "ATTACHMENT_SIZE_INVALID"),
    ],
)
def test_attachment_unknown_or_negative_size_skips_provider(
    tmp_path,
    size,
    expected_code,
):
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(context_text="must not run", processed_count=1)
    )

    with attachment_processing_context(provider=provider):
        result = build_attachment_prompt_context(
            settings(tmp_path),
            request_with_attachments(attachment(size=size)),
        )

    assert result.prompt_text == ""
    assert result.status == "skipped"
    assert expected_code in warning_codes(result)
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


def test_attachment_provider_call_is_wall_clock_timeout_bounded(tmp_path):
    provider = SleepingAttachmentProvider(sleep_seconds=0.35)

    with attachment_processing_context(provider=provider):
        started_at = time.perf_counter()
        result = build_attachment_prompt_context(
            settings(tmp_path, LINGNENG_ATTACHMENT_TIMEOUT_SECONDS="0.1"),
            request_with_attachments(attachment()),
        )
        elapsed = time.perf_counter() - started_at

    dumped = json.dumps(result.model_dump(), ensure_ascii=False)
    assert elapsed < 0.25
    assert result.prompt_text == ""
    assert result.status == "failed"
    assert "ATTACHMENT_PROVIDER_TIMEOUT" in warning_codes(result)
    assert "secret-token" not in dumped
    assert "/Users/rotas" not in dumped
    assert "traceback" not in dumped.lower()


def test_attachment_provider_request_includes_resource_ceilings(tmp_path):
    provider = FakeAttachmentProvider(
        AttachmentProcessingResult(
            context_text="当前附件摘要",
            selected_count=1,
            processed_count=1,
        )
    )

    with attachment_processing_context(provider=provider):
        build_attachment_prompt_context(settings(tmp_path), request_with_attachments(attachment()))

    provider_request = provider.requests[0]
    assert provider_request.max_files == 2
    assert provider_request.max_total_bytes == 1000
    assert provider_request.max_file_bytes == 800
    assert provider_request.max_image_bytes == 500
    assert provider_request.timeout_seconds == 0.1
    assert provider_request.context_max_chars == 500


def test_attachment_provider_timeout_preserves_contextvars(tmp_path):
    provider = ContextReadingProvider()
    token = _ATTACHMENT_CONTEXTVAR.set("current-request-value")

    try:
        with attachment_processing_context(provider=provider):
            result = build_attachment_prompt_context(
                settings(tmp_path),
                request_with_attachments(attachment()),
            )
    finally:
        _ATTACHMENT_CONTEXTVAR.reset(token)

    assert result.status == "succeeded"
    assert provider.context_value == "current-request-value"
    assert "context=current-request-value" in result.prompt_text


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
