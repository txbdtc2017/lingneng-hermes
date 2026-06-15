from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = REPO_ROOT / "tests" / "lingneng" / "fixtures" / "business_decision_mapping.json"
REPORT_PATH = (
    REPO_ROOT
    / "docs"
    / "lingneng-migration"
    / "reports"
    / "2026-06-15-business-decision-mapping.md"
)

JUDGMENT_AREAS = {
    "direct_answer",
    "non_jump_input",
    "route_suggest",
    "route_confirm",
    "explicit_switch",
    "boss_fallback",
    "tool_admission",
    "rag_internal",
    "web_realtime",
    "attachment_boundary",
    "history_boundary",
    "compliance_boundary",
}
HERMES_DESTINATIONS = {
    "employee_skill",
    "infrastructure_skill",
    "employee_handoff_tool",
    "tool_schema",
    "tool_run_guard",
    "sessiondb",
    "attachment_context",
    "sse_bridge",
}
MIGRATION_DECISIONS = {
    "migrate_as_guidance",
    "migrate_as_tool_contract",
    "migrate_as_fixture",
    "preserve_existing_runtime",
    "prohibit_runtime_migration",
}
REQUIRED_CASE_FIELDS = {
    "id",
    "old_judgment_area",
    "old_reference",
    "query",
    "current_employee_type",
    "expected_behavior",
    "expected_tool",
    "hermes_destination",
    "migration_decision",
    "forbidden_runtime_components",
    "notes",
}
REQUIRED_CASE_IDS = {
    "direct_answer:member_repurchase",
    "non_jump_input:identity",
    "route_suggest:content_to_planner",
    "route_confirm:broad_marketing",
    "explicit_switch:user_named_employee",
    "boss_fallback:unclear_business",
    "tool_admission:explicit_artifact",
    "rag_internal:training_rule",
    "web_realtime:latest_trend",
    "attachment_boundary:uploaded_file",
    "history_boundary:java_history",
    "compliance_boundary:unsafe_claim",
}
EMPLOYEE_TYPES = {
    "boss_assistant",
    "operation_specialist",
    "product_combo_advisor",
    "marketing_planner",
    "marketing_content_creator",
    "member_operator",
}
SAFE_ID_RE = re.compile(r"^[a-z0-9_:-]+$")
PROHIBITED_COMPONENTS = {
    "RuntimeDecisionService",
    "EntryDecisionService",
    "SemanticDecisionService",
    "RequestPlanner",
    "ToolAdmissionService",
    "light_llm_answer",
    "tool_only_agent",
    "direct_attachment_answer",
    "smalltalk_final_reply",
}


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_business_decision_mapping_fixture_shape() -> None:
    data = load_fixture()
    assert data["schema_version"] == "1.0"
    assert set(data["judgment_areas"]) == JUDGMENT_AREAS
    assert set(data["hermes_destinations"]) == HERMES_DESTINATIONS
    assert set(data["migration_decisions"]) == MIGRATION_DECISIONS
    assert isinstance(data["cases"], list)
    assert len(data["cases"]) >= len(JUDGMENT_AREAS)


def test_business_decision_mapping_covers_each_judgment_area() -> None:
    observed = {case["old_judgment_area"] for case in load_fixture()["cases"]}
    assert observed == JUDGMENT_AREAS


def test_business_decision_mapping_uses_planned_case_ids() -> None:
    observed = {case["id"] for case in load_fixture()["cases"]}
    assert observed == REQUIRED_CASE_IDS


def test_business_decision_mapping_cases_are_public_and_actionable() -> None:
    for case in load_fixture()["cases"]:
        assert set(case) == REQUIRED_CASE_FIELDS
        assert SAFE_ID_RE.fullmatch(case["id"])
        assert case["old_judgment_area"] in JUDGMENT_AREAS
        assert case["current_employee_type"] in EMPLOYEE_TYPES
        assert case["query"].strip()
        assert case["expected_behavior"].strip()
        assert case["hermes_destination"] in HERMES_DESTINATIONS
        assert case["migration_decision"] in MIGRATION_DECISIONS
        assert isinstance(case["forbidden_runtime_components"], list)
        for component in case["forbidden_runtime_components"]:
            assert component in PROHIBITED_COMPONENTS
        serialized = json.dumps(case, ensure_ascii=False)
        assert "/Users/" not in serialized
        assert "api_key" not in serialized.lower()
        assert "password" not in serialized.lower()
        assert "secret" not in serialized.lower()


def test_tool_expectations_match_judgment_area() -> None:
    cases = {case["id"]: case for case in load_fixture()["cases"]}
    assert cases["non_jump_input:identity"]["expected_tool"] is None
    assert cases["route_suggest:content_to_planner"]["expected_tool"] == "employee_handoff"
    assert cases["route_confirm:broad_marketing"]["expected_tool"] == "employee_handoff"
    assert cases["explicit_switch:user_named_employee"]["expected_tool"] == "employee_handoff"
    assert cases["rag_internal:training_rule"]["expected_tool"] == "retrieve_rag"
    assert cases["web_realtime:latest_trend"]["expected_tool"] == "web_search"


def test_mapping_report_mentions_every_case_and_forbidden_runtime() -> None:
    report = REPORT_PATH.read_text(encoding="utf-8")
    for case in load_fixture()["cases"]:
        assert case["id"] in report
    for component in PROHIBITED_COMPONENTS:
        assert component in report
    assert "Hermes-native destination" in report
    assert "No pre-agent router" in report
