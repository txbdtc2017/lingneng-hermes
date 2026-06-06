from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = (
    REPO_ROOT
    / "docs"
    / "lingneng-migration"
    / "reports"
    / "2026-06-06-output-comparison-fixture.json"
)
TEMPLATE_PATH = (
    REPO_ROOT
    / "docs"
    / "lingneng-migration"
    / "reports"
    / "2026-06-06-output-comparison-template.md"
)

REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "cases",
    "status_values",
    "scenario_types",
    "required_evidence",
}
REQUIRED_EMPLOYEE_TYPES = {
    "boss_assistant",
    "operation_specialist",
    "marketing_planner",
    "marketing_content_creator",
    "member_operator",
    "product_combo_advisor",
}
REQUIRED_SCENARIO_TYPES = {
    "no_tool",
    "rag",
    "artifact",
    "attachment",
    "long_conversation",
}
REQUIRED_CASE_FIELDS = {
    "case_id",
    "employee_type",
    "scenario_type",
    "request",
    "expected_event_order",
    "expected_tool_policy",
    "lingnengai_output",
    "lingneng_hermes_output",
    "citations",
    "artifacts",
    "trace_summary",
    "evaluator_notes",
    "status",
}
REQUIRED_STATUS_VALUES = {"pending", "pass", "fail", "deferred"}
REQUIRED_EVIDENCE = {
    "sanitized_java_compatible_request_summary",
    "sse_event_order",
    "tool_call_policy_result",
    "citation_summary",
    "artifact_summary",
    "trace_summary",
    "evaluator_notes",
    "final_decision",
}
REQUIRED_REQUEST_FIELDS = {
    "request_id",
    "tenant_id",
    "user_id",
    "session_id",
    "conversation_id",
    "query",
    "employee",
    "history",
    "attachments",
    "options",
    "stream_options",
}
REQUIRED_TOOL_POLICY_FIELDS = {
    "tool_calls_expected",
    "allowed_tools",
    "forbidden_tools",
    "placeholder_tool_calls",
    "notes",
}
REQUIRED_OUTPUT_FIELDS = {
    "status",
    "answer_text",
    "captured_events",
    "notes",
}
REQUIRED_TRACE_SUMMARY_FIELDS = {
    "status",
    "run_id",
    "event_order_observed",
    "tool_call_count",
    "history_count",
    "notes",
}
JAVA_COMPATIBLE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_:-]*$")
SECRET_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bauthorization\b",
        r"\b(?:access|refresh|id|session)_token\s*[:=]",
        r"\btoken\s*[:=]",
        r"\bapi-key\b",
        r"\bapi_key\b",
        r"\bbearer\b",
        r"\bpassword\b",
        r"\bx-amz-signature\b",
        r"\bx-amz-credential\b",
        r"\bx-amz-security-token\b",
        r"\bawsaccesskeyid\b",
        r"\bsignature=",
        r"file://",
        r"/Users/",
        r"/home/",
        r"/tmp/",
        r"\b[a-z]:\\",
        r"\bAKIA[0-9A-Z]*",
        r"BEGIN PRIVATE KEY",
        r"\bsk-[A-Za-z0-9_-]+",
    )
]
FORBIDDEN_JSON_FIELD_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        (
            r"(^|_)(?:raw|provider|tool|private)"
            r"(?:_[a-z0-9]+)*_"
            r"(?:payload|response|output|args|url|transcript|prompt)($|_)"
        ),
        r"(^|_)signed_url($|_)",
        r"(^|_)prompt_body($|_)",
        r"(^|_)customer_transcript($|_)",
    )
]
FORBIDDEN_JSON_VALUE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        (
            r"\b(?:raw|provider|tool|private)"
            r"(?:[ _-]+[a-z0-9]+)*[ _-]+"
            r"(?:payload|response|output|args|url|transcript|prompt)s?\b"
        ),
        r"\braw_payload\b",
        r"\bprovider_response\b",
        r"\btool_output\b",
        r"\btool_args\b",
        r"\bprivate_url\b",
        r"\bsigned_url\b",
        r"\bprompt_body\b",
        r"\bcustomer_transcript\b",
        r"\bprovider result\b",
        r"\bprovider response\b",
        r"\btool payload\b",
        r"\btool output\b",
    )
]


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def matches_any(patterns: list[re.Pattern[str]], value: str) -> bool:
    return any(pattern.search(value) for pattern in patterns)


def iter_json_paths(value: object, path: str = "$") -> list[tuple[str, object]]:
    items: list[tuple[str, object]] = [(path, value)]
    if isinstance(value, dict):
        for key, nested_value in value.items():
            items.append((f"{path}.{key}", key))
            items.extend(iter_json_paths(nested_value, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, nested_value in enumerate(value):
            items.extend(iter_json_paths(nested_value, f"{path}[{index}]"))
    return items


def parse_markdown_case_table(template: str) -> set[tuple[str, str, str, str]]:
    rows: set[tuple[str, str, str, str]] = set()
    in_case_table = False
    for line in template.splitlines():
        if line == "## Case Table":
            in_case_table = True
            continue
        if in_case_table and line.startswith("## "):
            break
        if not in_case_table or not line.startswith("|"):
            continue

        cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
        if len(cells) < 4 or cells[0] in {"Case id", "---"}:
            continue
        rows.add((cells[0], cells[1], cells[2], cells[3]))

    return rows


def test_secret_patterns_detect_token_assignments_without_plain_prose_tokens() -> None:
    secret_samples = [
        "refresh_token=refresh-value",
        "id_token: id-value",
        "session_token = session-value",
        "token=query-value",
    ]
    safe_samples = [
        "token count is recorded as a non-sensitive aggregate",
        "refresh token handling is described without an assignment",
    ]

    for sample in secret_samples:
        assert matches_any(SECRET_PATTERNS, sample), sample
    for sample in safe_samples:
        assert not matches_any(SECRET_PATTERNS, sample), sample


def test_json_guard_patterns_detect_composite_payload_names_without_false_positive() -> None:
    forbidden_field_samples = [
        "raw_provider_payload",
        "provider_payload",
        "tool_payload",
        "private_payload",
        "raw_tool_args",
        "provider_response",
        "private_url",
    ]
    forbidden_value_samples = [
        "provider payload captured from a service",
        "private payload copied from a request",
        "tool args from a live call",
        "raw prompt included by mistake",
    ]

    for sample in forbidden_field_samples:
        assert matches_any(FORBIDDEN_JSON_FIELD_PATTERNS, sample), sample
    for sample in forbidden_value_samples:
        assert matches_any(FORBIDDEN_JSON_VALUE_PATTERNS, sample), sample

    assert not matches_any(FORBIDDEN_JSON_FIELD_PATTERNS, "placeholder_tool_calls")
    assert not matches_any(FORBIDDEN_JSON_VALUE_PATTERNS, "placeholder_tool_calls")


def test_fixture_has_required_top_level_structure() -> None:
    fixture = load_fixture()

    assert REQUIRED_TOP_LEVEL_KEYS <= set(fixture)
    assert isinstance(fixture["cases"], list)
    assert fixture["cases"]
    assert REQUIRED_STATUS_VALUES <= set(fixture["status_values"])
    assert REQUIRED_SCENARIO_TYPES <= set(fixture["scenario_types"])
    assert REQUIRED_EVIDENCE <= set(fixture["required_evidence"])


def test_fixture_covers_required_employees_and_scenarios() -> None:
    cases = load_fixture()["cases"]

    assert REQUIRED_EMPLOYEE_TYPES <= {case["employee_type"] for case in cases}
    assert REQUIRED_SCENARIO_TYPES <= {case["scenario_type"] for case in cases}


def test_case_table_matches_fixture_cases_exactly() -> None:
    fixture = load_fixture()
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    fixture_rows = {
        (
            case["case_id"],
            case["employee_type"],
            case["scenario_type"],
            case["status"],
        )
        for case in fixture["cases"]
    }

    assert len(fixture_rows) == len(fixture["cases"])
    assert parse_markdown_case_table(template) == fixture_rows


def test_each_case_has_required_fields_and_valid_status() -> None:
    fixture = load_fixture()
    status_values = set(fixture["status_values"])
    scenario_types = set(fixture["scenario_types"])

    for case in fixture["cases"]:
        assert REQUIRED_CASE_FIELDS <= set(case), case.get("case_id")
        assert case["employee_type"] in REQUIRED_EMPLOYEE_TYPES
        assert case["scenario_type"] in scenario_types
        assert case["status"] in status_values


def test_each_case_has_java_compatible_placeholder_request() -> None:
    for case in load_fixture()["cases"]:
        request = case["request"]
        assert REQUIRED_REQUEST_FIELDS <= set(request), case["case_id"]

        identifier_fields = [
            "request_id",
            "tenant_id",
            "user_id",
            "session_id",
            "conversation_id",
        ]
        for field in identifier_fields:
            assert JAVA_COMPATIBLE_IDENTIFIER.fullmatch(request[field]), (
                case["case_id"],
                field,
            )

        query = request["query"]
        employee = request["employee"]
        assert set(query) >= {"content"}
        assert set(employee) >= {"employee_id", "employee_type"}
        assert employee["employee_type"] == case["employee_type"]
        assert JAVA_COMPATIBLE_IDENTIFIER.fullmatch(employee["employee_id"])

        content = query["content"]
        content_lower = content.lower()
        assert "placeholder" in content_lower
        assert "synthetic" in content_lower
        assert "customer transcript" not in content_lower
        assert len(content) <= 240
        assert request["history"] == []
        assert isinstance(request["attachments"], list)


def test_expected_tool_policy_shape_is_stable() -> None:
    for case in load_fixture()["cases"]:
        policy = case["expected_tool_policy"]
        assert REQUIRED_TOOL_POLICY_FIELDS <= set(policy), case["case_id"]
        assert isinstance(policy["tool_calls_expected"], bool)
        assert isinstance(policy["allowed_tools"], list)
        assert isinstance(policy["forbidden_tools"], list)
        assert isinstance(policy["placeholder_tool_calls"], list)
        for placeholder_tool_call in policy["placeholder_tool_calls"]:
            assert set(placeholder_tool_call) >= {"tool_name", "status", "evidence"}
            assert placeholder_tool_call["status"] == "pending"

        policy_notes = policy["notes"].lower()
        assert any(
            word in policy_notes for word in ("placeholder", "pending", "sanitized")
        )


def test_expected_event_order_starts_and_terminates_correctly() -> None:
    terminal_events = {"final", "error"}

    for case in load_fixture()["cases"]:
        event_order = case["expected_event_order"]
        assert isinstance(event_order, list)
        assert event_order[0] == "run_started"
        assert event_order[-1] in terminal_events


def test_outputs_are_pending_placeholders() -> None:
    for case in load_fixture()["cases"]:
        assert case["status"] == "pending"
        assert case["citations"] == []
        assert case["artifacts"] == []
        for output_key in ("lingnengai_output", "lingneng_hermes_output"):
            output = case[output_key]
            assert REQUIRED_OUTPUT_FIELDS <= set(output), case["case_id"]
            assert output["status"] == "pending"
            assert output["answer_text"] == ""
            assert output["captured_events"] == []
            assert "placeholder" in output["notes"].lower()

        trace_summary = case["trace_summary"]
        assert REQUIRED_TRACE_SUMMARY_FIELDS <= set(trace_summary), case["case_id"]
        assert trace_summary["status"] == "pending"
        assert trace_summary["run_id"] == ""
        assert trace_summary["event_order_observed"] == []
        assert "placeholder" in trace_summary["notes"].lower()

        evaluator_notes = case["evaluator_notes"]
        assert evaluator_notes["status"] == "pending"
        assert evaluator_notes["notes"] == ""


def test_fixture_and_template_do_not_contain_secrets_or_local_paths() -> None:
    combined_text = "\n".join(
        [
            FIXTURE_PATH.read_text(encoding="utf-8"),
            TEMPLATE_PATH.read_text(encoding="utf-8"),
        ]
    )

    for pattern in SECRET_PATTERNS:
        assert pattern.search(combined_text) is None, pattern.pattern


def test_fixture_json_has_no_raw_provider_tool_or_private_payload_fields() -> None:
    for path, value in iter_json_paths(load_fixture()):
        if isinstance(value, str):
            for pattern in FORBIDDEN_JSON_FIELD_PATTERNS:
                if path.split(".")[-1] == value:
                    assert pattern.search(value) is None, (path, pattern.pattern)
            for pattern in FORBIDDEN_JSON_VALUE_PATTERNS:
                assert pattern.search(value) is None, (path, pattern.pattern)


def test_markdown_template_references_fixture_and_required_sections() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    template_lower = template.lower()

    assert (
        "docs/lingneng-migration/reports/"
        "2026-06-06-output-comparison-fixture.json"
        in template
    )
    for required_text in (
        "objective",
        "instructions",
        "case table",
        "per-case checklist",
        "comparison scoring notes",
        "evaluator notes",
        "tool calls",
        "citations",
        "artifacts",
        "trace summary",
        "final decision",
        "migration report scaffold",
        "does not contain real business quality judgments",
    ):
        assert required_text in template_lower
