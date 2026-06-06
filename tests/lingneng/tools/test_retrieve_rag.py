from __future__ import annotations

import json
from typing import Any

import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from lingneng.tools.rag import (
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


def test_retrieve_rag_http_provider_uses_endpoint_without_live_network(
    tmp_path, monkeypatch
):
    calls: list[dict[str, Any]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "status": "hit",
                "context": "HTTP context",
                "citations": [],
                "metadata": {"source": "fake-http"},
            }

    class FakeClient:
        def __init__(self, *, timeout: float) -> None:
            calls.append({"timeout": timeout})

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

        def post(
            self,
            endpoint: str,
            *,
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> FakeResponse:
            calls.append({"endpoint": endpoint, "json": json, "headers": headers})
            return FakeResponse()

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
    assert calls[0] == {"timeout": 1.5}
    assert calls[1]["endpoint"] == "https://rag.example.test/retrieve"
    assert calls[1]["headers"] == {"Authorization": "Bearer secret-rag-key"}
    assert calls[1]["json"]["query"] == "需要资料"
    assert calls[1]["json"]["tenant_id"] == "tenant-a"
