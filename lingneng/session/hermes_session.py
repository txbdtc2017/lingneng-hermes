from __future__ import annotations

import logging
from typing import Any

from hermes_state import SessionDB

from lingneng.config.settings import LingNengSettings
from lingneng.session.keys import ResolvedSessionKey


logger = logging.getLogger(__name__)


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

    def resolve_active_session_id(self, resolved: ResolvedSessionKey | str) -> str:
        if isinstance(resolved, ResolvedSessionKey):
            root_session_id = resolved.session_key
        else:
            root_session_id = resolved

        try:
            compression_tip = self.db.get_compression_tip(root_session_id)
        except Exception as exc:
            logger.warning(
                "LingNeng active session lookup failed",
                extra={
                    "lookup_stage": "compression_tip",
                    "error_type": exc.__class__.__name__,
                },
            )
            compression_tip = None
        if compression_tip and compression_tip != root_session_id:
            return compression_tip

        if not self._is_compression_root(root_session_id):
            return root_session_id

        try:
            resume_session_id = self.db.resolve_resume_session_id(root_session_id)
        except Exception as exc:
            logger.warning(
                "LingNeng active session lookup failed",
                extra={
                    "lookup_stage": "resume_session",
                    "error_type": exc.__class__.__name__,
                },
            )
            resume_session_id = None
        if resume_session_id and resume_session_id != root_session_id:
            if self._is_compression_descendant(
                root_session_id,
                resume_session_id,
            ):
                return resume_session_id

        return root_session_id

    def _is_compression_root(self, session_id: str) -> bool:
        try:
            with self.db._lock:
                row = self.db._conn.execute(
                    "SELECT end_reason FROM sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
        except Exception as exc:
            logger.warning(
                "LingNeng active session lookup failed",
                extra={
                    "lookup_stage": "compression_root",
                    "error_type": exc.__class__.__name__,
                },
            )
            return False
        if row is None:
            return False
        return row["end_reason"] == "compression"

    def _is_compression_descendant(self, root_session_id: str, candidate_id: str) -> bool:
        if not root_session_id or not candidate_id or candidate_id == root_session_id:
            return False

        current = candidate_id
        seen = {candidate_id}
        for _ in range(100):
            try:
                with self.db._lock:
                    child_row = self.db._conn.execute(
                        "SELECT parent_session_id, started_at "
                        "FROM sessions WHERE id = ?",
                        (current,),
                    ).fetchone()
                    if child_row is None:
                        return False
                    parent_id = child_row["parent_session_id"]
                    if not parent_id:
                        return False
                    parent_row = self.db._conn.execute(
                        "SELECT parent_session_id, ended_at, end_reason "
                        "FROM sessions WHERE id = ?",
                        (parent_id,),
                    ).fetchone()
            except Exception as exc:
                logger.warning(
                    "LingNeng active session lookup failed",
                    extra={
                        "lookup_stage": "compression_descendant",
                        "error_type": exc.__class__.__name__,
                    },
                )
                return False

            if parent_row is None:
                return False
            if parent_row["end_reason"] != "compression":
                return False
            if parent_row["ended_at"] is None:
                return False
            if child_row["started_at"] < parent_row["ended_at"]:
                return False
            if parent_id == root_session_id:
                return True
            if parent_id in seen:
                return False
            seen.add(parent_id)
            current = parent_id
        return False

    def load_conversation_history(
        self,
        resolved: ResolvedSessionKey,
    ) -> list[dict[str, Any]]:
        active_session_id = self.resolve_active_session_id(resolved)
        return self.load_conversation_history_for_session_id(active_session_id)

    def load_conversation_history_for_session_id(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]:
        rows = self.db.get_messages(session_id)
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
