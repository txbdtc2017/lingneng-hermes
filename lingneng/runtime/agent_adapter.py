from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, Union

from lingneng.schemas.chat_events import (
    AnswerDeltaEvent,
    ErrorEvent,
    FinalEvent,
    RunStartedEvent,
)
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import ResolvedSessionKey


LingNengStreamEvent = Union[
    RunStartedEvent,
    AnswerDeltaEvent,
    FinalEvent,
    ErrorEvent,
]


class AgentRunAdapter(Protocol):
    def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[LingNengStreamEvent]:
        ...
