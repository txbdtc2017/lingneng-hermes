from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lingneng.schemas.chat_request import ChatStreamRequest


DegradationReason = Literal["conversation_id_missing"]


class ResolvedSessionKey(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_key: str
    tenant_id: str
    user_id: str
    conversation_id: str | None
    session_id: str
    employee_id: str | None
    employee_type: str
    degraded: bool = False
    degradation_reason: DegradationReason | None = None
    history_message_count: int = 0
    context_messages: list[dict[str, object]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_degradation_state(self) -> "ResolvedSessionKey":
        if self.degraded and self.degradation_reason is None:
            raise ValueError("degradation_reason is required when degraded")
        if not self.degraded and self.degradation_reason is not None:
            raise ValueError("degradation_reason must be None when not degraded")
        return self


def resolve_session_key(request: ChatStreamRequest) -> ResolvedSessionKey:
    tenant_id = _validate_session_key_segment("tenant_id", request.tenant_id)
    user_id = _validate_session_key_segment("user_id", request.user_id)
    employee_id = _optional_session_key_segment(
        "employee_id", request.employee.employee_id
    )
    employee_type = request.employee.employee_type.value
    employee_segment = _validate_session_key_segment(
        "employee_segment", employee_id or employee_type
    )
    conversation_id = _optional_session_key_segment(
        "conversation_id", request.conversation_id
    )
    degraded = False
    degradation_reason: DegradationReason | None = None

    if conversation_id:
        business_session_id = _validate_session_key_segment(
            "conversation_id", conversation_id
        )
    else:
        business_session_id = _validate_session_key_segment(
            "session_id", request.session_id
        )
        degraded = True
        degradation_reason = "conversation_id_missing"

    return ResolvedSessionKey(
        session_key=f"{tenant_id}:{user_id}:{employee_segment}:{business_session_id}",
        tenant_id=tenant_id,
        user_id=user_id,
        conversation_id=conversation_id,
        session_id=request.session_id,
        employee_id=employee_id,
        employee_type=employee_type,
        degraded=degraded,
        degradation_reason=degradation_reason,
        history_message_count=len(request.history),
        context_messages=[],
    )


def _optional_session_key_segment(name: str, value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return _validate_session_key_segment(name, value)


def _validate_session_key_segment(name: str, value: str) -> str:
    if not value.strip():
        raise ValueError(f"{name} session key segment must not be empty")
    if ":" in value:
        raise ValueError(f"{name} session key segment must not contain ':'")
    return value
