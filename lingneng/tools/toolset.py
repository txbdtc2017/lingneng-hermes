from __future__ import annotations

from lingneng.tools.rag import retrieve_rag_handler
from lingneng.tools.stubs import TOOL_SCHEMAS, iter_tool_entries
from tools.registry import registry


registry.register(
    name="retrieve_rag",
    toolset="lingneng",
    schema=TOOL_SCHEMAS["retrieve_rag"],
    handler=retrieve_rag_handler,
    description=TOOL_SCHEMAS["retrieve_rag"]["description"],
)

for _tool_name, _schema, _handler in iter_tool_entries():
    registry.register(
        name=_tool_name,
        toolset="lingneng",
        schema=_schema,
        handler=_handler,
        description=_schema["description"],
    )
