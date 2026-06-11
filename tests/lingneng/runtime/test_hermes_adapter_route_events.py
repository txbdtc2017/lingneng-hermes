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
