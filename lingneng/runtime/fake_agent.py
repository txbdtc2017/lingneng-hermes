from __future__ import annotations

from collections.abc import AsyncIterator

from lingneng.events.bridge import answer_delta, final_answer, run_started
from lingneng.runtime.agent_adapter import LingNengStreamEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import ResolvedSessionKey


class FakeAgentRunAdapter:
    def __init__(
        self,
        answer: str = "这是灵能 Hermes Phase 1 fake 回复。",
        chunk_size: int = 8,
    ) -> None:
        if not isinstance(chunk_size, int) or chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")
        self.answer = answer
        self.chunk_size = chunk_size

    async def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[LingNengStreamEvent]:
        yield run_started(run_id=run_id, request_id=request.request_id)

        sequence = 1
        for start in range(0, len(self.answer), self.chunk_size):
            yield answer_delta(
                text=self.answer[start : start + self.chunk_size],
                sequence=sequence,
            )
            sequence += 1

        yield final_answer(run_id=run_id, answer=self.answer)
