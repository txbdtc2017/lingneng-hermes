import json
import threading
import time

import pytest

import lingneng.runtime.hermes_adapter as hermes_adapter_module
from lingneng.config.settings import LingNengSettings
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.schemas.chat_events import (
    AgentStepEvent,
    AnswerDeltaEvent,
    CitationDeltaEvent,
    ErrorEvent,
    FinalEvent,
    RagContextEvent,
    RunStartedEvent,
)
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def settings(tmp_path) -> LingNengSettings:
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_AGENT_MODE": "hermes",
            "LINGNENG_INTERNAL_API_KEY": "key",
        }
    )


class StreamingAgent:
    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")

    def run_conversation(self, *args, **kwargs):
        self.stream_delta_callback("你")
        self.stream_delta_callback("好")
        return {"final_response": "你好", "messages": []}


class NonStreamingAgent:
    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")

    def run_conversation(self, *args, **kwargs):
        return {"final_response": "完成", "messages": []}


class EmptyAnswerAgent:
    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")

    def run_conversation(self, *args, **kwargs):
        return {"final_response": "", "messages": []}


class FailingAgent:
    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")

    def run_conversation(self, *args, **kwargs):
        raise RuntimeError("private provider detail")


class ToolProgressAgent:
    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")
        self.tool_progress_callback = kwargs.get("tool_progress_callback")

    def run_conversation(self, *args, **kwargs):
        self.tool_progress_callback(
            "tool.started",
            "retrieve_rag",
            "query='sales api_key=secret'",
            {"query": "sales api_key=secret"},
        )
        self.tool_progress_callback(
            "tool.completed",
            "retrieve_rag",
            None,
            None,
            duration=0.25,
            is_error=False,
            result='{"success": false, "code": "NOT_CONFIGURED"}',
        )
        return {"final_response": "完成", "messages": []}


class RagHitToolProgressAgent:
    def __init__(self, **kwargs):
        self.tool_progress_callback = kwargs.get("tool_progress_callback")

    def run_conversation(self, *args, **kwargs):
        self.tool_progress_callback(
            "tool.completed",
            "retrieve_rag",
            None,
            None,
            duration=0.25,
            is_error=False,
            result=json.dumps(
                {
                    "success": True,
                    "tool_name": "retrieve_rag",
                    "status": "hit",
                    "context": "套餐规则",
                    "citations": [
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
                    "metadata": {"selected_count": 1},
                },
                ensure_ascii=False,
            ),
        )
        return {"final_response": "完成", "messages": []}


class ConcurrentToolProgressAgent:
    def __init__(self, **kwargs):
        self.tool_progress_callback = kwargs.get("tool_progress_callback")

    def run_conversation(self, *args, **kwargs):
        worker_count = 8
        barrier = threading.Barrier(worker_count)
        threads = [
            threading.Thread(
                target=self._emit_tool_progress,
                args=(barrier, index),
            )
            for index in range(worker_count)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
            if thread.is_alive():
                raise AssertionError("tool progress worker did not finish")
        return {"final_response": "完成", "messages": []}

    def _emit_tool_progress(self, barrier: threading.Barrier, index: int) -> None:
        barrier.wait(timeout=5)
        self.tool_progress_callback(
            "tool.completed",
            f"retrieve_rag_{index}",
            None,
            None,
            duration=0.01,
            is_error=False,
            result="{}",
        )


def request_and_session():
    request = ChatStreamRequest.model_validate(full_payload())
    return request, resolve_session_key(request)


def request_and_session_with_rag_context():
    payload = full_payload()
    payload["stream_options"]["include_rag_context"] = True
    request = ChatStreamRequest.model_validate(payload)
    return request, resolve_session_key(request)


@pytest.mark.asyncio
async def test_stream_callback_becomes_ordered_answer_delta_events(tmp_path):
    request, resolved = request_and_session()
    adapter = HermesAgentRunAdapter(settings(tmp_path), agent_cls=StreamingAgent)

    events = [event async for event in adapter.stream(request, resolved, "run-1")]
    deltas = [event for event in events if isinstance(event, AnswerDeltaEvent)]
    final = events[-1]

    assert [delta.text for delta in deltas] == ["你", "好"]
    assert [delta.sequence for delta in deltas] == [1, 2]
    assert isinstance(final, FinalEvent)
    assert final.answer == "你好"
    assert "".join(delta.text for delta in deltas) == final.answer


@pytest.mark.asyncio
async def test_final_answer_is_synthesized_as_delta_when_no_streaming_occurs(
    tmp_path,
):
    request, resolved = request_and_session()
    adapter = HermesAgentRunAdapter(settings(tmp_path), agent_cls=NonStreamingAgent)

    events = [event async for event in adapter.stream(request, resolved, "run-1")]
    deltas = [event for event in events if isinstance(event, AnswerDeltaEvent)]
    final = events[-1]

    assert [delta.text for delta in deltas] == ["完成"]
    assert isinstance(final, FinalEvent)
    assert final.answer == "完成"


@pytest.mark.asyncio
async def test_empty_final_answer_synthesizes_empty_delta(tmp_path):
    request, resolved = request_and_session()
    adapter = HermesAgentRunAdapter(settings(tmp_path), agent_cls=EmptyAnswerAgent)

    events = [event async for event in adapter.stream(request, resolved, "run-1")]

    assert [type(event) for event in events] == [
        RunStartedEvent,
        AnswerDeltaEvent,
        FinalEvent,
    ]
    delta = events[1]
    final = events[2]
    assert delta.text == ""
    assert delta.sequence == 1
    assert final.answer == ""


@pytest.mark.asyncio
async def test_hermes_exception_maps_to_public_error(tmp_path):
    request, resolved = request_and_session()
    adapter = HermesAgentRunAdapter(settings(tmp_path), agent_cls=FailingAgent)

    events = [event async for event in adapter.stream(request, resolved, "run-1")]
    error = events[-1]

    assert isinstance(error, ErrorEvent)
    assert error.code == "RUNTIME_ERROR"
    assert error.message == "Agent runtime failed"
    assert error.recoverable is False


@pytest.mark.asyncio
async def test_tool_progress_callback_becomes_agent_step_events(tmp_path):
    request, resolved = request_and_session()
    adapter = HermesAgentRunAdapter(settings(tmp_path), agent_cls=ToolProgressAgent)

    events = [event async for event in adapter.stream(request, resolved, "run-1")]
    agent_steps = [event for event in events if isinstance(event, AgentStepEvent)]
    started_dumped = agent_steps[0].model_dump_json()

    assert [event.status for event in agent_steps] == ["started", "succeeded"]
    assert [event.sequence for event in agent_steps] == [1, 2]
    assert agent_steps[0].short_text == "Starting retrieve_rag."
    assert agent_steps[0].summary == "Tool input received."
    assert "api_key" not in started_dumped
    assert "secret" not in started_dumped
    assert agent_steps[1].short_text == "Completed retrieve_rag."
    assert agent_steps[1].summary == "Duration: 0.25s"
    assert isinstance(events[-1], FinalEvent)
    assert events[-1].answer == "完成"


@pytest.mark.asyncio
async def test_retrieve_rag_completion_emits_rag_events_and_final_citations(tmp_path):
    request, resolved = request_and_session_with_rag_context()
    adapter = HermesAgentRunAdapter(settings(tmp_path), agent_cls=RagHitToolProgressAgent)

    events = [event async for event in adapter.stream(request, resolved, "run-1")]

    assert [type(event) for event in events[1:4]] == [
        AgentStepEvent,
        CitationDeltaEvent,
        RagContextEvent,
    ]
    assert events[1].status == "succeeded"
    assert events[2].chunk_id == "chunk-1"
    assert events[3].status == "hit"
    assert isinstance(events[-1], FinalEvent)
    assert events[-1].model_dump()["citations"][0]["chunk_id"] == "chunk-1"


@pytest.mark.asyncio
async def test_concurrent_tool_progress_events_keep_ordered_unique_sequences(
    tmp_path,
    monkeypatch,
):
    original_agent_step_completed = hermes_adapter_module.agent_step_completed

    def delayed_agent_step_completed(*args, **kwargs):
        sequence = kwargs.get("sequence", args[0] if args else 0)
        time.sleep((9 - sequence) * 0.001)
        return original_agent_step_completed(*args, **kwargs)

    monkeypatch.setattr(
        hermes_adapter_module,
        "agent_step_completed",
        delayed_agent_step_completed,
    )
    request, resolved = request_and_session()
    adapter = HermesAgentRunAdapter(
        settings(tmp_path),
        agent_cls=ConcurrentToolProgressAgent,
    )

    events = [event async for event in adapter.stream(request, resolved, "run-1")]
    agent_steps = [event for event in events if isinstance(event, AgentStepEvent)]

    assert [event.sequence for event in agent_steps] == list(range(1, 9))
    assert [event.step_id for event in agent_steps] == [
        f"tool-{sequence}" for sequence in range(1, 9)
    ]
    assert len({event.sequence for event in agent_steps}) == 8
    assert len({event.step_id for event in agent_steps}) == 8
