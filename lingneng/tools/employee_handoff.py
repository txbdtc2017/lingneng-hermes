from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from lingneng.config.settings import LingNengSettings
from lingneng.routing.employees import LingNengEmployeeDirectory
from lingneng.routing.models import (
    NormalizedRouteDecision,
    RouteToolCandidate,
    failure_tool_result,
    normalize_handoff_command,
)
from lingneng.routing.store import (
    LingNengRoutePendingStore,
    PendingRouteConfirmation,
    PendingRouteConfirmationRecord,
)
from lingneng.schemas.chat_events import RouteCandidate
from lingneng.schemas.chat_request import ChatStreamRequest, EmployeeType
from lingneng.session.keys import ResolvedSessionKey


@dataclass(frozen=True)
class EmployeeHandoffContext:
    settings: LingNengSettings
    tenant_id: str
    user_id: str
    conversation_id: str | None
    session_key: str
    request_id: str
    query_message_id: str | None
    query: str
    current_employee_type: EmployeeType
    confirmed_employee_type: EmployeeType | None
    confirmation_message_id: str | None
    employee_directory: LingNengEmployeeDirectory
    pending_store: LingNengRoutePendingStore | None


_CURRENT_CONTEXT: ContextVar[EmployeeHandoffContext | None] = ContextVar(
    "lingneng_employee_handoff_context",
    default=None,
)


def build_handoff_request_context(
    *,
    settings: LingNengSettings,
    request: ChatStreamRequest,
    resolved_session: ResolvedSessionKey,
    pending_store: LingNengRoutePendingStore | None = None,
) -> EmployeeHandoffContext:
    return EmployeeHandoffContext(
        settings=settings,
        tenant_id=resolved_session.tenant_id,
        user_id=resolved_session.user_id,
        conversation_id=resolved_session.conversation_id,
        session_key=resolved_session.session_key,
        request_id=request.request_id,
        query_message_id=request.query.message_id,
        query=request.query.content,
        current_employee_type=request.employee.employee_type,
        confirmed_employee_type=request.routing.confirmed_employee_type,
        confirmation_message_id=request.routing.confirmation_message_id,
        employee_directory=LingNengEmployeeDirectory(settings),
        pending_store=pending_store,
    )


@contextmanager
def employee_handoff_context(
    context: EmployeeHandoffContext,
) -> Iterator[None]:
    token = _CURRENT_CONTEXT.set(context)
    try:
        yield
    finally:
        _CURRENT_CONTEXT.reset(token)


def employee_handoff_handler(args: dict[str, Any] | None = None, **kwargs: Any) -> str:
    del kwargs
    context = _CURRENT_CONTEXT.get()
    if context is None:
        return _json_failure(
            "HANDOFF_CONTEXT_MISSING",
            "LingNeng handoff context is not configured.",
        )
    if not isinstance(args, Mapping):
        return _json_failure(
            "INVALID_HANDOFF_ARGUMENT",
            "Employee handoff arguments must be an object.",
        )
    prepared_args = _prepare_handoff_args(args, context)
    if _has_unsupported_employee(prepared_args, context):
        return _json_failure(
            "INVALID_TARGET_EMPLOYEE",
            "Target employee is not supported.",
        )

    try:
        command = normalize_handoff_command(
            prepared_args,
            current_employee_type=context.current_employee_type,
            reason_max_chars=context.settings.route_reason_max_chars,
            reply_max_chars=context.settings.route_reply_max_chars,
            allow_current_suggest=(
                context.confirmed_employee_type == context.current_employee_type
            ),
        )
    except (TypeError, ValueError, ValidationError):
        return _json_failure(
            "INVALID_HANDOFF_ARGUMENT",
            "Employee handoff arguments are invalid.",
        )

    if context.confirmed_employee_type is not None:
        return _json_result(_confirmed_decision_result(context, command))

    if command.action == "current":
        return _json_result(_current_result(context, command.confidence, command.reason))
    if command.action == "suggest":
        assert command.target_employee_type is not None
        assert command.reply is not None
        return _json_result(
            _suggestion_result(
                context,
                target_employee_type=command.target_employee_type,
                confidence=command.confidence,
                reason=command.reason,
                reply=command.reply,
            )
        )

    assert command.action == "confirm"
    assert command.reply is not None
    candidates = _normalized_candidates(command.candidates, context)
    degradation_codes: list[str] = []
    pending_metadata = _pending_metadata_without_save()
    if context.conversation_id is None:
        degradation_codes.append("conversation_id_missing")
        pending_metadata = {
            "saved": False,
            "reason": "conversation_id_missing",
        }
    elif context.pending_store is None:
        pending_metadata = {
            "saved": False,
            "reason": "pending_store_missing",
        }

    decision = NormalizedRouteDecision(
        route_event_type="route_confirm_required",
        terminal=True,
        current_employee_type=context.current_employee_type,
        confidence=command.confidence,
        reason=command.reason,
        reply=command.reply,
        public_reply=command.reply,
        query=context.query,
        candidates=candidates,
        degradation_codes=degradation_codes,
    )
    result = decision.public_tool_result()

    if context.conversation_id is not None and context.pending_store is not None:
        pending_metadata = _safe_save_pending_confirmation(
            context,
            clarification_question=command.reply,
            candidates=candidates,
        )
    result["pending_confirmation"] = pending_metadata
    return _json_result(result)


def _current_result(
    context: EmployeeHandoffContext,
    confidence: float,
    reason: str,
) -> dict[str, Any]:
    decision = NormalizedRouteDecision(
        route_event_type="route_result",
        terminal=False,
        current_employee_type=context.current_employee_type,
        target_employee_type=context.current_employee_type,
        confidence=confidence,
        reason=reason,
        public_reply="",
        need_confirm=False,
        is_current_employee=True,
    )
    return decision.public_tool_result()


def _suggestion_result(
    context: EmployeeHandoffContext,
    *,
    target_employee_type: EmployeeType,
    confidence: float,
    reason: str,
    reply: str,
) -> dict[str, Any]:
    decision = NormalizedRouteDecision(
        route_event_type="route_suggestion",
        terminal=True,
        current_employee_type=context.current_employee_type,
        target_employee_type=target_employee_type,
        confidence=confidence,
        reason=reason,
        reply=reply,
        public_reply=reply,
    )
    return decision.public_tool_result()


def _confirmed_decision_result(
    context: EmployeeHandoffContext,
    command: Any,
) -> dict[str, Any]:
    confirmed = context.confirmed_employee_type
    assert confirmed is not None
    pending = _find_pending_confirmation(context)
    confirmation = _confirmation_metadata(context, pending, pending_consumed=False)

    if pending is not None and not _pending_contains_employee(pending, confirmed):
        result = failure_tool_result(
            "INVALID_TARGET_EMPLOYEE",
            "Confirmed employee is not a pending route candidate.",
        )
        result["confirmation"] = confirmation
        return result

    if pending is not None:
        consumed = context.pending_store.consume(pending.pending_id)
        confirmation = _confirmation_metadata(
            context,
            pending,
            pending_consumed=consumed is not None,
        )

    if confirmed == context.current_employee_type:
        result = _current_result(context, 1.0, command.reason)
    else:
        result = _suggestion_result(
            context,
            target_employee_type=confirmed,
            confidence=1.0,
            reason=_confirmed_reason(command.reason, pending, confirmed),
            reply=_confirmed_reply(context, command.reply, confirmed),
        )
    result["confirmation"] = confirmation
    return result


def _safe_save_pending_confirmation(
    context: EmployeeHandoffContext,
    *,
    clarification_question: str,
    candidates: list[RouteToolCandidate],
) -> dict[str, Any]:
    try:
        return _save_pending_confirmation(
            context,
            clarification_question=clarification_question,
            candidates=candidates,
        )
    except Exception:
        return {
            "saved": False,
            "reason": "pending_store_error",
        }


def _save_pending_confirmation(
    context: EmployeeHandoffContext,
    *,
    clarification_question: str,
    candidates: list[RouteToolCandidate],
) -> dict[str, Any]:
    assert context.conversation_id is not None
    assert context.pending_store is not None
    record = context.pending_store.save(
        PendingRouteConfirmation(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            conversation_id=context.conversation_id,
            request_id=context.request_id,
            query_message_id=context.query_message_id,
            current_employee_type=context.current_employee_type,
            previous_user_query=context.query,
            clarification_question=clarification_question,
            candidates=[_to_route_candidate(candidate) for candidate in candidates],
        )
    )
    return {
        "saved": True,
        "pending_id": record.pending_id,
        "expires_at": record.expires_at.isoformat(),
    }


def _find_pending_confirmation(
    context: EmployeeHandoffContext,
) -> PendingRouteConfirmationRecord | None:
    if context.conversation_id is None or context.pending_store is None:
        return None
    if context.confirmation_message_id:
        return context.pending_store.find_by_message_id(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            conversation_id=context.conversation_id,
            current_employee_type=context.current_employee_type,
            query_message_id=context.confirmation_message_id,
        )
    return context.pending_store.latest(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        conversation_id=context.conversation_id,
        current_employee_type=context.current_employee_type,
    )


def _confirmation_metadata(
    context: EmployeeHandoffContext,
    pending: PendingRouteConfirmationRecord | None,
    *,
    pending_consumed: bool,
) -> dict[str, Any]:
    assert context.confirmed_employee_type is not None
    metadata: dict[str, Any] = {
        "confirmed_employee_type": context.confirmed_employee_type.value,
        "confirmation_message_id": context.confirmation_message_id,
        "matched_pending": pending is not None,
        "pending_consumed": pending_consumed,
    }
    if pending is not None:
        metadata["pending_id"] = pending.pending_id
    return metadata


def _confirmed_reason(
    fallback_reason: str,
    pending: PendingRouteConfirmationRecord | None,
    confirmed: EmployeeType,
) -> str:
    if pending is not None:
        for candidate in pending.candidates:
            if candidate.employee_type == confirmed:
                return candidate.reason
    return fallback_reason


def _confirmed_reply(
    context: EmployeeHandoffContext,
    reply: str | None,
    confirmed: EmployeeType,
) -> str:
    if reply:
        return reply
    label = context.employee_directory.label_for(confirmed)
    return f"已确认交给{label}处理。"


def _pending_contains_employee(
    pending: PendingRouteConfirmationRecord,
    employee_type: EmployeeType,
) -> bool:
    return any(candidate.employee_type == employee_type for candidate in pending.candidates)


def _normalized_candidates(
    candidates: list[RouteToolCandidate],
    context: EmployeeHandoffContext,
) -> list[RouteToolCandidate]:
    return [
        RouteToolCandidate(
            employee_type=candidate.employee_type,
            confidence=candidate.confidence,
            label=context.employee_directory.label_for(candidate.employee_type),
            reason=candidate.reason,
        )
        for candidate in candidates
    ]


def _to_route_candidate(candidate: RouteToolCandidate) -> RouteCandidate:
    return RouteCandidate.model_validate(candidate.model_dump(mode="json"))


def _has_unsupported_employee(
    args: Mapping[str, Any],
    context: EmployeeHandoffContext,
) -> bool:
    target_employee_type = args.get("target_employee_type")
    if (
        target_employee_type is not None
        and context.employee_directory.get(target_employee_type) is None
    ):
        return True
    candidates = args.get("candidates")
    if not isinstance(candidates, list):
        return False
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        employee_type = candidate.get("employee_type")
        if (
            employee_type is not None
            and context.employee_directory.get(employee_type) is None
        ):
            return True
    return False


def _prepare_handoff_args(
    args: Mapping[str, Any],
    context: EmployeeHandoffContext,
) -> dict[str, Any]:
    prepared = dict(args)
    if (
        prepared.get("action") == "current"
        and prepared.get("target_employee_type") is None
    ):
        prepared["target_employee_type"] = context.current_employee_type
    return prepared


def _pending_metadata_without_save() -> dict[str, bool]:
    return {"saved": False}


def _json_failure(code: str, message: str) -> str:
    return _json_result(failure_tool_result(code, message))


def _json_result(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False)
