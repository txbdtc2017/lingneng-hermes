from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from lingneng.config.settings import LingNengSettings
from lingneng.context.time import (
    CalendarEventConfig,
    CurrentTimeContext,
    FestivalCalendarRepository,
    TimeContextEvent,
)


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
    with pytest.raises(ValidationError):
        CalendarEventConfig(
            id="bad_date",
            name="坏日期",
            category="marketing_event",
            calendar="solar",
            month=2,
            day=31,
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
