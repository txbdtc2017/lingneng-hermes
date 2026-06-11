import pytest
from pydantic import ValidationError

from lingneng.routing.models import (
    EmployeeHandoffCommand,
    NormalizedRouteDecision,
    failure_tool_result,
    normalize_handoff_command,
)
from lingneng.schemas.chat_request import EmployeeType


def test_normalizes_suggest_command():
    command = normalize_handoff_command(
        {
            "action": "suggest",
            "target_employee_type": "marketing_content_creator",
            "confidence": 0.86,
            "reason": "\x00 需要生成可直接发布的营销内容\n",
            "reply": " 这个问题更适合由营销内容创作处理。\x1f",
        },
        current_employee_type=EmployeeType.MARKETING_PLANNER,
        reason_max_chars=300,
        reply_max_chars=500,
    )

    assert isinstance(command, EmployeeHandoffCommand)
    assert command.action == "suggest"
    assert command.target_employee_type is EmployeeType.MARKETING_CONTENT_CREATOR
    assert command.reason == "需要生成可直接发布的营销内容"
    assert command.reply == "这个问题更适合由营销内容创作处理。"


def test_confirm_rejects_duplicate_candidates():
    with pytest.raises(ValidationError):
        normalize_handoff_command(
            {
                "action": "confirm",
                "confidence": 0.5,
                "reason": "方向不明确",
                "reply": "请选择一个方向。",
                "candidates": [
                    {
                        "employee_type": "marketing_planner",
                        "confidence": 0.6,
                        "label": "营销策划",
                        "reason": "活动方案",
                    },
                    {
                        "employee_type": "marketing_planner",
                        "confidence": 0.5,
                        "label": "营销策划",
                        "reason": "也是活动方案",
                    },
                ],
            },
            current_employee_type=EmployeeType.MARKETING_CONTENT_CREATOR,
            reason_max_chars=300,
            reply_max_chars=500,
        )


def test_current_requires_current_target_employee():
    with pytest.raises(ValidationError):
        normalize_handoff_command(
            {
                "action": "current",
                "target_employee_type": "marketing_content_creator",
                "confidence": 0.9,
                "reason": "当前员工可以处理",
            },
            current_employee_type=EmployeeType.MARKETING_PLANNER,
            reason_max_chars=300,
            reply_max_chars=500,
        )


def test_suggest_rejects_current_employee_target():
    with pytest.raises(ValidationError):
        normalize_handoff_command(
            {
                "action": "suggest",
                "target_employee_type": "marketing_planner",
                "confidence": 0.9,
                "reason": "当前员工可以处理",
                "reply": "由当前员工继续处理。",
            },
            current_employee_type=EmployeeType.MARKETING_PLANNER,
            reason_max_chars=300,
            reply_max_chars=500,
        )


@pytest.mark.parametrize("raw_args", [None, [], "not-object"])
def test_normalize_handoff_command_rejects_non_object_arguments(raw_args):
    with pytest.raises(ValueError, match="handoff arguments must be an object"):
        normalize_handoff_command(
            raw_args,
            current_employee_type=EmployeeType.MARKETING_PLANNER,
            reason_max_chars=300,
            reply_max_chars=500,
        )


def test_public_decision_dump_excludes_private_fields():
    decision = NormalizedRouteDecision(
        route_event_type="route_suggestion",
        terminal=True,
        current_employee_type=EmployeeType.MARKETING_PLANNER,
        target_employee_type=EmployeeType.MARKETING_CONTENT_CREATOR,
        confidence=0.86,
        reason="需要生成可直接发布的营销内容",
        reply="这个问题更适合由营销内容创作处理。",
        candidates=[],
        public_reply="这个问题更适合由营销内容创作处理。",
        degradation_codes=[],
    )

    data = decision.public_tool_result()

    assert data["success"] is True
    assert data["tool_name"] == "employee_handoff"
    assert data["route_event_type"] == "route_suggestion"
    assert data["route"] == {
        "current_employee_type": "marketing_planner",
        "target_employee_type": "marketing_content_creator",
        "confidence": 0.86,
        "reason": "需要生成可直接发布的营销内容",
        "reply": "这个问题更适合由营销内容创作处理。",
    }
    assert data["pending_confirmation"] is None
    assert forbidden_keys().isdisjoint(data)
    assert forbidden_keys().isdisjoint(data["route"])


def test_route_result_public_payload_is_bridge_readable():
    decision = NormalizedRouteDecision(
        route_event_type="route_result",
        terminal=False,
        current_employee_type=EmployeeType.MARKETING_PLANNER,
        target_employee_type=EmployeeType.MARKETING_PLANNER,
        confidence=1.0,
        reason="当前员工可以处理",
        public_reply="",
        need_confirm=False,
        is_current_employee=True,
    )

    data = decision.public_tool_result()

    assert data["route_event_type"] == "route_result"
    assert data["route"] == {
        "target_employee_type": "marketing_planner",
        "confidence": 1.0,
        "need_confirm": False,
        "is_current_employee": True,
    }


def test_confirm_public_payload_includes_query_candidates_reply():
    decision = NormalizedRouteDecision(
        route_event_type="route_confirm_required",
        terminal=True,
        current_employee_type=EmployeeType.MARKETING_PLANNER,
        confidence=0.6,
        reason="方向不明确",
        reply="请选择营销策划还是内容创作。",
        public_reply="请选择营销策划还是内容创作。",
        query="做一个营销活动",
        candidates=[
            {
                "employee_type": "marketing_planner",
                "confidence": 0.6,
                "label": "营销策划",
                "reason": "活动方案",
            },
            {
                "employee_type": "marketing_content_creator",
                "confidence": 0.55,
                "label": "营销内容创作",
                "reason": "文案内容",
            },
        ],
    )

    data = decision.public_tool_result()

    assert data["route_event_type"] == "route_confirm_required"
    assert data["route"] == {
        "query": "做一个营销活动",
        "candidates": [
            {
                "employee_type": "marketing_planner",
                "confidence": 0.6,
                "label": "营销策划",
                "reason": "活动方案",
            },
            {
                "employee_type": "marketing_content_creator",
                "confidence": 0.55,
                "label": "营销内容创作",
                "reason": "文案内容",
            },
        ],
        "reply": "请选择营销策划还是内容创作。",
    }


def test_failure_tool_result_is_public_envelope_only():
    data = failure_tool_result("INVALID_TARGET_EMPLOYEE", "Target not supported.")

    assert data == {
        "success": False,
        "tool_name": "employee_handoff",
        "code": "INVALID_TARGET_EMPLOYEE",
        "message": "Target not supported.",
    }


def forbidden_keys():
    return {
        "args",
        "request",
        "payload",
        "history",
        "traceback",
        "exception",
        "api_key",
        "token",
        "secret",
    }
