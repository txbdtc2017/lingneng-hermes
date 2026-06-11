from __future__ import annotations

from lingneng.tools.chart_visualization import chart_visualization_handler
from lingneng.tools.document_generation import document_generation_handler
from lingneng.tools.image_generation import image_generation_handler
from lingneng.tools.rag import retrieve_rag_handler
from lingneng.tools.skill_tools import (
    list_skills_handler,
    read_skill_handler,
    read_skill_resource_handler,
    search_skills_handler,
)
from lingneng.tools.stubs import TOOL_SCHEMAS, iter_tool_entries
from lingneng.tools.web_search import (
    is_lingneng_tool_context_active,
    web_search_handler,
)
from tools.registry import registry


_REAL_HANDLERS = {
    "retrieve_rag": retrieve_rag_handler,
    "list_skills": list_skills_handler,
    "search_skills": search_skills_handler,
    "read_skill": read_skill_handler,
    "read_skill_resource": read_skill_resource_handler,
    "document_generation": document_generation_handler,
    "image_generation": image_generation_handler,
    "chart_visualization": chart_visualization_handler,
}

for _tool_name, _handler in _REAL_HANDLERS.items():
    registry.register(
        name=_tool_name,
        toolset="lingneng",
        schema=TOOL_SCHEMAS[_tool_name],
        handler=_handler,
        description=TOOL_SCHEMAS[_tool_name]["description"],
    )

registry.register_context_override(
    name="web_search",
    schema=TOOL_SCHEMAS["web_search"],
    handler=web_search_handler,
    is_active=is_lingneng_tool_context_active,
    fail_closed=True,
    fail_closed_toolsets={"lingneng"},
)

for _tool_name, _schema, _handler in iter_tool_entries():
    registry.register(
        name=_tool_name,
        toolset="lingneng",
        schema=_schema,
        handler=_handler,
        description=_schema["description"],
    )
