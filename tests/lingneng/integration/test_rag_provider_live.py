import os
from urllib.parse import parse_qsl, urlsplit

import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.tools.rag import HttpRagProvider, RagRetrieveRequest


_LIVE_REQUEST_MARKERS = (
    "live-test-request",
    "live-test-tenant",
    "live-test-user",
    "live-test-conversation",
    "live-test-tenant:live-test-user",
    "request_id",
    "raw request",
    "raw_request",
    "request_body",
)


def _assert_absent(value: str, haystack: str, description: str) -> None:
    if value and value in haystack:
        raise AssertionError(f"live RAG result leaked {description}")


def test_live_rag_provider_smoke_is_gated_and_secret_safe(tmp_path):
    env = dict(os.environ)
    env.setdefault("LINGNENG_RUNTIME_DIR", str(tmp_path))
    settings = LingNengSettings.from_env(env)
    query = settings.rag_live_test_query.strip()

    if not (
        settings.rag_live_test_enabled
        and settings.rag_endpoint.strip()
        and query
    ):
        pytest.skip("live RAG provider smoke test is disabled")

    result = HttpRagProvider(settings).retrieve(
        RagRetrieveRequest(
            query=query,
            tenant_id="live-test-tenant",
            user_id="live-test-user",
            employee_type="live_test",
            conversation_id="live-test-conversation",
            session_key="live-test-tenant:live-test-user:live-test:live-test-conversation",
            request_id="live-test-request",
            top_k=settings.rag_default_top_k,
            filters={},
        )
    )

    assert result.status in {"hit", "empty", "failed"}
    serialized = result.model_dump_json()
    lowered_serialized = serialized.lower()
    endpoint = settings.rag_endpoint.strip()
    if settings.rag_api_key:
        _assert_absent(settings.rag_api_key, serialized, "API key")
    _assert_absent(query, serialized, "live query")
    if endpoint:
        _assert_absent(endpoint, serialized, "endpoint")
    endpoint_parts = urlsplit(endpoint)
    if endpoint_parts.query:
        _assert_absent(endpoint_parts.query, serialized, "endpoint query")
        for key, value in parse_qsl(endpoint_parts.query, keep_blank_values=True):
            _assert_absent(key, serialized, "endpoint query key")
            _assert_absent(value, serialized, "endpoint query value")
    for marker in _LIVE_REQUEST_MARKERS:
        _assert_absent(marker.lower(), lowered_serialized, "request marker")
