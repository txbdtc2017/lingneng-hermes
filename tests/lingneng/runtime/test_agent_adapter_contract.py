import pytest

from lingneng.runtime.fake_agent import FakeAgentRunAdapter
from lingneng.schemas.chat_events import AnswerDeltaEvent, FinalEvent, RunStartedEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from tests.lingneng.schemas.test_chat_request_schema import full_payload


@pytest.mark.asyncio
async def test_fake_adapter_streams_minimum_phase_1_events():
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = FakeAgentRunAdapter(answer="你好，已完成。")

    events = [event async for event in adapter.stream(request, resolved, "run-test")]

    assert isinstance(events[0], RunStartedEvent)
    assert any(isinstance(event, AnswerDeltaEvent) for event in events)
    assert isinstance(events[-1], FinalEvent)
    assert events[0].request_id == "req-001"
    assert events[0].run_id == "run-test"
    assert events[-1].run_id == "run-test"
    assert events[-1].status == "succeeded"


@pytest.mark.asyncio
async def test_joined_deltas_equal_final_answer():
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = FakeAgentRunAdapter(answer="第一段第二段", chunk_size=2)

    events = [event async for event in adapter.stream(request, resolved, "run-test")]
    deltas = [event for event in events if isinstance(event, AnswerDeltaEvent)]
    final = events[-1]

    assert isinstance(final, FinalEvent)
    assert [delta.sequence for delta in deltas] == [1, 2, 3]
    assert "".join(delta.text for delta in deltas) == final.answer


def test_chunk_size_must_be_positive():
    with pytest.raises(ValueError, match="chunk_size must be a positive integer"):
        FakeAgentRunAdapter(chunk_size=0)
