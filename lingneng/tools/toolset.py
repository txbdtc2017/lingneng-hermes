from __future__ import annotations

from lingneng.tools.stubs import iter_tool_entries
from tools.registry import registry


for _tool_name, _schema, _handler in iter_tool_entries():
    registry.register(
        name=_tool_name,
        toolset="lingneng",
        schema=_schema,
        handler=_handler,
        description=_schema["description"],
    )
