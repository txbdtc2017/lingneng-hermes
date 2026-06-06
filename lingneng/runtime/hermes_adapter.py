from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from run_agent import AIAgent

from lingneng.config.settings import LingNengSettings
from lingneng.events.bridge import answer_delta, final_answer, run_started
from lingneng.runtime.agent_adapter import LingNengStreamEvent
from lingneng.schemas.chat_events import ErrorEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.hermes_session import LingNengHermesSessionStore
from lingneng.session.keys import ResolvedSessionKey


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

        try:
            history = self.session_store.load_conversation_history(resolved_session)
            agent = self._build_agent(resolved_session)
            self._last_agent_for_tests = agent
            result = agent.run_conversation(
                request.query.content,
                system_message=request.system_prompt.content,
                conversation_history=history,
                task_id=run_id,
                persist_user_message=request.query.content,
            )
            final_text = _final_response_from_result(result)
            if final_text:
                yield answer_delta(text=final_text, sequence=1)
            yield final_answer(run_id=run_id, answer=final_text)
        except Exception:
            yield _public_runtime_error(run_id, request.request_id)

    def _build_agent(self, resolved_session: ResolvedSessionKey):
        return self.agent_cls(
            platform="lingneng",
            session_id=resolved_session.session_key,
            session_db=self.session_store.db,
            enabled_toolsets=[],
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
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
