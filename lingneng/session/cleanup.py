from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from hermes_state import SessionDB

from lingneng.config.settings import LingNengSettings
from lingneng.session.run_store import LingNengRunStore


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LingNengCleanupResult:
    non_archived_sessions_pruned: int
    archived_sessions_pruned: int
    run_records_pruned: int
    session_retention_days: int
    archived_session_retention_days: int
    idempotency_retention_days: int
    session_cutoff_at: datetime
    archived_session_cutoff_at: datetime
    idempotency_cutoff_at: datetime

    @property
    def session_records_pruned(self) -> int:
        return self.non_archived_sessions_pruned + self.archived_sessions_pruned


def run_lingneng_cleanup(
    settings: LingNengSettings,
    *,
    session_db: SessionDB | None = None,
    run_store: LingNengRunStore | None = None,
    logger: logging.Logger | None = None,
) -> LingNengCleanupResult:
    """Prune stale LingNeng sessions and idempotency records.

    This is a library boundary only. It deliberately has no scheduler, CLI,
    startup hook, deployment hook, or Java-facing session deletion endpoint.
    """

    cleanup_logger = logger or globals()["logger"]
    resolved_session_db = session_db or SessionDB(settings.session_db_path)
    resolved_run_store = run_store or LingNengRunStore(
        settings.runtime_dir / "runs.sqlite3",
        settings=settings,
    )
    now = datetime.now(timezone.utc)
    session_cutoff_at = now - timedelta(days=settings.session_retention_days)
    archived_session_cutoff_at = now - timedelta(
        days=settings.archived_session_retention_days
    )
    idempotency_cutoff_at = now - timedelta(days=settings.idempotency_retention_days)

    non_archived_session_ids = _select_stale_lingneng_session_ids(
        resolved_session_db,
        archived=False,
        cutoff_at=session_cutoff_at,
    )
    archived_session_ids = _select_stale_lingneng_session_ids(
        resolved_session_db,
        archived=True,
        cutoff_at=archived_session_cutoff_at,
    )
    prunable_session_ids = set(non_archived_session_ids) | set(archived_session_ids)
    protected_session_ids = _compression_ancestors_with_retained_descendants(
        resolved_session_db,
        prunable_session_ids,
    )
    if protected_session_ids:
        non_archived_session_ids = [
            session_id
            for session_id in non_archived_session_ids
            if session_id not in protected_session_ids
        ]
        archived_session_ids = [
            session_id
            for session_id in archived_session_ids
            if session_id not in protected_session_ids
        ]

    non_archived_sessions_pruned = resolved_session_db.delete_sessions(
        non_archived_session_ids
    )
    archived_sessions_pruned = resolved_session_db.delete_sessions(archived_session_ids)
    run_records_pruned = resolved_run_store.cleanup_older_than(
        settings.idempotency_retention_days
    )

    result = LingNengCleanupResult(
        non_archived_sessions_pruned=non_archived_sessions_pruned,
        archived_sessions_pruned=archived_sessions_pruned,
        run_records_pruned=run_records_pruned,
        session_retention_days=settings.session_retention_days,
        archived_session_retention_days=settings.archived_session_retention_days,
        idempotency_retention_days=settings.idempotency_retention_days,
        session_cutoff_at=session_cutoff_at,
        archived_session_cutoff_at=archived_session_cutoff_at,
        idempotency_cutoff_at=idempotency_cutoff_at,
    )
    _log_cleanup_result(cleanup_logger, result)
    return result


def _select_stale_lingneng_session_ids(
    session_db: SessionDB,
    *,
    archived: bool,
    cutoff_at: datetime,
) -> list[str]:
    cutoff_timestamp = cutoff_at.timestamp()
    with session_db._lock:
        rows = session_db._conn.execute(
            """
            SELECT id
            FROM sessions
            WHERE source = ?
              AND archived = ?
              AND ended_at IS NOT NULL
              AND ended_at < ?
            ORDER BY ended_at, id
            """,
            ("lingneng", 1 if archived else 0, cutoff_timestamp),
        ).fetchall()
    return [row["id"] for row in rows]


def _compression_ancestors_with_retained_descendants(
    session_db: SessionDB,
    candidate_ids: set[str],
) -> set[str]:
    if not candidate_ids:
        return set()

    candidate_values = list(candidate_ids)
    candidate_placeholders = ",".join("?" for _ in candidate_values)
    with session_db._lock:
        rows = session_db._conn.execute(
            f"""
            WITH RECURSIVE compression_edges(parent_id, child_id) AS (
                SELECT parent.id, child.id
                FROM sessions AS parent
                JOIN sessions AS child ON child.parent_session_id = parent.id
                WHERE parent.end_reason = 'compression'
                  AND parent.ended_at IS NOT NULL
                  AND child.started_at >= parent.ended_at
                UNION ALL
                SELECT edge.parent_id, child.id
                FROM compression_edges AS edge
                JOIN sessions AS current_child ON current_child.id = edge.child_id
                JOIN sessions AS child ON child.parent_session_id = current_child.id
                WHERE current_child.end_reason = 'compression'
                  AND current_child.ended_at IS NOT NULL
                  AND child.started_at >= current_child.ended_at
            )
            SELECT DISTINCT parent_id
            FROM compression_edges
            WHERE parent_id IN ({candidate_placeholders})
              AND child_id NOT IN ({candidate_placeholders})
            """,
            [*candidate_values, *candidate_values],
        ).fetchall()
    return {row["parent_id"] for row in rows}


def _log_cleanup_result(
    cleanup_logger: logging.Logger,
    result: LingNengCleanupResult,
) -> None:
    cleanup_logger.info(
        "LingNeng cleanup completed",
        extra={
            "event_name": "lingneng_cleanup_completed",
            "non_archived_sessions_pruned": result.non_archived_sessions_pruned,
            "archived_sessions_pruned": result.archived_sessions_pruned,
            "session_records_pruned": result.session_records_pruned,
            "run_records_pruned": result.run_records_pruned,
            "session_retention_days": result.session_retention_days,
            "archived_session_retention_days": (
                result.archived_session_retention_days
            ),
            "idempotency_retention_days": result.idempotency_retention_days,
            "session_cutoff_at": result.session_cutoff_at.isoformat(),
            "archived_session_cutoff_at": (
                result.archived_session_cutoff_at.isoformat()
            ),
            "idempotency_cutoff_at": result.idempotency_cutoff_at.isoformat(),
        },
    )
