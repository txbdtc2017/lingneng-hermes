from __future__ import annotations

from collections.abc import AsyncIterator

from lingneng.config.settings import LingNengSettings
from lingneng.runtime.agent_adapter import LingNengStreamEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import ResolvedSessionKey


class HermesAgentRunAdapter:
    def __init__(self, settings: LingNengSettings, **_kwargs: object) -> None:
        self.settings = settings

    def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[LingNengStreamEvent]:
        raise RuntimeError("Hermes adapter is not configured")
