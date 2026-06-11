from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import lingneng.tools.attachment_http_provider as http_provider_module

from lingneng.config.settings import LingNengSettings
from lingneng.tools.attachment_http_provider import (
    HttpAttachmentProcessingProvider,
)
from lingneng.tools.attachment_provider import (
    build_attachment_processing_provider,
)
from lingneng.schemas.chat_request import AttachmentPayload
from lingneng.tools.attachments import (
    AttachmentProcessingRequest,
    AttachmentProcessingResult,
)


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
                    "file_name": "menu.pdf",
                    "mime_type": "application/pdf",
                    "size": 100,
                    "download_url": "https://files.example.test/menu.pdf",
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

    result = AttachmentProcessingResult.model_validate(
        provider.process(attachment_request())
    )

    assert result.status == "skipped"
    assert result.context_text == ""
    assert result.processed_count == 0
    assert result.failed_count == 1
    assert result.selected_count == 0
    assert result.code == "ATTACHMENT_PROVIDER_NOT_CONFIGURED"
    assert result.warnings[0].code == "ATTACHMENT_PROVIDER_NOT_CONFIGURED"


def test_http_provider_factory_builds_configured_provider(tmp_path):
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


def test_http_attachment_provider_sends_bounded_request_and_normalizes_response(
    tmp_path,
):
    del tmp_path
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "status": "succeeded",
                "context_text": "### menu.pdf\n菜品摘要",
                "processed_count": 1,
                "failed_count": 0,
                "selected_count": 1,
                "warnings": [
                    {
                        "code": "ATTACHMENT_CONTEXT_TRUNCATED",
                        "file_id": "file-1",
                    }
                ],
                "files": [
                    {
                        "file_id": "file-1",
                        "file_name": "menu.pdf",
                        "status": "processed",
                    }
                ],
            },
        )

    provider = HttpAttachmentProcessingProvider(
        endpoint="https://attachments.example/process",
        api_key="secret-key",
        timeout_seconds=3,
        max_response_bytes=4096,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.process(attachment_request())

    assert captured["url"] == "https://attachments.example/process"
    assert captured["authorization"] == "Bearer secret-key"
    body = captured["body"]
    assert body["request_id"] == "req-1"
    assert body["limits"]["max_file_bytes"] == 800
    assert (
        body["attachments"][0]["download_url"]
        == "https://files.example.test/menu.pdf"
    )
    assert "query" not in body
    assert result.status == "succeeded"
    assert result.context_text == "### menu.pdf\n菜品摘要"
    assert result.processed_count == 1
    assert result.warnings[0].code == "ATTACHMENT_CONTEXT_TRUNCATED"


def test_http_attachment_provider_rejects_oversized_response(tmp_path):
    del tmp_path
    chunks_read: list[bytes] = []
    chunk_sizes: list[int | None] = []

    class FakeStreamResponse:
        status_code = 200

        @property
        def content(self) -> bytes:
            raise AssertionError("response content must not be buffered")

        def iter_bytes(self, *, chunk_size: int | None = None):
            chunk_sizes.append(chunk_size)
            for chunk in (b"x" * 40, b"y" * 40, b"z" * 40, b"w" * 40):
                chunks_read.append(chunk)
                yield chunk

    class FakeStreamContext:
        def __enter__(self) -> FakeStreamResponse:
            return FakeStreamResponse()

        def __exit__(self, *exc_info: object) -> None:
            return None

    class FakeClient:
        def stream(self, *args: Any, **kwargs: Any) -> FakeStreamContext:
            return FakeStreamContext()

    provider = HttpAttachmentProcessingProvider(
        endpoint="https://attachments.example/process",
        api_key="secret-key",
        timeout_seconds=3,
        max_response_bytes=100,
        http_client=FakeClient(),
    )

    result = provider.process(attachment_request())

    assert result.status == "failed"
    assert result.code == "ATTACHMENT_PROVIDER_INVALID_RESULT"
    assert result.context_text == ""
    assert chunk_sizes == [101]
    assert chunks_read == [b"x" * 40, b"y" * 40, b"z" * 40]


def test_http_attachment_provider_sanitizes_failures(tmp_path):
    del tmp_path

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            500,
            text="secret-token traceback /Users/rotas/private",
        )

    provider = HttpAttachmentProcessingProvider(
        endpoint="https://attachments.example/process?token=secret-token",
        api_key="secret-key",
        timeout_seconds=3,
        max_response_bytes=4096,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.process(attachment_request())

    dumped = result.model_dump_json()
    assert result.status == "failed"
    assert result.code == "ATTACHMENT_PROVIDER_ERROR"
    assert "secret-token" not in dumped
    assert "traceback" not in dumped
    assert "/Users/rotas" not in dumped


def test_http_attachment_provider_rejects_redirect_with_valid_json(tmp_path):
    del tmp_path

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            302,
            json={
                "status": "succeeded",
                "context_text": "must not be accepted",
                "processed_count": 1,
                "failed_count": 0,
                "selected_count": 1,
            },
        )

    provider = HttpAttachmentProcessingProvider(
        endpoint="https://attachments.example/process",
        api_key="secret-key",
        timeout_seconds=3,
        max_response_bytes=4096,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.process(attachment_request())

    assert result.status == "failed"
    assert result.code == "ATTACHMENT_PROVIDER_ERROR"
    assert result.context_text == ""


def test_http_attachment_provider_rejects_non_2xx_without_reading_body(tmp_path):
    del tmp_path

    class FakeStreamResponse:
        status_code = 500

        @property
        def content(self) -> bytes:
            raise AssertionError("response content must not be buffered")

        def iter_bytes(self):
            raise AssertionError("non-2xx response body must not be read")

    class FakeStreamContext:
        def __enter__(self) -> FakeStreamResponse:
            return FakeStreamResponse()

        def __exit__(self, *exc_info: object) -> None:
            return None

    class FakeClient:
        def stream(self, *args: Any, **kwargs: Any) -> FakeStreamContext:
            return FakeStreamContext()

    provider = HttpAttachmentProcessingProvider(
        endpoint="https://attachments.example/process",
        api_key="secret-key",
        timeout_seconds=3,
        max_response_bytes=4096,
        http_client=FakeClient(),
    )

    result = provider.process(attachment_request())

    assert result.status == "failed"
    assert result.code == "ATTACHMENT_PROVIDER_ERROR"
    assert result.context_text == ""


def test_http_attachment_provider_maps_timeout_to_timeout_result(tmp_path):
    del tmp_path

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        raise httpx.TimeoutException(
            "secret-token traceback /Users/rotas/private",
        )

    provider = HttpAttachmentProcessingProvider(
        endpoint="https://attachments.example/process",
        api_key="secret-key",
        timeout_seconds=3,
        max_response_bytes=4096,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.process(attachment_request())
    dumped = result.model_dump_json()

    assert result.status == "failed"
    assert result.code == "ATTACHMENT_PROVIDER_TIMEOUT"
    assert "secret-token" not in dumped
    assert "traceback" not in dumped
    assert "/Users/rotas" not in dumped


def test_http_attachment_provider_rejects_non_json_response(tmp_path):
    del tmp_path

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, text="not json")

    provider = HttpAttachmentProcessingProvider(
        endpoint="https://attachments.example/process",
        api_key="secret-key",
        timeout_seconds=3,
        max_response_bytes=4096,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.process(attachment_request())

    assert result.status == "failed"
    assert result.code == "ATTACHMENT_PROVIDER_INVALID_RESULT"
    assert result.context_text == ""


def test_http_attachment_provider_rejects_schema_invalid_json(tmp_path):
    del tmp_path

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "status": "succeeded",
                "context_text": "invalid",
                "processed_count": -1,
                "failed_count": 0,
                "selected_count": 1,
            },
        )

    provider = HttpAttachmentProcessingProvider(
        endpoint="https://attachments.example/process",
        api_key="secret-key",
        timeout_seconds=3,
        max_response_bytes=4096,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.process(attachment_request())

    assert result.status == "failed"
    assert result.code == "ATTACHMENT_PROVIDER_INVALID_RESULT"
    assert result.context_text == ""


def test_http_attachment_provider_default_client_disables_trust_env(
    tmp_path,
    monkeypatch,
):
    del tmp_path
    captured: dict[str, Any] = {}
    chunk_sizes: list[int | None] = []

    class FakeClient:
        def __init__(self, *, timeout: float, trust_env: bool) -> None:
            captured["timeout"] = timeout
            captured["trust_env"] = trust_env

        def __enter__(self) -> "FakeClient":
            captured["entered"] = True
            return self

        def __exit__(self, *exc_info: object) -> None:
            captured["exited"] = True

        def stream(
            self,
            method: str,
            url: str,
            *,
            json: dict[str, Any],
            headers: dict[str, str],
            timeout: float,
        ) -> Any:
            captured["method"] = method
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            captured["request_timeout"] = timeout
            return self

        def iter_bytes(self, *, chunk_size: int | None = None):
            chunk_sizes.append(chunk_size)
            yield json.dumps(
                {
                    "status": "succeeded",
                    "context_text": "ok",
                    "processed_count": 1,
                    "failed_count": 0,
                    "selected_count": 1,
                }
            ).encode()

        @property
        def status_code(self) -> int:
            return 200

        @property
        def content(self) -> bytes:
            raise AssertionError("response content must not be buffered")

        def post(
            self,
            url: str,
            *,
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> httpx.Response:
            del url, json, headers
            raise AssertionError("default client path must use stream")

    monkeypatch.setattr(http_provider_module.httpx, "Client", FakeClient)
    provider = HttpAttachmentProcessingProvider(
        endpoint="https://attachments.example/process",
        api_key="secret-key",
        timeout_seconds=7,
        max_response_bytes=4096,
    )

    result = provider.process(attachment_request())

    assert captured["timeout"] == 7
    assert captured["trust_env"] is False
    assert captured["entered"] is True
    assert captured["exited"] is True
    assert captured["method"] == "POST"
    assert captured["request_timeout"] == 7
    assert captured["url"] == "https://attachments.example/process"
    assert captured["headers"]["Authorization"] == "Bearer secret-key"
    assert chunk_sizes == [4097]
    assert result.status == "succeeded"
