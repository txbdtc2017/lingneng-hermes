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
    "read_workspace",
    "write_workspace",
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
        "Retrieve LingNeng business knowledge. Phase 3 returns NOT_CONFIGURED.",
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
        "List LingNeng employee skills. Phase 3 returns NOT_CONFIGURED.",
        {"employee_type": _string("Optional employee type filter.")},
    ),
    "search_skills": _object_schema(
        "search_skills",
        "Search LingNeng employee skills. Phase 3 returns NOT_CONFIGURED.",
        {
            "query": _string("Skill search query."),
            "employee_type": _string("Optional employee type filter."),
        },
        ("query",),
    ),
    "read_skill": _object_schema(
        "read_skill",
        "Read a LingNeng skill. Phase 3 returns NOT_CONFIGURED.",
        {"skill_id": _string("Skill identifier.")},
        ("skill_id",),
    ),
    "read_skill_resource": _object_schema(
        "read_skill_resource",
        "Read a LingNeng skill resource. Phase 3 returns NOT_CONFIGURED.",
        {
            "skill_id": _string("Skill identifier."),
            "resource_id": _string("Resource identifier."),
        },
        ("skill_id", "resource_id"),
    ),
    "document_generation": _object_schema(
        "document_generation",
        "Request LingNeng document generation. Phase 3 returns NOT_CONFIGURED.",
        {
            "instruction": _string("Document generation instruction."),
            "format": _string("Optional output format."),
        },
        ("instruction",),
    ),
    "image_generation": _object_schema(
        "image_generation",
        "Request LingNeng image generation. Phase 3 returns NOT_CONFIGURED.",
        {
            "prompt": _string("Image prompt."),
            "style": _string("Optional visual style."),
        },
        ("prompt",),
    ),
    "chart_visualization": _object_schema(
        "chart_visualization",
        "Request LingNeng chart generation. Phase 3 returns NOT_CONFIGURED.",
        {
            "instruction": _string("Chart instruction."),
            "data": {
                "type": "object",
                "description": "Optional chart data.",
                "additionalProperties": True,
            },
        },
        ("instruction",),
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
    for tool_name in LINGNENG_TOOL_NAMES:
        yield tool_name, TOOL_SCHEMAS[tool_name], handler_for(tool_name)
