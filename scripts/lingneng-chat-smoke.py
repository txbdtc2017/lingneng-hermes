#!/usr/bin/env python3
"""Client-side LingNeng Java-compatible SSE smoke check."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterable


DEFAULT_URL = "http://127.0.0.1:18083/internal/agent/chat/stream"
ALLOWED_EVENTS = frozenset(
    {
        "run_started",
        "agent_step",
        "route_result",
        "route_suggestion",
        "route_confirm_required",
        "citation_delta",
        "rag_context",
        "artifact_created",
        "answer_delta",
        "final",
        "compliance_block",
        "error",
    }
)


class SmokeError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class SmokeSummary:
    endpoint: str
    event_order: list[str] = field(default_factory=list)
    final_answer_length: int = 0
    citation_count: int = 0
    artifact_count: int = 0
    trace_summary_key_count: int = 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call a LingNeng Java-compatible chat SSE endpoint.",
    )
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--internal-key", default=None)
    parser.add_argument("--request-id", default="smoke-request")
    parser.add_argument("--tenant-id", default="smoke-tenant")
    parser.add_argument("--user-id", default="smoke-user")
    parser.add_argument("--session-id", default="smoke-session")
    parser.add_argument("--conversation-id", default="smoke-conversation")
    parser.add_argument("--employee-id", default="smoke-employee")
    parser.add_argument("--employee-type", default="boss_assistant")
    parser.add_argument("--query", default="ping")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args(argv)


def safe_endpoint(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port is not None else ""
    path = parsed.path or "/"
    return f"{host}{port}{path}"


def internal_key(args: argparse.Namespace) -> str:
    if args.internal_key is not None:
        return args.internal_key
    return os.environ.get("LINGNENG_INTERNAL_API_KEY", "")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "request_id": args.request_id,
        "tenant_id": args.tenant_id,
        "user_id": args.user_id,
        "session_id": args.session_id,
        "conversation_id": args.conversation_id,
        "query": {"content": args.query},
        "employee": {
            "employee_id": args.employee_id,
            "employee_type": args.employee_type,
        },
        "history": [],
        "attachments": [],
        "stream_options": {
            "include_citations": True,
            "include_rag_context": True,
        },
    }


def build_request(args: argparse.Namespace) -> urllib.request.Request:
    headers = {
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }
    key = internal_key(args)
    if key:
        headers["X-Internal-Key"] = key
    body = json.dumps(build_payload(args), ensure_ascii=False).encode("utf-8")
    return urllib.request.Request(
        args.url,
        data=body,
        headers=headers,
        method="POST",
    )


def iter_sse_frames(response: Any) -> Iterable[str]:
    lines: list[str] = []
    while True:
        raw_line = response.readline()
        if not raw_line:
            break
        try:
            line = raw_line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SmokeError("malformed_utf8") from exc
        line = line.rstrip("\r\n")
        if line:
            lines.append(line)
            continue
        if lines:
            yield "\n".join(lines)
            lines = []

    if lines:
        yield "\n".join(lines)


def _field_value(line: str, field_name: str) -> str:
    value = line.removeprefix(f"{field_name}:")
    return value.removeprefix(" ")


def parse_sse_frame(frame: str) -> tuple[str, dict[str, Any]] | None:
    lines = [line for line in frame.splitlines() if line]
    business_lines = [line for line in lines if not line.startswith(":")]
    if not business_lines:
        return None

    event_name = ""
    data_lines: list[str] = []
    for line in business_lines:
        if line.startswith("event:"):
            event_name = _field_value(line, "event").strip()
        elif line.startswith("data:"):
            data_lines.append(_field_value(line, "data"))

    if not event_name:
        raise SmokeError("missing_event")
    if not data_lines:
        raise SmokeError("missing_data")

    try:
        data = json.loads("\n".join(data_lines))
    except json.JSONDecodeError as exc:
        raise SmokeError("malformed_json") from exc
    if not isinstance(data, dict):
        raise SmokeError("malformed_json")
    return event_name, data


def _count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def update_final_summary(summary: SmokeSummary, data: dict[str, Any]) -> None:
    answer = data.get("answer", "")
    summary.final_answer_length = len(answer) if isinstance(answer, str) else 0
    summary.citation_count = _count(data.get("citations"))
    summary.artifact_count = _count(data.get("artifacts"))
    trace_summary = data.get("trace_summary")
    if isinstance(trace_summary, dict):
        summary.trace_summary_key_count = len(trace_summary)


def print_summary(summary: SmokeSummary) -> None:
    event_order = ",".join(summary.event_order) if summary.event_order else "none"
    print(f"endpoint: {summary.endpoint}")
    print(f"event_order: {event_order}")
    print(f"final_answer_length: {summary.final_answer_length}")
    print(f"citation_count: {summary.citation_count}")
    print(f"artifact_count: {summary.artifact_count}")
    print(f"trace_summary_key_count: {summary.trace_summary_key_count}")


def run_smoke(args: argparse.Namespace, summary: SmokeSummary) -> None:
    request = build_request(args)
    saw_final = False

    try:
        with urllib.request.urlopen(request, timeout=args.timeout_seconds) as response:
            for frame in iter_sse_frames(response):
                parsed = parse_sse_frame(frame)
                if parsed is None:
                    continue
                event_name, data = parsed
                if event_name not in ALLOWED_EVENTS:
                    raise SmokeError("unknown_event")
                summary.event_order.append(event_name)
                if event_name == "error":
                    raise SmokeError("sse_error")
                if event_name == "final":
                    update_final_summary(summary, data)
                    saw_final = True
                    break
    except urllib.error.HTTPError as exc:
        raise SmokeError(f"http_{exc.code}") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError | socket.timeout):
            raise SmokeError("timeout") from exc
        raise SmokeError("connection_error") from exc
    except TimeoutError as exc:
        raise SmokeError("timeout") from exc
    except socket.timeout as exc:
        raise SmokeError("timeout") from exc

    if not saw_final:
        raise SmokeError("no_final")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = SmokeSummary(endpoint=safe_endpoint(args.url))
    try:
        run_smoke(args, summary)
    except SmokeError as exc:
        print_summary(summary)
        print(f"error: {exc.code}", file=sys.stderr)
        return 1
    except Exception:
        print_summary(summary)
        print("error: unexpected_failure", file=sys.stderr)
        return 1

    print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
