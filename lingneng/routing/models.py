from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from lingneng.schemas.chat_request import EmployeeType


RouteAction = Literal["current", "suggest", "confirm"]
RouteEventType = Literal[
    "route_result",
    "route_suggestion",
    "route_confirm_required",
]

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_LABEL_MAX_CHARS = 80


class RouteToolCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_type: EmployeeType
    confidence: float = Field(ge=0, le=1)
    label: str = ""
    reason: str

    @model_validator(mode="after")
    def _validate_public_reason(self) -> "RouteToolCandidate":
        if not self.reason:
            raise ValueError("candidate reason is required")
        return self


class EmployeeHandoffCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: RouteAction
    target_employee_type: EmployeeType | None = None
    confidence: float = Field(ge=0, le=1)
    reason: str
    reply: str | None = None
    candidates: list[RouteToolCandidate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_route_rules(
        self,
        info: ValidationInfo,
    ) -> "EmployeeHandoffCommand":
        if not self.reason:
            raise ValueError("reason is required")

        if self.action in {"suggest", "confirm"} and not self.reply:
            raise ValueError("reply is required for suggest and confirm actions")

        if self.action == "suggest" and self.target_employee_type is None:
            raise ValueError("target_employee_type is required for suggest action")

        current_employee_type = _context_employee_type(info)
        if (
            self.action == "suggest"
            and current_employee_type is not None
            and self.target_employee_type == current_employee_type
            and not _context_allow_current_suggest(info)
        ):
            raise ValueError("suggest action target must differ from current employee")

        if self.action == "confirm":
            employee_types = [candidate.employee_type for candidate in self.candidates]
            if len(employee_types) < 2 or len(employee_types) > 4:
                raise ValueError("confirm action requires 2 to 4 candidates")
            if len(employee_types) != len(set(employee_types)):
                raise ValueError("confirm candidates must have unique employee types")

        if self.action == "current":
            if (
                current_employee_type is not None
                and self.target_employee_type != current_employee_type
            ):
                raise ValueError("current action target must equal current employee")

        return self


class NormalizedRouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_event_type: RouteEventType
    terminal: bool
    current_employee_type: EmployeeType
    target_employee_type: EmployeeType | None = None
    confidence: float = Field(ge=0, le=1)
    reason: str
    reply: str | None = None
    candidates: list[RouteToolCandidate] = Field(default_factory=list)
    query: str | None = None
    need_confirm: bool = False
    is_current_employee: bool = False
    public_reply: str
    degradation_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_event_payload_fields(self) -> "NormalizedRouteDecision":
        if self.route_event_type == "route_result":
            if self.target_employee_type is None:
                raise ValueError("route_result requires target_employee_type")
        elif self.route_event_type == "route_suggestion":
            if self.target_employee_type is None:
                raise ValueError("route_suggestion requires target_employee_type")
            if not self.reason:
                raise ValueError("route_suggestion requires reason")
            if not self.reply:
                raise ValueError("route_suggestion requires reply")
        elif self.route_event_type == "route_confirm_required":
            if not self.query:
                raise ValueError("route_confirm_required requires query")
            if not self.reply:
                raise ValueError("route_confirm_required requires reply")
            employee_types = [candidate.employee_type for candidate in self.candidates]
            if len(employee_types) < 2 or len(employee_types) > 4:
                raise ValueError("route_confirm_required requires 2 to 4 candidates")
            if len(employee_types) != len(set(employee_types)):
                raise ValueError("route_confirm_required candidates must be unique")
        return self

    def public_tool_result(self) -> dict[str, Any]:
        return {
            "success": True,
            "tool_name": "employee_handoff",
            "route_event_type": self.route_event_type,
            "terminal": self.terminal,
            "public_reply": self.public_reply,
            "route": self._route_payload(),
            "pending_confirmation": None,
            "degradation_codes": list(self.degradation_codes),
        }

    def _route_payload(self) -> dict[str, Any]:
        if self.route_event_type == "route_result":
            assert self.target_employee_type is not None
            return {
                "target_employee_type": self.target_employee_type.value,
                "confidence": self.confidence,
                "need_confirm": self.need_confirm,
                "is_current_employee": self.is_current_employee,
            }
        if self.route_event_type == "route_suggestion":
            assert self.target_employee_type is not None
            assert self.reply is not None
            return {
                "current_employee_type": self.current_employee_type.value,
                "target_employee_type": self.target_employee_type.value,
                "confidence": self.confidence,
                "reason": self.reason,
                "reply": self.reply,
            }
        assert self.query is not None
        assert self.reply is not None
        return {
            "query": self.query,
            "candidates": [
                candidate.model_dump(mode="json") for candidate in self.candidates
            ],
            "reply": self.reply,
        }


def normalize_handoff_command(
    raw_args: Mapping[str, Any],
    *,
    current_employee_type: EmployeeType | str,
    reason_max_chars: int,
    reply_max_chars: int,
    allow_current_suggest: bool = False,
) -> EmployeeHandoffCommand:
    if not isinstance(raw_args, Mapping):
        raise ValueError("handoff arguments must be an object")

    current = EmployeeType(current_employee_type)
    prepared = dict(raw_args)
    prepared["reason"] = _sanitize_public_text(
        prepared.get("reason"),
        max_chars=reason_max_chars,
    )
    prepared["reply"] = _sanitize_public_text(
        prepared.get("reply"),
        max_chars=reply_max_chars,
    )
    prepared["candidates"] = [
        _sanitize_candidate(candidate, reason_max_chars=reason_max_chars)
        for candidate in prepared.get("candidates") or []
    ]
    return EmployeeHandoffCommand.model_validate(
        prepared,
        context={
            "allow_current_suggest": allow_current_suggest,
            "current_employee_type": current,
        },
    )


def failure_tool_result(code: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "tool_name": "employee_handoff",
        "code": _sanitize_public_text(code, max_chars=80) or "ERROR",
        "message": _sanitize_public_text(message, max_chars=300) or "Request failed.",
    }


def _sanitize_candidate(
    value: Any,
    *,
    reason_max_chars: int,
) -> Any:
    if not isinstance(value, Mapping):
        return value
    candidate = dict(value)
    candidate["label"] = _sanitize_public_text(
        candidate.get("label", ""),
        max_chars=_LABEL_MAX_CHARS,
    )
    candidate["reason"] = _sanitize_public_text(
        candidate.get("reason"),
        max_chars=reason_max_chars,
    )
    return candidate


def _sanitize_public_text(value: Any, *, max_chars: int) -> Any:
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    sanitized = _CONTROL_CHARS_RE.sub("", value).strip()
    return sanitized[:max_chars]


def _context_employee_type(info: ValidationInfo) -> EmployeeType | None:
    if not info.context:
        return None
    value = info.context.get("current_employee_type")
    if value is None:
        return None
    return EmployeeType(value)


def _context_allow_current_suggest(info: ValidationInfo) -> bool:
    return bool(info.context and info.context.get("allow_current_suggest"))
