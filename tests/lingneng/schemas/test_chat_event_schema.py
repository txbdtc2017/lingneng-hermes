from lingneng.schemas.chat_events import (
    AnswerDeltaEvent,
    Artifact,
    ArtifactCreatedEvent,
    Citation,
    CitationDeltaEvent,
    ErrorEvent,
    FINAL_STATUSES,
    FORMAL_EVENT_NAMES,
    FinalEvent,
    RagContextEvent,
    RunStartedEvent,
)


def test_formal_event_names_match_lingneng_p1_contract():
    assert FORMAL_EVENT_NAMES == [
        "run_started",
        "agent_step",
        "route_result",
        "route_suggestion",
        "route_confirm_required",
        "citation_delta",
        "rag_context",
        "artifact_created",
        "answer_delta",
        "final",
        "compliance_block",
        "error",
    ]


def test_phase_1_event_payloads_dump_without_event_field():
    started = RunStartedEvent(run_id="run-1", request_id="req-1")
    delta = AnswerDeltaEvent(text="你好", sequence=1)
    final = FinalEvent(run_id="run-1", status="succeeded", answer="你好")
    error = ErrorEvent(
        run_id="run-1",
        request_id="req-1",
        code="RUNTIME_ERROR",
        message="运行失败",
        trace_id="trace-1",
        recoverable=False,
    )

    assert started.model_dump() == {"run_id": "run-1", "request_id": "req-1"}
    assert delta.model_dump() == {"text": "你好", "sequence": 1}
    assert final.model_dump() == {
        "run_id": "run-1",
        "status": "succeeded",
        "answer": "你好",
        "citations": [],
        "artifacts": [],
    }
    assert error.model_dump() == {
        "run_id": "run-1",
        "request_id": "req-1",
        "code": "RUNTIME_ERROR",
        "message": "运行失败",
        "trace_id": "trace-1",
        "recoverable": False,
    }
    assert "event" not in started.model_dump()
    assert "event" not in delta.model_dump()
    assert "event" not in final.model_dump()
    assert "event" not in error.model_dump()
    assert "tool_plan" not in final.model_dump()


def test_final_statuses_include_required_values():
    assert FINAL_STATUSES == {"succeeded", "degraded", "failed", "blocked"}


def test_rag_event_payloads_dump_without_event_field():
    citation = Citation(
        document_id="doc-1",
        source_file_id="file-1",
        source_file_name="menu.pdf",
        page_no=2,
        section_title="套餐",
        chunk_id="chunk-1",
        score=0.9,
    )
    delta = CitationDeltaEvent.model_validate(citation.model_dump())
    context = RagContextEvent(
        context="套餐规则",
        citations=[citation],
        status="hit",
        metadata={"selected_count": 1},
    )

    assert delta.model_dump()["chunk_id"] == "chunk-1"
    assert context.model_dump()["status"] == "hit"
    assert "event" not in delta.model_dump()
    assert "event" not in context.model_dump()


def test_artifact_event_payloads_dump_without_event_field():
    artifact = Artifact(
        artifact_id="artifact-doc-1",
        artifact_type="document",
        source="document_generation",
        file_name="report.pdf",
        mime_type="application/pdf",
        url="https://files.example.test/report.pdf",
        object_key="external/java-agent-file/artifact-doc-1",
        format="pdf",
        target_format="pdf",
        conversion_required=False,
        conversion_owner=None,
    )
    event = ArtifactCreatedEvent.model_validate(artifact.model_dump())
    final = FinalEvent(
        run_id="run-1",
        status="succeeded",
        answer="完成",
        artifacts=[artifact],
    )

    assert event.artifact_id == "artifact-doc-1"
    assert event.model_dump()["artifact_type"] == "document"
    assert final.model_dump()["artifacts"][0]["artifact_id"] == "artifact-doc-1"
    assert "event" not in event.model_dump()
    assert "event" not in final.model_dump()
