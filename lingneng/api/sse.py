from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel


def _jsonable(data: Any) -> Any:
    if isinstance(data, BaseModel):
        return data.model_dump(mode="json")
    return data


def _validate_event_name(event_name: str) -> None:
    if "\r" in event_name or "\n" in event_name:
        raise ValueError("SSE event name must not contain CR or LF")


def encode_sse(event_name: str, data: Any) -> str:
    _validate_event_name(event_name)
    payload = json.dumps(_jsonable(data), ensure_ascii=False)
    return f"event: {event_name}\ndata: {payload}\n\n"


def heartbeat_frame() -> str:
    return ": ping\n\n"


async def with_heartbeats(
    source: AsyncIterator[str],
    interval_seconds: float,
) -> AsyncIterator[str]:
    if interval_seconds <= 0:
        raise ValueError("heartbeat interval_seconds must be positive")

    iterator = source.__aiter__()
    pending = asyncio.create_task(anext(iterator))
    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=interval_seconds)
            if not done:
                yield heartbeat_frame()
                continue

            try:
                frame = pending.result()
            except StopAsyncIteration:
                return

            yield frame
            pending = asyncio.create_task(anext(iterator))
    finally:
        if not pending.done():
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pending
        aclose = getattr(iterator, "aclose", None)
        if aclose is not None:
            await aclose()
