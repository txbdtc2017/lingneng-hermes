import pytest
from pydantic import ValidationError

from lingneng.schemas.chat_events import (
    AnswerDeltaEvent,
    Artifact,
    ArtifactCreatedEvent,
    ComplianceBlockEvent,
    Citation,
    CitationDeltaEvent,
    ErrorEvent,
    FINAL_STATUSES,
    FORMAL_EVENT_NAMES,
    FinalEvent,
    RagContextEvent,
    RouteCandidate,
    RouteConfirmRequiredEvent,
    RouteResultEvent,
    RouteSuggestionEvent,
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


def test_route_event_payloads_dump_without_event_field():
    result = RouteResultEvent(
        target_employee_type="marketing_content_creator",
        confidence=0.91,
        need_confirm=False,
        is_current_employee=False,
    )
    suggestion = RouteSuggestionEvent(
        current_employee_type="marketing_planner",
        target_employee_type="marketing_content_creator",
        confidence=0.88,
        reason="需要生成可直接发布的营销内容",
        reply="这个问题更适合由营销内容创作处理，我为你切换到对应数字员工。",
    )
    confirm = RouteConfirmRequiredEvent(
        query="做一个营销活动",
        candidates=[
            RouteCandidate(
                employee_type="marketing_planner",
                confidence=0.62,
                label="营销策划",
                reason="需要活动方案",
            ),
            RouteCandidate(
                employee_type="marketing_content_creator",
                confidence=0.58,
                label="营销内容创作",
                reason="需要文案内容",
            ),
        ],
        reply="这个问题可能需要不同数字员工处理，请选择一个方向。",
    )
    compliance = ComplianceBlockEvent(
        risk_level="medium",
        risk_categories=["policy"],
        reply="该请求暂时无法处理。",
    )

    assert "event" not in result.model_dump()
    assert "event" not in suggestion.model_dump()
    assert "event" not in confirm.model_dump()
    assert "event" not in compliance.model_dump()
    result_json = result.model_dump(mode="json")
    suggestion_json = suggestion.model_dump(mode="json")
    confirm_json = confirm.model_dump(mode="json")
    assert result_json["target_employee_type"] == (
        "marketing_content_creator"
    )
    assert suggestion_json["current_employee_type"] == (
        "marketing_planner"
    )
    assert confirm_json["candidates"][0]["employee_type"] == "marketing_planner"
    assert confirm_json["candidates"][0]["label"] == "营销策划"


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_route_candidate_rejects_invalid_confidence(confidence):
    with pytest.raises(ValidationError):
        RouteCandidate(
            employee_type="marketing_planner",
            confidence=confidence,
            label="营销策划",
            reason="需要活动方案",
        )


@pytest.mark.parametrize("candidate_count", [0, 1, 5])
def test_route_confirm_required_rejects_wrong_candidate_count(candidate_count):
    candidates = [
        RouteCandidate(
            employee_type="marketing_planner",
            confidence=0.6,
            label="营销策划",
            reason="需要活动方案",
        )
        for _ in range(candidate_count)
    ]
    with pytest.raises(ValidationError):
        RouteConfirmRequiredEvent(
            query="做一个营销活动",
            candidates=candidates,
            reply="请选择处理方向。",
        )


def test_route_confirm_required_rejects_duplicate_candidate_employee_types():
    with pytest.raises(ValidationError):
        RouteConfirmRequiredEvent(
            query="做一个营销活动",
            candidates=[
                RouteCandidate(
                    employee_type="marketing_planner",
                    confidence=0.6,
                    label="营销策划",
                    reason="需要活动方案",
                ),
                RouteCandidate(
                    employee_type="marketing_planner",
                    confidence=0.5,
                    label="营销策划",
                    reason="仍然是活动方案",
                ),
            ],
            reply="请选择处理方向。",
        )
