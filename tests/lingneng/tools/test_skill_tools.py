from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import lingneng.tools.toolset  # noqa: F401
from lingneng.config.settings import LingNengSettings
from lingneng.tools.skill_tools import (
    list_skills_handler,
    read_skill_handler,
    read_skill_resource_handler,
    search_skills_handler,
    skill_tool_context,
)
from tests.lingneng.skills.test_skill_loader import write_skill
from tools.registry import registry


def settings(tmp_path: Path) -> LingNengSettings:
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path / ".runtime-test"),
        }
    )


def settings_with_skill_root(tmp_path: Path, skill_root: Path) -> LingNengSettings:
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path / ".runtime-test"),
            "LINGNENG_SKILL_ROOTS": str(skill_root),
        }
    )


def loads_tool_result(raw: str) -> dict[str, Any]:
    result = json.loads(raw)
    assert isinstance(result, dict)
    return result


def assert_public_result_shape(result: dict[str, Any], *, tool_name: str) -> None:
    assert set(result) == {
        "success",
        "tool_name",
        "status",
        "summary",
        "safe_output",
        "artifacts",
        "metadata",
        "code",
        "message",
    }
    assert result["tool_name"] == tool_name
    assert result["status"] in {"succeeded", "failed"}
    assert isinstance(result["safe_output"], dict)
    assert result["artifacts"] == []
    assert isinstance(result["metadata"], dict)


def assert_no_private_output(result: dict[str, Any]) -> None:
    serialized = json.dumps(result, ensure_ascii=False).lower()
    forbidden_fragments = (
        "traceback",
        "api_key",
        "/users/",
        "lingnengai/app/skills",
    )
    for fragment in forbidden_fragments:
        assert fragment not in serialized


def test_list_skills_handler_returns_real_bundled_skills_for_employee(tmp_path):
    with skill_tool_context(settings(tmp_path)):
        result = loads_tool_result(
            list_skills_handler(
                {
                    "employee_type": "marketing_planner",
                    "kind": "task",
                    "limit": 50,
                }
            )
        )

    assert_public_result_shape(result, tool_name="list_skills")
    assert result["success"] is True
    names = {item["package_name"] for item in result["safe_output"]["skills"]}
    assert "restaurant-campaign-planning" in names
    assert result.get("phase") != "phase_3_stub"
    assert_no_private_output(result)


def test_search_skills_handler_matches_chinese_copy_query(tmp_path):
    with skill_tool_context(settings(tmp_path)):
        result = loads_tool_result(search_skills_handler({"query": "小红书文案"}))

    assert_public_result_shape(result, tool_name="search_skills")
    assert result["success"] is True
    names = [item["package_name"] for item in result["safe_output"]["skills"]]
    assert "marketing-copy-generation" in names
    assert_no_private_output(result)


def test_search_skills_handler_rejects_overlong_query_before_catalog(tmp_path):
    overlong_query = "营" * 501

    with skill_tool_context(settings(tmp_path)):
        overlong_result = loads_tool_result(
            search_skills_handler({"query": overlong_query})
        )
        normal_result = loads_tool_result(search_skills_handler({"query": "营销"}))

    assert_public_result_shape(overlong_result, tool_name="search_skills")
    assert overlong_result["success"] is False
    assert overlong_result["code"] == "INVALID_ARGUMENT"
    assert_no_private_output(overlong_result)
    assert_public_result_shape(normal_result, tool_name="search_skills")
    assert normal_result["success"] is True
    assert_no_private_output(normal_result)


def test_read_skill_handler_returns_bounded_body_and_resource_manifest(tmp_path):
    with skill_tool_context(settings(tmp_path)):
        result = loads_tool_result(
            read_skill_handler(
                {
                    "skill_id": "restaurant-campaign-planning",
                    "max_chars": 600,
                }
            )
        )

    assert_public_result_shape(result, tool_name="read_skill")
    assert result["success"] is True
    assert result["safe_output"]["skill"]["package_name"] == (
        "restaurant-campaign-planning"
    )
    assert len(result["safe_output"]["body"]) <= 620
    resource_paths = {
        resource["path"]
        for resource in result["safe_output"]["resource_manifest"]["resources"]
    }
    assert "references/marketing-nodes.md" in resource_paths
    assert_no_private_output(result)


def test_read_skill_handler_preserves_normal_history_business_text(tmp_path):
    skill_root = tmp_path / "skills"
    write_skill(
        skill_root,
        "member-history-analysis",
        body="## Workflow\nRun member history analysis before campaign planning.\n",
    )

    with skill_tool_context(settings_with_skill_root(tmp_path, skill_root)):
        result = loads_tool_result(
            read_skill_handler(
                {
                    "skill_id": "member-history-analysis",
                    "max_chars": 600,
                }
            )
        )

    assert_public_result_shape(result, tool_name="read_skill")
    assert result["success"] is True
    assert result["safe_output"]["skill"]["package_name"] == "member-history-analysis"
    assert "member history analysis" in result["safe_output"]["body"]
    assert_no_private_output(result)


def test_read_skill_handler_removes_embedded_local_path_fragments(tmp_path):
    skill_root = tmp_path / "skills"
    write_skill(
        skill_root,
        "path-safety-skill",
        body=(
            "## Workflow\n"
            "请看 /workspace/private/data.csv 里的数据，并总结门店表现。\n"
            "Also remove /Users/alice/member.csv /home/app/private.json "
            "/tmp/cache.csv and C:\\Users\\alice\\member.csv, but keep guidance.\n"
        ),
    )

    with skill_tool_context(settings_with_skill_root(tmp_path, skill_root)):
        result = loads_tool_result(
            read_skill_handler(
                {
                    "skill_id": "path-safety-skill",
                    "max_chars": 600,
                }
            )
        )

    assert_public_result_shape(result, tool_name="read_skill")
    assert result["success"] is True
    serialized = json.dumps(result, ensure_ascii=False)
    for local_path in (
        "/workspace/private/data.csv",
        "/Users/alice/member.csv",
        "/home/app/private.json",
        "/tmp/cache.csv",
        "C:\\Users\\alice\\member.csv",
    ):
        assert local_path not in serialized
    assert "请看" in result["safe_output"]["body"]
    assert "里的数据" in result["safe_output"]["body"]
    assert "keep guidance" in result["safe_output"]["body"]
    assert_no_private_output(result)


def test_read_skill_resource_handler_rejects_path_traversal(tmp_path):
    with skill_tool_context(settings(tmp_path)):
        result = loads_tool_result(
            read_skill_resource_handler(
                {
                    "skill_id": "restaurant-campaign-planning",
                    "resource_id": "../SKILL.md",
                }
            )
        )

    assert_public_result_shape(result, tool_name="read_skill_resource")
    assert result["success"] is False
    assert result["code"] == "RESOURCE_NOT_ALLOWED"
    assert_no_private_output(result)


def test_read_skill_resource_handler_reads_manifest_listed_resource(tmp_path):
    with skill_tool_context(settings(tmp_path)):
        result = loads_tool_result(
            read_skill_resource_handler(
                {
                    "skill_id": "restaurant-campaign-planning",
                    "resource_id": "references/marketing-nodes.md",
                    "max_chars": 500,
                }
            )
        )

    assert_public_result_shape(result, tool_name="read_skill_resource")
    assert result["success"] is True
    assert result["tool_name"] == "read_skill_resource"
    assert result["safe_output"]["resource_id"] == "references/marketing-nodes.md"
    assert result["safe_output"]["content"]
    assert len(result["safe_output"]["content"]) <= 520
    assert "content_truncated" in result["safe_output"]
    assert result.get("phase") != "phase_3_stub"
    assert_no_private_output(result)


def test_registry_dispatch_read_skill_uses_real_handler_in_context(tmp_path):
    with skill_tool_context(settings(tmp_path)):
        result = loads_tool_result(
            registry.dispatch(
                "read_skill",
                {"skill_id": "restaurant-campaign-planning", "max_chars": 600},
            )
        )

    assert_public_result_shape(result, tool_name="read_skill")
    assert result["success"] is True
    assert result["safe_output"]["skill"]["package_name"] == (
        "restaurant-campaign-planning"
    )
    assert result.get("phase") != "phase_3_stub"
    assert_no_private_output(result)


def test_skill_handlers_fail_closed_without_context():
    handlers = (
        ("list_skills", list_skills_handler, {}),
        ("search_skills", search_skills_handler, {"query": "小红书文案"}),
        ("read_skill", read_skill_handler, {"skill_id": "restaurant-campaign-planning"}),
        (
            "read_skill_resource",
            read_skill_resource_handler,
            {
                "skill_id": "restaurant-campaign-planning",
                "resource_id": "references/marketing-nodes.md",
            },
        ),
    )

    for tool_name, handler, args in handlers:
        result = loads_tool_result(handler(args))
        assert_public_result_shape(result, tool_name=tool_name)
        assert result["success"] is False
        assert result["code"] == "NOT_CONFIGURED"
        assert result.get("phase") != "phase_3_stub"
        assert_no_private_output(result)


def test_unknown_skill_returns_not_found(tmp_path):
    with skill_tool_context(settings(tmp_path)):
        result = loads_tool_result(read_skill_handler({"skill_id": "unknown-skill"}))

    assert_public_result_shape(result, tool_name="read_skill")
    assert result["success"] is False
    assert result["code"] == "NOT_FOUND"
    assert_no_private_output(result)


def test_invalid_args_return_invalid_argument(tmp_path):
    cases = (
        ("search_skills", search_skills_handler, {}),
        ("read_skill", read_skill_handler, {}),
        (
            "read_skill_resource",
            read_skill_resource_handler,
            {"skill_id": "restaurant-campaign-planning"},
        ),
        (
            "read_skill",
            read_skill_handler,
            {
                "skill_id": "restaurant-campaign-planning",
                "max_chars": "not-an-int",
            },
        ),
    )

    with skill_tool_context(settings(tmp_path)):
        for tool_name, handler, args in cases:
            result = loads_tool_result(handler(args))
            assert_public_result_shape(result, tool_name=tool_name)
            assert result["success"] is False
            assert result["code"] == "INVALID_ARGUMENT"
            assert_no_private_output(result)


def test_list_and_search_malformed_optional_args_return_invalid_argument(tmp_path):
    cases = (
        ("list_skills", list_skills_handler, {"limit": 0}),
        ("list_skills", list_skills_handler, {"limit": "not-an-int"}),
        ("list_skills", list_skills_handler, {"employee_type": 123}),
        ("list_skills", list_skills_handler, {"kind": 123}),
        ("search_skills", search_skills_handler, {"query": "营销", "limit": 0}),
        (
            "search_skills",
            search_skills_handler,
            {"query": "营销", "limit": "not-an-int"},
        ),
        ("search_skills", search_skills_handler, {"query": "营销", "employee_type": 123}),
        ("search_skills", search_skills_handler, {"query": "营销", "kind": 123}),
    )

    with skill_tool_context(settings(tmp_path)):
        for tool_name, handler, args in cases:
            result = loads_tool_result(handler(args))
            assert_public_result_shape(result, tool_name=tool_name)
            assert result["success"] is False
            assert result["code"] == "INVALID_ARGUMENT"
            assert_no_private_output(result)
