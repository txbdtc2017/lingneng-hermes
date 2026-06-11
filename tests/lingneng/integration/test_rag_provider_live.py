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
        assert settings.rag_api_key not in serialized
    assert query not in serialized
    if endpoint:
        assert endpoint not in serialized
    endpoint_parts = urlsplit(endpoint)
    if endpoint_parts.query:
        assert endpoint_parts.query not in serialized
        for key, value in parse_qsl(endpoint_parts.query, keep_blank_values=True):
            if key:
                assert key not in serialized
            if value:
                assert value not in serialized
    for marker in _LIVE_REQUEST_MARKERS:
        assert marker.lower() not in lowered_serialized
