from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lingneng.api.app import create_app
from lingneng.config.settings import LingNengSettings
from tests.lingneng.schemas.test_chat_request_schema import full_payload


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = (
    REPO_ROOT / "tests" / "lingneng" / "fixtures" / "employee_answer_semantics.json"
)
CASE_IDS = (
    "boss_assistant:identity",
    "marketing_planner:in_scope",
    "marketing_content_creator:tool_needed",
    "member_operator:handoff",
)
INTERNAL_KEY = "key"
SKIP_REASON = (
    "Set LINGNENG_EMPLOYEE_SEMANTICS_LIVE_TEST_ENABLED=true to run live "
    "employee semantics checks."
)


def _enabled() -> bool:
    return (
        os.getenv("LINGNENG_EMPLOYEE_SEMANTICS_LIVE_TEST_ENABLED", "").lower()
        == "true"
    )


pytestmark = pytest.mark.skipif(
    not _enabled(),
    reason=SKIP_REASON,
)


def _settings(tmp_path: Path) -> LingNengSettings:
    return LingNengSettings.from_env(
        {
            "LINGNENG_APP_ENV": "test",
            "LINGNENG_RUNTIME_DIR": str(tmp_path),
            "LINGNENG_AGENT_MODE": "hermes",
            "LINGNENG_INTERNAL_API_KEY": INTERNAL_KEY,
        }
    )


def _load_cases_by_id() -> dict[str, dict[str, Any]]:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in fixture["cases"]}
    missing = [case_id for case_id in CASE_IDS if case_id not in cases]
    if missing:
        raise AssertionError(f"Missing live employee semantics fixture cases: {missing}")
    return {case_id: cases[case_id] for case_id in CASE_IDS}


@pytest.fixture(scope="module")
def representative_cases() -> dict[str, dict[str, Any]]:
    return _load_cases_by_id()


def _payload_for_case(case_id: str, case: dict[str, Any]) -> dict[str, Any]:
    safe_case_id = case_id.replace(":", "-").replace("_", "-")
    employee_type = str(case["employee_type"])
    payload = full_payload()

    payload.update(
        {
            "request_id": f"live-employee-semantics-{safe_case_id}",
            "tenant_id": "live-employee-semantics-tenant",
            "user_id": "live-employee-semantics-user",
            "session_id": f"live-employee-semantics-session-{safe_case_id}",
            "conversation_id": f"live-employee-semantics-conversation-{safe_case_id}",
        }
    )
    payload["query"].update(
        {
            "message_id": f"live-employee-semantics-message-{safe_case_id}",
            "content": str(case["query"]),
            "content_type": "text",
        }
    )
    payload["employee"].update(
        {
            "employee_id": f"live-employee-{employee_type}",
            "employee_type": employee_type,
            "display_name": employee_type,
        }
    )
    payload["system_prompt"].update(
        {
            "content": f"LingNeng {employee_type} live semantics acceptance.",
            "version": "live-semantics",
        }
    )
    payload["skill"].update(
        {
            "skill_id": "",
            "skill_version": "live-semantics",
            "skill_hash": "live-semantics",
            "inline": None,
        }
    )
    payload["routing"]["confirmed_employee_type"] = employee_type
    payload["history"] = []
    payload["attachments"] = []
    return payload


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_live_employee_semantics_stream_acceptance(
    tmp_path: Path,
    representative_cases: dict[str, dict[str, Any]],
    case_id: str,
) -> None:
    app = create_app(settings=_settings(tmp_path))
    response = TestClient(app).post(
        "/internal/agent/chat/stream",
        json=_payload_for_case(case_id, representative_cases[case_id]),
        headers={"X-Internal-Key": INTERNAL_KEY},
    )

    assert response.status_code == 200, response.text
    assert "event: run_started\n" in response.text
    assert "event: final\n" in response.text
    assert "event: error\n" not in response.text
