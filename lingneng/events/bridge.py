from __future__ import annotations

from lingneng.schemas.chat_events import AnswerDeltaEvent, FinalEvent, RunStartedEvent


def run_started(run_id: str, request_id: str) -> RunStartedEvent:
    return RunStartedEvent(run_id=run_id, request_id=request_id)


def answer_delta(text: str, sequence: int) -> AnswerDeltaEvent:
    return AnswerDeltaEvent(text=text, sequence=sequence)


def final_answer(run_id: str, answer: str) -> FinalEvent:
    return FinalEvent(run_id=run_id, status="succeeded", answer=answer)
