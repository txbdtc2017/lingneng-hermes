import json
from typing import Any, cast

from lingneng.events.bridge import (
    dedupe_citations,
    final_answer,
    rag_events_from_tool_result as _rag_events_from_tool_result,
)
from lingneng.schemas.chat_events import CitationDeltaEvent, FinalEvent, RagContextEvent


CITATION = {
    "document_id": "doc-1",
    "source_file_id": "file-1",
    "source_file_name": "menu.pdf",
    "page_no": 2,
    "section_title": "套餐",
    "chunk_id": "chunk-1",
    "score": 0.9,
}


def rag_events_from_tool_result(
    **kwargs: Any,
) -> tuple[list[Any], list[dict[str, Any]]]:
    return cast(
        tuple[list[Any], list[dict[str, Any]]],
        _rag_events_from_tool_result(**kwargs),
    )


def result_payload(**overrides):
    payload = {
        "success": True,
        "tool_name": "retrieve_rag",
        "status": "hit",
        "context": "套餐规则",
        "citations": [CITATION],
        "metadata": {"selected_count": 1},
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def test_rag_hit_emits_citation_and_context_when_requested():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(),
        include_citations=True,
        include_rag_context=True,
    )

    assert [type(event) for event in events] == [CitationDeltaEvent, RagContextEvent]
    assert events[0].chunk_id == "chunk-1"
    assert events[1].status == "hit"
    assert citations == [CITATION]


def test_rag_context_allows_benign_request_query_input_words():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(
            context="Customer request classification and query input routing policy."
        ),
        include_citations=True,
        include_rag_context=True,
    )

    assert [type(event) for event in events] == [CitationDeltaEvent, RagContextEvent]
    assert (
        events[1].context
        == "Customer request classification and query input routing policy."
    )
    assert events[1].status == "hit"
    assert citations == [CITATION]


def test_rag_events_allow_benign_token_usage_and_exception_rate_text():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(
            context="token usage trend and exception rate are business metrics.",
            metadata={
                "notes": [
                    "token usage is high",
                    "exception rate changed",
                ]
            },
        ),
        include_citations=True,
        include_rag_context=True,
    )

    assert [type(event) for event in events] == [CitationDeltaEvent, RagContextEvent]
    assert events[1].context == "token usage trend and exception rate are business metrics."
    assert events[1].metadata["notes"] == [
        "token usage is high",
        "exception rate changed",
    ]
    assert citations == [CITATION]


def test_rag_events_strip_percent_encoded_private_values_and_citation_fields():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(
            context="api%5Fkey%3Dabc123 %2FUsers%2Frotas%2Fprivate",
            citations=[
                {
                    **CITATION,
                    "source_file_name": "%2FUsers%2Frotas%2Fprivate.pdf",
                    "section_title": "token%3Dsecret",
                    "raw_payload": "api_key=secret",
                }
            ],
            metadata={
                "selected_count": 1,
                "notes": ["x-amz-signature=abc", "public retrieval summary"],
                "request_payload": "query=USER PRIVATE INPUT",
            },
        ),
        include_citations=True,
        include_rag_context=True,
    )

    dumped = json.dumps(
        [event.model_dump(mode="json") for event in events],
        ensure_ascii=False,
    )
    assert [type(event) for event in events] == [CitationDeltaEvent, RagContextEvent]
    assert events[0].source_file_name == ""
    assert events[0].section_title == ""
    assert events[1].context == ""
    assert events[1].metadata == {
        "selected_count": 1,
        "notes": ["", "public retrieval summary"],
    }
    assert citations[0]["source_file_name"] == ""
    assert "raw_payload" not in dumped
    assert "api%5Fkey" not in dumped
    assert "%2FUsers" not in dumped
    assert "x-amz-signature" not in dumped


def test_rag_events_strip_json_shaped_raw_dump_metadata_values():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(
            metadata={
                "selected_count": 1,
                "notes": [
                    '{"query":"客户问套餐"}',
                    '{"input":"客户问套餐"}',
                    '{"summary":"public retrieval summary"}',
                ],
            },
        ),
        include_citations=True,
        include_rag_context=True,
    )

    dumped = json.dumps(
        [event.model_dump(mode="json") for event in events],
        ensure_ascii=False,
    )
    assert [type(event) for event in events] == [CitationDeltaEvent, RagContextEvent]
    assert events[1].metadata["notes"] == [
        "",
        "",
        '{"summary":"public retrieval summary"}',
    ]
    assert "客户问套餐" not in dumped
    assert citations == [CITATION]


def test_rag_events_strip_common_local_path_metadata_values():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(
            context="file:///Volumes/private/rag.txt",
            metadata={
                "selected_count": 1,
                "notes": [
                    "/Volumes/private/rag.txt",
                    "~/Library/Application Support/rag.txt",
                    "../private/rag.txt",
                    "Volume discount policy remains public",
                ],
            },
        ),
        include_citations=True,
        include_rag_context=True,
    )

    dumped = json.dumps(
        [event.model_dump(mode="json") for event in events],
        ensure_ascii=False,
    )
    assert [type(event) for event in events] == [CitationDeltaEvent, RagContextEvent]
    assert events[1].context == ""
    assert events[1].metadata["notes"] == [
        "",
        "",
        "",
        "Volume discount policy remains public",
    ]
    assert "/Volumes" not in dumped
    assert "~/Library" not in dumped
    assert "../private" not in dumped
    assert "file:///Volumes" not in dumped
    assert citations == [CITATION]


def test_rag_empty_emits_empty_context_only_when_requested():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(status="empty", context="", citations=[]),
        include_citations=True,
        include_rag_context=True,
    )

    assert [type(event) for event in events] == [RagContextEvent]
    assert events[0].status == "empty"
    assert citations == []


def test_rag_hit_with_no_public_context_or_citations_emits_empty_status():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(
            status="hit",
            context="Authorization: Bearer abc123",
            citations=[],
        ),
        include_citations=True,
        include_rag_context=True,
    )

    assert [type(event) for event in events] == [RagContextEvent]
    assert events[0].context == ""
    assert events[0].status == "empty"
    assert events[0].citations == []
    assert citations == []


def test_rag_events_honor_stream_options():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(),
        include_citations=False,
        include_rag_context=False,
    )

    assert events == []
    assert citations == []


def test_non_rag_tool_result_is_ignored():
    events, citations = rag_events_from_tool_result(
        tool_name="document_generation",
        result=result_payload(),
        include_citations=True,
        include_rag_context=True,
    )

    assert events == []
    assert citations == []


def test_invalid_tool_result_is_ignored():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=json.dumps({"unexpected": True}),
        include_citations=True,
        include_rag_context=True,
    )

    assert events == []
    assert citations == []


def test_invalid_json_tool_result_is_ignored():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result="{not-json",
        include_citations=True,
        include_rag_context=True,
    )

    assert events == []
    assert citations == []


def test_invalid_citation_items_are_ignored():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(citations=[CITATION, {**CITATION, "score": -1}]),
        include_citations=True,
        include_rag_context=True,
    )

    assert [type(event) for event in events] == [CitationDeltaEvent, RagContextEvent]
    assert events[0].chunk_id == "chunk-1"
    assert events[1].citations[0].chunk_id == "chunk-1"
    assert citations == [CITATION]


def test_failed_rag_context_uses_public_message_and_sanitizes_metadata():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(
            success=False,
            status="failed",
            context="traceback api_key=secret",
            message="LingNeng RAG provider failed.",
            citations=[],
            metadata={"selected_count": 0, "api_key": "secret"},
        ),
        include_citations=True,
        include_rag_context=True,
    )

    assert [type(event) for event in events] == [RagContextEvent]
    assert events[0].status == "failed"
    assert events[0].context == "LingNeng RAG provider failed."
    assert events[0].metadata == {"selected_count": 0}
    assert citations == []


def test_rag_context_metadata_strips_request_and_authorization_details():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(
            metadata={
                "selected_count": 1,
                "citation_count": 1,
                "duration_ms": 42,
                "request_payload": {"query": "USER PRIVATE INPUT"},
                "authorization": "Bearer abc123",
                "notes": ["Bearer abc123"],
            }
        ),
        include_citations=True,
        include_rag_context=True,
    )

    assert [type(event) for event in events] == [CitationDeltaEvent, RagContextEvent]
    assert events[1].metadata == {
        "selected_count": 1,
        "citation_count": 1,
        "duration_ms": 42,
        "notes": [""],
    }
    assert citations == [CITATION]


def test_rag_context_metadata_strips_input_shaped_string_values():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(
            metadata={
                "notes": ["raw request query input: USER PRIVATE INPUT"],
                "selected_count": 1,
            }
        ),
        include_citations=True,
        include_rag_context=True,
    )

    assert [type(event) for event in events] == [CitationDeltaEvent, RagContextEvent]
    assert events[1].metadata == {"notes": [""], "selected_count": 1}
    assert "USER PRIVATE INPUT" not in json.dumps(
        events[1].metadata,
        ensure_ascii=False,
    )
    assert citations == [CITATION]


def test_failure_shaped_result_without_status_emits_failed_context():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=json.dumps(
            {
                "success": False,
                "tool_name": "retrieve_rag",
                "code": "NOT_CONFIGURED",
                "message": "LingNeng RAG provider is not configured.",
            }
        ),
        include_citations=True,
        include_rag_context=True,
    )

    assert [type(event) for event in events] == [RagContextEvent]
    assert events[0].status == "failed"
    assert events[0].context == "LingNeng RAG provider is not configured."
    assert events[0].metadata == {}
    assert citations == []


def test_missing_status_defaults_from_valid_citations():
    events, citations = rag_events_from_tool_result(
        tool_name="retrieve_rag",
        result=result_payload(status=None),
        include_citations=True,
        include_rag_context=True,
    )

    assert events[-1].status == "hit"
    assert citations == [CITATION]


def test_dedupe_citations_by_chunk_id():
    duplicate = {**CITATION, "source_file_name": "duplicate.pdf"}

    assert dedupe_citations(
        [CITATION, duplicate, {**CITATION, "chunk_id": "chunk-2"}]
    ) == [
        CITATION,
        {**CITATION, "chunk_id": "chunk-2"},
    ]


def test_final_answer_accepts_citations():
    event = final_answer(run_id="run-1", answer="完成", citations=[CITATION])

    assert isinstance(event, FinalEvent)
    assert event.model_dump()["citations"] == [CITATION]
