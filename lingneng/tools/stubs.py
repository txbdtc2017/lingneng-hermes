from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from typing import Any


LINGNENG_TOOL_NAMES = (
    "retrieve_rag",
    "list_skills",
    "search_skills",
    "read_skill",
    "read_skill_resource",
    "document_generation",
    "image_generation",
    "chart_visualization",
    "web_search",
    "read_workspace",
    "write_workspace",
)

REAL_TOOL_NAMES = (
    "retrieve_rag",
    "list_skills",
    "search_skills",
    "read_skill",
    "read_skill_resource",
    "document_generation",
    "image_generation",
    "chart_visualization",
    "web_search",
)

STUB_TOOL_NAMES = tuple(
    tool_name for tool_name in LINGNENG_TOOL_NAMES if tool_name not in REAL_TOOL_NAMES
)


def _string(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


def _integer(description: str, minimum: int | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "integer", "description": description}
    if minimum is not None:
        schema["minimum"] = minimum
    return schema


def _object_schema(
    name: str,
    description: str,
    properties: Mapping[str, dict[str, Any]],
    required: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": dict(properties),
            "required": list(required),
            "additionalProperties": False,
        },
    }


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "retrieve_rag": _object_schema(
        "retrieve_rag",
        "Retrieve LingNeng business knowledge through the configured RAG provider.",
        {
            "query": _string("Business question to retrieve context for."),
            "top_k": _integer("Maximum number of references to retrieve.", minimum=1),
            "filters": {
                "type": "object",
                "description": "Business filters.",
                "additionalProperties": True,
            },
        },
        ("query",),
    ),
    "list_skills": _object_schema(
        "list_skills",
        "List validated LingNeng bundled skills from the native skill catalog.",
        {
            "employee_type": _string("Optional employee type filter."),
            "kind": _string(
                "Optional skill kind: employee_base, task, capability, or infrastructure."
            ),
            "limit": _integer("Optional maximum number of skills to return.", minimum=1),
        },
    ),
    "search_skills": _object_schema(
        "search_skills",
        "Search validated LingNeng bundled skills by query and metadata.",
        {
            "query": _string("Skill search query."),
            "employee_type": _string("Optional employee type filter."),
            "kind": _string(
                "Optional skill kind: employee_base, task, capability, or infrastructure."
            ),
            "limit": _integer("Optional maximum number of matches to return.", minimum=1),
        },
        ("query",),
    ),
    "read_skill": _object_schema(
        "read_skill",
        "Read bounded instructions and resource manifest for a LingNeng skill.",
        {
            "skill_id": _string("Skill identifier."),
            "max_chars": _integer("Optional maximum body characters to return.", minimum=1),
        },
        ("skill_id",),
    ),
    "read_skill_resource": _object_schema(
        "read_skill_resource",
        "Read a bounded manifest-listed LingNeng skill resource.",
        {
            "skill_id": _string("Skill identifier."),
            "resource_id": _string("Resource identifier."),
            "max_chars": _integer(
                "Optional maximum resource characters to return.",
                minimum=1,
            ),
        },
        ("skill_id", "resource_id"),
    ),
    "document_generation": _object_schema(
        "document_generation",
        "Generate a LingNeng business document through the controlled provider.",
        {
            "title": _string("Document title."),
            "instruction": _string("Document generation instruction."),
            "content": _string("Bounded source content for the document."),
            "format": _string("Optional output format."),
            "target_format": _string("Optional target output format."),
        },
        ("instruction",),
    ),
    "image_generation": _object_schema(
        "image_generation",
        "Generate LingNeng business images through the controlled provider.",
        {
            "prompt": _string("Image prompt."),
            "count": _integer("Number of images to generate.", minimum=1),
            "size": _string("Optional image size, such as 1024x1024."),
            "quality": _string("Optional image quality."),
            "style": _string("Optional visual style."),
        },
        ("prompt",),
    ),
    "chart_visualization": _object_schema(
        "chart_visualization",
        "Generate a LingNeng chart image through the controlled provider.",
        {
            "instruction": _string("Chart instruction."),
            "title": _string("Optional chart title."),
            "chart_type": _string("Optional chart type."),
            "data": {
                "type": "object",
                "description": "Optional chart data.",
                "additionalProperties": True,
            },
            "data_summary": _string("Optional bounded public chart data summary."),
        },
        ("instruction",),
    ),
    "web_search": _object_schema(
        "web_search",
        "Search the web through the controlled LingNeng search provider.",
        {
            "query": _string("Search query."),
            "top_k": _integer("Maximum number of public sources to return.", minimum=1),
            "recency_filter": _string("Optional recency filter."),
            "site_filter": _string("Optional site or domain filter."),
        },
        ("query",),
    ),
    "read_workspace": _object_schema(
        "read_workspace",
        "Read from a LingNeng-controlled workspace. Phase 3 returns NOT_CONFIGURED.",
        {
            "path": _string("Workspace-relative path."),
            "purpose": _string("Why the content is needed."),
        },
        ("path",),
    ),
    "write_workspace": _object_schema(
        "write_workspace",
        "Write through a LingNeng-controlled workspace. Phase 3 returns NOT_CONFIGURED.",
        {
            "path": _string("Workspace-relative path."),
            "content": _string("Content to write."),
            "purpose": _string("Why the write is needed."),
        },
        ("path", "content"),
    ),
}


def not_configured_result(tool_name: str) -> str:
    return json.dumps(
        {
            "success": False,
            "code": "NOT_CONFIGURED",
            "tool_name": tool_name,
            "phase": "phase_3_stub",
            "message": (
                f"LingNeng tool '{tool_name}' is not configured in this "
                "runtime phase."
            ),
        },
        ensure_ascii=False,
    )


def handler_for(tool_name: str) -> Callable[[dict[str, Any]], str]:
    def _handler(args: dict[str, Any] | None = None, **kwargs: Any) -> str:
        return not_configured_result(tool_name)

    return _handler


def iter_tool_entries() -> Iterator[tuple[str, dict[str, Any], Callable[[dict[str, Any]], str]]]:
    for tool_name in STUB_TOOL_NAMES:
        yield tool_name, TOOL_SCHEMAS[tool_name], handler_for(tool_name)
