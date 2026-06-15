from __future__ import annotations

import os

import pytest

from lingneng.config.settings import LingNengSettings
from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter
from lingneng.schemas.chat_events import FinalEvent, RouteSuggestionEvent
from lingneng.schemas.chat_request import ChatStreamRequest
from lingneng.session.keys import resolve_session_key
from tests.lingneng.schemas.test_chat_request_schema import full_payload


pytestmark = pytest.mark.skipif(
    os.getenv("LINGNENG_BUSINESS_DECISION_LIVE_TEST_ENABLED") != "1",
    reason="live business decision acceptance is opt-in",
)


def settings(tmp_path):
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_AGENT_MODE": "hermes",
            "LINGNENG_INTERNAL_API_KEY": "key",
        }
    )


def request_for(query: str, employee_type: str) -> ChatStreamRequest:
    payload = full_payload()
    payload["query"]["content"] = query
    payload["employee"]["employee_type"] = employee_type
    payload["employee"]["employee_id"] = employee_type
    payload["request_id"] = f"live-{employee_type}-{abs(hash(query))}"
    payload["conversation_id"] = payload["request_id"]
    return ChatStreamRequest.model_validate(payload)


async def collect_events(tmp_path, query: str, employee_type: str):
    request = request_for(query, employee_type)
    adapter = HermesAgentRunAdapter(settings(tmp_path))
    resolved = resolve_session_key(request)
    return [event async for event in adapter.stream(request, resolved, "live-run")]


@pytest.mark.asyncio
async def test_live_identity_question_stays_with_current_employee(tmp_path):
    events = await collect_events(tmp_path, "你是谁，能帮我做什么", "marketing_content_creator")

    assert isinstance(events[-1], FinalEvent)
    assert not any(isinstance(event, RouteSuggestionEvent) for event in events)
    assert events[-1].answer.strip()


@pytest.mark.asyncio
async def test_live_clear_cross_employee_request_can_emit_route_suggestion(tmp_path):
    events = await collect_events(
        tmp_path,
        "帮我策划端午节门店活动主题和优惠组合",
        "marketing_content_creator",
    )

    assert isinstance(events[-1], FinalEvent)
    route_events = [event for event in events if isinstance(event, RouteSuggestionEvent)]
    if route_events:
        assert route_events[-1].target_employee_type == "marketing_planner"
    else:
        assert events[-1].answer.strip()
        assert "活动" in events[-1].answer or "策划" in events[-1].answer
