from __future__ import annotations

from lingneng.tools.chart_visualization import chart_visualization_handler
from lingneng.tools.document_generation import document_generation_handler
from lingneng.tools.image_generation import image_generation_handler
from lingneng.tools.rag import retrieve_rag_handler
from lingneng.tools.stubs import TOOL_SCHEMAS, iter_tool_entries
from lingneng.tools.web_search import web_search_handler
from tools.registry import registry


_REAL_HANDLERS = {
    "retrieve_rag": retrieve_rag_handler,
    "document_generation": document_generation_handler,
    "image_generation": image_generation_handler,
    "chart_visualization": chart_visualization_handler,
    "web_search": web_search_handler,
}

for _tool_name, _handler in _REAL_HANDLERS.items():
    registry.register(
        name=_tool_name,
        toolset="lingneng",
        schema=TOOL_SCHEMAS[_tool_name],
        handler=_handler,
        description=TOOL_SCHEMAS[_tool_name]["description"],
        # Hermes core also registers a generic browser-backed web_search.
        # LingNeng's Java API must route this name to the controlled provider
        # adapter, so this single intentional override is explicit and tested.
        override=_tool_name == "web_search",
    )

for _tool_name, _schema, _handler in iter_tool_entries():
    registry.register(
        name=_tool_name,
        toolset="lingneng",
        schema=_schema,
        handler=_handler,
        description=_schema["description"],
    )
