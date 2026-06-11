from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from lingneng.config.settings import LingNengSettings
from lingneng.context.time import (
    CalendarEventConfig,
    CurrentTimeContext,
    FestivalCalendarRepository,
    TimeContextService,
    TimeContextEvent,
    determine_time_context_scope,
)
from lingneng.schemas.chat_request import ChatStreamRequest
from tests.lingneng.schemas.test_chat_request_schema import full_payload


def settings(tmp_path, **overrides):
    env = {"LINGNENG_RUNTIME_DIR": str(tmp_path)}
    env.update(overrides)
    return LingNengSettings.from_env(env)


def frozen_now() -> datetime:
    return datetime(2026, 6, 11, 10, 30, tzinfo=ZoneInfo("Asia/Shanghai"))


def test_calendar_model_rejects_invalid_solar_event():
    with pytest.raises(ValidationError):
        CalendarEventConfig(
            id="bad",
            name="坏数据",
            category="marketing_event",
            calendar="solar",
            marketing_hint="坏数据",
        )


def test_calendar_model_rejects_impossible_solar_date():
    for month, day in ((2, 31), (2, 29)):
        with pytest.raises(ValidationError):
            CalendarEventConfig(
                id="bad_date",
                name="坏日期",
                category="marketing_event",
                calendar="solar",
                month=month,
                day=day,
                marketing_hint="坏日期",
            )


def test_calendar_model_rejects_invalid_explicit_date_and_employee_type():
    with pytest.raises(ValidationError):
        CalendarEventConfig(
            id="bad_explicit_date",
            name="坏日期",
            category="marketing_event",
            calendar="explicit_date",
            dates=["2026-02-31"],
            marketing_hint="坏日期",
        )

    with pytest.raises(ValidationError):
        CalendarEventConfig(
            id="bad_employee",
            name="坏员工",
            category="marketing_event",
            calendar="solar",
            month=6,
            day=18,
            marketing_hint="坏员工",
            suitable_employee_types=["old_app_employee"],
        )


def test_calendar_repository_loads_bundled_cn_events(tmp_path):
    repository = FestivalCalendarRepository.load_default()

    events = repository.events_for_region("CN")

    assert {event.id for event in events} >= {
        "childrens_day",
        "internet_618",
        "fathers_day",
        "dragon_boat_festival",
    }
    assert all("LingNengAI" not in event.name for event in events)


def test_calendar_repository_returns_defensive_copies():
    repository = FestivalCalendarRepository.load_default()
    first_event = repository.events_for_region("CN")[0]
    first_event.name = "mutated"

    assert repository.events_for_region("CN")[0].name != "mutated"


def test_current_time_context_prompt_is_bounded_and_safe(tmp_path):
    context = CurrentTimeContext(
        current_date="2026-06-11",
        current_datetime=frozen_now().isoformat(timespec="seconds"),
        timezone="Asia/Shanghai",
        region="CN",
        weekday_cn="周四",
        scope="upcoming_30_days",
        events=[
            TimeContextEvent(
                id="internet_618",
                name="618",
                category="internet_culture",
                date="2026-06-18",
                days_until=7,
                marketing_hint="适合做年中促销。",
                marketing_tier="S",
                heat_score=5,
                business_type="电商促销",
                marketing_focus="年中大促",
                focus_level="primary",
                priority_reason="用户本轮明确提到该节点，应作为本轮营销主线。",
            )
        ],
    )

    prompt = context.to_prompt_text(max_events=5, max_chars=500)

    assert "Current Date: 2026-06-11" in prompt
    assert "Event: 618" in prompt
    assert "app." not in prompt
    assert "LingNengAI" not in prompt
    assert len(prompt) <= 500


@pytest.mark.parametrize("max_chars", [0, 1, 5, 14])
def test_current_time_context_prompt_respects_tiny_bounds(max_chars):
    context = CurrentTimeContext(
        current_date="2026-06-11",
        current_datetime=frozen_now().isoformat(timespec="seconds"),
        timezone="Asia/Shanghai",
        region="CN",
        weekday_cn="周四",
        scope="today",
    )

    assert len(context.to_prompt_text(max_events=5, max_chars=max_chars)) <= max_chars


def test_current_time_context_trace_summary_is_sanitized():
    context = CurrentTimeContext(
        current_date="2026-06-11",
        current_datetime=frozen_now().isoformat(timespec="seconds"),
        timezone="Asia/Shanghai",
        region="CN",
        weekday_cn="周四",
        scope="today",
    )

    assert context.trace_summary() == {
        "scope": "today",
        "event_count": 0,
        "timezone": "Asia/Shanghai",
        "region": "CN",
    }


def request(
    query="未来30天有什么营销节点",
    employee_type="marketing_planner",
    **runtime,
) -> ChatStreamRequest:
    payload = full_payload()
    payload["query"]["content"] = query
    payload["employee"]["employee_type"] = employee_type
    payload["runtime_context"].update(runtime)
    return ChatStreamRequest.model_validate(payload)


def test_time_context_scope_detection():
    assert determine_time_context_scope("今天适合做什么活动") == "today"
    assert determine_time_context_scope("未来30天有什么营销节点") == "upcoming_30_days"
    assert determine_time_context_scope("帮我写一段文案") == "today"


def test_time_service_builds_upcoming_context_with_bundled_events(tmp_path):
    service = TimeContextService(
        settings(tmp_path),
        now_provider=lambda timezone_info: frozen_now(),
    )

    context = service.build(request("未来30天有什么营销节点"))

    assert context.current_date == "2026-06-11"
    assert context.weekday_cn == "周四"
    assert context.scope == "upcoming_30_days"
    assert context.timezone == "Asia/Shanghai"
    assert context.region == "CN"
    assert [event.id for event in context.events][:2] == [
        "internet_618",
        "dragon_boat_festival",
    ]
    assert context.events[0].focus_level == "primary"


def test_time_service_degrades_invalid_timezone_and_region(tmp_path):
    service = TimeContextService(
        settings(tmp_path),
        now_provider=lambda timezone_info: frozen_now(),
    )

    context = service.build(
        request(
            "未来30天有什么营销节点",
            timezone="Invalid/Timezone",
            region="US",
        )
    )

    assert context.timezone == "Asia/Shanghai"
    assert context.region == "CN"
    assert "TIMEZONE_FALLBACK_TO_DEFAULT" in context.warnings
    assert "REGION_FALLBACK_TO_DEFAULT" in context.warnings


def test_time_service_degrades_value_error_timezone_and_bad_default(tmp_path):
    service = TimeContextService(
        settings(
            tmp_path,
            LINGNENG_TIME_CONTEXT_DEFAULT_TIMEZONE=".",
        ),
        now_provider=lambda timezone_info: frozen_now(),
    )

    context = service.build(request("未来30天有什么营销节点", timezone="."))

    assert context.timezone == "Asia/Shanghai"
    assert "TIMEZONE_FALLBACK_TO_DEFAULT" in context.warnings


def test_time_service_uses_naive_now_provider_with_requested_timezone(tmp_path):
    service = TimeContextService(
        settings(tmp_path),
        now_provider=lambda timezone_info: datetime(2026, 6, 11, 10, 30),
    )

    context = service.build(request("未来30天有什么营销节点"))

    assert context.current_datetime == "2026-06-11T10:30:00+08:00"


def test_time_service_filters_events_by_employee_type(tmp_path):
    service = TimeContextService(
        settings(tmp_path),
        now_provider=lambda timezone_info: frozen_now(),
    )

    context = service.build(
        request(
            "未来30天有什么营销节点",
            employee_type="operation_specialist",
        )
    )

    assert "internet_618" not in {event.id for event in context.events}


def test_query_mention_boosts_matching_event(tmp_path):
    service = TimeContextService(
        settings(tmp_path),
        now_provider=lambda timezone_info: frozen_now(),
    )

    context = service.build(request("父亲节做什么活动"))

    assert context.scope == "upcoming_30_days"
    assert context.events[0].id == "fathers_day"
    assert context.events[0].date == "2026-06-21"
    assert context.events[0].focus_level == "primary"
    assert "明确提到" in context.events[0].priority_reason


def test_business_terms_do_not_count_as_explicit_event_mentions(tmp_path):
    service = TimeContextService(
        settings(tmp_path),
        now_provider=lambda timezone_info: frozen_now(),
    )

    context = service.build(request("家庭消费怎么做会员运营"))

    assert context.scope == "today"
    assert "fathers_day" not in {event.id for event in context.events}


def test_time_service_respects_max_events_setting(tmp_path):
    service = TimeContextService(
        settings(tmp_path, LINGNENG_TIME_CONTEXT_MAX_EVENTS="1"),
        now_provider=lambda timezone_info: frozen_now(),
    )

    context = service.build(request("未来30天有什么营销节点"))

    assert [event.id for event in context.events] == ["internet_618"]

    disabled_events_service = TimeContextService(
        settings(tmp_path, LINGNENG_TIME_CONTEXT_MAX_EVENTS="0"),
        now_provider=lambda timezone_info: frozen_now(),
    )

    assert disabled_events_service.build(request("未来30天有什么营销节点")).events == []
