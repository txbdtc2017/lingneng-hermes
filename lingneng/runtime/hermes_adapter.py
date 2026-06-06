from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from run_agent import AIAgent

from lingneng.config.settings import LingNengSettings
from lingneng.events.bridge import answer_delta, final_answer, run_started
from lingneng.runtime.agent_adapter import LingNengStreamEvent
from lingneng.schemas.chat_events import AnswerDeltaEvent, ErrorEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.hermes_session import LingNengHermesSessionStore
from lingneng.session.keys import ResolvedSessionKey


@dataclass(frozen=True)
class _ThreadResult:
    final_response: str = ""
    error: BaseException | None = None


class HermesAgentRunAdapter:
    def __init__(
        self,
        settings: LingNengSettings,
        agent_cls: type = AIAgent,
        session_store: LingNengHermesSessionStore | None = None,
    ) -> None:
        self.settings = settings
        self.agent_cls = agent_cls
        self.session_store = session_store or LingNengHermesSessionStore(settings)
        self._last_agent_for_tests: Any | None = None

    async def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[LingNengStreamEvent]:
        yield run_started(run_id=run_id, request_id=request.request_id)

        queue: asyncio.Queue[AnswerDeltaEvent | _ThreadResult] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        sequence = 0
        streamed_text: list[str] = []

        def on_delta(text: str | None) -> None:
            nonlocal sequence
            if not text:
                return
            sequence += 1
            streamed_text.append(text)
            loop.call_soon_threadsafe(
                queue.put_nowait,
                answer_delta(text=text, sequence=sequence),
            )

        def run_agent() -> _ThreadResult:
            try:
                history = self.session_store.load_conversation_history(
                    resolved_session
                )
                agent = self._build_agent(
                    resolved_session,
                    stream_delta_callback=on_delta,
                )
                self._last_agent_for_tests = agent
                result = agent.run_conversation(
                    request.query.content,
                    system_message=request.system_prompt.content,
                    conversation_history=history,
                    task_id=run_id,
                    persist_user_message=request.query.content,
                )
                return _ThreadResult(
                    final_response=_final_response_from_result(result)
                )
            except BaseException as exc:
                return _ThreadResult(error=exc)

        task = asyncio.create_task(asyncio.to_thread(run_agent))

        while True:
            if task.done() and queue.empty():
                result = task.result()
                if result.error is not None:
                    yield _public_runtime_error(run_id, request.request_id)
                    return
                final_text = result.final_response
                if not streamed_text and final_text:
                    sequence += 1
                    yield answer_delta(text=final_text, sequence=sequence)
                yield final_answer(run_id=run_id, answer=final_text)
                return

            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.05)
            except asyncio.TimeoutError:
                continue
            yield item

    def _build_agent(
        self,
        resolved_session: ResolvedSessionKey,
        stream_delta_callback=None,
    ):
        return self.agent_cls(
            platform="lingneng",
            session_id=resolved_session.session_key,
            session_db=self.session_store.db,
            enabled_toolsets=[],
            disabled_toolsets=["kanban"],
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            stream_delta_callback=stream_delta_callback,
        )


def _final_response_from_result(result: Any) -> str:
    if isinstance(result, dict):
        value = result.get("final_response")
        return value if isinstance(value, str) else ""
    return ""


def _public_runtime_error(run_id: str, request_id: str) -> ErrorEvent:
    return ErrorEvent(
        run_id=run_id,
        request_id=request_id,
        code="RUNTIME_ERROR",
        message="Agent runtime failed",
        trace_id=f"trace_{uuid.uuid4().hex}",
        recoverable=False,
    )
