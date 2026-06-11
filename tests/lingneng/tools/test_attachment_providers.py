from __future__ import annotations

from pathlib import Path

from lingneng.config.settings import LingNengSettings
from lingneng.tools.attachment_provider import (
    build_attachment_processing_provider,
)
from lingneng.tools.attachments import AttachmentProcessingRequest
from lingneng.schemas.chat_request import AttachmentPayload


def settings(tmp_path: Path, **overrides: str) -> LingNengSettings:
    env = {"LINGNENG_RUNTIME_DIR": str(tmp_path)}
    env.update(overrides)
    return LingNengSettings.from_env(env)


def attachment_request() -> AttachmentProcessingRequest:
    return AttachmentProcessingRequest(
        tenant_id="tenant-1",
        user_id="user-1",
        session_id="session-1",
        conversation_id="conv-1",
        request_id="req-1",
        employee_type="marketing_content_creator",
        attachments=[
            AttachmentPayload.model_validate(
                {
                    "file_id": "file-1",
                    "file_name": "menu.txt",
                    "mime_type": "text/plain",
                    "size": 100,
                    "download_url": "https://files.example.test/menu.txt",
                    "usage": "session_context",
                }
            )
        ],
        timeout_seconds=3,
        context_max_chars=500,
        max_files=5,
        max_total_bytes=1000,
        max_file_bytes=800,
        max_image_bytes=500,
    )


def test_attachment_provider_factory_returns_none_for_incomplete_config(tmp_path):
    assert build_attachment_processing_provider(settings(tmp_path)) is None
    assert (
        build_attachment_processing_provider(
            settings(
                tmp_path,
                LINGNENG_ATTACHMENT_PROVIDER="http",
                LINGNENG_ATTACHMENT_HTTP_ENDPOINT="",
            )
        )
        is None
    )


def test_attachment_provider_factory_builds_local_text_provider(tmp_path):
    provider = build_attachment_processing_provider(
        settings(tmp_path, LINGNENG_ATTACHMENT_PROVIDER="local_text")
    )

    assert provider.__class__.__name__ == "LocalTextAttachmentProcessingProvider"


def test_local_text_provider_skeleton_process_fail_closes(tmp_path):
    provider = build_attachment_processing_provider(
        settings(tmp_path, LINGNENG_ATTACHMENT_PROVIDER="local_text")
    )

    assert provider is not None
    assert callable(provider.process)

    result = provider.process(attachment_request())

    assert result.status == "skipped"
    assert result.context_text == ""
    assert result.processed_count == 0
    assert result.failed_count == 1
    assert result.selected_count == 0
    assert result.code == "ATTACHMENT_PROVIDER_NOT_CONFIGURED"
    assert result.warnings[0].code == "ATTACHMENT_PROVIDER_NOT_CONFIGURED"


def test_http_provider_skeleton_process_fail_closes_without_secret_leak(tmp_path):
    provider = build_attachment_processing_provider(
        settings(
            tmp_path,
            LINGNENG_ATTACHMENT_PROVIDER="http",
            LINGNENG_ATTACHMENT_HTTP_ENDPOINT="https://attachments.example/process",
            LINGNENG_ATTACHMENT_HTTP_API_KEY="attachment-secret",
        )
    )

    assert provider is not None
    assert provider.__class__.__name__ == "HttpAttachmentProcessingProvider"
    assert callable(provider.process)

    result = provider.process(attachment_request())
    dumped = result.model_dump_json()

    assert result.status == "skipped"
    assert result.context_text == ""
    assert result.processed_count == 0
    assert result.failed_count == 1
    assert result.selected_count == 0
    assert result.code == "ATTACHMENT_PROVIDER_NOT_CONFIGURED"
    assert result.warnings[0].code == "ATTACHMENT_PROVIDER_NOT_CONFIGURED"
    assert "attachment-secret" not in dumped
    assert "attachments.example" not in dumped


def test_attachment_provider_factory_fail_closes_construction_errors(
    tmp_path,
    monkeypatch,
    caplog,
):
    import lingneng.tools.attachment_local_text_provider as local_provider_module

    class ExplodingProvider:
        def __init__(self, settings):
            del settings
            raise ValueError("https://secret.example?token=secret-token")

    monkeypatch.setattr(
        local_provider_module,
        "LocalTextAttachmentProcessingProvider",
        ExplodingProvider,
    )

    with caplog.at_level("WARNING", logger="lingneng.tools.attachment_provider"):
        provider = build_attachment_processing_provider(
            settings(tmp_path, LINGNENG_ATTACHMENT_PROVIDER="local_text")
        )

    assert provider is None
    assert "attachment local_text provider construction failed" in caplog.text
    assert "secret-token" not in caplog.text
    assert "https://secret.example" not in caplog.text
