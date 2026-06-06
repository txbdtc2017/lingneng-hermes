from __future__ import annotations

import pytest
from pydantic import ValidationError

from lingneng.events.bridge import (
    agent_step_completed,
    agent_step_skipped,
    agent_step_started,
)
from lingneng.schemas.chat_events import AgentStepEvent, FORMAL_EVENT_NAMES


def test_agent_step_is_formal_event_name():
    assert "agent_step" in FORMAL_EVENT_NAMES


def test_agent_step_event_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        AgentStepEvent(
            sequence=1,
            step_id="tool-1",
            phase="tool",
            status="started",
            title="Tool started",
            short_text="Starting tool.",
            refs=[],
            raw_args={"query": "secret"},
        )


def test_tool_started_maps_to_public_agent_step():
    event = agent_step_started(
        sequence=1,
        tool_name="retrieve_rag",
        preview="query='sales'",
    )

    assert event.sequence == 1
    assert event.step_id == "tool-1"
    assert event.phase == "tool"
    assert event.status == "started"
    assert event.title == "retrieve_rag"
    assert event.short_text == "Starting retrieve_rag."
    assert event.summary == "query='sales'"
    assert event.refs == []


def test_tool_success_maps_to_public_agent_step():
    event = agent_step_completed(
        sequence=2,
        tool_name="retrieve_rag",
        duration=1.25,
        is_error=False,
        result='{"success": false, "code": "NOT_CONFIGURED"}',
    )

    assert event.sequence == 2
    assert event.step_id == "tool-2"
    assert event.status == "succeeded"
    assert event.short_text == "Completed retrieve_rag."
    assert event.summary == "Duration: 1.25s"


def test_tool_skip_maps_to_public_agent_step():
    event = agent_step_skipped(
        sequence=3,
        tool_name="retrieve_rag",
        reason="blocked by policy",
    )

    assert event.sequence == 3
    assert event.step_id == "tool-3"
    assert event.status == "skipped"
    assert event.short_text == "Skipped retrieve_rag."
    assert event.summary == "blocked by policy"


def test_tool_failure_does_not_leak_internal_exception_text():
    event = agent_step_completed(
        sequence=4,
        tool_name="retrieve_rag",
        duration=0.5,
        is_error=True,
        result="RuntimeError: private provider detail api_key=secret",
    )

    dumped = event.model_dump_json()
    assert event.status == "failed"
    assert event.short_text == "retrieve_rag failed."
    assert event.summary == "Tool failed with a public error summary."
    assert "private provider detail" not in dumped
    assert "api_key" not in dumped
    assert "secret" not in dumped
