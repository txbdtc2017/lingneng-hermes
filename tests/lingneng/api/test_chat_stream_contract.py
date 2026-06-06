import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from lingneng.api.app import create_app
from lingneng.api.routes import _adapter_stream
from lingneng.api.sse import with_heartbeats
from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_events import (
    AnswerDeltaEvent,
    ErrorEvent,
    FinalEvent,
    RunStartedEvent,
)
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import ResolvedSessionKey, resolve_session_key
from lingneng.session.run_store import LingNengRunStore, RunStatus
from tests.lingneng.schemas.test_chat_request_schema import full_payload


INTERNAL_KEY = "valid-internal-key"
SENSITIVE_INPUT_VALUE = "sensitive-field-value-8b2f5bd5"


def settings(tmp_path, **overrides) -> LingNengSettings:
    values = {
        "LINGNENG_APP_ENV": "test",
        "LINGNENG_RUNTIME_DIR": str(tmp_path),
        "LINGNENG_INTERNAL_API_KEY": INTERNAL_KEY,
    }
    values.update(overrides)
    return LingNengSettings.from_env(values)


def client(tmp_path, **settings_overrides) -> TestClient:
    app = create_app(
        settings=settings(tmp_path, **settings_overrides),
        run_store=LingNengRunStore(tmp_path / "runs.sqlite3"),
    )
    return TestClient(app)


def post_stream(app_client: TestClient, payload: dict, key: str = INTERNAL_KEY):
    return app_client.post(
        "/internal/agent/chat/stream",
        json=payload,
        headers={"X-Internal-Key": key},
    )


def parse_sse(text: str) -> list[tuple[str, dict]]:
    frames = []
    for raw_frame in text.strip().split("\n\n"):
        lines = raw_frame.splitlines()
        if not lines or lines[0].startswith(":"):
            continue
        event_line = next(line for line in lines if line.startswith("event: "))
        data_line = next(line for line in lines if line.startswith("data: "))
        frames.append(
            (
                event_line.removeprefix("event: "),
                json.loads(data_line.removeprefix("data: ")),
            )
        )
    return frames


def test_health_returns_ok(tmp_path):
    response = client(tmp_path).get("/internal/agent/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_non_secret_summary(tmp_path):
    response = client(tmp_path).get("/internal/agent/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["app_env"] == "test"
    assert body["agent_mode"] == "fake"
    assert body["auth_required"] is True
    assert "internal_api_key" not in body
    assert INTERNAL_KEY not in repr(body)


def test_ready_reports_local_insecure_empty_key_state(tmp_path):
    insecure_blocked = client(
        tmp_path,
        LINGNENG_INTERNAL_API_KEY="",
        LINGNENG_ALLOW_INSECURE_LOCAL="false",
    ).get("/internal/agent/ready")
    insecure_allowed = client(
        tmp_path,
        LINGNENG_INTERNAL_API_KEY="",
        LINGNENG_ALLOW_INSECURE_LOCAL="true",
    ).get("/internal/agent/ready")

    assert insecure_blocked.status_code == 200
    assert insecure_blocked.json()["status"] == "not_ready"
    assert insecure_allowed.status_code == 200
    assert insecure_allowed.json()["status"] == "ready"


def test_ready_is_not_ready_for_production_like_empty_key(tmp_path):
    response = client(
        tmp_path,
        LINGNENG_APP_ENV="prod",
        LINGNENG_INTERNAL_API_KEY="",
    ).get("/internal/agent/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_ready"
    assert "internal_api_key" not in body


def test_chat_stream_success_returns_sse_with_minimum_event_order(tmp_path):
    response = post_stream(client(tmp_path), full_payload())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = parse_sse(response.text)
    event_names = [event_name for event_name, _data in frames]
    deltas = [
        data["text"] for event_name, data in frames if event_name == "answer_delta"
    ]
    final_payload = frames[-1][1]

    assert event_names[0] == "run_started"
    assert "answer_delta" in event_names
    assert event_names[-1] == "final"
    assert "".join(deltas) == final_payload["answer"]


def test_missing_or_invalid_key_returns_non_sse_401(tmp_path):
    app_client = client(tmp_path)

    missing = app_client.post("/internal/agent/chat/stream", json=full_payload())
    invalid = post_stream(app_client, full_payload(), key="wrong")

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert "text/event-stream" not in missing.headers.get("content-type", "")
    assert "text/event-stream" not in invalid.headers.get("content-type", "")


def test_missing_key_with_malformed_body_returns_non_sse_401(tmp_path):
    response = client(tmp_path).post(
        "/internal/agent/chat/stream",
        json={"sensitive": SENSITIVE_INPUT_VALUE},
    )

    assert response.status_code == 401
    assert "text/event-stream" not in response.headers.get("content-type", "")
    assert SENSITIVE_INPUT_VALUE not in response.text


def test_invalid_key_with_malformed_body_returns_non_sse_401(tmp_path):
    response = post_stream(
        client(tmp_path),
        {"sensitive": SENSITIVE_INPUT_VALUE},
        key="wrong",
    )

    assert response.status_code == 401
    assert "text/event-stream" not in response.headers.get("content-type", "")
    assert SENSITIVE_INPUT_VALUE not in response.text


def test_valid_key_with_malformed_body_returns_non_sse_422_without_input_echo(
    tmp_path,
):
    response = post_stream(
        client(tmp_path),
        {"sensitive": SENSITIVE_INPUT_VALUE},
    )

    assert response.status_code == 422
    assert "text/event-stream" not in response.headers.get("content-type", "")
    assert response.json() == {"detail": "Invalid chat request"}
    assert SENSITIVE_INPUT_VALUE not in response.text


def test_valid_key_with_invalid_json_returns_non_sse_422_without_body_echo(tmp_path):
    response = client(tmp_path).post(
        "/internal/agent/chat/stream",
        content=f'{{"sensitive": "{SENSITIVE_INPUT_VALUE}"',
        headers={
            "Content-Type": "application/json",
            "X-Internal-Key": INTERNAL_KEY,
        },
    )

    assert response.status_code == 422
    assert "text/event-stream" not in response.headers.get("content-type", "")
    assert response.json() == {"detail": "Invalid chat request"}
    assert SENSITIVE_INPUT_VALUE not in response.text


def test_invalid_session_key_segment_returns_non_sse_422_without_adapter(tmp_path):
    adapter = CountingFinalAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    app = create_app(settings=settings(tmp_path), adapter=adapter, run_store=store)
    payload = full_payload()
    payload["tenant_id"] = "tenant:a"

    response = TestClient(app, raise_server_exceptions=False).post(
        "/internal/agent/chat/stream",
        json=payload,
        headers={"X-Internal-Key": INTERNAL_KEY},
    )

    assert response.status_code == 422
    assert "text/event-stream" not in response.headers.get("content-type", "")
    assert response.json() == {"detail": "Invalid chat request"}
    assert adapter.calls == 0
    assert store.count_runs() == 0


@pytest.mark.parametrize("request_id", ["", "   "])
def test_empty_request_id_returns_non_sse_422_without_adapter(tmp_path, request_id):
    adapter = CountingFinalAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    app = create_app(settings=settings(tmp_path), adapter=adapter, run_store=store)
    payload = full_payload()
    payload["request_id"] = request_id

    response = TestClient(app, raise_server_exceptions=False).post(
        "/internal/agent/chat/stream",
        json=payload,
        headers={"X-Internal-Key": INTERNAL_KEY},
    )

    assert response.status_code == 422
    assert "text/event-stream" not in response.headers.get("content-type", "")
    assert response.json() == {"detail": "Invalid chat request"}
    assert adapter.calls == 0
    assert store.count_runs() == 0


def test_local_like_empty_key_without_explicit_allow_returns_non_sse_503(tmp_path):
    response = client(
        tmp_path,
        LINGNENG_INTERNAL_API_KEY="",
        LINGNENG_ALLOW_INSECURE_LOCAL="false",
    ).post("/internal/agent/chat/stream", json=full_payload())

    assert response.status_code == 503
    assert "text/event-stream" not in response.headers.get("content-type", "")


def test_production_like_empty_key_returns_non_sse_503(tmp_path):
    response = client(
        tmp_path,
        LINGNENG_APP_ENV="prod",
        LINGNENG_INTERNAL_API_KEY="",
    ).post("/internal/agent/chat/stream", json=full_payload())

    assert response.status_code == 503
    assert "text/event-stream" not in response.headers.get("content-type", "")


class FailingAdapter:
    async def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[RunStartedEvent | AnswerDeltaEvent]:
        yield RunStartedEvent(run_id=run_id, request_id=request.request_id)
        raise RuntimeError("private exception detail")


def test_adapter_failure_after_stream_start_returns_terminal_error(tmp_path):
    app = create_app(
        settings=settings(tmp_path),
        adapter=FailingAdapter(),
        run_store=LingNengRunStore(tmp_path / "runs.sqlite3"),
    )
    response = TestClient(app).post(
        "/internal/agent/chat/stream",
        json=full_payload(),
        headers={"X-Internal-Key": INTERNAL_KEY},
    )

    frames = parse_sse(response.text)
    event_names = [event_name for event_name, _data in frames]
    error_payload = frames[-1][1]

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert event_names == ["run_started", "error"]
    assert error_payload["run_id"].startswith("run_")
    assert error_payload["request_id"] == "req-001"
    assert error_payload["code"] == "RUNTIME_ERROR"
    assert error_payload["message"] == "Agent runtime failed"
    assert error_payload["trace_id"].startswith("trace_")
    assert error_payload["recoverable"] is False
    assert "event: final" not in response.text
    assert "private exception detail" not in response.text


class MissingTerminalAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[RunStartedEvent]:
        self.calls += 1
        yield RunStartedEvent(run_id=run_id, request_id=request.request_id)


class HangingAfterStartAdapter:
    def __init__(self) -> None:
        self.waiting_for_next_frame = asyncio.Event()
        self.cancelled = False

    async def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[RunStartedEvent]:
        yield RunStartedEvent(run_id=run_id, request_id=request.request_id)
        self.waiting_for_next_frame.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            self.cancelled = True
            raise


def test_adapter_normal_end_without_terminal_marks_failed_and_closes_with_error(
    tmp_path,
):
    adapter = MissingTerminalAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    app = create_app(settings=settings(tmp_path), adapter=adapter, run_store=store)
    app_client = TestClient(app)

    first = post_stream(app_client, full_payload())
    first_frames = parse_sse(first.text)
    run_id = first_frames[0][1]["run_id"]
    record = store.get_by_run_id(run_id)
    second = post_stream(app_client, full_payload())
    second_frames = parse_sse(second.text)

    assert first.status_code == 200
    assert [event_name for event_name, _data in first_frames] == [
        "run_started",
        "error",
    ]
    assert first_frames[-1][1]["code"] == "RUNTIME_ERROR"
    assert first_frames[-1][1]["message"] == "Agent runtime failed"
    assert first_frames[-1][1]["recoverable"] is False
    assert record is not None
    assert record.status is RunStatus.FAILED
    assert record.error_code == "RUNTIME_ERROR"
    assert second.status_code == 200
    assert second_frames[0][0] == "error"
    assert second_frames[0][1]["code"] == "RUNTIME_ERROR"
    assert second_frames[0][1]["message"] == "Agent runtime failed"
    assert second_frames[0][1]["recoverable"] is False
    assert adapter.calls == 1


@pytest.mark.asyncio
async def test_client_disconnect_while_waiting_for_next_frame_marks_run_failed(
    tmp_path,
):
    request = ChatStreamRequest.model_validate(full_payload())
    resolved = resolve_session_key(request)
    adapter = HangingAfterStartAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    reservation = store.reserve_run(resolved.session_key, request.request_id)
    stream = with_heartbeats(
        _adapter_stream(
            adapter,
            store,
            request,
            resolved,
            reservation.record.run_id,
        ),
        interval_seconds=60,
    )

    first_frame = await anext(stream)
    next_frame_task = asyncio.create_task(anext(stream))
    await adapter.waiting_for_next_frame.wait()
    next_frame_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await next_frame_task

    record = store.get_by_run_id(reservation.record.run_id)
    assert first_frame.startswith("event: run_started\n")
    assert adapter.cancelled is True
    assert record is not None
    assert record.status is RunStatus.FAILED
    assert record.error_code == "CLIENT_STREAM_CANCELLED"
    assert record.error_message == "Client disconnected before stream completed"


class CountingFinalAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[RunStartedEvent | AnswerDeltaEvent | FinalEvent]:
        self.calls += 1
        yield RunStartedEvent(run_id=run_id, request_id=request.request_id)
        yield AnswerDeltaEvent(text="完成", sequence=1)
        yield FinalEvent(run_id=run_id, status="succeeded", answer="完成")


def test_repeated_running_request_does_not_invoke_adapter(tmp_path):
    adapter = CountingFinalAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    store.reserve_run("tenant-a:user-a:emp-001:conv-a", "req-001")
    app = create_app(settings=settings(tmp_path), adapter=adapter, run_store=store)

    response = post_stream(TestClient(app), full_payload())
    frames = parse_sse(response.text)

    assert response.status_code == 200
    assert frames == [
        (
            "error",
            {
                **frames[0][1],
                "code": "REQUEST_ALREADY_RUNNING",
                "message": "Request is already running",
                "recoverable": True,
            },
        )
    ]
    assert adapter.calls == 0


def test_repeated_completed_request_replays_final_without_second_adapter_call(tmp_path):
    adapter = CountingFinalAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    app = create_app(settings=settings(tmp_path), adapter=adapter, run_store=store)
    app_client = TestClient(app)

    first = post_stream(app_client, full_payload())
    second = post_stream(app_client, full_payload())
    frames = parse_sse(second.text)

    assert first.status_code == 200
    assert "event: final" in first.text
    assert second.status_code == 200
    assert [event_name for event_name, _data in frames] == [
        "run_started",
        "answer_delta",
        "final",
    ]
    assert frames[1][1]["text"] == "完成"
    assert frames[2][1]["status"] == "succeeded"
    assert frames[2][1]["answer"] == "完成"
    assert adapter.calls == 1
