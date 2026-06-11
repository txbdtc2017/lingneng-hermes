from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from lingneng.tools.rag import (
    HttpRagProvider,
    RagRetrieveRequest,
    RagRetrieveResult,
    build_rag_request_context,
    rag_request_context,
    retrieve_rag_handler,
)
from tests.lingneng.schemas.test_chat_request_schema import full_payload


class FakeRagProvider:
    def __init__(self, result: Any | Exception) -> None:
        self.result = result
        self.requests: list[RagRetrieveRequest] = []

    def retrieve(self, request: RagRetrieveRequest) -> RagRetrieveResult:
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeStreamContext:
    def __init__(self, response: Any) -> None:
        self.response = response

    def __enter__(self) -> Any:
        return self.response

    def __exit__(self, *exc_info: object) -> None:
        return None


def make_context(
    tmp_path,
    request: ChatStreamRequest | None = None,
    *,
    env: dict[str, str] | None = None,
):
    request = request or ChatStreamRequest.model_validate(full_payload())
    source = {
        "LINGNENG_RUNTIME_DIR": str(tmp_path),
        "LINGNENG_RAG_DEFAULT_TOP_K": "3",
        "LINGNENG_RAG_MAX_TOP_K": "5",
        "LINGNENG_RAG_CONTEXT_MAX_CHARS": "500",
    }
    source.update(env or {})
    settings = LingNengSettings.from_env(source)
    return build_rag_request_context(
        settings=settings,
        request=request,
        resolved_session=resolve_session_key(request),
    )


def test_retrieve_rag_builds_contextual_request(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(
            status="hit",
            context="套餐规则来自知识库。",
            citations=[
                {
                    "document_id": "doc-1",
                    "source_file_id": "file-1",
                    "source_file_name": "menu.pdf",
                    "page_no": 2,
                    "section_title": "套餐",
                    "chunk_id": "chunk-1",
                    "score": 0.9,
                }
            ],
            metadata={"duration_ms": 12},
        )
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(
            retrieve_rag_handler(
                {
                    "query": "会员套餐怎么写",
                    "top_k": 99,
                    "filters": {"document_type": "menu"},
                }
            )
        )

    assert result["success"] is True
    assert result["tool_name"] == "retrieve_rag"
    assert result["status"] == "hit"
    assert result["context"] == "套餐规则来自知识库。"
    assert result["citations"][0]["chunk_id"] == "chunk-1"
    assert result["metadata"] == {
        "duration_ms": 12,
        "selected_count": 1,
        "citation_count": 1,
    }
    sent = provider.requests[0]
    assert sent.query == "会员套餐怎么写"
    assert sent.tenant_id == "tenant-a"
    assert sent.user_id == "user-a"
    assert sent.employee_type == "marketing_content_creator"
    assert sent.conversation_id == "conv-a"
    assert sent.session_key == "tenant-a:user-a:emp-001:conv-a"
    assert sent.request_id == "req-001"
    assert sent.top_k == 5
    assert sent.filters == {"document_type": "menu"}


def test_retrieve_rag_uses_default_top_k_and_truncates_context(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(
            status="hit",
            context="长内容" * 200,
            citations=[],
            metadata={},
        )
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    assert provider.requests[0].top_k == 3
    assert len(result["context"]) == 500
    assert result["metadata"] == {"selected_count": 0, "citation_count": 0}


def test_retrieve_rag_empty_result_shape(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(status="empty", context="", citations=[], metadata={})
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "没有资料"}))

    assert result == {
        "success": True,
        "tool_name": "retrieve_rag",
        "status": "empty",
        "context": "",
        "citations": [],
        "metadata": {"selected_count": 0, "citation_count": 0},
    }


def test_retrieve_rag_success_metadata_is_sanitized(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(
            status="hit",
            context="安全上下文",
            citations=[],
            metadata={
                "duration_ms": 12,
                "api_key": "secret-rag-key",
                "nested": {"token": "secret-token"},
                "note": "provider leaked api_key=secret",
            },
        )
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    dumped = json.dumps(result, ensure_ascii=False)
    assert result["success"] is True
    assert result["metadata"]["duration_ms"] == 12
    assert "api_key" not in dumped
    assert "secret" not in dumped
    assert "token" not in dumped


def test_retrieve_rag_success_strips_authorization_bearer_leaks(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(
            status="hit",
            context="Authorization: Bearer abc123",
            citations=[],
            metadata={
                "duration_ms": 12,
                "authorization": "Bearer abc123",
                "bearer": "abc123",
                "nested": {"Authorization": "Bearer abc123"},
                "notes": ["Authorization: Bearer abc123"],
            },
        )
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    dumped = json.dumps(result, ensure_ascii=False)
    assert result["success"] is True
    assert result["context"] == ""
    assert result["metadata"] == {
        "duration_ms": 12,
        "nested": {},
        "notes": [""],
        "selected_count": 0,
        "citation_count": 0,
    }
    assert "Authorization" not in dumped
    assert "authorization" not in dumped
    assert "Bearer" not in dumped
    assert "bearer" not in dumped
    assert "abc123" not in dumped


def test_retrieve_rag_success_strips_raw_input_and_credential_metadata(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(
            status="hit",
            context="raw input: USER PRIVATE INPUT",
            citations=[],
            metadata={
                "duration_ms": 12,
                "query": "USER PRIVATE INPUT",
                "input": "USER PRIVATE INPUT",
                "password": "hunter2",
                "passwd_hash": "hunter2",
                "credential": "hunter2",
                "nested": {
                    "query": "USER PRIVATE INPUT",
                    "safe": "public summary",
                    "notes": [
                        "raw query: USER PRIVATE INPUT",
                        "password=hunter2",
                        "public summary",
                    ],
                },
                "items": [
                    {"input": "USER PRIVATE INPUT", "source": "public-source"},
                ],
                "note": "raw request: USER PRIVATE INPUT",
            },
        )
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    dumped = json.dumps(result, ensure_ascii=False)
    assert result["success"] is True
    assert result["context"] == ""
    assert result["metadata"] == {
        "duration_ms": 12,
        "nested": {
            "safe": "public summary",
            "notes": ["", "", "public summary"],
        },
        "items": [{"source": "public-source"}],
        "note": "",
        "selected_count": 0,
        "citation_count": 0,
    }
    assert "query" not in dumped
    assert "input" not in dumped
    assert "password" not in dumped
    assert "passwd" not in dumped
    assert "credential" not in dumped
    assert "USER PRIVATE INPUT" not in dumped
    assert "hunter2" not in dumped
    assert "raw query" not in dumped
    assert "raw input" not in dumped
    assert "raw request" not in dumped


def test_retrieve_rag_context_allows_benign_query_input_words(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(
            status="hit",
            context="Customer query input routing policy.",
            citations=[],
            metadata={},
        )
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    assert result["success"] is True
    assert result["context"] == "Customer query input routing policy."


def test_retrieve_rag_sanitizes_percent_encoded_secret_context_and_metadata(
    tmp_path,
):
    provider = FakeRagProvider(
        RagRetrieveResult(
            status="hit",
            context="api%5Fkey%3Dabc123 %2FUsers%2Frotas%2Fprivate",
            citations=[],
            metadata={
                "notes": ["x-amz-signature=abc", "public retrieval summary"],
            },
        )
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    dumped = json.dumps(result, ensure_ascii=False).lower()
    assert result["context"] == ""
    assert result["metadata"]["notes"] == ["", "public retrieval summary"]
    assert "api%5fkey" not in dumped
    assert "%2fusers" not in dumped
    assert "x-amz-signature" not in dumped


def test_retrieve_rag_sanitizes_json_shaped_raw_dump_metadata_values(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(
            status="hit",
            context="公共上下文",
            citations=[],
            metadata={
                "notes": [
                    '{"query":"客户问套餐"}',
                    '{"input":"客户问套餐"}',
                    '{"summary":"public retrieval summary"}',
                ],
            },
        )
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    dumped = json.dumps(result, ensure_ascii=False)
    assert result["metadata"]["notes"] == [
        "",
        "",
        '{"summary":"public retrieval summary"}',
    ]
    assert "客户问套餐" not in dumped


def test_retrieve_rag_sanitizes_citation_private_fields(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(
            status="hit",
            context="公共上下文",
            citations=[
                {
                    "document_id": "doc-1",
                    "source_file_id": "file-1",
                    "source_file_name": "/Users/rotas/private/menu.pdf",
                    "page_no": 2,
                    "section_title": "Authorization: Bearer abc123",
                    "chunk_id": "chunk-1",
                    "score": 0.9,
                    "raw_payload": "api_key=secret",
                }
            ],
            metadata={},
        )
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    dumped = json.dumps(result, ensure_ascii=False)
    assert result["citations"][0]["chunk_id"] == "chunk-1"
    assert result["citations"][0]["source_file_name"] == ""
    assert result["citations"][0]["section_title"] == ""
    assert "raw_payload" not in dumped
    assert "api_key" not in dumped
    assert "/Users/rotas" not in dumped


def test_retrieve_rag_drops_invalid_public_citations_and_counts_valid(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(
            status="hit",
            context="公共上下文",
            citations=[
                {
                    "document_id": "doc-1",
                    "source_file_id": "file-1",
                    "source_file_name": "menu.pdf",
                    "page_no": 2,
                    "section_title": "套餐",
                    "chunk_id": "chunk-1",
                    "score": 0.9,
                },
                {
                    "document_id": "doc-2",
                    "source_file_id": "file-2",
                    "source_file_name": "invalid-score.pdf",
                    "chunk_id": "chunk-2",
                    "score": -1,
                },
                {
                    "document_id": "doc-3",
                    "source_file_id": "file-3",
                    "source_file_name": "missing-chunk.pdf",
                    "score": 0.8,
                },
            ],
            metadata={},
        )
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    assert result["citations"] == [
        {
            "document_id": "doc-1",
            "source_file_id": "file-1",
            "source_file_name": "menu.pdf",
            "page_no": 2,
            "section_title": "套餐",
            "chunk_id": "chunk-1",
            "score": 0.9,
        }
    ]
    assert result["metadata"]["selected_count"] == 1
    assert result["metadata"]["citation_count"] == 1


def test_retrieve_rag_not_configured_is_safe(tmp_path):
    with rag_request_context(make_context(tmp_path), provider=None):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    dumped = json.dumps(result, ensure_ascii=False)
    assert result["success"] is False
    assert result["code"] == "NOT_CONFIGURED"
    assert result["status"] == "failed"
    assert "api_key" not in dumped
    assert "history" not in dumped
    assert "需要资料" not in dumped


def test_retrieve_rag_provider_exception_is_sanitized(tmp_path):
    provider = FakeRagProvider(RuntimeError("private provider api_key=secret"))

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    dumped = json.dumps(result, ensure_ascii=False)
    assert result["success"] is False
    assert result["code"] == "RAG_PROVIDER_ERROR"
    assert result["status"] == "failed"
    assert "private provider" not in dumped
    assert "api_key" not in dumped
    assert "secret" not in dumped
    assert "traceback" not in dumped
    assert "需要资料" not in dumped


@pytest.mark.parametrize(
    "provider_result",
    [
        None,
        {"status": "hit", "context": "api_key=secret", "metadata": {"token": "x"}},
    ],
)
def test_retrieve_rag_invalid_provider_result_is_safe(tmp_path, provider_result):
    provider = FakeRagProvider(provider_result)

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    dumped = json.dumps(result, ensure_ascii=False)
    assert result["success"] is False
    assert result["code"] == "RAG_PROVIDER_INVALID_RESULT"
    assert result["status"] == "failed"
    assert "api_key" not in dumped
    assert "secret" not in dumped
    assert "token" not in dumped
    assert "traceback" not in dumped
    assert "需要资料" not in dumped


def test_retrieve_rag_failed_provider_code_is_sanitized(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(
            status="failed",
            context="api_key=secret",
            citations=[],
            metadata={"token": "secret-token"},
            code="RAG_PROVIDER_ERROR api_key=secret",
        )
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    dumped = json.dumps(result, ensure_ascii=False)
    assert result["success"] is False
    assert result["code"] == "RAG_PROVIDER_ERROR"
    assert result["status"] == "failed"
    assert "api_key" not in dumped
    assert "secret" not in dumped
    assert "token" not in dumped
    assert "traceback" not in dumped
    assert "需要资料" not in dumped


def test_retrieve_rag_timeout_failure_code_is_public(tmp_path):
    provider = FakeRagProvider(
        RagRetrieveResult(
            status="failed",
            context="traceback secret-token",
            citations=[],
            metadata={"authorization": "Bearer secret"},
            code="RAG_PROVIDER_TIMEOUT",
        )
    )

    with rag_request_context(make_context(tmp_path), provider=provider):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    dumped = json.dumps(result, ensure_ascii=False)
    assert result["success"] is False
    assert result["code"] == "RAG_PROVIDER_TIMEOUT"
    assert result["message"] == "LingNeng RAG provider timed out."
    assert "secret-token" not in dumped
    assert "Bearer" not in dumped


def test_http_rag_provider_streams_success_request_and_normalizes_response(tmp_path):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "status": "hit",
                "context": "套餐规则",
                "citations": [{"chunk_id": "chunk-1", "score": 0.8}],
                "metadata": {"duration_ms": 11},
            },
        )

    settings_obj = LingNengSettings.from_env(
        {
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
            "LINGNENG_RAG_API_KEY": "secret-rag-key",
            "LINGNENG_RAG_TIMEOUT_SECONDS": "2",
            "LINGNENG_RAG_HTTP_MAX_RESPONSE_BYTES": "4096",
        }
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = HttpRagProvider(settings_obj, http_client=client)

        result = provider.retrieve(
            RagRetrieveRequest(
                query="会员套餐",
                tenant_id="tenant-a",
                user_id="user-a",
                employee_type="marketing_content_creator",
                conversation_id="conv-a",
                session_key="tenant-a:user-a:emp-001:conv-a",
                request_id="req-001",
                top_k=3,
                filters={"document_type": "menu"},
            )
        )

    assert captured["url"] == "https://rag.example.test/retrieve"
    assert captured["authorization"] == "Bearer secret-rag-key"
    assert captured["body"]["query"] == "会员套餐"
    assert captured["body"]["top_k"] == 3
    assert result.status == "hit"
    assert result.context == "套餐规则"
    assert result.citations[0]["chunk_id"] == "chunk-1"
    assert result.metadata["duration_ms"] == 11


def test_http_rag_provider_normalizes_old_lingneng_shape(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "context": "旧服务上下文",
                "citations": [{"chunk_id": "chunk-old", "score": 0.9}],
                "route_debug": {"retrieval_status": "hit"},
            },
        )

    provider = HttpRagProvider(
        LingNengSettings.from_env(
            {
                "LINGNENG_RUNTIME_DIR": str(tmp_path),
                "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
            }
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.retrieve(
        RagRetrieveRequest(
            query="会员套餐",
            tenant_id="tenant-a",
            user_id="user-a",
            employee_type="marketing_content_creator",
            conversation_id="conv-a",
            session_key="session",
            request_id="req-001",
            top_k=3,
            filters={},
        )
    )

    assert result.status == "hit"
    assert result.context == "旧服务上下文"
    assert result.citations[0]["chunk_id"] == "chunk-old"
    assert result.metadata == {"retrieval_status": "hit"}


def test_http_rag_provider_rejects_old_lingneng_invalid_citations(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "context": "旧服务上下文",
                "citations": "not-a-list",
                "route_debug": {"retrieval_status": "hit"},
            },
        )

    provider = HttpRagProvider(
        LingNengSettings.from_env(
            {
                "LINGNENG_RUNTIME_DIR": str(tmp_path),
                "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
            }
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.retrieve(
        RagRetrieveRequest(
            query="会员套餐",
            tenant_id="tenant-a",
            user_id="user-a",
            employee_type="marketing_content_creator",
            conversation_id="conv-a",
            session_key="session",
            request_id="req-001",
            top_k=3,
            filters={},
        )
    )

    assert result.status == "failed"
    assert result.code == "RAG_PROVIDER_INVALID_RESULT"


def test_http_rag_provider_rejects_old_lingneng_invalid_context(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "context": {"text": "not-a-string"},
                "citations": [],
                "route_debug": {"retrieval_status": "hit"},
            },
        )

    provider = HttpRagProvider(
        LingNengSettings.from_env(
            {
                "LINGNENG_RUNTIME_DIR": str(tmp_path),
                "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
            }
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = provider.retrieve(
        RagRetrieveRequest(
            query="会员套餐",
            tenant_id="tenant-a",
            user_id="user-a",
            employee_type="marketing_content_creator",
            conversation_id="conv-a",
            session_key="session",
            request_id="req-001",
            top_k=3,
            filters={},
        )
    )

    assert result.status == "failed"
    assert result.code == "RAG_PROVIDER_INVALID_RESULT"


def test_http_rag_provider_rejects_oversized_stream_without_buffering(tmp_path):
    class FakeStreamResponse:
        status_code = 200

        @property
        def content(self) -> bytes:
            raise AssertionError("response content must not be buffered")

        def iter_bytes(self, *, chunk_size: int | None = None):
            assert chunk_size == 1025
            yield b"x" * 400
            yield b"y" * 400
            yield b"z" * 400

    class FakeClient:
        def stream(self, *args: Any, **kwargs: Any) -> FakeStreamContext:
            del args, kwargs
            return FakeStreamContext(FakeStreamResponse())

    provider = HttpRagProvider(
        LingNengSettings.from_env(
            {
                "LINGNENG_RUNTIME_DIR": str(tmp_path),
                "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
                "LINGNENG_RAG_HTTP_MAX_RESPONSE_BYTES": "1024",
            }
        ),
        http_client=FakeClient(),
    )

    result = provider.retrieve(
        RagRetrieveRequest(
            query="会员套餐",
            tenant_id="tenant-a",
            user_id="user-a",
            employee_type="marketing_content_creator",
            conversation_id="conv-a",
            session_key="session",
            request_id="req-001",
            top_k=3,
            filters={},
        )
    )

    assert result.status == "failed"
    assert result.code == "RAG_PROVIDER_INVALID_RESULT"


def test_http_rag_provider_rejects_non_2xx_without_reading_body(tmp_path):
    body_read = {"content": False, "iter_bytes": False}

    class FakeStreamResponse:
        status_code = 503

        @property
        def content(self) -> bytes:
            body_read["content"] = True
            return b"must not be buffered"

        def iter_bytes(self, *, chunk_size: int | None = None):
            del chunk_size
            body_read["iter_bytes"] = True
            yield b"must not be streamed"

    class FakeClient:
        def stream(self, *args: Any, **kwargs: Any) -> FakeStreamContext:
            del args, kwargs
            return FakeStreamContext(FakeStreamResponse())

    provider = HttpRagProvider(
        LingNengSettings.from_env(
            {
                "LINGNENG_RUNTIME_DIR": str(tmp_path),
                "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
                "LINGNENG_RAG_API_KEY": "secret-rag-key",
            }
        ),
        http_client=FakeClient(),
    )

    result = provider.retrieve(
        RagRetrieveRequest(
            query="会员套餐",
            tenant_id="tenant-a",
            user_id="user-a",
            employee_type="marketing_content_creator",
            conversation_id="conv-a",
            session_key="session",
            request_id="req-001",
            top_k=3,
            filters={},
        )
    )

    dumped = result.model_dump_json()
    assert result.status == "failed"
    assert result.code == "RAG_PROVIDER_ERROR"
    assert body_read == {"content": False, "iter_bytes": False}
    assert "secret-rag-key" not in dumped
    assert "rag.example.test" not in dumped


def test_http_rag_provider_maps_timeout_to_public_failed_result(tmp_path):
    class FakeClient:
        def stream(self, *args: Any, **kwargs: Any) -> FakeStreamContext:
            del args, kwargs
            raise httpx.TimeoutException("timeout secret-rag-key")

    provider = HttpRagProvider(
        LingNengSettings.from_env(
            {
                "LINGNENG_RUNTIME_DIR": str(tmp_path),
                "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
                "LINGNENG_RAG_API_KEY": "secret-rag-key",
            }
        ),
        http_client=FakeClient(),
    )

    result = provider.retrieve(
        RagRetrieveRequest(
            query="会员套餐",
            tenant_id="tenant-a",
            user_id="user-a",
            employee_type="marketing_content_creator",
            conversation_id="conv-a",
            session_key="session",
            request_id="req-001",
            top_k=3,
            filters={},
        )
    )

    dumped = result.model_dump_json()
    assert result.status == "failed"
    assert result.code == "RAG_PROVIDER_TIMEOUT"
    assert "secret-rag-key" not in dumped
    assert "timeout secret" not in dumped


def test_http_rag_provider_rejects_invalid_json(tmp_path):
    class FakeStreamResponse:
        status_code = 200

        def iter_bytes(self, *, chunk_size: int | None = None):
            assert chunk_size == 4097
            yield b"{not-json"

    class FakeClient:
        def stream(self, *args: Any, **kwargs: Any) -> FakeStreamContext:
            del args, kwargs
            return FakeStreamContext(FakeStreamResponse())

    provider = HttpRagProvider(
        LingNengSettings.from_env(
            {
                "LINGNENG_RUNTIME_DIR": str(tmp_path),
                "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
                "LINGNENG_RAG_HTTP_MAX_RESPONSE_BYTES": "4096",
            }
        ),
        http_client=FakeClient(),
    )

    result = provider.retrieve(
        RagRetrieveRequest(
            query="会员套餐",
            tenant_id="tenant-a",
            user_id="user-a",
            employee_type="marketing_content_creator",
            conversation_id="conv-a",
            session_key="session",
            request_id="req-001",
            top_k=3,
            filters={},
        )
    )

    assert result.status == "failed"
    assert result.code == "RAG_PROVIDER_INVALID_RESULT"


def test_http_rag_provider_rejects_invalid_schema(tmp_path):
    class FakeStreamResponse:
        status_code = 200

        def iter_bytes(self, *, chunk_size: int | None = None):
            del chunk_size
            yield json.dumps({"status": "unknown", "context": "secret"}).encode()

    class FakeClient:
        def stream(self, *args: Any, **kwargs: Any) -> FakeStreamContext:
            del args, kwargs
            return FakeStreamContext(FakeStreamResponse())

    provider = HttpRagProvider(
        LingNengSettings.from_env(
            {
                "LINGNENG_RUNTIME_DIR": str(tmp_path),
                "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
            }
        ),
        http_client=FakeClient(),
    )

    result = provider.retrieve(
        RagRetrieveRequest(
            query="会员套餐",
            tenant_id="tenant-a",
            user_id="user-a",
            employee_type="marketing_content_creator",
            conversation_id="conv-a",
            session_key="session",
            request_id="req-001",
            top_k=3,
            filters={},
        )
    )

    assert result.status == "failed"
    assert result.code == "RAG_PROVIDER_INVALID_RESULT"
    assert result.context == ""


def test_http_rag_provider_default_client_disables_env_and_redirects(
    tmp_path, monkeypatch
):
    calls: list[dict[str, Any]] = []

    class FakeStreamResponse:
        status_code = 200

        def iter_bytes(self, *, chunk_size: int | None = None):
            calls.append({"chunk_size": chunk_size})
            yield json.dumps(
                {
                    "status": "hit",
                    "context": "HTTP context",
                    "citations": [],
                    "metadata": {"source": "fake-http"},
                }
            ).encode()

    class FakeClient:
        def __init__(
            self,
            *,
            timeout: float,
            trust_env: bool,
            follow_redirects: bool,
        ) -> None:
            calls.append(
                {
                    "timeout": timeout,
                    "trust_env": trust_env,
                    "follow_redirects": follow_redirects,
                }
            )

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

        def stream(
            self,
            method: str,
            endpoint: str,
            *,
            json: dict[str, Any],
            headers: dict[str, str],
            timeout: float,
        ) -> FakeStreamContext:
            calls.append(
                {
                    "method": method,
                    "endpoint": endpoint,
                    "json": json,
                    "headers": headers,
                    "timeout": timeout,
                }
            )
            return FakeStreamContext(FakeStreamResponse())

    monkeypatch.setattr("lingneng.tools.rag.httpx.Client", FakeClient)
    provider = HttpRagProvider(
        LingNengSettings.from_env(
            {
                "LINGNENG_RUNTIME_DIR": str(tmp_path),
                "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
                "LINGNENG_RAG_API_KEY": "secret-rag-key",
                "LINGNENG_RAG_TIMEOUT_SECONDS": "1.5",
                "LINGNENG_RAG_HTTP_MAX_RESPONSE_BYTES": "4096",
            }
        )
    )

    result = provider.retrieve(
        RagRetrieveRequest(
            query="会员套餐",
            tenant_id="tenant-a",
            user_id="user-a",
            employee_type="marketing_content_creator",
            conversation_id="conv-a",
            session_key="session",
            request_id="req-001",
            top_k=3,
            filters={},
        )
    )

    assert result.status == "hit"
    assert calls[0] == {
        "timeout": 1.5,
        "trust_env": False,
        "follow_redirects": False,
    }
    assert calls[1]["method"] == "POST"
    assert calls[1]["endpoint"] == "https://rag.example.test/retrieve"
    assert calls[1]["headers"] == {"Authorization": "Bearer secret-rag-key"}
    assert calls[1]["json"]["query"] == "会员套餐"
    assert calls[1]["timeout"] == 1.5
    assert calls[2] == {"chunk_size": 4097}


def test_retrieve_rag_http_provider_uses_endpoint_without_live_network(
    tmp_path, monkeypatch
):
    calls: list[dict[str, Any]] = []

    class FakeStreamResponse:
        status_code = 200

        def iter_bytes(self, *, chunk_size: int | None = None):
            del chunk_size
            yield json.dumps(
                {
                    "status": "hit",
                    "context": "HTTP context",
                    "citations": [],
                    "metadata": {"source": "fake-http"},
                }
            ).encode()

    class FakeClient:
        def __init__(
            self,
            *,
            timeout: float,
            trust_env: bool,
            follow_redirects: bool,
        ) -> None:
            calls.append(
                {
                    "timeout": timeout,
                    "trust_env": trust_env,
                    "follow_redirects": follow_redirects,
                }
            )

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

        def stream(
            self,
            method: str,
            endpoint: str,
            *,
            json: dict[str, Any],
            headers: dict[str, str],
            timeout: float,
        ) -> FakeStreamContext:
            calls.append(
                {
                    "method": method,
                    "endpoint": endpoint,
                    "json": json,
                    "headers": headers,
                    "timeout": timeout,
                }
            )
            return FakeStreamContext(FakeStreamResponse())

    monkeypatch.setattr("lingneng.tools.rag.httpx.Client", FakeClient)
    context = make_context(
        tmp_path,
        env={
            "LINGNENG_RAG_ENDPOINT": "https://rag.example.test/retrieve",
            "LINGNENG_RAG_API_KEY": "secret-rag-key",
            "LINGNENG_RAG_TIMEOUT_SECONDS": "1.5",
        },
    )

    with rag_request_context(context, provider=None):
        result = json.loads(retrieve_rag_handler({"query": "需要资料"}))

    assert result["success"] is True
    assert calls[0] == {
        "timeout": 1.5,
        "trust_env": False,
        "follow_redirects": False,
    }
    assert calls[1]["method"] == "POST"
    assert calls[1]["endpoint"] == "https://rag.example.test/retrieve"
    assert calls[1]["headers"] == {"Authorization": "Bearer secret-rag-key"}
    assert calls[1]["json"]["query"] == "需要资料"
    assert calls[1]["json"]["tenant_id"] == "tenant-a"
