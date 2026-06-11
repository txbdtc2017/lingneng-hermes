import sqlite3
from datetime import timedelta

from lingneng.routing.store import LingNengRoutePendingStore, PendingRouteConfirmation
from lingneng.schemas.chat_events import RouteCandidate


def pending():
    return PendingRouteConfirmation(
        tenant_id="tenant-a",
        user_id="user-a",
        conversation_id="conv-a",
        request_id="req-1",
        query_message_id="msg-1",
        current_employee_type="marketing_planner",
        previous_user_query="做一个营销活动",
        clarification_question="请选择营销策划还是内容创作。",
        candidates=[
            RouteCandidate(
                employee_type="marketing_planner",
                confidence=0.6,
                label="营销策划",
                reason="活动方案",
            ),
            RouteCandidate(
                employee_type="marketing_content_creator",
                confidence=0.55,
                label="营销内容创作",
                reason="文案内容",
            ),
        ],
    )


def test_pending_store_saves_finds_and_consumes(tmp_path):
    store = LingNengRoutePendingStore(tmp_path / "route.sqlite3", ttl_seconds=600)
    record = store.save(pending())

    latest = store.latest(
        tenant_id="tenant-a",
        user_id="user-a",
        conversation_id="conv-a",
        current_employee_type="marketing_planner",
    )
    by_message = store.find_by_message_id(
        tenant_id="tenant-a",
        user_id="user-a",
        conversation_id="conv-a",
        current_employee_type="marketing_planner",
        query_message_id="msg-1",
    )

    assert latest is not None
    assert by_message is not None
    assert latest.request_id == "req-1"
    assert by_message.candidates[1].employee_type == "marketing_content_creator"
    consumed = store.consume(record.pending_id)
    assert consumed is not None
    assert store.consume(record.pending_id) is None


def test_pending_store_consume_returns_none_when_interleaved_consumer_wins(
    tmp_path,
    monkeypatch,
):
    store = LingNengRoutePendingStore(tmp_path / "route.sqlite3", ttl_seconds=600)
    record = store.save(pending())
    consumed_at = "2026-06-11T00:00:00+00:00"
    real_connect = store._connect

    class InterleavedConnection:
        def __init__(self):
            self.conn = real_connect()
            self.interleaved = False

        def __enter__(self):
            self.conn.__enter__()
            return self

        def __exit__(self, exc_type, exc, tb):
            return self.conn.__exit__(exc_type, exc, tb)

        def execute(self, sql, params=()):
            normalized = " ".join(sql.split()).upper()
            if (
                not self.interleaved
                and normalized.startswith("UPDATE LINGNENG_ROUTE_PENDING")
                and "SET CONSUMED_AT" in normalized
            ):
                self.interleaved = True
                self.conn.execute(
                    """
                    UPDATE lingneng_route_pending
                    SET consumed_at = ?
                    WHERE pending_id = ?
                    """,
                    (consumed_at, record.pending_id),
                )
            return self.conn.execute(sql, params)

    monkeypatch.setattr(store, "_connect", InterleavedConnection)

    assert store.consume(record.pending_id) is None

    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT consumed_at FROM lingneng_route_pending WHERE pending_id = ?",
            (record.pending_id,),
        ).fetchone()
    assert row[0] == consumed_at


def test_pending_store_ignores_expired_records(tmp_path):
    store = LingNengRoutePendingStore(tmp_path / "route.sqlite3", ttl_seconds=1)
    record = store.save(pending())
    store.force_update_expires_at(record.pending_id, delta=timedelta(seconds=-5))

    assert (
        store.latest(
            tenant_id="tenant-a",
            user_id="user-a",
            conversation_id="conv-a",
            current_employee_type="marketing_planner",
        )
        is None
    )
    assert store.cleanup_expired() == 1
