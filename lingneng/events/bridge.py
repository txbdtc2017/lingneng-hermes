from __future__ import annotations

from typing import Any

from lingneng.schemas.chat_events import (
    AgentStepEvent,
    AnswerDeltaEvent,
    FinalEvent,
    RunStartedEvent,
)


def _tool_step_id(sequence: int) -> str:
    return f"tool-{sequence}"


def _public_tool_name(tool_name: str) -> str:
    safe = "".join(
        ch for ch in tool_name if ch.isascii() and (ch.isalnum() or ch in {"_", "-", "."})
    )
    return safe or "tool"


def run_started(run_id: str, request_id: str) -> RunStartedEvent:
    return RunStartedEvent(run_id=run_id, request_id=request_id)


def answer_delta(text: str, sequence: int) -> AnswerDeltaEvent:
    return AnswerDeltaEvent(text=text, sequence=sequence)


def agent_step_started(
    sequence: int,
    tool_name: str,
    preview: str | None = None,
) -> AgentStepEvent:
    safe_name = _public_tool_name(tool_name)
    return AgentStepEvent(
        sequence=sequence,
        step_id=_tool_step_id(sequence),
        phase="tool",
        status="started",
        title=safe_name,
        short_text=f"Starting {safe_name}.",
        summary=preview,
        refs=[],
    )


def agent_step_completed(
    sequence: int,
    tool_name: str,
    duration: float | None = None,
    is_error: bool = False,
    result: Any = None,
) -> AgentStepEvent:
    safe_name = _public_tool_name(tool_name)
    if is_error:
        return AgentStepEvent(
            sequence=sequence,
            step_id=_tool_step_id(sequence),
            phase="tool",
            status="failed",
            title=safe_name,
            short_text=f"{safe_name} failed.",
            summary="Tool failed with a public error summary.",
            refs=[],
        )

    summary = f"Duration: {duration:.2f}s" if duration is not None else None
    return AgentStepEvent(
        sequence=sequence,
        step_id=_tool_step_id(sequence),
        phase="tool",
        status="succeeded",
        title=safe_name,
        short_text=f"Completed {safe_name}.",
        summary=summary,
        refs=[],
    )


def agent_step_skipped(
    sequence: int,
    tool_name: str,
    reason: str | None = None,
) -> AgentStepEvent:
    safe_name = _public_tool_name(tool_name)
    return AgentStepEvent(
        sequence=sequence,
        step_id=_tool_step_id(sequence),
        phase="tool",
        status="skipped",
        title=safe_name,
        short_text=f"Skipped {safe_name}.",
        summary=reason,
        refs=[],
    )


def final_answer(run_id: str, answer: str) -> FinalEvent:
    return FinalEvent(run_id=run_id, status="succeeded", answer=answer)
