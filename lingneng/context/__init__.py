from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "CalendarEventConfig": "lingneng.context.time",
    "CurrentTimeContext": "lingneng.context.time",
    "FestivalCalendarRepository": "lingneng.context.time",
    "TimeContextEvent": "lingneng.context.time",
    "TimeContextService": "lingneng.context.time",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(name)
    module = import_module(_EXPORTS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value
