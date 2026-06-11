from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta
from functools import lru_cache
from importlib import resources
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from lingneng.config.settings import LingNengSettings
from lingneng.schemas.chat_request import ChatStreamRequest
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

WEEKDAYS_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
UPCOMING_WINDOW_DAYS = 30
MARKETING_TIER_SCORES = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}
EXPLICIT_EVENT_SCORE_BOOST = 1000
MAX_PRIMARY_EVENTS = 2
_UPCOMING_KEYWORDS = (
    "最近",
    "接下来",
    "未来",
    "近期",
    "本月",
    "这个月",
    "下个月",
    "有哪些节日",
    "有什么节日",
    "节日",
    "营销节点",
    "重大活动",
    "活动节点",
)
_TODAY_KEYWORDS = ("今天", "今日", "当天")


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
            date(2023, self.month, self.day)
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


def determine_time_context_scope(query: str) -> TimeContextScope:
    normalized_query = query.strip()
    if any(keyword in normalized_query for keyword in _TODAY_KEYWORDS):
        return "today"
    if any(keyword in normalized_query for keyword in _UPCOMING_KEYWORDS):
        return "upcoming_30_days"
    return "today"


class TimeContextService:
    def __init__(
        self,
        settings: LingNengSettings,
        *,
        repository: FestivalCalendarRepository | None = None,
        now_provider: Callable[[ZoneInfo], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self._repository = repository or FestivalCalendarRepository.load_default()
        self._now_provider = now_provider or datetime.now

    def build(self, request: ChatStreamRequest) -> CurrentTimeContext:
        timezone_name, timezone_info, timezone_warnings = _resolve_timezone(
            request.runtime_context.timezone,
            default_timezone=self.settings.time_context_default_timezone,
        )
        now = _normalize_datetime(self._now_provider(timezone_info), timezone_info)
        region, region_warnings = _resolve_region(
            request.runtime_context.region,
            default_region=self.settings.time_context_default_region,
        )
        current_date = now.date()
        query = request.query.content
        calendar_events = self._repository.events_for_region(region)
        scope = determine_time_context_scope(query)
        if scope == "today" and not _query_has_today_keyword(query):
            if _mentioned_event_in_window(
                events=calendar_events,
                current_date=current_date,
                employee_type=request.employee.employee_type,
                query=query,
            ):
                scope = "upcoming_30_days"

        events = _match_events(
            events=calendar_events,
            current_date=current_date,
            employee_type=request.employee.employee_type,
            scope=scope,
            query=query,
        )[: self.settings.time_context_max_events]

        return CurrentTimeContext(
            current_date=current_date.isoformat(),
            current_datetime=now.isoformat(timespec="seconds"),
            timezone=timezone_name,
            region=region,
            weekday_cn=WEEKDAYS_CN[current_date.weekday()],
            scope=scope,
            events=events,
            warnings=[*timezone_warnings, *region_warnings],
        )


def _resolve_timezone(
    timezone_name: str,
    *,
    default_timezone: str,
) -> tuple[str, ZoneInfo, list[str]]:
    fallback_name = (default_timezone or "Asia/Shanghai").strip() or "Asia/Shanghai"
    candidate = (timezone_name or fallback_name).strip()
    try:
        return candidate, ZoneInfo(candidate), []
    except (ZoneInfoNotFoundError, ValueError):
        try:
            return fallback_name, ZoneInfo(fallback_name), [
                "TIMEZONE_FALLBACK_TO_DEFAULT"
            ]
        except (ZoneInfoNotFoundError, ValueError):
            return "Asia/Shanghai", ZoneInfo("Asia/Shanghai"), [
                "TIMEZONE_FALLBACK_TO_DEFAULT"
            ]


def _resolve_region(region: str, *, default_region: str) -> tuple[str, list[str]]:
    fallback_region = (default_region or "CN").strip().upper() or "CN"
    if fallback_region != "CN":
        fallback_region = "CN"

    candidate = (region or "").strip().upper()
    if candidate == fallback_region:
        return fallback_region, []
    return fallback_region, ["REGION_FALLBACK_TO_DEFAULT"]


def _normalize_datetime(value: datetime, timezone_info: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone_info)
    return value.astimezone(timezone_info)


def _match_events(
    *,
    events: list[CalendarEventConfig],
    current_date: date,
    employee_type: EmployeeType,
    scope: TimeContextScope,
    query: str,
) -> list[TimeContextEvent]:
    end_date = (
        current_date
        if scope == "today"
        else current_date + timedelta(days=UPCOMING_WINDOW_DAYS)
    )
    matched: list[TimeContextEvent] = []
    seen: set[tuple[str, date]] = set()
    for event in events:
        if (
            event.suitable_employee_types
            and employee_type not in event.suitable_employee_types
        ):
            continue
        for event_date in _candidate_dates(event, current_date.year):
            if not current_date <= event_date <= end_date:
                continue
            key = (event.id, event_date)
            if key in seen:
                continue
            seen.add(key)
            matched.append(
                TimeContextEvent(
                    id=event.id,
                    name=event.name,
                    category=event.category,
                    date=event_date.isoformat(),
                    days_until=(event_date - current_date).days,
                    marketing_hint=event.marketing_hint,
                    marketing_tier=event.marketing_tier,
                    heat_score=event.heat_score,
                    business_type=event.business_type,
                    marketing_focus=event.marketing_focus,
                )
            )
    return _prioritize_events(matched, query=query)


def _candidate_dates(event: CalendarEventConfig, current_year: int) -> Iterable[date]:
    if event.calendar == "explicit_date":
        for value in event.dates:
            yield date.fromisoformat(value)
        return

    years = (current_year, current_year + 1)
    if event.calendar == "solar":
        for year in years:
            if event.month is not None and event.day is not None:
                yield date(year, event.month, event.day)
        return

    if event.calendar == "solar_nth_weekday":
        for year in years:
            if event.month is None or event.nth is None or event.weekday is None:
                continue
            event_date = _solar_nth_weekday(
                year=year,
                month=event.month,
                nth=event.nth,
                weekday=event.weekday,
            )
            if event_date is not None:
                yield event_date


def _solar_nth_weekday(
    *,
    year: int,
    month: int,
    nth: int,
    weekday: int,
) -> date | None:
    first_day = date(year, month, 1)
    day_offset = (weekday - first_day.isoweekday()) % 7
    day = 1 + day_offset + ((nth - 1) * 7)
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _prioritize_events(
    events: list[TimeContextEvent],
    *,
    query: str,
) -> list[TimeContextEvent]:
    scored_events = []
    for event in events:
        mentioned = _event_is_mentioned(event, query)
        priority = EXPLICIT_EVENT_SCORE_BOOST if mentioned else 0
        scored_events.append(
            (
                (
                    -priority,
                    -MARKETING_TIER_SCORES[event.marketing_tier],
                    -event.heat_score,
                    event.days_until,
                    event.name,
                    event.id,
                ),
                mentioned,
                event,
            )
        )

    prioritized: list[TimeContextEvent] = []
    for index, (_, mentioned, event) in enumerate(sorted(scored_events)):
        focus_level: FocusLevel = "primary" if index < MAX_PRIMARY_EVENTS else "secondary"
        prioritized.append(
            event.model_copy(
                update={
                    "focus_level": focus_level,
                    "priority_reason": _primary_reason(
                        event,
                        mentioned=mentioned,
                        focus_level=focus_level,
                    ),
                }
            )
        )
    return prioritized


def _event_is_mentioned(
    event: CalendarEventConfig | TimeContextEvent,
    query: str,
) -> bool:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return False

    tokens = [
        event.id,
        event.name,
    ]
    if event.name.endswith("节"):
        tokens.append(event.name[:-1])

    return any(token and token.strip().lower() in normalized_query for token in tokens)


def _primary_reason(
    event: TimeContextEvent,
    *,
    mentioned: bool,
    focus_level: FocusLevel,
) -> str:
    if mentioned:
        return "用户本轮明确提到该节点，应作为本轮营销主线。"
    if focus_level == "primary":
        return "该节点处于本轮时间窗口内，营销层级和热度较高，应优先纳入规划。"
    return "该节点处于本轮时间窗口内，可作为辅助营销参考。"


def _query_has_today_keyword(query: str) -> bool:
    return any(keyword in query.strip() for keyword in _TODAY_KEYWORDS)


def _mentioned_event_in_window(
    *,
    events: list[CalendarEventConfig],
    current_date: date,
    employee_type: EmployeeType,
    query: str,
) -> bool:
    end_date = current_date + timedelta(days=UPCOMING_WINDOW_DAYS)
    for event in events:
        if (
            event.suitable_employee_types
            and employee_type not in event.suitable_employee_types
        ):
            continue
        if not _event_is_mentioned(event, query):
            continue
        if any(
            current_date <= event_date <= end_date
            for event_date in _candidate_dates(event, current_date.year)
        ):
            return True
    return False


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
