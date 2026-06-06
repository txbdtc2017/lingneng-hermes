from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import lingneng.tools.toolset  # noqa: F401
import model_tools
from lingneng.config.settings import LingNengSettings
from lingneng.tools.stubs import LINGNENG_TOOL_NAMES, handler_for
from lingneng.tools.web_search import lingneng_tool_context, web_search_context
from model_tools import get_tool_definitions
from toolsets import resolve_toolset, validate_toolset
from tools.registry import ToolRegistry, registry


APPROVED_LINGNENG_TOOLS = {
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
}

REAL_PHASE_5_TOOLS = {
    "retrieve_rag",
    "document_generation",
    "image_generation",
    "chart_visualization",
    "web_search",
}

STUB_ONLY_TOOLS = APPROVED_LINGNENG_TOOLS - REAL_PHASE_5_TOOLS
COLLIDING_LINGNENG_TOOL_NAMES = {"web_search"}

DISALLOWED_HERMES_TOOLS = {
    "terminal",
    "web_extract",
    "process",
    "read_file",
    "write_file",
    "patch",
    "search_files",
    "browser_navigate",
    "browser_snapshot",
    "browser_click",
    "browser_type",
    "browser_scroll",
    "browser_back",
    "browser_press",
    "browser_get_images",
    "browser_vision",
    "browser_console",
    "browser_cdp",
    "browser_dialog",
    "execute_code",
    "delegate_task",
    "send_message",
    "kanban_show",
    "kanban_list",
    "kanban_complete",
    "kanban_block",
    "kanban_heartbeat",
    "kanban_comment",
    "kanban_create",
    "kanban_link",
    "kanban_unblock",
}


def settings(tmp_path: Path) -> LingNengSettings:
    return LingNengSettings.from_env({"LINGNENG_RUNTIME_DIR": str(tmp_path)})


def test_lingneng_tools_package_import_is_lightweight():
    code = (
        "import sys\n"
        "import lingneng.tools\n"
        "raise SystemExit(1 if 'run_agent' in sys.modules else 0)\n"
    )
    repo_root = Path(__file__).resolve().parents[3]

    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )

    assert completed.returncode == 0, completed.stderr


def test_lingneng_toolset_is_valid_and_resolves_only_approved_tools():
    assert validate_toolset("lingneng") is True
    assert set(resolve_toolset("lingneng")) == APPROVED_LINGNENG_TOOLS
    assert set(resolve_toolset("lingneng")).isdisjoint(DISALLOWED_HERMES_TOOLS)


def test_lingneng_tool_registry_entries_are_registered():
    assert set(LINGNENG_TOOL_NAMES) == APPROVED_LINGNENG_TOOLS
    for tool_name in APPROVED_LINGNENG_TOOLS:
        entry = registry.get_entry(tool_name)
        assert entry is not None
        if tool_name in COLLIDING_LINGNENG_TOOL_NAMES:
            assert entry.toolset != "lingneng"
        else:
            assert entry.toolset == "lingneng"


def test_lingneng_tool_definitions_expose_only_lingneng_schemas(tmp_path):
    with lingneng_tool_context(settings(tmp_path)):
        definitions = get_tool_definitions(
            enabled_toolsets=["lingneng"],
            disabled_toolsets=["kanban"],
            quiet_mode=True,
        )
    names = {tool["function"]["name"] for tool in definitions}

    assert names == APPROVED_LINGNENG_TOOLS
    assert names.isdisjoint(DISALLOWED_HERMES_TOOLS)
    for definition in definitions:
        schema = definition["function"]
        assert schema["description"]
        assert schema["parameters"]["type"] == "object"
        assert "properties" in schema["parameters"]
        assert schema["parameters"]["additionalProperties"] is False
    web_search_schema = next(
        item["function"] for item in definitions if item["function"]["name"] == "web_search"
    )
    assert "top_k" in web_search_schema["parameters"]["properties"]
    assert "limit" not in web_search_schema["parameters"]["properties"]


def test_lingneng_toolset_ignores_registry_extra_tools(monkeypatch):
    probe_registry = ToolRegistry()
    for tool_name in APPROVED_LINGNENG_TOOLS:
        entry = registry.get_entry(tool_name)
        assert entry is not None
        probe_registry.register(
            name=tool_name,
            toolset=entry.toolset,
            schema=entry.schema,
            handler=entry.handler,
        )
    probe_registry.register(
        name="lingneng_extra_probe",
        toolset="lingneng",
        schema={
            "name": "lingneng_extra_probe",
            "description": "Probe for LingNeng toolset boundary regression.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        handler=lambda args, **kwargs: "{}",
    )

    monkeypatch.setattr("tools.registry.registry", probe_registry)
    monkeypatch.setattr(model_tools, "registry", probe_registry)

    assert set(resolve_toolset("lingneng")) == APPROVED_LINGNENG_TOOLS

    definitions = get_tool_definitions(
        enabled_toolsets=["lingneng"],
        disabled_toolsets=["kanban"],
        quiet_mode=True,
    )
    names = {tool["function"]["name"] for tool in definitions}

    assert "lingneng_extra_probe" not in names
    assert names == APPROVED_LINGNENG_TOOLS


def test_lingneng_stub_handlers_return_not_configured_shape():
    forbidden_keys = {
        "args",
        "request",
        "payload",
        "history",
        "traceback",
        "exception",
        "api_key",
        "token",
        "secret",
    }
    for tool_name in STUB_ONLY_TOOLS:
        result = json.loads(handler_for(tool_name)({"query": "hello"}))
        dispatched = json.loads(registry.dispatch(tool_name, {"query": "hello"}))
        assert result["success"] is False
        assert result["code"] == "NOT_CONFIGURED"
        assert result["tool_name"] == tool_name
        assert result["phase"] == "phase_3_stub"
        assert "not configured" in result["message"].lower()
        assert forbidden_keys.isdisjoint(result)
        assert dispatched == result


def test_retrieve_rag_registered_handler_is_not_phase_3_stub():
    result = json.loads(registry.dispatch("retrieve_rag", {"query": "hello"}))

    assert result["success"] is False
    assert result["tool_name"] == "retrieve_rag"
    assert result.get("phase") != "phase_3_stub"


def test_phase_5_real_handlers_are_not_phase_3_stubs_when_unconfigured():
    for tool_name in REAL_PHASE_5_TOOLS - {"retrieve_rag"}:
        if tool_name == "web_search":
            with web_search_context(settings(Path(".runtime/test")), provider=None):
                result = json.loads(registry.dispatch(tool_name, {"query": "hello"}))
        else:
            result = json.loads(registry.dispatch(tool_name, {"query": "hello"}))

        assert result["success"] is False
        assert result["tool_name"] == tool_name
        assert result["code"] == "NOT_CONFIGURED"
        assert result.get("phase") != "phase_3_stub"
