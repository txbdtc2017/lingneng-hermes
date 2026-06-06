import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lingneng.api.app import create_app
from lingneng.api.routes import _adapter_stream
from lingneng.config.settings import LingNengSettings
from lingneng.observability.logging import sanitize_trace_payload
from lingneng.schemas.chat_events import (
    AgentStepEvent,
    AnswerDeltaEvent,
    Artifact,
    ArtifactCreatedEvent,
    Citation,
    CitationDeltaEvent,
    FinalEvent,
    RunStartedEvent,
)
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import ResolvedSessionKey, resolve_session_key
from lingneng.session.run_store import LingNengRunStore
from tests.lingneng.schemas.test_chat_request_schema import full_payload


INTERNAL_KEY = "valid-internal-key"
SECRET_SENTINELS = {
    "QUERY_CONTENT_DO_NOT_LOG",
    "HISTORY_CONTENT_DO_NOT_LOG",
    "SYSTEM_PROMPT_DO_NOT_LOG",
    "SKILL_PROMPT_BODY_DO_NOT_LOG",
    "ATTACHMENT_TEXT_DO_NOT_LOG",
    "SIGNED_URL_DO_NOT_LOG",
    "RAW_TOOL_RESULT_DO_NOT_LOG",
    "RAW_TOOL_ARGS_DO_NOT_LOG",
    "PROVIDER_EXCEPTION_DO_NOT_LOG",
    "API_KEY_DO_NOT_LOG",
    "BEARER_TOKEN_DO_NOT_LOG",
    "PASSWORD_DO_NOT_LOG",
    "/Users/rotas/private/local-path",
}


def settings(tmp_path, **overrides: str) -> LingNengSettings:
    values = {
        "LINGNENG_APP_ENV": "test",
        "LINGNENG_RUNTIME_DIR": str(tmp_path),
        "LINGNENG_INTERNAL_API_KEY": INTERNAL_KEY,
    }
    values.update(overrides)
    return LingNengSettings.from_env(values)


def post_stream(app_client: TestClient, payload: dict[str, Any]):
    return app_client.post(
        "/internal/agent/chat/stream",
        json=payload,
        headers={"X-Internal-Key": INTERNAL_KEY},
    )


def parse_sse(text: str) -> list[tuple[str, dict[str, Any]]]:
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


def sensitive_payload() -> dict[str, Any]:
    payload = full_payload()
    payload["query"]["content"] = (
        "QUERY_CONTENT_DO_NOT_LOG bearer BEARER_TOKEN_DO_NOT_LOG "
        "api_key=API_KEY_DO_NOT_LOG password=PASSWORD_DO_NOT_LOG"
    )
    payload["system_prompt"]["content"] = "SYSTEM_PROMPT_DO_NOT_LOG"
    payload["skill"]["inline"] = {
        "body": "SKILL_PROMPT_BODY_DO_NOT_LOG",
        "args": "RAW_TOOL_ARGS_DO_NOT_LOG",
        "api_key": "API_KEY_DO_NOT_LOG",
    }
    payload["history"] = [
        {
            "message_id": "h-secret",
            "role": "user",
            "content": "HISTORY_CONTENT_DO_NOT_LOG",
        }
    ]
    payload["attachments"][0]["download_url"] = (
        "https://files.example.test/brief.pdf"
        "?X-Amz-Signature=SIGNED_URL_DO_NOT_LOG"
    )
    payload["attachments"][0]["text"] = "ATTACHMENT_TEXT_DO_NOT_LOG"
    payload["local_path"] = "/Users/rotas/private/local-path"
    return payload


def trace_payloads(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    return [
        record.trace_payload
        for record in caplog.records
        if record.name.startswith("lingneng.observability")
        and hasattr(record, "trace_payload")
    ]


def payload_for(
    payloads: list[dict[str, Any]],
    event_name: str,
) -> dict[str, Any]:
    return next(item for item in payloads if item["event_name"] == event_name)


def assert_no_secret_sentinels(value: Any) -> None:
    serialized = repr(value)
    for sentinel in SECRET_SENTINELS:
        assert sentinel not in serialized


class RichSuccessfulAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[
        RunStartedEvent
        | AgentStepEvent
        | CitationDeltaEvent
        | ArtifactCreatedEvent
        | AnswerDeltaEvent
        | FinalEvent
    ]:
        self.calls += 1
        citation = Citation(
            document_id="doc-1",
            source_file_id="file-1",
            source_file_name="public-source.pdf",
            page_no=1,
            section_title="summary",
            chunk_id="chunk-1",
            score=0.88,
        )
        artifact = Artifact(
            artifact_id="artifact-1",
            artifact_type="document",
            source="document_generation",
            file_name="report.pdf",
            mime_type="application/pdf",
            url="https://files.example.test/report.pdf",
            object_key="external/java-agent-file/artifact-1",
            format="pdf",
            target_format="pdf",
        )

        yield RunStartedEvent(run_id=run_id, request_id=request.request_id)
        yield AgentStepEvent(
            sequence=1,
            step_id="tool-1",
            phase="tool",
            status="succeeded",
            title="retrieve_rag",
            short_text="Completed retrieve_rag.",
            summary="RAW_TOOL_RESULT_DO_NOT_LOG",
            refs=[],
        )
        yield CitationDeltaEvent.model_validate(citation.model_dump())
        yield ArtifactCreatedEvent.model_validate(artifact.model_dump())
        yield AnswerDeltaEvent(text="safe ", sequence=1)
        yield AnswerDeltaEvent(text="answer", sequence=2)
        yield FinalEvent(
            run_id=run_id,
            status="succeeded",
            answer="safe answer",
            citations=[citation],
            artifacts=[artifact],
        )


class FailingAdapter:
    async def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[RunStartedEvent]:
        yield RunStartedEvent(run_id=run_id, request_id=request.request_id)
        raise RuntimeError("PROVIDER_EXCEPTION_DO_NOT_LOG")


class HangingAdapter:
    def __init__(self) -> None:
        self.waiting_for_next_frame = asyncio.Event()

    async def stream(
        self,
        request: ChatStreamRequest,
        resolved_session: ResolvedSessionKey,
        run_id: str,
    ) -> AsyncIterator[RunStartedEvent]:
        yield RunStartedEvent(run_id=run_id, request_id=request.request_id)
        self.waiting_for_next_frame.set()
        await asyncio.sleep(3600)


def test_final_event_trace_summary_defaults_to_empty():
    event = FinalEvent(run_id="run-1", status="succeeded", answer="ok")

    assert event.trace_summary == {}


def test_trace_sanitizer_drops_nested_payloads_by_default():
    payload = sanitize_trace_payload(
        {
            "request_id": {"content": "NON_SECRET_LOOKING_CONTENT"},
            "session_key": ["tenant", "user", "conversation"],
            "answer_chars": 12,
        }
    )

    assert payload == {"answer_chars": 12}


def test_live_success_emits_safe_trace_summary_and_structured_logs(
    tmp_path,
    caplog,
    monkeypatch,
):
    monkeypatch.setenv("LINGNENG_DEPLOY_ENV", "test-deploy")
    monkeypatch.setenv("LINGNENG_IMAGE_REF", "registry.example.test/lingneng:dev")
    monkeypatch.setenv("LINGNENG_GIT_SHA", "abc123def456")
    monkeypatch.setenv("LINGNENG_BUILD_ID", "build-42")
    caplog.set_level(logging.INFO, logger="lingneng.observability")
    adapter = RichSuccessfulAdapter()
    runtime_settings = settings(tmp_path)
    store = LingNengRunStore(tmp_path / "runs.sqlite3", settings=runtime_settings)
    app = create_app(
        settings=runtime_settings,
        adapter=adapter,
        run_store=store,
    )

    response = post_stream(TestClient(app), sensitive_payload())
    frames = parse_sse(response.text)
    final_payload = frames[-1][1]
    summary = final_payload["trace_summary"]
    log_payloads = trace_payloads(caplog)
    completed = payload_for(log_payloads, "adapter_stream_completed")

    assert response.status_code == 200
    assert [event_name for event_name, _data in frames] == [
        "run_started",
        "agent_step",
        "citation_delta",
        "artifact_created",
        "answer_delta",
        "answer_delta",
        "final",
    ]
    assert {item["event_name"] for item in log_payloads} >= {
        "request_accepted",
        "adapter_stream_started",
        "adapter_stream_completed",
    }
    required_keys = {
        "event_name",
        "request_id",
        "run_id",
        "tenant_id",
        "user_id",
        "conversation_id",
        "session_key",
        "employee_id",
        "employee_type",
        "status",
        "duration_ms",
        "agent_mode",
        "history_count",
        "attachment_count",
        "agent_step_count",
        "citation_count",
        "artifact_count",
        "answer_chars",
        "active_hermes_session_id",
        "compression_root_session_id",
        "compression_active_session_id",
        "deploy_env",
        "deploy_image_ref",
        "deploy_git_sha",
        "deploy_build_id",
    }
    assert required_keys <= completed.keys()
    assert required_keys <= summary.keys()
    assert completed["request_id"] == "req-001"
    assert completed["run_id"].startswith("run_")
    assert completed["tenant_id"] == "tenant-a"
    assert completed["user_id"] == "user-a"
    assert completed["conversation_id"] == "conv-a"
    assert completed["session_key"] == "tenant-a:user-a:emp-001:conv-a"
    assert completed["employee_id"] == "emp-001"
    assert completed["employee_type"] == "marketing_content_creator"
    assert completed["status"] == "succeeded"
    assert completed["agent_mode"] == "fake"
    assert completed["history_count"] == 1
    assert completed["attachment_count"] == 1
    assert completed["agent_step_count"] == 1
    assert completed["citation_count"] == 1
    assert completed["artifact_count"] == 1
    assert completed["answer_chars"] == len("safe answer")
    assert completed["active_hermes_session_id"] == completed["session_key"]
    assert completed["compression_root_session_id"] == completed["session_key"]
    assert completed["compression_active_session_id"] == completed["session_key"]
    assert completed["deploy_env"] == "test-deploy"
    assert completed["deploy_image_ref"] == "registry.example.test/lingneng:dev"
    assert completed["deploy_git_sha"] == "abc123def456"
    assert completed["deploy_build_id"] == "build-42"
    assert '"event_name":"adapter_stream_completed"' in caplog.text
    assert '"request_id":"req-001"' in caplog.text
    assert '"run_id":"' in caplog.text
    assert summary["event_name"] == "final"
    assert summary["status"] == "succeeded"
    assert summary["answer_chars"] == len("safe answer")
    assert_no_secret_sentinels(log_payloads)
    assert_no_secret_sentinels(summary)
    assert_no_secret_sentinels(caplog.text)


def test_successful_replay_includes_trace_summary_without_second_adapter_call(
    tmp_path,
    caplog,
):
    caplog.set_level(logging.INFO, logger="lingneng.observability")
    adapter = RichSuccessfulAdapter()
    runtime_settings = settings(tmp_path)
    app = create_app(
        settings=runtime_settings,
        adapter=adapter,
        run_store=LingNengRunStore(
            tmp_path / "runs.sqlite3",
            settings=runtime_settings,
        ),
    )
    app_client = TestClient(app)
    payload = sensitive_payload()

    first = post_stream(app_client, payload)
    second = post_stream(app_client, payload)
    replay_frames = parse_sse(second.text)
    summary = replay_frames[-1][1]["trace_summary"]
    replay_log = payload_for(trace_payloads(caplog), "request_replayed")

    assert first.status_code == 200
    assert second.status_code == 200
    assert [event_name for event_name, _data in replay_frames] == [
        "run_started",
        "answer_delta",
        "final",
    ]
    assert adapter.calls == 1
    assert summary["event_name"] == "final"
    assert summary["status"] == "succeeded"
    assert summary["request_id"] == "req-001"
    assert summary["session_key"] == "tenant-a:user-a:emp-001:conv-a"
    assert summary["answer_chars"] == len("safe answer")
    assert summary["citation_count"] == 1
    assert summary["artifact_count"] == 1
    assert replay_log["status"] == "succeeded"
    assert_no_secret_sentinels(summary)
    assert_no_secret_sentinels(replay_log)


def test_invalid_json_logs_sanitized_pre_stream_failure(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="lingneng.observability")
    app = create_app(
        settings=settings(tmp_path),
        adapter=RichSuccessfulAdapter(),
        run_store=LingNengRunStore(tmp_path / "runs.sqlite3"),
    )

    response = TestClient(app).post(
        "/internal/agent/chat/stream",
        content='{"sensitive": "QUERY_CONTENT_DO_NOT_LOG"',
        headers={
            "Content-Type": "application/json",
            "X-Internal-Key": INTERNAL_KEY,
        },
    )
    validation_log = payload_for(
        trace_payloads(caplog),
        "request_validation_failed",
    )

    assert response.status_code == 422
    assert validation_log["status"] == "failed"
    assert validation_log["error_code"] == "INVALID_CHAT_REQUEST"
    assert validation_log["recoverable"] is False
    assert_no_secret_sentinels(validation_log)
    assert_no_secret_sentinels(caplog.text)


def test_invalid_session_key_logs_sanitized_pre_stream_failure(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="lingneng.observability")
    payload = sensitive_payload()
    payload["tenant_id"] = "tenant:a"
    app = create_app(
        settings=settings(tmp_path),
        adapter=RichSuccessfulAdapter(),
        run_store=LingNengRunStore(tmp_path / "runs.sqlite3"),
    )

    response = post_stream(TestClient(app), payload)
    validation_log = payload_for(
        trace_payloads(caplog),
        "request_validation_failed",
    )

    assert response.status_code == 422
    assert validation_log["request_id"] == "req-001"
    assert validation_log["history_count"] == 1
    assert validation_log["attachment_count"] == 1
    assert validation_log["status"] == "failed"
    assert validation_log["error_code"] == "INVALID_SESSION_KEY"
    assert validation_log["recoverable"] is False
    assert_no_secret_sentinels(validation_log)
    assert_no_secret_sentinels(caplog.text)


def test_duplicate_running_request_logs_public_error_without_adapter_call(
    tmp_path,
    caplog,
):
    caplog.set_level(logging.INFO, logger="lingneng.observability")
    adapter = RichSuccessfulAdapter()
    runtime_settings = settings(tmp_path)
    store = LingNengRunStore(tmp_path / "runs.sqlite3", settings=runtime_settings)
    store.reserve_run("tenant-a:user-a:emp-001:conv-a", "req-001")
    app = create_app(
        settings=runtime_settings,
        adapter=adapter,
        run_store=store,
    )

    response = post_stream(TestClient(app), sensitive_payload())
    frames = parse_sse(response.text)
    duplicate_log = payload_for(trace_payloads(caplog), "request_duplicate")

    assert response.status_code == 200
    assert frames[0][0] == "error"
    assert frames[0][1]["code"] == "REQUEST_ALREADY_RUNNING"
    assert adapter.calls == 0
    assert duplicate_log["error_code"] == "REQUEST_ALREADY_RUNNING"
    assert duplicate_log["recoverable"] is True
    assert_no_secret_sentinels(duplicate_log)


def test_failed_adapter_stream_logs_sanitized_public_failure(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="lingneng.observability")
    runtime_settings = settings(tmp_path)
    app = create_app(
        settings=runtime_settings,
        adapter=FailingAdapter(),
        run_store=LingNengRunStore(
            tmp_path / "runs.sqlite3",
            settings=runtime_settings,
        ),
    )

    response = post_stream(TestClient(app), sensitive_payload())
    frames = parse_sse(response.text)
    failed_log = payload_for(trace_payloads(caplog), "adapter_stream_failed")

    assert response.status_code == 200
    assert frames[-1][0] == "error"
    assert frames[-1][1]["code"] == "RUNTIME_ERROR"
    assert "PROVIDER_EXCEPTION_DO_NOT_LOG" not in response.text
    assert failed_log["status"] == "failed"
    assert failed_log["error_code"] == "RUNTIME_ERROR"
    assert failed_log["recoverable"] is False
    assert_no_secret_sentinels(failed_log)
    assert_no_secret_sentinels(caplog.text)


@pytest.mark.asyncio
async def test_client_stream_cancelled_logs_sanitized_event(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="lingneng.observability")
    request = ChatStreamRequest.model_validate(sensitive_payload())
    resolved = resolve_session_key(request)
    store = LingNengRunStore(tmp_path / "runs.sqlite3")
    reservation = store.reserve_run(resolved.session_key, request.request_id)
    stream = _adapter_stream(
        HangingAdapter(),
        store,
        request,
        resolved,
        reservation.record.run_id,
    )

    first_frame = await anext(stream)
    next_frame_task = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    next_frame_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await next_frame_task

    cancelled_log = payload_for(trace_payloads(caplog), "client_stream_cancelled")

    assert first_frame.startswith("event: run_started\n")
    assert cancelled_log["status"] == "failed"
    assert cancelled_log["error_code"] == "CLIENT_STREAM_CANCELLED"
    assert cancelled_log["recoverable"] is True
    assert_no_secret_sentinels(cancelled_log)
