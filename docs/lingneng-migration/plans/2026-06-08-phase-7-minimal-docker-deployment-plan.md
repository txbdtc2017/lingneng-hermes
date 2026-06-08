# Phase 7 Minimal Docker Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the smallest Docker deployment path that can run the LingNeng-Hermes Java-compatible API without CI/CD.

**Architecture:** Add a dedicated `deploy/lingneng/` Docker surface that runs only `python -m lingneng.api.server`. The image installs the Python/Hermes runtime from the repository lockfile, while Compose mounts runtime state and Hermes config under `deploy/lingneng/data/`. Static tests lock the deployment boundary so root Hermes gateway/dashboard Docker assets are not repurposed accidentally.

**Tech Stack:** Docker, Docker Compose, Python 3.13, uv, FastAPI/Uvicorn, pytest, PyYAML, shell script with `curl`.

---

## Approved Spec

This plan implements:

```text
docs/lingneng-migration/specs/2026-06-08-phase-7-minimal-docker-deployment-spec.md
```

Required durable context was reloaded before writing this plan:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`
- `docs/lingneng-migration/specs/2026-06-08-phase-7-minimal-docker-deployment-spec.md`

## Scope

Implement the minimal Docker deployment assets:

- `deploy/lingneng/Dockerfile`
- `deploy/lingneng/docker-compose.yml`
- `deploy/lingneng/.env.example`
- `deploy/lingneng/README.md`
- `scripts/lingneng-health-check.sh`
- `tests/lingneng/deploy/test_lingneng_compose.py`
- `tests/lingneng/deploy/test_dockerfile.py`
- `tests/lingneng/deploy/test_health_check_script.py`

## Non-Goals

Do not implement:

- GitHub Actions, Jenkins, Gitea, or any CI/CD workflow.
- Registry push/pull flow.
- Remote SSH deployment.
- Automated rollback scripts.
- Kubernetes, Helm, Swarm, Nomad, or systemd.
- Redis, Milvus, MinIO, RocketMQ, Nacos, RAG, or training ingestion services.
- Java code changes.
- Runtime API behavior changes under `lingneng/`.
- Changes to the upstream root `Dockerfile`, `docker-compose.yml`, or `docker-compose.windows.yml`.

## File Map

- `deploy/lingneng/Dockerfile`: Dedicated LingNeng API image. It installs locked Python dependencies and starts `/app/.venv/bin/python -m lingneng.api.server`.
- `deploy/lingneng/docker-compose.yml`: Single-service Compose template for `lingneng-hermes-api`.
- `deploy/lingneng/.env.example`: No-secret local fake-mode defaults plus empty keys for Hermes-mode operation.
- `deploy/lingneng/README.md`: Manual runbook for build/start/log/health/stop and Hermes-mode LLM config.
- `scripts/lingneng-health-check.sh`: Manual health/ready/SSE smoke helper.
- `tests/lingneng/deploy/test_lingneng_compose.py`: Static tests for compose and `.env.example`.
- `tests/lingneng/deploy/test_dockerfile.py`: Static tests for dedicated Dockerfile boundary.
- `tests/lingneng/deploy/test_health_check_script.py`: Static tests for the health-check script.

## Decisions

- Use the pinned `uv` Python 3.13 base image already present in the upstream Dockerfile:

```text
ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie@sha256:b3c543b6c4f23a5f2df22866bd7857e5d304b67a564f4feab6ac22044dde719b
```

- Use `uv sync --frozen --no-dev` during image build.
- Use `/app/.venv/bin/python -m lingneng.api.server` at runtime instead of `uv run`, so startup does not resolve dependencies.
- Use `LINGNENG_API_HOST=0.0.0.0` inside the container and default host publishing to `127.0.0.1:18083`.
- Use Compose bridge networking. Do not use `network_mode: host`.
- Use `user: "${LINGNENG_UID:-10000}:${LINGNENG_GID:-10000}"` in Compose so operators can map writes to a host UID/GID.
- Use the existing `scripts/lingneng-chat-smoke.py` from the health-check script for SSE parsing instead of duplicating SSE parsing in shell.

## User Confirmations Needed Before Execution

None. The user has already confirmed:

- no CI/CD is needed.
- only the simplest Docker-deployable path is needed.

If the user later wants a different default port, bind address, runtime path, or auth policy, update the spec and this plan before implementation.

---

## Task 1: Add Minimal Docker Static Tests And Assets

**Files:**
- Create: `tests/lingneng/deploy/test_lingneng_compose.py`
- Create: `tests/lingneng/deploy/test_dockerfile.py`
- Create: `tests/lingneng/deploy/test_health_check_script.py`
- Create: `deploy/lingneng/Dockerfile`
- Create: `deploy/lingneng/docker-compose.yml`
- Create: `deploy/lingneng/.env.example`
- Create: `deploy/lingneng/README.md`
- Create: `scripts/lingneng-health-check.sh`

### Step 1: Create the failing Compose and env tests

- [ ] Add `tests/lingneng/deploy/test_lingneng_compose.py`:

```python
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

    assert env["LINGNENG_API_HOST"] == "${LINGNENG_API_HOST:-0.0.0.0}"
    assert env["LINGNENG_API_PORT"] == "${LINGNENG_API_PORT:-18083}"
    assert env["LINGNENG_RUNTIME_DIR"] == "${LINGNENG_RUNTIME_DIR:-/data/runtime}"
    assert env["HERMES_HOME"] == "${HERMES_HOME:-/data/hermes}"
    assert env["LINGNENG_AGENT_MODE"] == "${LINGNENG_AGENT_MODE:-fake}"
    assert env["LINGNENG_ALLOW_INSECURE_LOCAL"] == "${LINGNENG_ALLOW_INSECURE_LOCAL:-1}"
    assert env["LINGNENG_INTERNAL_API_KEY"] == "${LINGNENG_INTERNAL_API_KEY:-}"
    assert env["OPENAI_API_KEY"] == "${OPENAI_API_KEY:-}"


def test_env_example_defaults_to_no_secret_fake_mode() -> None:
    env = _parse_env_example()

    assert env["LINGNENG_APP_ENV"] == "dev"
    assert env["LINGNENG_AGENT_MODE"] == "fake"
    assert env["LINGNENG_API_HOST"] == "0.0.0.0"
    assert env["LINGNENG_API_PORT"] == "18083"
    assert env["LINGNENG_API_BIND_HOST"] == "127.0.0.1"
    assert env["LINGNENG_API_HOST_PORT"] == "18083"
    assert env["LINGNENG_RUNTIME_DIR"] == "/data/runtime"
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
```

### Step 2: Create the failing Dockerfile tests

- [ ] Add `tests/lingneng/deploy/test_dockerfile.py`:

```python
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

    assert "ENV HERMES_HOME=/data/hermes" in text
    assert "ENV LINGNENG_RUNTIME_DIR=/data/runtime" in text
    assert "ENV LINGNENG_API_HOST=0.0.0.0" in text
    assert "ENV LINGNENG_API_PORT=18083" in text

    forbidden_secret_assignments = [
        "OPENAI_API_KEY=",
        "ANTHROPIC_API_KEY=",
        "OPENROUTER_API_KEY=",
        "LINGNENG_INTERNAL_API_KEY=",
        "LINGNENG_RAG_API_KEY=",
    ]
    for assignment in forbidden_secret_assignments:
        assert assignment not in text
```

### Step 3: Create the failing health-check script tests

- [ ] Add `tests/lingneng/deploy/test_health_check_script.py`:

```python
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
```

### Step 4: Run static tests and verify they fail

- [ ] Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/deploy/test_lingneng_compose.py \
  tests/lingneng/deploy/test_dockerfile.py \
  tests/lingneng/deploy/test_health_check_script.py \
  -q
```

Expected: fail because `deploy/lingneng/` assets and `scripts/lingneng-health-check.sh` do not exist yet.

### Step 5: Add the dedicated Dockerfile

- [ ] Create `deploy/lingneng/Dockerfile`:

```Dockerfile
FROM ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie@sha256:b3c543b6c4f23a5f2df22866bd7857e5d304b67a564f4feab6ac22044dde719b

ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy
ENV HERMES_HOME=/data/hermes
ENV LINGNENG_RUNTIME_DIR=/data/runtime
ENV LINGNENG_API_HOST=0.0.0.0
ENV LINGNENG_API_PORT=18083

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      gcc \
      git \
      libffi-dev \
      libolm-dev \
      procps \
      python3-dev \
      ripgrep && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN touch README.md && uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

RUN mkdir -p /data/runtime /data/hermes/logs && \
    chmod -R 0775 /data

EXPOSE 18083

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS "http://127.0.0.1:${LINGNENG_API_PORT:-18083}/internal/agent/health" || exit 1

CMD ["/app/.venv/bin/python", "-m", "lingneng.api.server"]
```

### Step 6: Add the dedicated Compose template

- [ ] Create `deploy/lingneng/docker-compose.yml`:

```yaml
services:
  lingneng-hermes-api:
    build:
      context: ../..
      dockerfile: deploy/lingneng/Dockerfile
    image: ${LINGNENG_HERMES_IMAGE:-lingneng-hermes:local}
    restart: unless-stopped
    user: "${LINGNENG_UID:-10000}:${LINGNENG_GID:-10000}"
    ports:
      - "${LINGNENG_API_BIND_HOST:-127.0.0.1}:${LINGNENG_API_HOST_PORT:-18083}:${LINGNENG_API_PORT:-18083}"
    environment:
      HERMES_HOME: ${HERMES_HOME:-/data/hermes}
      LINGNENG_APP_ENV: ${LINGNENG_APP_ENV:-dev}
      LINGNENG_AGENT_MODE: ${LINGNENG_AGENT_MODE:-fake}
      LINGNENG_API_HOST: ${LINGNENG_API_HOST:-0.0.0.0}
      LINGNENG_API_PORT: ${LINGNENG_API_PORT:-18083}
      LINGNENG_RUNTIME_DIR: ${LINGNENG_RUNTIME_DIR:-/data/runtime}
      LINGNENG_SESSION_DB_PATH: ${LINGNENG_SESSION_DB_PATH:-/data/runtime/sessions.sqlite3}
      LINGNENG_ALLOW_INSECURE_LOCAL: ${LINGNENG_ALLOW_INSECURE_LOCAL:-1}
      LINGNENG_INTERNAL_API_KEY: ${LINGNENG_INTERNAL_API_KEY:-}
      LINGNENG_RAG_ENDPOINT: ${LINGNENG_RAG_ENDPOINT:-}
      LINGNENG_RAG_API_KEY: ${LINGNENG_RAG_API_KEY:-}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
      OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:-}
      TAVILY_API_KEY: ${TAVILY_API_KEY:-}
    volumes:
      - ./data/runtime:/data/runtime
      - ./data/hermes:/data/hermes
      - ./logs:/data/hermes/logs
```

### Step 7: Add the no-secret env example

- [ ] Create `deploy/lingneng/.env.example`:

```dotenv
# LingNeng-Hermes minimal Docker deployment.
# Copy to deploy/lingneng/.env and fill real values there.

LINGNENG_HERMES_IMAGE=lingneng-hermes:local
LINGNENG_UID=10000
LINGNENG_GID=10000

LINGNENG_APP_ENV=dev
LINGNENG_AGENT_MODE=fake
LINGNENG_API_HOST=0.0.0.0
LINGNENG_API_PORT=18083
LINGNENG_API_BIND_HOST=127.0.0.1
LINGNENG_API_HOST_PORT=18083
LINGNENG_RUNTIME_DIR=/data/runtime
LINGNENG_SESSION_DB_PATH=/data/runtime/sessions.sqlite3
HERMES_HOME=/data/hermes

# Local no-secret smoke mode only. Set to 0 and configure
# LINGNENG_INTERNAL_API_KEY before exposing beyond localhost.
LINGNENG_ALLOW_INSECURE_LOCAL=1
LINGNENG_INTERNAL_API_KEY=

# Basic Hermes-mode LLM secrets. Keep real values in deploy/lingneng/.env only.
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
OPENROUTER_API_KEY=

# Optional business integrations. Empty means not configured.
LINGNENG_RAG_ENDPOINT=
LINGNENG_RAG_API_KEY=
TAVILY_API_KEY=
```

### Step 8: Add the manual runbook

- [ ] Create `deploy/lingneng/README.md`:

````markdown
# LingNeng-Hermes Minimal Docker Deployment

This Compose setup runs only the LingNeng Java-compatible API:

```text
POST /internal/agent/chat/stream
GET  /internal/agent/health
GET  /internal/agent/ready
```

It does not start Hermes dashboard, gateway, Redis, Milvus, MinIO, RocketMQ,
Nacos, or any CI/CD job.

## 1. Prepare Environment

From the repository root:

```bash
cp deploy/lingneng/.env.example deploy/lingneng/.env
mkdir -p deploy/lingneng/data/runtime deploy/lingneng/data/hermes deploy/lingneng/logs
```

On Linux, set host UID/GID so bind-mounted files remain writable:

```bash
sed -i.bak "s/^LINGNENG_UID=.*/LINGNENG_UID=$(id -u)/" deploy/lingneng/.env
sed -i.bak "s/^LINGNENG_GID=.*/LINGNENG_GID=$(id -g)/" deploy/lingneng/.env
```

## 2. Preflight Port

Default host port is `127.0.0.1:18083`.

```bash
lsof -nP -iTCP:18083 -sTCP:LISTEN
```

If an unrelated process is already listening, edit `deploy/lingneng/.env`:

```dotenv
LINGNENG_API_HOST_PORT=18085
```

## 3. Start In Fake Smoke Mode

The default `.env.example` values use `LINGNENG_AGENT_MODE=fake` and do not need
LLM credentials.

```bash
docker compose --env-file deploy/lingneng/.env \
  -f deploy/lingneng/docker-compose.yml \
  -p lingneng-hermes up -d --build
```

Check logs:

```bash
docker compose --env-file deploy/lingneng/.env \
  -f deploy/lingneng/docker-compose.yml \
  -p lingneng-hermes logs -f lingneng-hermes-api
```

Run health and SSE smoke:

```bash
scripts/lingneng-health-check.sh http://127.0.0.1:18083
```

## 4. Configure Real Hermes LLM Mode

Edit `deploy/lingneng/.env`:

```dotenv
LINGNENG_AGENT_MODE=hermes
LINGNENG_ALLOW_INSECURE_LOCAL=0
LINGNENG_INTERNAL_API_KEY=replace-with-server-local-secret
OPENAI_API_KEY=replace-with-llm-secret
```

Create `deploy/lingneng/data/hermes/config.yaml`:

```yaml
model:
  provider: custom
  default: your-model-name
  base_url: https://your-llm-endpoint.example/v1
  api_key: ""
  api_mode: chat_completions
```

Keep `api_key` empty in `config.yaml`; inject the real key through
`deploy/lingneng/.env`.

When `LINGNENG_INTERNAL_API_KEY` is set, Java callers must send:

```text
X-Internal-Key: <same value>
```

## 5. Expose Safely To Java

Keep `LINGNENG_API_BIND_HOST=127.0.0.1` when Java runs on the same host or behind
a local reverse proxy.

Use a private LAN bind address only when needed:

```dotenv
LINGNENG_API_BIND_HOST=10.0.0.12
```

Do not set `LINGNENG_API_BIND_HOST=0.0.0.0` unless
`LINGNENG_INTERNAL_API_KEY` is non-empty and network access is otherwise
controlled.

## 6. Stop

```bash
docker compose --env-file deploy/lingneng/.env \
  -f deploy/lingneng/docker-compose.yml \
  -p lingneng-hermes down
```
````

### Step 9: Add the health-check script

- [ ] Create `scripts/lingneng-health-check.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

base_url="${1:-http://127.0.0.1:18083}"
timeout_seconds="${LINGNENG_HEALTH_TIMEOUT_SECONDS:-30}"
python_bin="${PYTHON:-python3}"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/.." && pwd)"

curl_headers=()
if [[ -n "${LINGNENG_INTERNAL_API_KEY:-}" ]]; then
  curl_headers=(-H "X-Internal-Key: ${LINGNENG_INTERNAL_API_KEY}")
fi

check_json_status() {
  local url="$1"
  local expected_status="$2"
  local body

  body="$(curl -fsS --max-time "${timeout_seconds}" "${curl_headers[@]}" "${url}")"
  BODY="${body}" EXPECTED_STATUS="${expected_status}" "${python_bin}" - <<'PY'
import json
import os
import sys

body = os.environ["BODY"]
expected = os.environ["EXPECTED_STATUS"]
data = json.loads(body)
actual = data.get("status")
if actual != expected:
    print(f"expected status {expected!r}, got {actual!r}", file=sys.stderr)
    sys.exit(1)
PY
}

echo "checking health"
check_json_status "${base_url%/}/internal/agent/health" "ok"

echo "checking ready"
check_json_status "${base_url%/}/internal/agent/ready" "ready"

echo "checking sse final"
"${python_bin}" "${repo_root}/scripts/lingneng-chat-smoke.py" \
  --url "${base_url%/}/internal/agent/chat/stream" \
  --request-id "docker-smoke-$(date +%s)" \
  --tenant-id "docker-smoke-tenant" \
  --user-id "docker-smoke-user" \
  --session-id "docker-smoke-session" \
  --conversation-id "docker-smoke-conversation" \
  --employee-id "docker-smoke-employee" \
  --employee-type "boss_assistant" \
  --query "ping" \
  --timeout-seconds "${timeout_seconds}" | tee /tmp/lingneng-health-check-sse.txt

grep -q "event_order: .*final" /tmp/lingneng-health-check-sse.txt
echo "lingneng health check passed"
```

- [ ] Make it executable:

```bash
chmod +x scripts/lingneng-health-check.sh
```

### Step 10: Run static tests and verify they pass

- [ ] Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/deploy/test_lingneng_compose.py \
  tests/lingneng/deploy/test_dockerfile.py \
  tests/lingneng/deploy/test_health_check_script.py \
  -q
```

Expected: pass.

### Step 11: Run targeted lint on new Python tests

- [ ] Run:

```bash
uv run --extra dev python -m ruff check tests/lingneng/deploy
```

Expected: pass.

### Step 12: Commit and push Task 1

- [ ] Run:

```bash
git status --short
git add \
  docs/lingneng-migration/specs/2026-06-08-phase-7-minimal-docker-deployment-spec.md \
  docs/lingneng-migration/plans/2026-06-08-phase-7-minimal-docker-deployment-plan.md \
  deploy/lingneng/Dockerfile \
  deploy/lingneng/docker-compose.yml \
  deploy/lingneng/.env.example \
  deploy/lingneng/README.md \
  scripts/lingneng-health-check.sh \
  tests/lingneng/deploy/test_lingneng_compose.py \
  tests/lingneng/deploy/test_dockerfile.py \
  tests/lingneng/deploy/test_health_check_script.py
git commit -m "feat: 增加灵能最小 Docker 部署"
git push
```

Expected: commit and push succeed only after Step 10 and Step 11 pass.

---

## Task 2: Validate Compose Rendering And Docker Image Build

**Files:**
- Modify if needed: `deploy/lingneng/Dockerfile`
- Modify if needed: `deploy/lingneng/docker-compose.yml`
- Modify if needed: `deploy/lingneng/README.md`

### Step 1: Preflight Docker availability

- [ ] Run:

```bash
docker --version
docker compose version
```

Expected: both commands exit 0. If Docker is not available in the current environment, stop this task, record the exact failure in the final response, and do not claim Docker verification passed.

### Step 2: Validate Compose config

- [ ] Run:

```bash
docker compose --env-file deploy/lingneng/.env.example \
  -f deploy/lingneng/docker-compose.yml \
  config >/tmp/lingneng-compose-config.txt
```

Expected: command exits 0 and writes rendered config to `/tmp/lingneng-compose-config.txt`.

### Step 3: Inspect rendered config for critical service fields

- [ ] Run:

```bash
rg -n "lingneng-hermes-api|127.0.0.1:18083:18083|LINGNENG_AGENT_MODE|/data/runtime|/data/hermes" /tmp/lingneng-compose-config.txt
```

Expected: output contains the service name, port mapping, fake mode env, runtime mount, and Hermes mount.

### Step 4: Build the dedicated image

- [ ] Run:

```bash
docker build -f deploy/lingneng/Dockerfile \
  -t lingneng-hermes:local-smoke .
```

Expected: image builds successfully.

### Step 5: Fix build or config issues if any appear

- [ ] If Step 2 or Step 4 fails because of a deployment asset bug, edit only the minimal affected files:

```text
deploy/lingneng/Dockerfile
deploy/lingneng/docker-compose.yml
deploy/lingneng/README.md
tests/lingneng/deploy/test_lingneng_compose.py
tests/lingneng/deploy/test_dockerfile.py
```

- [ ] Re-run:

```bash
uv run --extra dev python -m pytest tests/lingneng/deploy -q
docker compose --env-file deploy/lingneng/.env.example \
  -f deploy/lingneng/docker-compose.yml \
  config >/tmp/lingneng-compose-config.txt
docker build -f deploy/lingneng/Dockerfile \
  -t lingneng-hermes:local-smoke .
```

Expected: all commands pass.

### Step 6: Commit and push any corrections

- [ ] If this task changed files, run:

```bash
git status --short
git add deploy/lingneng tests/lingneng/deploy
git commit -m "fix: 修复灵能镜像构建配置"
git push
```

Expected: commit and push succeed only after Step 5 passes. If no files changed, do not create an empty commit.

---

## Task 3: Run Local Fake-Mode Compose Smoke

**Files:**
- Modify if needed: `deploy/lingneng/README.md`
- Modify if needed: `scripts/lingneng-health-check.sh`
- Modify if needed: `deploy/lingneng/docker-compose.yml`

### Step 1: Preflight the intended host port

- [ ] Run:

```bash
lsof -nP -iTCP:18083 -sTCP:LISTEN
```

Expected: no unrelated listener on `18083`.

If an unrelated listener exists, do not kill it. Create a local untracked env file for smoke:

```bash
cp deploy/lingneng/.env.example /tmp/lingneng-hermes-smoke.env
printf '\nLINGNENG_API_HOST_PORT=18085\n' >> /tmp/lingneng-hermes-smoke.env
lsof -nP -iTCP:18085 -sTCP:LISTEN
```

Expected: selected alternate port has no unrelated listener. Use `18085` in the health-check URL for the rest of this task. If `18085` is also occupied, choose another free high port and record it.

### Step 2: Start Compose in fake mode

- [ ] If using the default env file, run:

```bash
docker compose --env-file deploy/lingneng/.env.example \
  -f deploy/lingneng/docker-compose.yml \
  -p lingneng-hermes-smoke up -d --build
```

- [ ] If using `/tmp/lingneng-hermes-smoke.env`, run:

```bash
docker compose --env-file /tmp/lingneng-hermes-smoke.env \
  -f deploy/lingneng/docker-compose.yml \
  -p lingneng-hermes-smoke up -d --build
```

Expected: service starts and remains running.

### Step 3: Inspect service status and logs

- [ ] Run:

```bash
docker compose --env-file deploy/lingneng/.env.example \
  -f deploy/lingneng/docker-compose.yml \
  -p lingneng-hermes-smoke ps
docker compose --env-file deploy/lingneng/.env.example \
  -f deploy/lingneng/docker-compose.yml \
  -p lingneng-hermes-smoke logs --tail=100 lingneng-hermes-api
```

If using `/tmp/lingneng-hermes-smoke.env`, substitute that env file in both commands.

Expected: `lingneng-hermes-api` is up; logs show Uvicorn started without tracebacks.

### Step 4: Run health and SSE smoke

- [ ] For default port, run:

```bash
scripts/lingneng-health-check.sh http://127.0.0.1:18083
```

- [ ] For alternate port `18085`, run:

```bash
scripts/lingneng-health-check.sh http://127.0.0.1:18085
```

Expected:

```text
checking health
checking ready
checking sse final
lingneng health check passed
```

The smoke script output should include an `event_order` containing `run_started`, `answer_delta`, and `final`.

### Step 5: Stop the smoke Compose project

- [ ] If using the default env file, run:

```bash
docker compose --env-file deploy/lingneng/.env.example \
  -f deploy/lingneng/docker-compose.yml \
  -p lingneng-hermes-smoke down
```

- [ ] If using `/tmp/lingneng-hermes-smoke.env`, run:

```bash
docker compose --env-file /tmp/lingneng-hermes-smoke.env \
  -f deploy/lingneng/docker-compose.yml \
  -p lingneng-hermes-smoke down
```

Expected: containers stop and are removed.

### Step 6: Fix smoke issues if needed

- [ ] If the container starts but health or SSE smoke fails because of a deployment asset bug, edit only the minimal affected files:

```text
deploy/lingneng/Dockerfile
deploy/lingneng/docker-compose.yml
deploy/lingneng/README.md
scripts/lingneng-health-check.sh
tests/lingneng/deploy
```

- [ ] Re-run:

```bash
uv run --extra dev python -m pytest tests/lingneng/deploy -q
docker compose --env-file deploy/lingneng/.env.example \
  -f deploy/lingneng/docker-compose.yml \
  config >/tmp/lingneng-compose-config.txt
docker build -f deploy/lingneng/Dockerfile \
  -t lingneng-hermes:local-smoke .
scripts/lingneng-health-check.sh http://127.0.0.1:18083
```

Expected: all commands pass, with the health-check URL adjusted if an alternate port is used.

### Step 7: Commit and push any smoke corrections

- [ ] If this task changed files, run:

```bash
git status --short
git add deploy/lingneng scripts/lingneng-health-check.sh tests/lingneng/deploy
git commit -m "fix: 修复灵能容器冒烟验证"
git push
```

Expected: commit and push succeed only after the corrected smoke run passes. If no files changed, do not create an empty commit.

---

## Task 4: Final Phase Verification

**Files:**
- Read-only unless final verification reveals a concrete bug.

### Step 1: Re-run static deployment tests

- [ ] Run:

```bash
uv run --extra dev python -m pytest tests/lingneng/deploy -q
```

Expected: all deployment tests pass.

### Step 2: Re-run focused LingNeng regression tests

- [ ] Run:

```bash
uv run --extra dev python -m pytest \
  tests/lingneng/api \
  tests/lingneng/runtime \
  tests/lingneng/contract/test_chat_smoke_script.py \
  -q
```

Expected: all selected tests pass.

### Step 3: Check no forbidden scope files were changed

- [ ] Run:

```bash
git diff --name-only HEAD
git status --short
```

Expected:

- no `.github/workflows/` changes.
- no `/Users/rotas/Documents/work/hailun/LingNengAI` changes.
- no root `Dockerfile`, `docker-compose.yml`, or `docker-compose.windows.yml` changes.
- no runtime API behavior files under `lingneng/` changed unless a real packaging bug was discovered and documented.

### Step 4: Record final Docker evidence

- [ ] Confirm the final response can report the exact verification evidence:

```text
uv run --extra dev python -m pytest tests/lingneng/deploy -q
docker compose --env-file deploy/lingneng/.env.example -f deploy/lingneng/docker-compose.yml config
docker build -f deploy/lingneng/Dockerfile -t lingneng-hermes:local-smoke .
scripts/lingneng-health-check.sh http://127.0.0.1:<port>
```

Expected: either all pass, or Docker-specific failures are reported with exact command and reason.

### Step 5: Commit and push any final corrections

- [ ] If this task changed files, run:

```bash
git status --short
git add deploy/lingneng scripts/lingneng-health-check.sh tests/lingneng/deploy docs/lingneng-migration
git commit -m "docs: 更新灵能 Docker 部署验证说明"
git push
```

Expected: commit and push succeed only after final verification passes. If no files changed, do not create an empty commit.

## Rollback Notes

- If Task 1 introduces bad deployment assets before commit, remove only the newly created files:

```bash
rm -rf deploy/lingneng
rm -f scripts/lingneng-health-check.sh
rm -rf tests/lingneng/deploy
```

- If a committed deployment change needs to be reverted, use a normal non-destructive revert commit:

```bash
git revert <commit-sha>
```

- Do not use `git reset --hard` or `git checkout --` unless the user explicitly requests it.

## Phase Completion Criteria

Phase 7 minimal Docker is complete when:

- `deploy/lingneng/Dockerfile` builds `lingneng-hermes:local-smoke`.
- `deploy/lingneng/docker-compose.yml` starts only `lingneng-hermes-api`.
- `deploy/lingneng/.env.example` has no real secrets and defaults to fake-mode smoke.
- `deploy/lingneng/README.md` documents manual deployment and Hermes-mode LLM config.
- `scripts/lingneng-health-check.sh` validates health, ready, and SSE final.
- `uv run --extra dev python -m pytest tests/lingneng/deploy -q` passes.
- `docker compose config` passes.
- local fake-mode Compose smoke passes, unless Docker is unavailable in the current environment and that is reported clearly.
- no CI/CD workflow files are created.
- no Java files are changed.
- upstream root Docker assets are unchanged.
