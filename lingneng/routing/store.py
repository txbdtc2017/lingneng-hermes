from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, model_validator

from lingneng.schemas.chat_events import RouteCandidate
from lingneng.schemas.chat_request import EmployeeType


class PendingRouteConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    user_id: str
    conversation_id: str
    request_id: str
    query_message_id: str | None = None
    current_employee_type: EmployeeType
    previous_user_query: str
    clarification_question: str
    candidates: list[RouteCandidate]

    @model_validator(mode="after")
    def _validate_candidates(self) -> "PendingRouteConfirmation":
        employee_types = [candidate.employee_type for candidate in self.candidates]
        if len(employee_types) < 2 or len(employee_types) > 4:
            raise ValueError("pending route confirmation requires 2 to 4 candidates")
        if len(employee_types) != len(set(employee_types)):
            raise ValueError("pending route candidates must have unique employee types")
        return self


class PendingRouteConfirmationRecord(PendingRouteConfirmation):
    pending_id: str
    created_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None


class LingNengRoutePendingStore:
    def __init__(self, db_path: str | Path, ttl_seconds: int) -> None:
        self.db_path = Path(db_path)
        self.ttl = timedelta(seconds=ttl_seconds)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def save(
        self,
        pending: PendingRouteConfirmation,
    ) -> PendingRouteConfirmationRecord:
        now = _utc_now()
        record = PendingRouteConfirmationRecord(
            pending_id=f"route_pending_{uuid4().hex}",
            created_at=now,
            expires_at=now + self.ttl,
            consumed_at=None,
            **pending.model_dump(),
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO lingneng_route_pending (
                    pending_id,
                    tenant_id,
                    user_id,
                    conversation_id,
                    request_id,
                    query_message_id,
                    current_employee_type,
                    previous_user_query,
                    clarification_question,
                    candidates_json,
                    created_at,
                    expires_at,
                    consumed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _record_values(record),
            )
        return record

    def latest(
        self,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
        current_employee_type: EmployeeType | str,
    ) -> PendingRouteConfirmationRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM lingneng_route_pending
                WHERE tenant_id = ?
                  AND user_id = ?
                  AND conversation_id = ?
                  AND current_employee_type = ?
                  AND consumed_at IS NULL
                  AND expires_at > ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (
                    tenant_id,
                    user_id,
                    conversation_id,
                    EmployeeType(current_employee_type).value,
                    _to_iso(_utc_now()),
                ),
            ).fetchone()
        return _record_from_row(row)

    def find_by_message_id(
        self,
        tenant_id: str,
        user_id: str,
        conversation_id: str,
        current_employee_type: EmployeeType | str,
        query_message_id: str | None,
    ) -> PendingRouteConfirmationRecord | None:
        message_filter = (
            "query_message_id IS NULL"
            if query_message_id is None
            else "query_message_id = ?"
        )
        params: list[Any] = [
            tenant_id,
            user_id,
            conversation_id,
            EmployeeType(current_employee_type).value,
        ]
        if query_message_id is not None:
            params.append(query_message_id)
        params.append(_to_iso(_utc_now()))

        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT * FROM lingneng_route_pending
                WHERE tenant_id = ?
                  AND user_id = ?
                  AND conversation_id = ?
                  AND current_employee_type = ?
                  AND {message_filter}
                  AND consumed_at IS NULL
                  AND expires_at > ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
        return _record_from_row(row)

    def consume(self, pending_id: str) -> PendingRouteConfirmationRecord | None:
        now_iso = _to_iso(_utc_now())
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE lingneng_route_pending
                SET consumed_at = ?
                WHERE pending_id = ?
                  AND consumed_at IS NULL
                  AND expires_at > ?
                """,
                (now_iso, pending_id, now_iso),
            )
            if cursor.rowcount != 1:
                return None
            consumed = conn.execute(
                "SELECT * FROM lingneng_route_pending WHERE pending_id = ?",
                (pending_id,),
            ).fetchone()
        return _record_from_row(consumed)

    def cleanup_expired(self) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM lingneng_route_pending WHERE expires_at <= ?",
                (_to_iso(_utc_now()),),
            )
        return cursor.rowcount

    def force_update_expires_at(self, pending_id: str, delta: timedelta) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT expires_at FROM lingneng_route_pending WHERE pending_id = ?",
                (pending_id,),
            ).fetchone()
            if row is None:
                return
            expires_at = _from_iso(row["expires_at"]) + delta
            conn.execute(
                "UPDATE lingneng_route_pending SET expires_at = ? WHERE pending_id = ?",
                (_to_iso(expires_at), pending_id),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lingneng_route_pending (
                    pending_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    query_message_id TEXT,
                    current_employee_type TEXT NOT NULL,
                    previous_user_query TEXT NOT NULL,
                    clarification_question TEXT NOT NULL,
                    candidates_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT
                )
                """
            )


def _record_values(record: PendingRouteConfirmationRecord) -> tuple[Any, ...]:
    return (
        record.pending_id,
        record.tenant_id,
        record.user_id,
        record.conversation_id,
        record.request_id,
        record.query_message_id,
        record.current_employee_type.value,
        record.previous_user_query,
        record.clarification_question,
        json.dumps(
            [candidate.model_dump(mode="json") for candidate in record.candidates],
            ensure_ascii=False,
        ),
        _to_iso(record.created_at),
        _to_iso(record.expires_at),
        _to_iso(record.consumed_at) if record.consumed_at is not None else None,
    )


def _record_from_row(
    row: sqlite3.Row | None,
) -> PendingRouteConfirmationRecord | None:
    if row is None:
        return None
    return PendingRouteConfirmationRecord(
        pending_id=row["pending_id"],
        tenant_id=row["tenant_id"],
        user_id=row["user_id"],
        conversation_id=row["conversation_id"],
        request_id=row["request_id"],
        query_message_id=row["query_message_id"],
        current_employee_type=row["current_employee_type"],
        previous_user_query=row["previous_user_query"],
        clarification_question=row["clarification_question"],
        candidates=[
            RouteCandidate.model_validate(candidate)
            for candidate in json.loads(row["candidates_json"])
        ],
        created_at=_from_iso(row["created_at"]),
        expires_at=_from_iso(row["expires_at"]),
        consumed_at=_from_iso(row["consumed_at"])
        if row["consumed_at"] is not None
        else None,
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _from_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
