from __future__ import annotations

from datetime import date
from functools import lru_cache
from importlib import resources
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from lingneng.schemas.chat_request import EmployeeType

FestivalCategory = Literal[
    "public_holiday",
    "traditional_festival",
    "marketing_event",
    "internet_culture",
    "western_festival",
]
CalendarKind = Literal["solar", "solar_nth_weekday", "explicit_date"]
TimeContextScope = Literal["today", "upcoming_30_days"]
MarketingTier = Literal["S", "A", "B", "C", "D"]
FocusLevel = Literal["primary", "secondary", "background"]


class CalendarEventConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    category: FestivalCategory
    calendar: CalendarKind
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)
    nth: int | None = Field(default=None, ge=1, le=5)
    weekday: int | None = Field(default=None, ge=1, le=7)
    dates: list[str] = Field(default_factory=list)
    marketing_hint: str
    marketing_tier: MarketingTier = "B"
    heat_score: int = Field(default=3, ge=1, le=5)
    business_type: str = ""
    marketing_focus: str = ""
    suitable_employee_types: list[EmployeeType] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def default_marketing_focus(cls, data: object) -> object:
        if isinstance(data, dict) and not data.get("marketing_focus"):
            marketing_hint = data.get("marketing_hint")
            if marketing_hint:
                return {**data, "marketing_focus": marketing_hint}
        return data

    @model_validator(mode="after")
    def validate_calendar_fields(self) -> CalendarEventConfig:
        if self.calendar == "solar":
            if self.month is None or self.day is None:
                raise ValueError("solar calendar events require month and day")
            date(2000, self.month, self.day)
        if self.calendar == "solar_nth_weekday" and (
            self.month is None or self.nth is None or self.weekday is None
        ):
            raise ValueError("solar_nth_weekday events require month, nth, and weekday")
        if self.calendar == "explicit_date" and not self.dates:
            raise ValueError("explicit_date events require dates")
        return self

    @field_validator("dates")
    @classmethod
    def validate_dates(cls, values: list[str]) -> list[str]:
        for value in values:
            date.fromisoformat(value)
        return values


class TimeContextEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    category: FestivalCategory
    date: str
    days_until: int = Field(ge=0)
    marketing_hint: str
    marketing_tier: MarketingTier = "B"
    heat_score: int = Field(default=3, ge=1, le=5)
    business_type: str = ""
    marketing_focus: str = ""
    focus_level: FocusLevel = "background"
    priority_reason: str = ""


class CurrentTimeContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_date: str
    current_datetime: str
    timezone: str
    region: str
    weekday_cn: str
    scope: TimeContextScope
    events: list[TimeContextEvent] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def to_prompt_text(self, *, max_events: int, max_chars: int) -> str:
        event_lines: list[str] = []
        for event in self.events[:max_events]:
            event_lines.extend(
                [
                    f"- Event: {event.name}",
                    f"  Date: {event.date}",
                    f"  Days Until: {event.days_until}",
                    f"  Focus: {event.focus_level}",
                    f"  Marketing Tier: {event.marketing_tier}",
                    f"  Marketing Focus: {event.marketing_focus}",
                    f"  Hint: {event.marketing_hint}",
                    f"  Priority Reason: {event.priority_reason}",
                ]
            )
        if not event_lines:
            event_lines.append("- No configured festival event matched this scope.")

        warning_lines = [f"- {warning}" for warning in self.warnings]
        sections = [
            "Current Time Context",
            f"Current Date: {self.current_date}",
            f"Current Datetime: {self.current_datetime}",
            f"Timezone: {self.timezone}",
            f"Region: {self.region}",
            f"Weekday: {self.weekday_cn}",
            f"Scope: {self.scope}",
            "Matched Events:",
            *event_lines,
        ]
        if warning_lines:
            sections.extend(["Warnings:", *warning_lines])

        return _bounded_text("\n".join(sections), max_chars=max_chars)

    def trace_summary(self) -> dict[str, object]:
        return {
            "scope": self.scope,
            "event_count": len(self.events),
            "timezone": self.timezone,
            "region": self.region,
        }


class FestivalCalendarRepository:
    def __init__(self, config: _FestivalCalendarConfig) -> None:
        self._config = config

    @classmethod
    def load_default(cls) -> FestivalCalendarRepository:
        return cls(_load_default_calendar_config())

    def events_for_region(self, region: str) -> list[CalendarEventConfig]:
        region_config = self._config.regions.get(region) or self._config.regions["CN"]
        return [event.model_copy(deep=True) for event in region_config.events]


class TimeContextService:
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError("TimeContextService is implemented in Task 11.2")


class _RegionCalendarConfig(BaseModel):
    events: list[CalendarEventConfig] = Field(default_factory=list)


class _FestivalCalendarConfig(BaseModel):
    regions: dict[str, _RegionCalendarConfig]

    @model_validator(mode="after")
    def validate_default_region(self) -> _FestivalCalendarConfig:
        if "CN" not in self.regions:
            raise ValueError("default region CN is required")
        return self


@lru_cache(maxsize=1)
def _load_default_calendar_config() -> _FestivalCalendarConfig:
    calendar_path = resources.files("lingneng.context").joinpath(
        "festival_calendar.yaml"
    )
    raw_config = yaml.safe_load(calendar_path.read_text(encoding="utf-8")) or {}
    return _FestivalCalendarConfig.model_validate(raw_config)


def _bounded_text(text: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""

    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped

    marker = "\n...[truncated]"
    if max_chars <= len(marker):
        return marker[-max_chars:]

    return stripped[: max_chars - len(marker)].rstrip() + marker
