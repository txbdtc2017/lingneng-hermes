from lingneng.schemas.chat_events import (
    AnswerDeltaEvent,
    ErrorEvent,
    FINAL_STATUSES,
    FORMAL_EVENT_NAMES,
    FinalEvent,
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
