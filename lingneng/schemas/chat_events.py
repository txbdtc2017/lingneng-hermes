from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


FORMAL_EVENT_NAMES = [
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
]

FINAL_STATUSES = {"succeeded", "degraded", "failed", "blocked"}
FinalStatus = Literal["succeeded", "degraded", "failed", "blocked"]
AgentStepPhase = Literal["tool"]
AgentStepStatus = Literal["started", "succeeded", "skipped", "failed"]


class LingNengEventModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunStartedEvent(LingNengEventModel):
    run_id: str
    request_id: str


class AnswerDeltaEvent(LingNengEventModel):
    text: str
    sequence: int


class AgentStepEvent(LingNengEventModel):
    sequence: int
    step_id: str
    phase: AgentStepPhase
    status: AgentStepStatus
    title: str
    short_text: str
    summary: str | None = None
    refs: list[dict] = Field(default_factory=list)


class Citation(LingNengEventModel):
    document_id: str
    source_file_id: str
    source_file_name: str
    page_no: int | None = None
    section_title: str | None = None
    chunk_id: str
    score: float = Field(ge=0)


class CitationDeltaEvent(Citation):
    pass


class RagContextEvent(LingNengEventModel):
    context: str
    citations: list[Citation] = Field(default_factory=list)
    status: Literal["hit", "empty", "failed"]
    metadata: dict[str, Any] = Field(default_factory=dict)


class FinalEvent(LingNengEventModel):
    run_id: str
    status: FinalStatus
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    artifacts: list[dict] = Field(default_factory=list)


class ErrorEvent(LingNengEventModel):
    run_id: str
    request_id: str
    code: str
    message: str
    trace_id: str
    recoverable: bool
