from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = (
    REPO_ROOT / "tests" / "lingneng" / "fixtures" / "employee_answer_semantics.json"
)
TEMPLATE_PATH = (
    REPO_ROOT
    / "docs"
    / "lingneng-migration"
    / "reports"
    / "2026-06-14-employee-answer-semantics-comparison-template.md"
)

EMPLOYEE_TYPES = {
    "boss_assistant",
    "operation_specialist",
    "product_combo_advisor",
    "marketing_planner",
    "marketing_content_creator",
    "member_operator",
}
SCENARIO_TYPES = {
    "identity",
    "in_scope",
    "out_of_scope",
    "handoff",
    "insufficient_data",
    "tool_needed",
}
VALID_TOOLS = {
    "retrieve_rag",
    "employee_handoff",
    "list_skills",
    "search_skills",
    "read_skill",
    "read_skill_resource",
    "document_generation",
    "image_generation",
    "chart_visualization",
    "web_search",
}
REQUIRED_CASE_FIELDS = {
    "id",
    "employee_type",
    "query",
    "scenario_type",
    "expected_profile_markers",
    "forbidden_markers",
    "expected_handoff_target",
    "expected_tool_guidance",
    "expected_answer_shape",
    "requires_live_llm",
    "notes",
}
SAFE_ID_RE = re.compile(r"^[a-z0-9_:-]+$")


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_employee_answer_semantics_fixture_shape() -> None:
    data = load_fixture()
    assert data["schema_version"] == "1.0"
    assert set(data["employee_types"]) == EMPLOYEE_TYPES
    assert set(data["scenario_types"]) == SCENARIO_TYPES
    assert isinstance(data["cases"], list)
    assert len(data["cases"]) == len(EMPLOYEE_TYPES) * len(SCENARIO_TYPES)


def test_employee_answer_semantics_fixture_covers_each_employee_and_scenario() -> None:
    cases = load_fixture()["cases"]
    observed = {(case["employee_type"], case["scenario_type"]) for case in cases}
    expected = {
        (employee_type, scenario_type)
        for employee_type in EMPLOYEE_TYPES
        for scenario_type in SCENARIO_TYPES
    }
    assert observed == expected


def test_employee_answer_semantics_cases_are_public_and_actionable() -> None:
    for case in load_fixture()["cases"]:
        assert set(case) == REQUIRED_CASE_FIELDS
        assert SAFE_ID_RE.fullmatch(case["id"])
        assert case["employee_type"] in EMPLOYEE_TYPES
        assert case["scenario_type"] in SCENARIO_TYPES
        assert case["query"].strip()
        assert isinstance(case["requires_live_llm"], bool)
        assert case["requires_live_llm"] is False
        assert case["expected_profile_markers"]
        assert case["expected_answer_shape"]
        case_text = json.dumps(case, ensure_ascii=False)
        assert "/Users/" not in case_text
        assert "LingNengAI/app" not in case_text
        assert "entry_decision" not in case_text
        assert "request_plan" not in case_text
        assert "business_agent" not in case_text


def test_handoff_and_tool_guidance_values_are_valid() -> None:
    for case in load_fixture()["cases"]:
        target = case["expected_handoff_target"]
        if case["scenario_type"] == "handoff":
            assert target in EMPLOYEE_TYPES - {case["employee_type"]}
            assert "employee_handoff" in case["expected_tool_guidance"]
        else:
            assert target is None
        for tool_name in case["expected_tool_guidance"]:
            assert tool_name in VALID_TOOLS


def test_employee_answer_semantics_template_mentions_all_cases() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    for case in load_fixture()["cases"]:
        assert case["id"] in template
    assert "No exact live LLM wording is required" in template
    assert "LINGNENG_EMPLOYEE_SEMANTICS_LIVE_TEST_ENABLED" in template
