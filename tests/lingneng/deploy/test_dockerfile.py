from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = ROOT / "deploy" / "lingneng" / "Dockerfile"


def _dockerfile_text() -> str:
    return DOCKERFILE.read_text()


def test_dockerfile_uses_pinned_uv_python_base() -> None:
    text = _dockerfile_text()

    assert re.search(
        r"^FROM ghcr\.io/astral-sh/uv:0\.11\.6-python3\.13-trixie@sha256:[a-f0-9]{64}",
        text,
        re.MULTILINE,
    )


def test_dockerfile_uses_frozen_uv_dependency_install_with_cacheable_inputs() -> None:
    text = _dockerfile_text()

    pyproject_index = text.index("COPY pyproject.toml uv.lock ./")
    dependency_sync_index = text.index(
        "uv sync --frozen --no-dev --no-install-project"
    )
    source_index = text.index("COPY . .")
    project_sync_index = text.rindex("uv sync --frozen --no-dev")

    assert pyproject_index < dependency_sync_index < source_index
    assert source_index < project_sync_index
    assert "touch README.md" in text


def test_dockerfile_starts_only_lingneng_api() -> None:
    text = _dockerfile_text()

    assert 'CMD ["/app/.venv/bin/python", "-m", "lingneng.api.server"]' in text
    assert "lingneng.api.server" in text
    assert "gateway run" not in text
    assert "dashboard" not in text
    assert "npm install" not in text
    assert "npm run build" not in text
    assert "ui-tui" not in text
    assert "web &&" not in text


def test_dockerfile_has_safe_runtime_defaults_without_secret_values() -> None:
    text = _dockerfile_text()

    assert "ENV PYTHONUNBUFFERED=1" in text
    assert "ENV UV_LINK_MODE=copy" in text
    assert "ENV HERMES_HOME=/data/hermes" in text
    assert "ENV LINGNENG_RUNTIME_DIR=/data/runtime" in text
    assert "ENV LINGNENG_API_HOST=0.0.0.0" in text
    assert "ENV LINGNENG_API_PORT=18083" in text
    assert "WORKDIR /app" in text
    assert "EXPOSE 18083" in text
    assert "/internal/agent/health" in text

    forbidden_secret_assignments = [
        "OPENAI_API_KEY=",
        "ANTHROPIC_API_KEY=",
        "OPENROUTER_API_KEY=",
        "LINGNENG_INTERNAL_API_KEY=",
        "LINGNENG_RAG_API_KEY=",
    ]
    for assignment in forbidden_secret_assignments:
        assert assignment not in text


def test_dockerfile_installs_minimal_system_dependencies() -> None:
    text = _dockerfile_text()

    for package in [
        "ca-certificates",
        "curl",
        "gcc",
        "git",
        "libffi-dev",
        "libolm-dev",
        "procps",
        "python3-dev",
        "ripgrep",
    ]:
        assert package in text
    assert "rm -rf /var/lib/apt/lists/*" in text
    assert "mkdir -p /data/runtime /data/hermes/logs" in text
    assert "chmod -R 0775 /data" in text
