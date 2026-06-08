from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "lingneng-health-check.sh"


def _script_text() -> str:
    return SCRIPT.read_text()


def test_health_check_script_checks_health_ready_and_sse() -> None:
    text = _script_text()

    assert "/internal/agent/health" in text
    assert "/internal/agent/ready" in text
    assert "/internal/agent/chat/stream" in text
    assert "lingneng-chat-smoke.py" in text
    assert "final" in text


def test_health_check_script_uses_safe_shell_settings_and_curl() -> None:
    text = _script_text()

    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text
    assert "curl" in text
    assert "python3" in text or "${PYTHON:-python3}" in text


def test_health_check_script_does_not_echo_internal_key() -> None:
    text = _script_text()

    assert "set -x" not in text
    assert 'echo "$LINGNENG_INTERNAL_API_KEY"' not in text
    assert "echo ${LINGNENG_INTERNAL_API_KEY}" not in text
    assert "printenv LINGNENG_INTERNAL_API_KEY" not in text
