import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.schemas.chat_events import AnswerDeltaEvent, ErrorEvent, FinalEvent
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


class FailingAgent:
    def __init__(self, **kwargs):
        self.stream_delta_callback = kwargs.get("stream_delta_callback")

    def run_conversation(self, *args, **kwargs):
        raise RuntimeError("private provider detail")


def request_and_session():
    request = ChatStreamRequest.model_validate(full_payload())
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
async def test_hermes_exception_maps_to_public_error(tmp_path):
    request, resolved = request_and_session()
    adapter = HermesAgentRunAdapter(settings(tmp_path), agent_cls=FailingAgent)

    events = [event async for event in adapter.stream(request, resolved, "run-1")]
    error = events[-1]

    assert isinstance(error, ErrorEvent)
    assert error.code == "RUNTIME_ERROR"
    assert error.message == "Agent runtime failed"
    assert error.recoverable is False
