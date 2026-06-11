import json

import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.schemas.chat_events import FinalEvent, RouteSuggestionEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def settings(tmp_path):
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_AGENT_MODE": "hermes",
            "LINGNENG_INTERNAL_API_KEY": "key",
        }
    )


class HandoffToolProgressAgent:
    def __init__(self, **kwargs):
        self.tool_progress_callback = kwargs.get("tool_progress_callback")

    def run_conversation(self, *args, **kwargs):
        self.tool_progress_callback(
            "tool.completed",
            "employee_handoff",
            None,
            None,
            duration=0.01,
            is_error=False,
            result=json.dumps(
                {
                    "success": True,
                    "tool_name": "employee_handoff",
                    "route_event_type": "route_suggestion",
                    "terminal": True,
                    "public_reply": "交给营销内容创作处理。",
                    "route": {
                        "current_employee_type": "marketing_planner",
                        "target_employee_type": "marketing_content_creator",
                        "confidence": 0.86,
                        "reason": "需要生成营销内容",
                        "reply": "交给营销内容创作处理。",
                    },
                },
                ensure_ascii=False,
            ),
        )
        return {"final_response": "交给营销内容创作处理。", "messages": []}


class HandoffContextProbeAgent:
    def __init__(self, **kwargs):
        pass

    def run_conversation(self, *args, **kwargs):
        from lingneng.tools.employee_handoff import employee_handoff_handler

        result = json.loads(
            employee_handoff_handler(
                {
                    "action": "suggest",
                    "target_employee_type": "marketing_content_creator",
                    "confidence": 1.0,
                    "reason": "用户已确认切换员工",
                    "reply": "我为你切换到营销内容创作。",
                }
            )
        )
        if not result["success"]:
            raise AssertionError(result)
        if result["route"]["target_employee_type"] != "marketing_content_creator":
            raise AssertionError(result)
        return {"final_response": "我为你切换到营销内容创作。", "messages": []}


class HandoffConfirmPendingStoreProbeAgent:
    last_result: dict | None = None

    def __init__(self, **kwargs):
        pass

    def run_conversation(self, *args, **kwargs):
        from lingneng.tools.employee_handoff import employee_handoff_handler

        result = json.loads(
            employee_handoff_handler(
                {
                    "action": "confirm",
                    "confidence": 0.58,
                    "reason": "需要用户确认员工边界",
                    "reply": "这件事可能由活动策划或内容创作处理，请确认。",
                    "candidates": [
                        {
                            "employee_type": "marketing_planner",
                            "confidence": 0.58,
                            "reason": "需要规划活动方案",
                        },
                        {
                            "employee_type": "marketing_content_creator",
                            "confidence": 0.52,
                            "reason": "需要生成营销内容",
                        },
                    ],
                }
            )
        )
        type(self).last_result = result
        if not result["success"]:
            raise AssertionError(result)
        pending = result["pending_confirmation"]
        if pending["reason"] != "pending_store_missing":
            raise AssertionError(result)
        return {"final_response": result["public_reply"], "messages": []}


@pytest.mark.asyncio
async def test_adapter_emits_route_event_before_final(tmp_path):
    payload = full_payload()
    payload["employee"]["employee_type"] = "marketing_planner"
    request = ChatStreamRequest.model_validate(payload)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path),
        agent_cls=HandoffToolProgressAgent,
    )

    events = [
        event
        async for event in adapter.stream(
            request,
            resolve_session_key(request),
            "run-1",
        )
    ]
    names = [type(event).__name__ for event in events]

    assert "RouteSuggestionEvent" in names
    assert names.index("RouteSuggestionEvent") < names.index("FinalEvent")
    route_event = next(event for event in events if isinstance(event, RouteSuggestionEvent))
    final = events[-1]
    assert isinstance(final, FinalEvent)
    assert route_event.target_employee_type == "marketing_content_creator"
    assert final.trace_summary["route"]["route_event_type"] == "route_suggestion"


@pytest.mark.asyncio
async def test_adapter_activates_employee_handoff_context(tmp_path):
    payload = full_payload()
    payload["employee"]["employee_type"] = "marketing_planner"
    payload["routing"]["confirmed_employee_type"] = "marketing_content_creator"
    request = ChatStreamRequest.model_validate(payload)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path),
        agent_cls=HandoffContextProbeAgent,
    )

    events = [
        event
        async for event in adapter.stream(
            request,
            resolve_session_key(request),
            "run-1",
        )
    ]

    final = events[-1]
    assert isinstance(final, FinalEvent)
    assert final.status == "succeeded"


@pytest.mark.asyncio
async def test_adapter_degrades_when_route_pending_store_cannot_open(tmp_path):
    pending_db_path = tmp_path / "route-pending-as-directory"
    pending_db_path.mkdir()
    payload = full_payload()
    payload["employee"]["employee_type"] = "marketing_planner"
    payload["routing"]["confirmed_employee_type"] = None
    payload["routing"]["confirmation_message_id"] = None
    request = ChatStreamRequest.model_validate(payload)
    adapter = HermesAgentRunAdapter(
        settings=LingNengSettings.from_env(
            {
                "LINGNENG_APP_ENV": "test",
                "LINGNENG_RUNTIME_DIR": str(tmp_path),
                "LINGNENG_AGENT_MODE": "hermes",
                "LINGNENG_INTERNAL_API_KEY": "key",
                "LINGNENG_ROUTE_PENDING_DB_PATH": str(pending_db_path),
            }
        ),
        agent_cls=HandoffConfirmPendingStoreProbeAgent,
    )
    HandoffConfirmPendingStoreProbeAgent.last_result = None

    events = [
        event
        async for event in adapter.stream(
            request,
            resolve_session_key(request),
            "run-1",
        )
    ]

    final = events[-1]
    assert isinstance(final, FinalEvent)
    assert final.status == "succeeded"
    assert HandoffConfirmPendingStoreProbeAgent.last_result is not None
    assert (
        HandoffConfirmPendingStoreProbeAgent.last_result["pending_confirmation"][
            "reason"
        ]
        == "pending_store_missing"
    )


@pytest.mark.asyncio
async def test_adapter_resets_employee_handoff_context_after_stream(tmp_path):
    payload = full_payload()
    payload["employee"]["employee_type"] = "marketing_planner"
    request = ChatStreamRequest.model_validate(payload)
    adapter = HermesAgentRunAdapter(
        settings=settings(tmp_path),
        agent_cls=HandoffContextProbeAgent,
    )

    [
        event
        async for event in adapter.stream(
            request,
            resolve_session_key(request),
            "run-1",
        )
    ]

    from lingneng.tools.employee_handoff import employee_handoff_handler

    result = json.loads(
        employee_handoff_handler(
            {
                "action": "current",
                "confidence": 1.0,
                "reason": "上下文应已清理",
            }
        )
    )

    assert result["success"] is False
    assert result["code"] == "HANDOFF_CONTEXT_MISSING"
