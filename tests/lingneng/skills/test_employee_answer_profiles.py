from pathlib import Path

import pytest
import yaml

from tests.lingneng.tools.test_toolset_policy import APPROVED_LINGNENG_TOOLS


REPO_ROOT = Path(__file__).resolve().parents[3]
EMPLOYEE_ROOT = REPO_ROOT / "skills" / "lingneng" / "employees"

EMPLOYEE_PROFILES = {
    "employee-boss-assistant": {
        "employee_type": "boss_assistant",
        "target_employee_types": [
            "operation_specialist",
            "product_combo_advisor",
            "marketing_planner",
            "marketing_content_creator",
            "member_operator",
        ],
        "tools": [
            "employee_handoff",
            "retrieve_rag",
            "read_skill",
            "search_skills",
            "document_generation",
            "chart_visualization",
            "web_search",
        ],
        "marker": "跨角色经营统筹",
    },
    "employee-operation-specialist": {
        "employee_type": "operation_specialist",
        "target_employee_types": [
            "boss_assistant",
            "product_combo_advisor",
            "marketing_planner",
            "member_operator",
        ],
        "tools": [
            "employee_handoff",
            "retrieve_rag",
            "read_skill",
            "search_skills",
            "document_generation",
            "chart_visualization",
            "web_search",
        ],
        "marker": "指标、原因、动作、负责人和周期",
    },
    "employee-product-combo-advisor": {
        "employee_type": "product_combo_advisor",
        "target_employee_types": [
            "boss_assistant",
            "operation_specialist",
            "marketing_planner",
            "marketing_content_creator",
        ],
        "tools": [
            "employee_handoff",
            "retrieve_rag",
            "read_skill",
            "search_skills",
            "document_generation",
            "chart_visualization",
            "web_search",
        ],
        "marker": "价格带、毛利约束和验证指标",
    },
    "employee-marketing-planner": {
        "employee_type": "marketing_planner",
        "target_employee_types": [
            "boss_assistant",
            "product_combo_advisor",
            "marketing_content_creator",
            "member_operator",
        ],
        "tools": [
            "employee_handoff",
            "retrieve_rag",
            "read_skill",
            "search_skills",
            "document_generation",
            "image_generation",
            "chart_visualization",
            "web_search",
        ],
        "marker": "主题、机制、渠道节奏和评估指标",
    },
    "employee-marketing-content-creator": {
        "employee_type": "marketing_content_creator",
        "target_employee_types": [
            "boss_assistant",
            "product_combo_advisor",
            "marketing_planner",
            "member_operator",
        ],
        "tools": [
            "employee_handoff",
            "retrieve_rag",
            "read_skill",
            "search_skills",
            "document_generation",
            "image_generation",
            "web_search",
        ],
        "marker": "渠道、卖点、语气和行动号召",
    },
    "employee-member-operator": {
        "employee_type": "member_operator",
        "target_employee_types": [
            "boss_assistant",
            "operation_specialist",
            "marketing_planner",
            "marketing_content_creator",
        ],
        "tools": [
            "employee_handoff",
            "retrieve_rag",
            "read_skill",
            "search_skills",
            "document_generation",
            "chart_visualization",
            "web_search",
        ],
        "marker": "会员分层、权益、触达节奏和复盘指标",
    },
}

REQUIRED_HEADINGS = [
    "## Role Identity",
    "## Service Audience",
    "## Business Scope",
    "## Operating Principles",
    "## Communication Style",
    "## Normal Answer Structure",
    "## Identity Reply Guidance",
    "## Out-of-Scope Guidance",
    "## Insufficient Data Guidance",
    "## Handoff Guidance",
    "## Tool Guidance",
    "## Prohibited Claims",
    "## Degradation",
]

COMMON_BODY_MARKERS = [
    "身份、问候、能力范围或越界",
    "不要把固定介绍追加到每个正常业务回答",
]

FORBIDDEN_MARKERS = [
    "/Users/",
    "LingNengAI/app",
    "entry_decision",
    "request_plan",
    "business_agent_node",
    "langchain_business_agent",
]


def _read_employee_skill(package_name: str) -> tuple[dict, str]:
    skill_file = EMPLOYEE_ROOT / package_name / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "---", skill_file
    frontmatter_end = next(
        index for index, line in enumerate(lines[1:], start=1) if line == "---"
    )
    frontmatter = yaml.safe_load("\n".join(lines[1:frontmatter_end]))
    body = "\n".join(lines[frontmatter_end + 1 :])
    assert isinstance(frontmatter, dict)
    return frontmatter, body


@pytest.mark.parametrize("package_name, expected", EMPLOYEE_PROFILES.items())
def test_employee_skill_profile_metadata(package_name, expected):
    frontmatter, _body = _read_employee_skill(package_name)
    metadata = frontmatter["metadata"]["lingneng"]

    assert metadata["employee_type"] == expected["employee_type"]
    assert metadata["target_employee_types"] == expected["target_employee_types"]
    assert metadata["target_employee_types"]
    valid_employee_types = _valid_employee_types()
    assert all(
        employee_type in valid_employee_types
        for employee_type in metadata["target_employee_types"]
    )
    assert metadata["employee_type"] not in metadata["target_employee_types"]

    assert metadata["tools"] == expected["tools"]
    assert metadata["tools"]
    assert set(metadata["tools"]) <= APPROVED_LINGNENG_TOOLS
    assert {"employee_handoff", "retrieve_rag", "read_skill"} <= set(
        metadata["tools"]
    )


@pytest.mark.parametrize("package_name, expected", EMPLOYEE_PROFILES.items())
def test_employee_skill_answer_profile_body(package_name, expected):
    _frontmatter, body = _read_employee_skill(package_name)

    for heading in REQUIRED_HEADINGS:
        assert heading in body
    for marker in COMMON_BODY_MARKERS:
        assert marker in body
    assert ("员工跳转" in body) or ("转交" in body)
    assert expected["marker"] in body
    for forbidden_marker in FORBIDDEN_MARKERS:
        assert forbidden_marker not in body


def _valid_employee_types() -> set[str]:
    return {profile["employee_type"] for profile in EMPLOYEE_PROFILES.values()}
