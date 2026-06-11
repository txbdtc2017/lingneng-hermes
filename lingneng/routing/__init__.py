from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "EMPLOYEE_PUBLIC_DISPLAY_NAMES": "lingneng.routing.employees",
    "EmployeeDirectoryItem": "lingneng.routing.employees",
    "LingNengEmployeeDirectory": "lingneng.routing.employees",
    "RouteToolCandidate": "lingneng.routing.models",
    "EmployeeHandoffCommand": "lingneng.routing.models",
    "NormalizedRouteDecision": "lingneng.routing.models",
    "normalize_handoff_command": "lingneng.routing.models",
    "failure_tool_result": "lingneng.routing.models",
    "PendingRouteConfirmation": "lingneng.routing.store",
    "PendingRouteConfirmationRecord": "lingneng.routing.store",
    "LingNengRoutePendingStore": "lingneng.routing.store",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(name)
    module = import_module(_EXPORTS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value
