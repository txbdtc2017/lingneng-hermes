import json
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from lingneng.api.app import create_app
from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_events import (
    AnswerDeltaEvent,
    ErrorEvent,
    FinalEvent,
    RunStartedEvent,
)
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import ResolvedSessionKey
from lingneng.session.run_store import LingNengRunStore
from tests.lingneng.schemas.test_chat_request_schema import full_payload


INTERNAL_KEY = "key"


def settings(tmp_path) -> LingNengSettings:
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_INTERNAL_API_KEY": INTERNAL_KEY,
        }
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


class CountingSuccessAdapter:
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
        yield FinalEvent(
            run_id=run_id,
            status="succeeded",
            answer="完成",
            artifacts=[{"artifact_id": "a-1"}],
        )


class CountingFailureAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[ErrorEvent]:
        self.calls += 1
        yield ErrorEvent(
            run_id=run_id,
            request_id=request.request_id,
            code="RUNTIME_ERROR",
            message="Agent runtime failed",
            trace_id="trace-test",
            recoverable=False,
        )


class CountingEmptySuccessAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[RunStartedEvent | FinalEvent]:
        self.calls += 1
        yield RunStartedEvent(run_id=run_id, request_id=request.request_id)
        yield FinalEvent(run_id=run_id, status="succeeded", answer="")


def post(client: TestClient, payload: dict):
    return client.post(
        "/internal/agent/chat/stream",
        json=payload,
        headers={"X-Internal-Key": INTERNAL_KEY},
    )


def test_repeated_success_replays_stored_sse_without_adapter(tmp_path):
    adapter = CountingSuccessAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    app = create_app(settings=settings(tmp_path), adapter=adapter, run_store=store)
    client = TestClient(app)

    first = post(client, full_payload())
    second = post(client, full_payload())
    frames = parse_sse(second.text)

    assert first.status_code == 200
    assert second.status_code == 200
    assert [event for event, _ in frames] == ["run_started", "answer_delta", "final"]
    assert frames[1][1]["text"] == "完成"
    assert frames[2][1]["status"] == "succeeded"
    assert frames[2][1]["answer"] == "完成"
    assert frames[2][1]["artifacts"] == [{"artifact_id": "a-1"}]
    assert adapter.calls == 1


def test_repeated_empty_success_replays_empty_answer_delta(tmp_path):
    adapter = CountingEmptySuccessAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    app = create_app(settings=settings(tmp_path), adapter=adapter, run_store=store)
    client = TestClient(app)

    first = post(client, full_payload())
    second = post(client, full_payload())
    frames = parse_sse(second.text)

    assert first.status_code == 200
    assert second.status_code == 200
    assert [event for event, _ in frames] == ["run_started", "answer_delta", "final"]
    assert frames[1][1]["text"] == ""
    assert frames[1][1]["sequence"] == 1
    assert frames[2][1]["status"] == "succeeded"
    assert frames[2][1]["answer"] == ""
    assert adapter.calls == 1


def test_repeated_failure_replays_stored_public_error_without_adapter(tmp_path):
    adapter = CountingFailureAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    app = create_app(settings=settings(tmp_path), adapter=adapter, run_store=store)
    client = TestClient(app)

    first = post(client, full_payload())
    second = post(client, full_payload())
    frames = parse_sse(second.text)

    assert first.status_code == 200
    assert second.status_code == 200
    assert [event for event, _ in frames] == ["error"]
    assert frames[0][1]["code"] == "RUNTIME_ERROR"
    assert frames[0][1]["message"] == "Agent runtime failed"
    assert frames[0][1]["recoverable"] is False
    assert adapter.calls == 1


def test_repeated_running_still_returns_running_error_without_adapter(tmp_path):
    adapter = CountingSuccessAdapter()
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    store.reserve_run("tenant-a:user-a:emp-001:conv-a", "req-001")
    app = create_app(settings=settings(tmp_path), adapter=adapter, run_store=store)

    response = post(TestClient(app), full_payload())
    frames = parse_sse(response.text)

    assert response.status_code == 200
    assert [event for event, _ in frames] == ["error"]
    assert frames[0][1]["code"] == "REQUEST_ALREADY_RUNNING"
    assert adapter.calls == 0
