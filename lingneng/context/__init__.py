from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "CalendarEventConfig": "lingneng.context.time",
    "CurrentTimeContext": "lingneng.context.time",
    "FestivalCalendarRepository": "lingneng.context.time",
    "PromptSection": "lingneng.context.prompt",
    "TOOL_DERIVED_PUBLIC_GUIDANCE_HEADING": "lingneng.context.prompt",
    "TRUSTED_RUNTIME_CONTEXT_HEADING": "lingneng.context.prompt",
    "TimeContextEvent": "lingneng.context.time",
    "TimeContextService": "lingneng.context.time",
    "UNTRUSTED_REQUEST_CONTEXT_HEADING": "lingneng.context.prompt",
    "compose_lingneng_ephemeral_prompt": "lingneng.context.prompt",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(name)
    module = import_module(_EXPORTS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value
