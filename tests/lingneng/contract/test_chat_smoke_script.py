import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from lingneng.schemas.chat_request import ChatStreamRequest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "lingneng-chat-smoke.py"
INTERNAL_KEY = "smoke-test-internal-key"
ENV_INTERNAL_KEY = "smoke-test-env-internal-key"
SENSITIVE_EVENT_NAME = (
    "unknown_event_api_key_X-Amz-Signature_"
    "/Users/rotas/private_RAW_TOOL_OUTPUT_SECRET_VALUE"
)
SENSITIVE_QUERY = (
    "请分析订单 SENSITIVE_ORDER_42 "
    "https://storage.example.com/file?X-Amz-Signature=query-secret "
    "/Users/rotas/private/report.txt"
)
SYNTHETIC_SYSTEM_PROMPT = "synthetic smoke system prompt"
SYNTHETIC_SYSTEM_PROMPT_VERSION = "synthetic-system-prompt-v1"
SYNTHETIC_SKILL_ID = "synthetic-smoke-skill-id"
SYNTHETIC_SKILL_VERSION = "synthetic-smoke-skill-v1"
SYNTHETIC_SKILL_HASH = "synthetic-smoke-skill-hash"
CLI_SYSTEM_PROMPT = "cli synthetic system prompt CLI_SYSTEM_PROMPT_SECRET"
CLI_SYSTEM_PROMPT_VERSION = "cli-system-prompt-v1"
CLI_SKILL_ID = "cli-synthetic-smoke-skill-id"
CLI_SKILL_VERSION = "cli-synthetic-smoke-skill-v1"
CLI_SKILL_HASH = "cli-synthetic-smoke-skill-hash"
RAW_TOOL_OUTPUT = "RAW_TOOL_OUTPUT_SECRET_VALUE"


def sse_frame(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def final_frame() -> str:
    return sse_frame(
        "final",
        {
            "answer": "完成回答",
            "citations": [
                {"source": "doc-a", "url": "https://example.com/a"},
                {"source": "doc-b", "url": "https://example.com/b"},
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact-1",
                    "url": (
                        "https://files.example.com/a.pdf?"
                        "X-Amz-Signature=artifact-secret"
                    ),
                    "local_path": "/Users/rotas/private/output.pdf",
                }
            ],
            "trace_summary": {
                "latency_ms": 12,
                "api_key": "trace-secret",
                "X-Amz-Signature": "trace-signed-url-fragment",
                "/Users/rotas/private/key.txt": "trace-local-path",
                RAW_TOOL_OUTPUT: "trace-raw-tool-output-marker",
            },
        },
    )


class SmokeServer:
    def __init__(
        self,
        frames: list[str] | None = None,
        status: int = 200,
        heartbeat_duration_seconds: float | None = None,
        heartbeat_interval_seconds: float = 0.05,
    ):
        self.frames = frames or []
        self.status = status
        self.heartbeat_duration_seconds = heartbeat_duration_seconds
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.requests: list[dict[str, Any]] = []
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.httpd.frames = self.frames  # type: ignore[attr-defined]
        self.httpd.status = self.status  # type: ignore[attr-defined]
        self.httpd.heartbeat_duration_seconds = heartbeat_duration_seconds  # type: ignore[attr-defined]
        self.httpd.heartbeat_interval_seconds = heartbeat_interval_seconds  # type: ignore[attr-defined]
        self.httpd.requests = self.requests  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address
        return f"http://{host}:{port}/internal/agent/chat/stream"

    def __enter__(self) -> "SmokeServer":
        self.thread.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    @staticmethod
    def _handler() -> type[BaseHTTPRequestHandler]:
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                record = {
                    "method": self.command,
                    "path": self.path,
                    "content_type": self.headers.get("Content-Type"),
                    "internal_key": self.headers.get("X-Internal-Key"),
                    "payload": json.loads(body.decode("utf-8")),
                }
                self.server.requests.append(record)  # type: ignore[attr-defined]

                if self.server.status >= 400:  # type: ignore[attr-defined]
                    self.send_response(self.server.status)  # type: ignore[attr-defined]
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(b"server failure")
                    return

                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.end_headers()
                heartbeat_duration = self.server.heartbeat_duration_seconds  # type: ignore[attr-defined]
                if heartbeat_duration is not None:
                    deadline = time.monotonic() + heartbeat_duration
                    interval = self.server.heartbeat_interval_seconds  # type: ignore[attr-defined]
                    while time.monotonic() < deadline:
                        try:
                            self.wfile.write(b": ping\n\n")
                            self.wfile.flush()
                        except (BrokenPipeError, ConnectionResetError):
                            return
                        time.sleep(interval)
                    return
                for frame in self.server.frames:  # type: ignore[attr-defined]
                    self.wfile.write(frame.encode("utf-8"))
                    self.wfile.flush()

            def log_message(self, format: str, *args: object) -> None:
                return

        return Handler


def run_smoke(
    url: str,
    *,
    internal_key: str | None = INTERNAL_KEY,
    env_internal_key: str | None = None,
    timeout_seconds: str = "5",
    include_schema_cli_args: bool = False,
) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable,
        str(SCRIPT),
        "--url",
        url,
        "--request-id",
        "req-smoke-1",
        "--tenant-id",
        "tenant-smoke",
        "--user-id",
        "user-smoke",
        "--session-id",
        "session-smoke",
        "--conversation-id",
        "conversation-smoke",
        "--employee-id",
        "employee-smoke",
        "--employee-type",
        "boss_assistant",
        "--query",
        SENSITIVE_QUERY,
        "--timeout-seconds",
        timeout_seconds,
    ]
    if include_schema_cli_args:
        args.extend(
            [
                "--system-prompt",
                CLI_SYSTEM_PROMPT,
                "--system-prompt-version",
                CLI_SYSTEM_PROMPT_VERSION,
                "--skill-id",
                CLI_SKILL_ID,
                "--skill-version",
                CLI_SKILL_VERSION,
                "--skill-hash",
                CLI_SKILL_HASH,
            ]
        )
    if internal_key is not None:
        args.extend(["--internal-key", internal_key])
    env = os.environ.copy()
    if env_internal_key is None:
        env.pop("LINGNENG_INTERNAL_API_KEY", None)
    else:
        env["LINGNENG_INTERNAL_API_KEY"] = env_internal_key
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )


def assert_java_payload(
    record: dict[str, Any],
    expected_key: str | None,
    *,
    system_prompt: str = SYNTHETIC_SYSTEM_PROMPT,
    system_prompt_version: str = SYNTHETIC_SYSTEM_PROMPT_VERSION,
    skill_id: str = SYNTHETIC_SKILL_ID,
    skill_version: str = SYNTHETIC_SKILL_VERSION,
    skill_hash: str = SYNTHETIC_SKILL_HASH,
) -> None:
    payload = record["payload"]
    validated = ChatStreamRequest.model_validate(payload)

    assert record["method"] == "POST"
    assert record["path"] == "/internal/agent/chat/stream"
    assert record["content_type"] == "application/json"
    assert record["internal_key"] == expected_key
    assert payload["request_id"] == "req-smoke-1"
    assert payload["tenant_id"] == "tenant-smoke"
    assert payload["user_id"] == "user-smoke"
    assert payload["session_id"] == "session-smoke"
    assert payload["conversation_id"] == "conversation-smoke"
    assert payload["query"]["content"] == SENSITIVE_QUERY
    assert payload["employee"]["employee_id"] == "employee-smoke"
    assert payload["employee"]["employee_type"] == "boss_assistant"
    assert payload["system_prompt"]["content"] == system_prompt
    assert payload["system_prompt"]["version"] == system_prompt_version
    assert payload["skill"]["skill_id"] == skill_id
    assert payload["skill"]["skill_version"] == skill_version
    assert payload["skill"]["skill_hash"] == skill_hash
    assert payload["history"] == []
    assert payload["attachments"] == []
    assert payload["stream_options"]["include_citations"] is True
    assert payload["stream_options"]["include_rag_context"] is True
    assert validated.system_prompt.content == system_prompt
    assert validated.system_prompt.version == system_prompt_version
    assert validated.skill.skill_id == skill_id
    assert validated.skill.skill_version == skill_version
    assert validated.skill.skill_hash == skill_hash


def assert_safe_output(result: subprocess.CompletedProcess[str]) -> None:
    combined = result.stdout + result.stderr

    assert INTERNAL_KEY not in combined
    assert ENV_INTERNAL_KEY not in combined
    assert SENSITIVE_QUERY not in combined
    assert SYNTHETIC_SYSTEM_PROMPT not in combined
    assert SYNTHETIC_SYSTEM_PROMPT_VERSION not in combined
    assert SYNTHETIC_SKILL_ID not in combined
    assert SYNTHETIC_SKILL_VERSION not in combined
    assert SYNTHETIC_SKILL_HASH not in combined
    assert CLI_SYSTEM_PROMPT not in combined
    assert CLI_SYSTEM_PROMPT_VERSION not in combined
    assert CLI_SKILL_ID not in combined
    assert CLI_SKILL_VERSION not in combined
    assert CLI_SKILL_HASH not in combined
    assert "SENSITIVE_ORDER_42" not in combined
    assert "api_key" not in combined
    assert "X-Amz-Signature" not in combined
    assert "/Users/rotas" not in combined
    assert RAW_TOOL_OUTPUT not in combined
    assert '"query"' not in combined
    assert '"request_id"' not in combined
    assert '"system_prompt"' not in combined
    assert '"skill"' not in combined


def test_smoke_script_posts_java_payload_and_succeeds_after_final() -> None:
    frames = [
        ": ping\n\n",
        sse_frame("run_started", {"run_id": "run-1"}),
        sse_frame("answer_delta", {"text": "完成"}),
        final_frame(),
    ]

    with SmokeServer(frames=frames) as server:
        result = run_smoke(server.url)

    assert result.returncode == 0, result.stderr
    assert len(server.requests) == 1
    assert_java_payload(server.requests[0], INTERNAL_KEY)
    assert "endpoint: 127.0.0.1" in result.stdout
    assert "/internal/agent/chat/stream" in result.stdout
    assert "event_order: run_started,answer_delta,final" in result.stdout
    assert "final_answer_length: 4" in result.stdout
    assert "citation_count: 2" in result.stdout
    assert "artifact_count: 1" in result.stdout
    assert "trace_summary_key_count: 5" in result.stdout
    assert "trace_summary_keys:" not in result.stdout
    assert_safe_output(result)


def test_smoke_script_uses_internal_key_from_environment() -> None:
    frames = [
        sse_frame("run_started", {"run_id": "run-1"}),
        final_frame(),
    ]

    with SmokeServer(frames=frames) as server:
        result = run_smoke(
            server.url,
            internal_key=None,
            env_internal_key=ENV_INTERNAL_KEY,
        )

    assert result.returncode == 0, result.stderr
    assert_java_payload(server.requests[0], ENV_INTERNAL_KEY)
    assert_safe_output(result)


def test_smoke_script_accepts_system_prompt_and_skill_cli_args() -> None:
    frames = [
        sse_frame("run_started", {"run_id": "run-1"}),
        final_frame(),
    ]

    with SmokeServer(frames=frames) as server:
        result = run_smoke(server.url, include_schema_cli_args=True)

    assert result.returncode == 0, result.stderr
    assert_java_payload(
        server.requests[0],
        INTERNAL_KEY,
        system_prompt=CLI_SYSTEM_PROMPT,
        system_prompt_version=CLI_SYSTEM_PROMPT_VERSION,
        skill_id=CLI_SKILL_ID,
        skill_version=CLI_SKILL_VERSION,
        skill_hash=CLI_SKILL_HASH,
    )
    assert_safe_output(result)


def test_smoke_script_omits_empty_internal_key_header() -> None:
    frames = [
        sse_frame("run_started", {"run_id": "run-1"}),
        final_frame(),
    ]

    with SmokeServer(frames=frames) as server:
        result = run_smoke(server.url, internal_key=None, env_internal_key="")

    assert result.returncode == 0, result.stderr
    assert_java_payload(server.requests[0], None)
    assert_safe_output(result)


def test_smoke_script_returns_nonzero_on_http_500() -> None:
    with SmokeServer(status=500) as server:
        result = run_smoke(server.url)

    assert result.returncode == 1
    assert_java_payload(server.requests[0], INTERNAL_KEY)
    assert_safe_output(result)


def test_smoke_script_returns_nonzero_on_sse_error() -> None:
    frames = [
        sse_frame("run_started", {"run_id": "run-1"}),
        sse_frame(
            "error",
            {
                "code": "UPSTREAM_FAILURE",
                "message": f"do not leak {SENSITIVE_QUERY} {RAW_TOOL_OUTPUT}",
            },
        ),
    ]

    with SmokeServer(frames=frames) as server:
        result = run_smoke(server.url)

    assert result.returncode == 1
    assert_java_payload(server.requests[0], INTERNAL_KEY)
    assert "event_order: run_started,error" in result.stdout
    assert_safe_output(result)


def test_smoke_script_returns_nonzero_when_stream_ends_before_final() -> None:
    frames = [
        ": ping\n\n",
        sse_frame("run_started", {"run_id": "run-1"}),
        sse_frame("answer_delta", {"text": "partial"}),
    ]

    with SmokeServer(frames=frames) as server:
        result = run_smoke(server.url)

    assert result.returncode == 1
    assert_java_payload(server.requests[0], INTERNAL_KEY)
    assert "event_order: run_started,answer_delta" in result.stdout
    assert_safe_output(result)


def test_smoke_script_times_out_when_heartbeat_stream_never_reaches_final() -> None:
    with SmokeServer(heartbeat_duration_seconds=0.65) as server:
        result = run_smoke(server.url, timeout_seconds="0.2")

    assert result.returncode == 1
    assert_java_payload(server.requests[0], INTERNAL_KEY)
    assert "error: timeout" in result.stderr
    assert "event_order: none" in result.stdout
    assert_safe_output(result)


def test_smoke_script_returns_nonzero_on_malformed_data_json() -> None:
    frames = [
        sse_frame("run_started", {"run_id": "run-1"}),
        "event: answer_delta\ndata: {malformed-json}\n\n",
    ]

    with SmokeServer(frames=frames) as server:
        result = run_smoke(server.url)

    assert result.returncode == 1
    assert_java_payload(server.requests[0], INTERNAL_KEY)
    assert "event_order: run_started" in result.stdout
    assert_safe_output(result)


def test_smoke_script_returns_nonzero_when_business_frame_has_no_event() -> None:
    frames = [
        sse_frame("run_started", {"run_id": "run-1"}),
        'data: {"answer": "missing event"}\n\n',
    ]

    with SmokeServer(frames=frames) as server:
        result = run_smoke(server.url)

    assert result.returncode == 1
    assert_java_payload(server.requests[0], INTERNAL_KEY)
    assert "event_order: run_started" in result.stdout
    assert_safe_output(result)


def test_smoke_script_returns_nonzero_without_leaking_unknown_event_name() -> None:
    frames = [
        sse_frame("run_started", {"run_id": "run-1"}),
        sse_frame(SENSITIVE_EVENT_NAME, {"value": "ignored"}),
        final_frame(),
    ]

    with SmokeServer(frames=frames) as server:
        result = run_smoke(server.url)

    combined = result.stdout + result.stderr

    assert result.returncode == 1
    assert_java_payload(server.requests[0], INTERNAL_KEY)
    assert "error: unknown_event" in result.stderr
    assert "event_order: run_started" in result.stdout
    assert SENSITIVE_EVENT_NAME not in combined
    assert "unknown_event_api_key" not in combined
    assert_safe_output(result)
