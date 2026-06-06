"""Session helpers for LingNeng Java-compatible requests."""

from typing import TYPE_CHECKING, Any

from lingneng.session.keys import ResolvedSessionKey, resolve_session_key

if TYPE_CHECKING:
    from lingneng.session.hermes_session import LingNengHermesSessionStore

__all__ = [
    "LingNengHermesSessionStore",
    "ResolvedSessionKey",
    "resolve_session_key",
]


def __getattr__(name: str) -> Any:
    if name == "LingNengHermesSessionStore":
        from lingneng.session.hermes_session import LingNengHermesSessionStore

        return LingNengHermesSessionStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
