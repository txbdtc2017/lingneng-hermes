import json

import pytest

from lingneng.events.bridge import route_events_from_tool_result
from lingneng.schemas.chat_events import (
    RouteConfirmRequiredEvent,
    RouteResultEvent,
    RouteSuggestionEvent,
)


def payload(event_type, route):
    return json.dumps(
        {
            "success": True,
            "tool_name": "employee_handoff",
            "route_event_type": event_type,
            "terminal": event_type != "route_result",
            "public_reply": route.get("reply", ""),
            "route": route,
        },
        ensure_ascii=False,
    )


def test_bridge_extracts_route_result():
    events, trace = route_events_from_tool_result(
        tool_name="employee_handoff",
        result=payload(
            "route_result",
            {
                "target_employee_type": "marketing_content_creator",
                "confidence": 0.9,
                "need_confirm": False,
                "is_current_employee": True,
            },
        ),
    )

    assert [type(event) for event in events] == [RouteResultEvent]
    assert trace["route_event_type"] == "route_result"


def test_bridge_extracts_route_suggestion():
    events, trace = route_events_from_tool_result(
        tool_name="employee_handoff",
        result=payload(
            "route_suggestion",
            {
                "current_employee_type": "marketing_planner",
                "target_employee_type": "marketing_content_creator",
                "confidence": 0.86,
                "reason": "需要生成营销内容",
                "reply": "交给营销内容创作处理。",
            },
        ),
    )

    assert [type(event) for event in events] == [RouteSuggestionEvent]
    assert events[0].target_employee_type == "marketing_content_creator"
    assert trace["target_employee_type"] == "marketing_content_creator"


def test_bridge_extracts_route_confirm_required():
    events, trace = route_events_from_tool_result(
        tool_name="employee_handoff",
        result=payload(
            "route_confirm_required",
            {
                "query": "做一个营销活动",
                "reply": "请选择一个处理方向。",
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
            },
        ),
    )

    assert [type(event) for event in events] == [RouteConfirmRequiredEvent]
    assert len(events[0].candidates) == 2
    assert trace["route_event_type"] == "route_confirm_required"


def test_bridge_ignores_unrelated_tool():
    events, trace = route_events_from_tool_result(
        tool_name="retrieve_rag",
        result=payload("route_result", {}),
    )

    assert events == []
    assert trace is None


@pytest.mark.parametrize(
    "result",
    [
        "{not-json",
        json.dumps([], ensure_ascii=False),
        json.dumps({"success": False}, ensure_ascii=False),
        json.dumps(
            {
                "success": True,
                "route_event_type": "unknown",
                "route": {},
            },
            ensure_ascii=False,
        ),
        json.dumps(
            {
                "success": True,
                "route_event_type": "route_result",
                "route": {"confidence": 0.9},
            },
            ensure_ascii=False,
        ),
        json.dumps(
            {
                "success": True,
                "route_event_type": "route_result",
                "route": {
                    "target_employee_type": "marketing_content_creator",
                    "confidence": 1.5,
                    "need_confirm": False,
                    "is_current_employee": True,
                },
            },
            ensure_ascii=False,
        ),
        json.dumps(
            {
                "success": True,
                "route_event_type": "route_result",
                "route": [],
            },
            ensure_ascii=False,
        ),
    ],
)
def test_bridge_fail_closed_for_malformed_route_payloads(result):
    events, trace = route_events_from_tool_result(
        tool_name="employee_handoff",
        result=result,
    )

    assert events == []
    assert trace is None


def test_bridge_route_trace_omits_sensitive_payload_fields():
    result = json.dumps(
        {
            "success": True,
            "tool_name": "employee_handoff",
            "route_event_type": "route_suggestion",
            "terminal": True,
            "public_reply": "交给营销内容创作处理。",
            "request": {"query": "private"},
            "args": {"token": "secret-token"},
            "traceback": "Traceback private detail",
            "route": {
                "current_employee_type": "marketing_planner",
                "target_employee_type": "marketing_content_creator",
                "confidence": 0.86,
                "reason": "需要生成营销内容",
                "reply": "交给营销内容创作处理。",
            },
        },
        ensure_ascii=False,
    )

    events, trace = route_events_from_tool_result(
        tool_name="employee_handoff",
        result=result,
    )

    assert [type(event) for event in events] == [RouteSuggestionEvent]
    assert trace == {
        "route_event_type": "route_suggestion",
        "terminal": True,
        "target_employee_type": "marketing_content_creator",
        "current_employee_type": "marketing_planner",
        "confidence": 0.86,
    }
