import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import BaseModel

from lingneng.api.sse import encode_sse, heartbeat_frame, with_heartbeats
from lingneng.schemas.chat_events import AnswerDeltaEvent


def _json_data(frame: str) -> dict[str, Any]:
    data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
    return json.loads(data_line.removeprefix("data: "))


def test_encode_sse_uses_event_line_and_utf8_json():
    assert (
        encode_sse("answer_delta", {"text": "你好"})
        == 'event: answer_delta\ndata: {"text": "你好"}\n\n'
    )


def test_encode_sse_does_not_require_event_in_data():
    frame = encode_sse("final", {"answer": "完成"})

    assert frame == 'event: final\ndata: {"answer": "完成"}\n\n'
    assert '"event"' not in frame


def test_heartbeat_frame_is_comment_ping():
    assert heartbeat_frame() == ": ping\n\n"


def test_encode_sse_accepts_pydantic_model():
    event = AnswerDeltaEvent(text="你好", sequence=1)

    assert (
        encode_sse("answer_delta", event)
        == 'event: answer_delta\ndata: {"text": "你好", "sequence": 1}\n\n'
    )


def test_encode_sse_uses_pydantic_json_mode_for_datetime():
    class TimedEvent(BaseModel):
        created_at: datetime

    event = TimedEvent(created_at=datetime(2026, 6, 6, 12, 34, 56, tzinfo=timezone.utc))
    frame = encode_sse("timed_event", event)

    assert _json_data(frame)["created_at"] == "2026-06-06T12:34:56Z"


def test_encode_sse_rejects_event_name_with_newline():
    with pytest.raises(ValueError):
        encode_sse("answer_delta\nbad", {"text": "你好"})


@pytest.mark.asyncio
async def test_with_heartbeats_yields_ping_before_slow_source_frame():
    frame = 'event: answer_delta\ndata: {"text": "你好"}\n\n'
    source_ready = asyncio.Event()

    async def slow_source():
        await source_ready.wait()
        yield frame

    stream = with_heartbeats(slow_source(), interval_seconds=0.01)

    assert await anext(stream) == ": ping\n\n"
    source_ready.set()
    assert await anext(stream) == frame
    await stream.aclose()


@pytest.mark.asyncio
async def test_with_heartbeats_rejects_non_positive_interval():
    async def source():
        yield 'event: final\ndata: {"answer": "完成"}\n\n'

    stream = with_heartbeats(source(), interval_seconds=0)

    with pytest.raises(ValueError):
        await anext(stream)
