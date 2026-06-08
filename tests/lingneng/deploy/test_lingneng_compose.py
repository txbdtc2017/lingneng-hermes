from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = ROOT / "deploy" / "lingneng" / "docker-compose.yml"
ENV_EXAMPLE = ROOT / "deploy" / "lingneng" / ".env.example"


def _load_compose() -> dict[str, Any]:
    return yaml.safe_load(COMPOSE_FILE.read_text()) or {}


def _parse_env_example() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in ENV_EXAMPLE.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        assert sep == "=", f"Invalid env line: {raw_line!r}"
        values[key] = value
    return values


def _service_environment(service: dict[str, Any]) -> dict[str, str]:
    env = service.get("environment", {})
    if isinstance(env, dict):
        return {str(key): str(value) for key, value in env.items()}
    if isinstance(env, list):
        parsed: dict[str, str] = {}
        for item in env:
            key, _, value = str(item).partition("=")
            parsed[key] = value
        return parsed
    raise AssertionError(f"Unsupported compose environment type: {type(env)!r}")


def test_compose_defines_only_lingneng_api_service() -> None:
    compose = _load_compose()
    services = compose.get("services")

    assert isinstance(services, dict)
    assert set(services) == {"lingneng-hermes-api"}

    service = services["lingneng-hermes-api"]
    assert "container_name" not in service
    assert service.get("network_mode") != "host"
    assert "dashboard" not in services
    assert "gateway" not in services
    assert "redis" not in services
    assert "milvus" not in services
    assert "minio" not in services
    assert "rocketmq" not in services
    assert "nacos" not in services


def test_compose_builds_dedicated_lingneng_image() -> None:
    service = _load_compose()["services"]["lingneng-hermes-api"]

    assert service["image"] == "${LINGNENG_HERMES_IMAGE:-lingneng-hermes:local}"
    assert service["build"] == {
        "context": "../..",
        "dockerfile": "deploy/lingneng/Dockerfile",
    }


def test_compose_uses_safe_port_and_runtime_mounts() -> None:
    service = _load_compose()["services"]["lingneng-hermes-api"]

    assert service["ports"] == [
        "${LINGNENG_API_BIND_HOST:-127.0.0.1}:${LINGNENG_API_HOST_PORT:-18083}:${LINGNENG_API_PORT:-18083}"
    ]
    assert service["volumes"] == [
        "./data/runtime:/data/runtime",
        "./data/hermes:/data/hermes",
        "./logs:/data/hermes/logs",
    ]


def test_compose_sets_container_runtime_environment() -> None:
    service = _load_compose()["services"]["lingneng-hermes-api"]
    env = _service_environment(service)

    assert env["HERMES_HOME"] == "${HERMES_HOME:-/data/hermes}"
    assert env["LINGNENG_APP_ENV"] == "${LINGNENG_APP_ENV:-dev}"
    assert env["LINGNENG_AGENT_MODE"] == "${LINGNENG_AGENT_MODE:-fake}"
    assert env["LINGNENG_API_HOST"] == "${LINGNENG_API_HOST:-0.0.0.0}"
    assert env["LINGNENG_API_PORT"] == "${LINGNENG_API_PORT:-18083}"
    assert env["LINGNENG_RUNTIME_DIR"] == "${LINGNENG_RUNTIME_DIR:-/data/runtime}"
    assert (
        env["LINGNENG_SESSION_DB_PATH"]
        == "${LINGNENG_SESSION_DB_PATH:-/data/runtime/sessions.sqlite3}"
    )
    assert env["LINGNENG_ALLOW_INSECURE_LOCAL"] == "${LINGNENG_ALLOW_INSECURE_LOCAL:-1}"
    assert env["LINGNENG_INTERNAL_API_KEY"] == "${LINGNENG_INTERNAL_API_KEY:-}"
    assert env["LINGNENG_RAG_ENDPOINT"] == "${LINGNENG_RAG_ENDPOINT:-}"
    assert env["LINGNENG_RAG_API_KEY"] == "${LINGNENG_RAG_API_KEY:-}"
    assert env["OPENAI_API_KEY"] == "${OPENAI_API_KEY:-}"
    assert env["ANTHROPIC_API_KEY"] == "${ANTHROPIC_API_KEY:-}"
    assert env["OPENROUTER_API_KEY"] == "${OPENROUTER_API_KEY:-}"
    assert env["TAVILY_API_KEY"] == "${TAVILY_API_KEY:-}"


def test_env_example_defaults_to_no_secret_fake_mode() -> None:
    env = _parse_env_example()

    assert env["LINGNENG_HERMES_IMAGE"] == "lingneng-hermes:local"
    assert env["LINGNENG_UID"] == "10000"
    assert env["LINGNENG_GID"] == "10000"
    assert env["LINGNENG_APP_ENV"] == "dev"
    assert env["LINGNENG_AGENT_MODE"] == "fake"
    assert env["LINGNENG_API_HOST"] == "0.0.0.0"
    assert env["LINGNENG_API_PORT"] == "18083"
    assert env["LINGNENG_API_BIND_HOST"] == "127.0.0.1"
    assert env["LINGNENG_API_HOST_PORT"] == "18083"
    assert env["LINGNENG_RUNTIME_DIR"] == "/data/runtime"
    assert env["LINGNENG_SESSION_DB_PATH"] == "/data/runtime/sessions.sqlite3"
    assert env["HERMES_HOME"] == "/data/hermes"
    assert env["LINGNENG_ALLOW_INSECURE_LOCAL"] == "1"


def test_env_example_keeps_known_secrets_empty() -> None:
    env = _parse_env_example()
    secret_keys = {
        "LINGNENG_INTERNAL_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENROUTER_API_KEY",
        "LINGNENG_RAG_API_KEY",
        "TAVILY_API_KEY",
    }

    for key in secret_keys:
        assert key in env
        assert env[key] == ""
