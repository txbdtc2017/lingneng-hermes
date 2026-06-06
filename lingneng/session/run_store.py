from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RunStoreStateError(RuntimeError):
    """Raised when a run is missing or cannot change state."""


@dataclass(frozen=True)
class RunRecord:
    session_key: str
    request_id: str
    run_id: str
    status: RunStatus
    answer: str | None
    error_code: str | None
    error_message: str | None
    citations: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True)
class ReserveRunResult:
    created: bool
    record: RunRecord


class LingNengRunStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def reserve_run(self, session_key: str, request_id: str) -> ReserveRunResult:
        now = _now()
        run_id = f"run_{uuid.uuid4().hex}"
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO lingneng_runs (
                    session_key,
                    request_id,
                    run_id,
                    status,
                    artifacts_json,
                    citations_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_key, request_id) DO NOTHING
                """,
                (
                    session_key,
                    request_id,
                    run_id,
                    RunStatus.RUNNING.value,
                    "[]",
                    "[]",
                    _to_db_time(now),
                    _to_db_time(now),
                ),
            )
            row = conn.execute(
                """
                SELECT *
                FROM lingneng_runs
                WHERE session_key = ? AND request_id = ?
                """,
                (session_key, request_id),
            ).fetchone()

        return ReserveRunResult(
            created=cursor.rowcount == 1,
            record=_record_from_row(row),
        )

    def mark_succeeded(
        self,
        run_id: str,
        answer: str,
        artifacts: list[dict[str, Any]] | None = None,
        citations: list[Any] | None = None,
    ) -> None:
        now = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE lingneng_runs
                SET status = ?,
                    answer = ?,
                    error_code = NULL,
                    error_message = NULL,
                    artifacts_json = ?,
                    citations_json = ?,
                    updated_at = ?,
                    completed_at = ?
                WHERE run_id = ?
                  AND status = ?
                """,
                (
                    RunStatus.SUCCEEDED.value,
                    answer,
                    _dump_json_list(artifacts),
                    _dump_json_list(citations),
                    _to_db_time(now),
                    _to_db_time(now),
                    run_id,
                    RunStatus.RUNNING.value,
                ),
            )
            if cursor.rowcount != 1:
                self._raise_state_error(conn, run_id)

    def mark_failed(self, run_id: str, error_code: str, error_message: str) -> None:
        now = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE lingneng_runs
                SET status = ?,
                    answer = NULL,
                    error_code = ?,
                    error_message = ?,
                    artifacts_json = ?,
                    citations_json = ?,
                    updated_at = ?,
                    completed_at = ?
                WHERE run_id = ?
                  AND status = ?
                """,
                (
                    RunStatus.FAILED.value,
                    error_code,
                    error_message,
                    "[]",
                    "[]",
                    _to_db_time(now),
                    _to_db_time(now),
                    run_id,
                    RunStatus.RUNNING.value,
                ),
            )
            if cursor.rowcount != 1:
                self._raise_state_error(conn, run_id)

    def get_by_run_id(self, run_id: str) -> RunRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM lingneng_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return _record_from_row(row)

    def count_runs(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM lingneng_runs"
            ).fetchone()
        return int(row["count"])

    def cleanup_older_than(self, days: int) -> int:
        cutoff = _now() - timedelta(days=days)
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM lingneng_runs WHERE created_at < ?",
                (_to_db_time(cutoff),),
            )
            return cursor.rowcount

    def force_update_created_at(self, run_id: str, created_at: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE lingneng_runs SET created_at = ? WHERE run_id = ?",
                (_to_db_time(created_at), run_id),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lingneng_runs (
                    session_key TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    run_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    answer TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    artifacts_json TEXT NOT NULL DEFAULT '[]',
                    citations_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    PRIMARY KEY (session_key, request_id)
                )
                """
            )
            columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(lingneng_runs)")
            }
            if "citations_json" not in columns:
                conn.execute(
                    "ALTER TABLE lingneng_runs "
                    "ADD COLUMN citations_json TEXT NOT NULL DEFAULT '[]'"
                )

    def _raise_state_error(self, conn: sqlite3.Connection, run_id: str) -> None:
        row = conn.execute(
            "SELECT status FROM lingneng_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise RunStoreStateError(f"run_id {run_id!r} is missing")
        status = RunStatus(row["status"])
        raise RunStoreStateError(
            f"invalid transition for run_id {run_id!r}: "
            f"{status.value} cannot be changed"
        )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_db_time(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("run store datetimes must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _from_db_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _from_optional_db_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    return _from_db_time(value)


def _record_from_row(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        session_key=row["session_key"],
        request_id=row["request_id"],
        run_id=row["run_id"],
        status=RunStatus(row["status"]),
        answer=row["answer"],
        error_code=row["error_code"],
        error_message=row["error_message"],
        citations=_dict_list_from_json(row["citations_json"]),
        artifacts=_dict_list_from_json(row["artifacts_json"]),
        created_at=_from_db_time(row["created_at"]),
        updated_at=_from_db_time(row["updated_at"]),
        completed_at=_from_optional_db_time(row["completed_at"]),
    )


def _dump_json_list(value: list[Any] | None) -> str:
    return json.dumps(_jsonable(value or []), ensure_ascii=False)


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    return value


def _dict_list_from_json(value: str | None) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]
