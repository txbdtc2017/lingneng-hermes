from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lingneng.schemas.chat_request import EmployeeType


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
ArtifactType = Literal["image", "document"]
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


class RouteCandidate(LingNengEventModel):
    employee_type: EmployeeType
    confidence: float = Field(ge=0, le=1)
    label: str
    reason: str


class RouteResultEvent(LingNengEventModel):
    target_employee_type: EmployeeType
    confidence: float = Field(ge=0, le=1)
    need_confirm: bool
    is_current_employee: bool


class RouteSuggestionEvent(LingNengEventModel):
    current_employee_type: EmployeeType
    target_employee_type: EmployeeType
    confidence: float = Field(ge=0, le=1)
    reason: str
    reply: str


class RouteConfirmRequiredEvent(LingNengEventModel):
    query: str
    candidates: list[RouteCandidate]
    reply: str

    @model_validator(mode="after")
    def validate_candidate_count(self) -> "RouteConfirmRequiredEvent":
        if len(self.candidates) < 2 or len(self.candidates) > 4:
            raise ValueError("route confirmation requires 2 to 4 candidates")
        employee_types = [candidate.employee_type for candidate in self.candidates]
        if len(employee_types) != len(set(employee_types)):
            raise ValueError("route confirmation candidates must be unique")
        return self


class ComplianceBlockEvent(LingNengEventModel):
    risk_level: str
    risk_categories: list[str]
    reply: str


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


class Artifact(LingNengEventModel):
    artifact_id: str
    artifact_type: ArtifactType
    source: str
    file_name: str
    mime_type: str
    url: str
    object_key: str
    format: str | None = None
    target_format: str | None = None
    conversion_required: bool = False
    conversion_owner: str | None = None


class ArtifactCreatedEvent(Artifact):
    pass


class FinalEvent(LingNengEventModel):
    run_id: str
    status: FinalStatus
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    trace_summary: dict[str, Any] = Field(
        default_factory=dict,
        exclude_if=lambda value: not value,
    )


class ErrorEvent(LingNengEventModel):
    run_id: str
    request_id: str
    code: str
    message: str
    trace_id: str
    recoverable: bool
