from __future__ import annotations

from typing import Any

from hermes_state import SessionDB

from lingneng.config.settings import LingNengSettings
from lingneng.session.keys import ResolvedSessionKey


class LingNengHermesSessionStore:
    def __init__(
        self,
        settings: LingNengSettings,
        db: SessionDB | None = None,
    ) -> None:
        self.settings = settings
        self.db = db or SessionDB(db_path=settings.session_db_path)

    def ensure_session(self, resolved: ResolvedSessionKey) -> str:
        return self.db.ensure_session(
            resolved.session_key,
            source="lingneng",
            user_id=resolved.user_id,
        )

    def load_conversation_history(
        self,
        resolved: ResolvedSessionKey,
    ) -> list[dict[str, Any]]:
        rows = self.db.get_messages(resolved.session_key)
        history: list[dict[str, Any]] = []
        for row in rows:
            message = self._row_to_message(row)
            if message is not None:
                history.append(message)
        return history

    def _row_to_message(self, row: dict[str, Any]) -> dict[str, Any] | None:
        role = row.get("role")
        if role not in {"user", "assistant", "tool"}:
            return None

        message: dict[str, Any] = {"role": role, "content": row.get("content")}
        for key in ("tool_call_id", "tool_calls", "tool_name", "finish_reason"):
            value = row.get(key)
            if value is not None:
                message[key] = value
        return message
