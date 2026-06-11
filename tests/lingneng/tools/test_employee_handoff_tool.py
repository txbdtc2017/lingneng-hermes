import json

import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.routing.store import LingNengRoutePendingStore
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from lingneng.tools.employee_handoff import (
    build_handoff_request_context,
    employee_handoff_context,
    employee_handoff_handler,
)
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def settings(tmp_path):
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_ROUTE_REASON_MAX_CHARS": "120",
            "LINGNENG_ROUTE_REPLY_MAX_CHARS": "180",
        }
    )


def context(tmp_path, payload=None, pending_store=None):
    request = ChatStreamRequest.model_validate(payload or _payload_without_routing())
    cfg = settings(tmp_path)
    return build_handoff_request_context(
        settings=cfg,
        request=request,
        resolved_session=resolve_session_key(request),
        pending_store=pending_store
        if pending_store is not None
        else LingNengRoutePendingStore(
            cfg.route_pending_db_path,
            ttl_seconds=cfg.route_pending_ttl_seconds,
        ),
    )


def dispatch(ctx, args):
    with employee_handoff_context(ctx):
        return json.loads(employee_handoff_handler(args))


def test_current_action_returns_route_result(tmp_path):
    payload = _payload_without_routing()
    payload["employee"]["employee_type"] = "marketing_content_creator"
    result = dispatch(
        context(tmp_path, payload),
        {
            "action": "current",
            "target_employee_type": "marketing_content_creator",
            "confidence": 0.9,
            "reason": "当前员工可以处理",
        },
    )

    assert result["success"] is True
    assert result["route_event_type"] == "route_result"
    assert result["terminal"] is False
    assert result["route"] == {
        "target_employee_type": "marketing_content_creator",
        "confidence": 0.9,
        "need_confirm": False,
        "is_current_employee": True,
    }


def test_current_action_defaults_to_context_employee_when_target_omitted(tmp_path):
    payload = _payload_without_routing()
    payload["employee"]["employee_type"] = "marketing_content_creator"
    result = dispatch(
        context(tmp_path, payload),
        {
            "action": "current",
            "confidence": 0.9,
            "reason": "当前员工可以处理",
        },
    )

    assert result["success"] is True
    assert result["route_event_type"] == "route_result"
    assert result["terminal"] is False
    assert result["route"] == {
        "target_employee_type": "marketing_content_creator",
        "confidence": 0.9,
        "need_confirm": False,
        "is_current_employee": True,
    }


def test_suggest_action_returns_route_suggestion(tmp_path):
    payload = _payload_without_routing()
    payload["employee"]["employee_type"] = "marketing_planner"
    result = dispatch(
        context(tmp_path, payload),
        {
            "action": "suggest",
            "target_employee_type": "marketing_content_creator",
            "confidence": 0.86,
            "reason": "需要生成可直接发布的营销内容",
            "reply": "这个问题更适合由营销内容创作处理，我为你切换到对应数字员工。",
        },
    )

    assert result["success"] is True
    assert result["route_event_type"] == "route_suggestion"
    assert result["terminal"] is True
    assert result["public_reply"] == result["route"]["reply"]
    assert result["route"]["current_employee_type"] == "marketing_planner"
    assert result["route"]["target_employee_type"] == "marketing_content_creator"


def test_confirm_action_saves_pending_confirmation(tmp_path):
    payload = _payload_without_routing()
    payload["employee"]["employee_type"] = "marketing_planner"
    result = dispatch(
        context(tmp_path, payload),
        {
            "action": "confirm",
            "confidence": 0.52,
            "reason": "问题可能属于营销策划或内容创作",
            "reply": "请选择营销策划还是营销内容创作。",
            "candidates": [
                {
                    "employee_type": "marketing_planner",
                    "confidence": 0.62,
                    "label": "营销策划",
                    "reason": "需要活动方案",
                },
                {
                    "employee_type": "marketing_content_creator",
                    "confidence": 0.58,
                    "label": "营销内容创作",
                    "reason": "需要文案内容",
                },
            ],
        },
    )

    assert result["success"] is True
    assert result["route_event_type"] == "route_confirm_required"
    assert result["terminal"] is True
    assert result["pending_confirmation"]["saved"] is True
    assert result["pending_confirmation"]["pending_id"].startswith("route_pending_")
    assert result["pending_confirmation"]["expires_at"]
    assert result["route"]["query"] == "请生成一段会员运营文案"
    assert result["route"]["candidates"][0]["employee_type"] == "marketing_planner"


def test_confirm_action_without_conversation_does_not_save_pending(tmp_path):
    payload = _payload_without_routing()
    payload["conversation_id"] = None
    result = dispatch(
        context(tmp_path, payload),
        {
            "action": "confirm",
            "confidence": 0.52,
            "reason": "问题可能属于营销策划或内容创作",
            "reply": "请选择营销策划还是营销内容创作。",
            "candidates": _confirm_candidates(),
        },
    )

    assert result["success"] is True
    assert result["pending_confirmation"] == {
        "saved": False,
        "reason": "conversation_id_missing",
    }
    assert result["degradation_codes"] == ["conversation_id_missing"]


def test_confirm_action_handles_pending_store_save_error_safely(tmp_path):
    payload = _payload_without_routing()
    payload["employee"]["employee_type"] = "marketing_planner"
    result = dispatch(
        context(tmp_path, payload, pending_store=FailingPendingStore()),
        {
            "action": "confirm",
            "confidence": 0.52,
            "reason": "问题可能属于营销策划或内容创作",
            "reply": "请选择营销策划还是营销内容创作。",
            "candidates": _confirm_candidates(),
        },
    )

    assert result["success"] is True
    assert result["route_event_type"] == "route_confirm_required"
    assert result["pending_confirmation"] == {
        "saved": False,
        "reason": "pending_store_error",
    }
    text = json.dumps(result, ensure_ascii=False).lower()
    for forbidden in [
        "/private/tmp/route_pending.sqlite3",
        "secret-token",
        "traceback",
        "exception",
        "permission denied",
    ]:
        assert forbidden not in text


def test_confirmed_employee_consumes_matching_pending_record(tmp_path):
    pending_store = LingNengRoutePendingStore(
        tmp_path / "route_pending.sqlite3",
        ttl_seconds=600,
    )
    first_payload = _payload_without_routing()
    first_payload["employee"]["employee_type"] = "marketing_planner"
    pending_result = dispatch(
        context(tmp_path, first_payload, pending_store=pending_store),
        {
            "action": "confirm",
            "confidence": 0.52,
            "reason": "问题可能属于营销策划或内容创作",
            "reply": "请选择营销策划还是营销内容创作。",
            "candidates": _confirm_candidates(),
        },
    )

    confirmed_payload = _payload_without_routing()
    confirmed_payload["employee"]["employee_type"] = "marketing_planner"
    confirmed_payload["routing"] = {
        "confirmed_employee_type": "marketing_content_creator",
        "confirmation_message_id": "msg-001",
    }
    result = dispatch(
        context(tmp_path, confirmed_payload, pending_store=pending_store),
        {
            "action": "suggest",
            "target_employee_type": "marketing_content_creator",
            "confidence": 0.9,
            "reason": "用户已确认由营销内容创作处理",
            "reply": "已确认交给营销内容创作处理。",
        },
    )

    assert result["success"] is True
    assert result["route_event_type"] == "route_suggestion"
    assert result["terminal"] is True
    assert result["confirmation"] == {
        "confirmed_employee_type": "marketing_content_creator",
        "confirmation_message_id": "msg-001",
        "matched_pending": True,
        "pending_consumed": True,
        "pending_id": pending_result["pending_confirmation"]["pending_id"],
    }
    assert (
        pending_store.consume(pending_result["pending_confirmation"]["pending_id"])
        is None
    )


def test_confirmed_employee_without_pending_record_emits_route_decision(tmp_path):
    pending_store = LingNengRoutePendingStore(
        tmp_path / "route_pending.sqlite3",
        ttl_seconds=600,
    )
    payload = _payload_without_routing()
    payload["employee"]["employee_type"] = "marketing_planner"
    payload["routing"] = {
        "confirmed_employee_type": "marketing_content_creator",
    }
    result = dispatch(
        context(tmp_path, payload, pending_store=pending_store),
        {
            "action": "suggest",
            "target_employee_type": "marketing_content_creator",
            "confidence": 0.9,
            "reason": "用户已确认由营销内容创作处理",
            "reply": "已确认交给营销内容创作处理。",
        },
    )

    assert result["success"] is True
    assert result["route_event_type"] == "route_suggestion"
    assert result["route"]["target_employee_type"] == "marketing_content_creator"
    assert result["confirmation"] == {
        "confirmed_employee_type": "marketing_content_creator",
        "confirmation_message_id": None,
        "matched_pending": False,
        "pending_consumed": False,
    }


def test_confirmed_employee_with_unmatched_message_id_does_not_consume_latest_pending(
    tmp_path,
):
    pending_store = LingNengRoutePendingStore(
        tmp_path / "route_pending.sqlite3",
        ttl_seconds=600,
    )
    first_payload = _payload_without_routing()
    first_payload["employee"]["employee_type"] = "marketing_planner"
    pending_result = dispatch(
        context(tmp_path, first_payload, pending_store=pending_store),
        {
            "action": "confirm",
            "confidence": 0.52,
            "reason": "问题可能属于营销策划或内容创作",
            "reply": "请选择营销策划还是营销内容创作。",
            "candidates": _confirm_candidates(),
        },
    )

    confirmed_payload = _payload_without_routing()
    confirmed_payload["employee"]["employee_type"] = "marketing_planner"
    confirmed_payload["routing"] = {
        "confirmed_employee_type": "marketing_content_creator",
        "confirmation_message_id": "not-the-original-message",
    }
    result = dispatch(
        context(tmp_path, confirmed_payload, pending_store=pending_store),
        {
            "action": "suggest",
            "target_employee_type": "marketing_content_creator",
            "confidence": 0.9,
            "reason": "用户已确认由营销内容创作处理",
            "reply": "已确认交给营销内容创作处理。",
        },
    )

    assert result["success"] is True
    assert result["route_event_type"] == "route_suggestion"
    assert result["confirmation"] == {
        "confirmed_employee_type": "marketing_content_creator",
        "confirmation_message_id": "not-the-original-message",
        "matched_pending": False,
        "pending_consumed": False,
    }
    assert (
        pending_store.consume(pending_result["pending_confirmation"]["pending_id"])
        is not None
    )


def test_confirmed_employee_rejects_non_candidate_pending_choice(tmp_path):
    pending_store = LingNengRoutePendingStore(
        tmp_path / "route_pending.sqlite3",
        ttl_seconds=600,
    )
    first_payload = _payload_without_routing()
    first_payload["employee"]["employee_type"] = "marketing_planner"
    dispatch(
        context(tmp_path, first_payload, pending_store=pending_store),
        {
            "action": "confirm",
            "confidence": 0.52,
            "reason": "问题可能属于营销策划或内容创作",
            "reply": "请选择营销策划还是营销内容创作。",
            "candidates": _confirm_candidates(),
        },
    )

    confirmed_payload = _payload_without_routing()
    confirmed_payload["employee"]["employee_type"] = "marketing_planner"
    confirmed_payload["routing"] = {
        "confirmed_employee_type": "member_operator",
        "confirmation_message_id": "msg-001",
    }
    result = dispatch(
        context(tmp_path, confirmed_payload, pending_store=pending_store),
        {
            "action": "suggest",
            "target_employee_type": "member_operator",
            "confidence": 0.9,
            "reason": "用户确认了会员运营",
            "reply": "交给会员运营处理。",
        },
    )

    assert result["success"] is False
    assert result["code"] == "INVALID_TARGET_EMPLOYEE"
    assert result["confirmation"]["matched_pending"] is True
    assert result["confirmation"]["pending_consumed"] is False


def test_handoff_without_context_fails_closed():
    result = json.loads(
        employee_handoff_handler(
            {
                "action": "suggest",
                "target_employee_type": "marketing_content_creator",
                "confidence": 0.8,
                "reason": "需要内容创作",
                "reply": "切换到内容员工。",
            }
        )
    )

    assert result["success"] is False
    assert result["code"] == "HANDOFF_CONTEXT_MISSING"


@pytest.mark.parametrize("args", [None, [], "not-object"])
def test_invalid_non_object_arguments_fail_closed(tmp_path, args):
    result = dispatch(context(tmp_path), args)

    assert result["success"] is False
    assert result["code"] == "INVALID_HANDOFF_ARGUMENT"


@pytest.mark.parametrize(
    "args",
    [
        {
            "action": "suggest",
            "target_employee_type": "unknown_employee",
            "confidence": 0.8,
            "reason": "未知员工",
            "reply": "切换。",
        },
        {
            "action": "confirm",
            "confidence": 0.5,
            "reason": "候选包含未知员工",
            "reply": "请选择。",
            "candidates": [
                {
                    "employee_type": "marketing_planner",
                    "confidence": 0.6,
                    "label": "营销策划",
                    "reason": "活动方案",
                },
                {
                    "employee_type": "unknown_employee",
                    "confidence": 0.5,
                    "label": "未知",
                    "reason": "未知",
                },
            ],
        },
    ],
)
def test_unsupported_target_or_candidate_employee_fails_closed(tmp_path, args):
    result = dispatch(context(tmp_path), args)

    assert result["success"] is False
    assert result["code"] == "INVALID_TARGET_EMPLOYEE"


def test_tool_result_excludes_forbidden_keys(tmp_path):
    result = dispatch(
        context(tmp_path),
        {
            "action": "suggest",
            "target_employee_type": "marketing_planner",
            "confidence": 0.8,
            "reason": "需要策划",
            "reply": "交给营销策划处理。",
        },
    )

    text = json.dumps(result, ensure_ascii=False)
    for forbidden in [
        "api_key",
        "secret",
        "token",
        "traceback",
        "history",
        "payload",
        "request",
        "args",
    ]:
        assert forbidden not in text


def _payload_without_routing() -> dict:
    payload = full_payload()
    payload["routing"] = {}
    return payload


def _confirm_candidates() -> list[dict[str, object]]:
    return [
        {
            "employee_type": "marketing_planner",
            "confidence": 0.62,
            "label": "营销策划",
            "reason": "需要活动方案",
        },
        {
            "employee_type": "marketing_content_creator",
            "confidence": 0.58,
            "label": "营销内容创作",
            "reason": "需要文案内容",
        },
    ]


class FailingPendingStore:
    def save(self, pending):
        del pending
        raise RuntimeError(
            "permission denied for /private/tmp/route_pending.sqlite3 "
            "token=secret-token traceback exception"
        )
