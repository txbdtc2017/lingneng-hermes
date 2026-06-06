"""Runtime adapters for LingNeng API execution."""

from typing import TYPE_CHECKING, Any

from lingneng.runtime.agent_adapter import AgentRunAdapter, LingNengStreamEvent
from lingneng.runtime.fake_agent import FakeAgentRunAdapter

if TYPE_CHECKING:
    from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter

__all__ = [
    "AgentRunAdapter",
    "FakeAgentRunAdapter",
    "HermesAgentRunAdapter",
    "LingNengStreamEvent",
]


def __getattr__(name: str) -> Any:
    if name == "HermesAgentRunAdapter":
        from lingneng.runtime.hermes_adapter import HermesAgentRunAdapter

        return HermesAgentRunAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
