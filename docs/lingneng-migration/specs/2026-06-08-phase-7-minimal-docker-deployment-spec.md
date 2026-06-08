# Phase 7 Minimal Docker Deployment Spec

## Status

Drafted after the user narrowed Phase 7 from full deployment/CI/CD to the
smallest Docker path that can run the LingNeng Java-compatible API.

Required durable context reloaded before writing this spec:

- `LINGNENG_MIGRATION_CONTEXT.md`
- `docs/lingneng-migration/specs/2026-06-06-lingneng-hermes-runtime-design.md`
- `docs/lingneng-migration/plans/2026-06-06-lingneng-hermes-runtime-implementation-plan.md`

Repository state before drafting:

- Branch: `dev`
- HEAD: `ecfd2eea80181f1e98bfb410d817f16c1c80e8a2`
- Working tree before drafting: clean
- Existing root Docker assets:
  - `Dockerfile`
  - `docker-compose.yml`
  - `docker-compose.windows.yml`

The root Docker assets are upstream Hermes assets. They build and run Hermes
gateway/dashboard services and are not the LingNeng Java API deployment target.
This spec defines the dedicated LingNeng Docker deployment surface under
`deploy/lingneng/`.

## Goal

Provide the smallest Docker deployment path that can run the
LingNeng-Hermes Java-compatible API:

```text
POST /internal/agent/chat/stream
GET  /internal/agent/health
GET  /internal/agent/ready
```

The result should let an operator build the image, configure environment
values, start the API with Docker Compose, check health/ready, run a minimal
SSE smoke test, inspect logs, and stop the service.

## Scope

### Dedicated LingNeng Image

Add a dedicated Dockerfile for LingNeng API runtime:

```text
deploy/lingneng/Dockerfile
```

The image must:

- Build from the repository source.
- Install Python dependencies from `pyproject.toml` and `uv.lock` with frozen
  resolution.
- Install only what is needed for the LingNeng API and Hermes agent runtime.
- Not build or start Hermes dashboard, desktop, TUI, gateway, browser UI, or
  messaging channels.
- Start with:

```text
python -m lingneng.api.server
```

The image should default to Python 3.13 because the project supports
`>=3.11,<3.14` and the existing upstream image already uses Python 3.13. The
plan may choose a pinned `uv` Python base image consistent with the repository's
dependency pinning policy.

### Dedicated Compose Service

Add a dedicated Compose template:

```text
deploy/lingneng/docker-compose.yml
```

The default service model contains one service only:

```text
lingneng-hermes-api
```

The service must:

- Build from the repository root with `deploy/lingneng/Dockerfile`.
- Avoid a fixed `container_name`, so multiple environments can run with
  different Compose project names.
- Run only the LingNeng API server.
- Use bridge networking by default, not `network_mode: host`.
- Bind the host port through explicit env values.
- Mount persistent runtime data and Hermes configuration.
- Avoid exposing Hermes dashboard/gateway ports.

Default port behavior:

```text
container listen host: 0.0.0.0
container listen port: 18083
host bind address: 127.0.0.1
host bind port: 18083
```

The container must listen on `0.0.0.0` internally so Docker port publishing
works. The host binding must default to `127.0.0.1` so the API is not opened to
the LAN or public network by accident.

Expected port mapping shape:

```yaml
ports:
  - "${LINGNENG_API_BIND_HOST:-127.0.0.1}:${LINGNENG_API_HOST_PORT:-18083}:${LINGNENG_API_PORT:-18083}"
```

### Environment Template

Add a safe example env file:

```text
deploy/lingneng/.env.example
```

The example env must support a no-secret local smoke run by default:

```text
LINGNENG_APP_ENV=dev
LINGNENG_AGENT_MODE=fake
LINGNENG_API_HOST=0.0.0.0
LINGNENG_API_PORT=18083
LINGNENG_API_BIND_HOST=127.0.0.1
LINGNENG_API_HOST_PORT=18083
LINGNENG_RUNTIME_DIR=/data/runtime
HERMES_HOME=/data/hermes
LINGNENG_ALLOW_INSECURE_LOCAL=1
```

Secret values in `.env.example` must be empty. This includes:

- `LINGNENG_INTERNAL_API_KEY`
- `OPENAI_API_KEY`
- provider-specific API keys
- search keys
- RAG keys
- artifact or storage credentials

For real Hermes-mode LLM chat, the operator will change:

```text
LINGNENG_AGENT_MODE=hermes
LINGNENG_ALLOW_INSECURE_LOCAL=0
LINGNENG_INTERNAL_API_KEY=<server-local secret>
OPENAI_API_KEY=<llm secret, or provider-specific secret>
```

The LLM base URL, model, and `api_mode` should be configured through the
mounted Hermes config at:

```text
deploy/lingneng/data/hermes/config.yaml
```

The README must include a minimal example:

```yaml
model:
  provider: custom
  default: your-model-name
  base_url: https://your-llm-endpoint.example/v1
  api_key: ""
  api_mode: chat_completions
```

`api_key` stays empty in `config.yaml`; the runtime uses the injected
`OPENAI_API_KEY` or provider-specific key from the server env.

### Persistent Data

The Compose template must keep runtime state outside the container image.

Required mounts:

```text
deploy/lingneng/data/runtime -> /data/runtime
deploy/lingneng/data/hermes  -> /data/hermes
deploy/lingneng/logs         -> /data/hermes/logs
```

`/data/runtime` stores LingNeng runtime state such as run-store SQLite files and
session database files configured through `LingNengSettings`.

`/data/hermes` stores Hermes config, `.env`, profile files, model settings, and
Hermes SessionDB/log state when Hermes mode is used.

`/data/hermes/logs` should be mounted separately as `deploy/lingneng/logs` for
easy operator access.

### Manual Runbook

Add a runbook:

```text
deploy/lingneng/README.md
```

The runbook must include:

- How to copy `.env.example` to `.env`.
- How to create required data/log directories.
- How to configure fake mode for smoke tests.
- How to configure Hermes mode with LLM base URL, model, `api_mode`, and API
  key.
- How to preflight the intended host port before starting.
- How to build and start:

```bash
docker compose --env-file deploy/lingneng/.env \
  -f deploy/lingneng/docker-compose.yml \
  -p lingneng-hermes up -d --build
```

- How to check logs:

```bash
docker compose --env-file deploy/lingneng/.env \
  -f deploy/lingneng/docker-compose.yml \
  -p lingneng-hermes logs -f lingneng-hermes-api
```

- How to stop:

```bash
docker compose --env-file deploy/lingneng/.env \
  -f deploy/lingneng/docker-compose.yml \
  -p lingneng-hermes down
```

- How to expose to Java safely:
  - keep host binding on `127.0.0.1` when Java is on the same host or behind a
    local reverse proxy.
  - use a private LAN bind address only when needed.
  - never bind `0.0.0.0` without setting `LINGNENG_INTERNAL_API_KEY`.

### Health Check Script

Add a small script:

```text
scripts/lingneng-health-check.sh
```

The script should:

- Accept a base URL, defaulting to `http://127.0.0.1:18083`.
- Accept an optional internal key through `LINGNENG_INTERNAL_API_KEY`.
- Check `/internal/agent/health`.
- Check `/internal/agent/ready`.
- Run a minimal fake-mode SSE smoke request against
  `/internal/agent/chat/stream`.
- Exit non-zero on HTTP errors, not-ready status, malformed SSE, SSE `error`,
  timeout, or missing `final`.
- Avoid printing secrets or the full request body.

The script is for local/manual verification. It is not a deployment automation
framework.

## Non-Goals

This phase does not:

- Add GitHub Actions.
- Add Jenkins, Gitea, or any other CI/CD integration.
- Push images to a registry.
- Deploy to a remote server automatically.
- Add SSH deploy jobs or protected environments.
- Add a full deployment script with rollback.
- Add Kubernetes, Helm, Swarm, Nomad, or systemd units.
- Start Redis, Milvus, MinIO, RocketMQ, Nacos, or RAG services in Compose.
- Migrate LingNengAI training ingestion.
- Implement RAG storage or vector database deployment.
- Modify Java code.
- Change the Java request schema or SSE event names.
- Change LingNeng runtime behavior beyond deployment packaging.
- Replace or delete the upstream Hermes root Dockerfile/compose files.
- Expose Hermes dashboard/gateway through this Compose template.

Manual rollback is limited to normal Docker operator actions: stop the current
Compose project and start a previously built image tag or previous checkout.
Automated rollback scripts are out of scope for this minimal phase.

## Accepted Decisions

1. The current Phase 7 execution scope is minimal Docker deployment only.
2. CI/CD is explicitly excluded from this phase by user request.
3. The deployment target is the LingNeng Java-compatible API facade, not the
   upstream Hermes gateway/dashboard.
4. The dedicated deployment files live under `deploy/lingneng/`.
5. The default compose service is a single API service named
   `lingneng-hermes-api`.
6. Default smoke mode uses `LINGNENG_AGENT_MODE=fake` and
   `LINGNENG_ALLOW_INSECURE_LOCAL=1` with host binding on `127.0.0.1`.
7. Real model mode uses `LINGNENG_AGENT_MODE=hermes`, a non-empty
   `LINGNENG_INTERNAL_API_KEY`, and mounted Hermes model config/secrets.
8. Container API host is `0.0.0.0`; host publish bind defaults to
   `127.0.0.1`.
9. No secrets are committed in Dockerfile, Compose, env examples, README, tests,
   or health-check script.
10. Existing root Docker assets remain untouched unless a later bug requires a
    separate change.

## Open Decisions

No user confirmation is required before writing the implementation plan if the
defaults in this spec are acceptable.

Implementation-plan decisions that can be made by the agent:

- Exact pinned base image and runtime user details.
- Exact pytest file names under `tests/lingneng/deploy/`.
- Whether the health-check script uses `curl` plus shell parsing or invokes the
  existing Python smoke script when available.
- Whether the Dockerfile uses a single-stage or multi-stage build, provided the
  result builds reliably and does not include unnecessary UI build steps.

## Contracts

### Java-Facing API Contract

Docker deployment must not change the Java-facing API:

```text
POST /internal/agent/chat/stream
Content-Type: application/json
Accept: text/event-stream
Response: text/event-stream
```

The minimum successful smoke event order remains:

```text
run_started -> answer_delta... -> final
```

SSE error behavior remains:

```text
error
```

Heartbeats remain SSE comment frames:

```text
: ping
```

### Runtime Mode Contract

`LINGNENG_AGENT_MODE=fake`:

- Used for no-secret Docker smoke tests.
- Does not require a real LLM provider.
- Must be enough for health, ready, and minimal SSE verification.

`LINGNENG_AGENT_MODE=hermes`:

- Uses `HermesAgentRunAdapter`.
- Requires valid Hermes model configuration and provider credentials.
- Does not require RAG configuration for basic chat.
- May return `retrieve_rag` not configured if the model calls RAG without
  `LINGNENG_RAG_ENDPOINT`.

### Auth Contract

When `LINGNENG_INTERNAL_API_KEY` is set:

- Java or smoke clients must send `X-Internal-Key`.
- Invalid or missing keys return non-SSE HTTP `401`.

When `LINGNENG_INTERNAL_API_KEY` is empty:

- The service is ready only when `LINGNENG_APP_ENV` is local-like and
  `LINGNENG_ALLOW_INSECURE_LOCAL=1`.
- This mode is for local/fake smoke only.

### Port Contract

Before starting a local service, the implementation or runbook must require a
port preflight:

```bash
lsof -nP -iTCP:18083 -sTCP:LISTEN
```

If `18083` is occupied by an unrelated process, the operator should set:

```text
LINGNENG_API_HOST_PORT=<free high port>
```

The Compose service should still pass `LINGNENG_API_PORT=18083` into the
container unless there is a specific reason to change the container port too.

## Module Boundaries

Expected new files:

```text
deploy/lingneng/Dockerfile
deploy/lingneng/docker-compose.yml
deploy/lingneng/.env.example
deploy/lingneng/README.md
scripts/lingneng-health-check.sh
tests/lingneng/deploy/test_dockerfile.py
tests/lingneng/deploy/test_lingneng_compose.py
tests/lingneng/deploy/test_health_check_script.py
```

Allowed modifications:

- Documentation or tests directly related to minimal Docker deployment.
- `.dockerignore` only if the dedicated build context needs a narrowly scoped
  correction and the change does not break the upstream Hermes Docker build.

Disallowed modifications:

- Java project files under `/Users/rotas/Documents/work/hailun/LingNengAI`.
- Hermes root `Dockerfile` and root `docker-compose.yml`, unless a later
  explicit decision says to align them.
- `.github/workflows/`.
- Runtime API behavior files under `lingneng/`, unless Docker execution exposes
  a packaging bug that cannot be fixed in deployment assets.

## Test Strategy

### Static Deployment Tests

Add tests that inspect `deploy/lingneng/docker-compose.yml` and assert:

- Service `lingneng-hermes-api` exists.
- No fixed `container_name` is configured.
- The service does not use `network_mode: host`.
- The service publishes
  `${LINGNENG_API_BIND_HOST:-127.0.0.1}:${LINGNENG_API_HOST_PORT:-18083}:${LINGNENG_API_PORT:-18083}`.
- The service sets `LINGNENG_API_HOST=0.0.0.0` inside the container.
- The service mounts runtime data, Hermes config, and logs.
- The service does not start dashboard, gateway, Redis, Milvus, MinIO, MQ, or
  Nacos services.

Add tests that inspect `.env.example` and assert:

- `LINGNENG_AGENT_MODE=fake`.
- `LINGNENG_ALLOW_INSECURE_LOCAL=1`.
- `LINGNENG_API_BIND_HOST=127.0.0.1`.
- Secret-like keys exist only with empty values.

Add tests that inspect `deploy/lingneng/Dockerfile` and assert:

- It uses a pinned or otherwise policy-compatible base image.
- It copies `pyproject.toml` and `uv.lock` before source code for layer caching.
- It runs `uv sync --frozen`.
- It starts `python -m lingneng.api.server`.
- It does not run `npm install`, build `web`, build `ui-tui`, or start Hermes
  dashboard/gateway.
- It does not bake secret values.

Add tests that inspect `scripts/lingneng-health-check.sh` and assert:

- It checks health.
- It checks ready.
- It posts to `/internal/agent/chat/stream`.
- It looks for a terminal `final` event.
- It does not echo `LINGNENG_INTERNAL_API_KEY`.

### Compose Validation

The plan must include:

```bash
docker compose --env-file deploy/lingneng/.env.example \
  -f deploy/lingneng/docker-compose.yml \
  config
```

Expected: command exits 0.

### Image Build Smoke

The plan must include:

```bash
docker build -f deploy/lingneng/Dockerfile \
  -t lingneng-hermes:local-smoke .
```

Expected: image builds successfully.

### Container Smoke

The plan must include a local fake-mode container smoke run:

```bash
docker compose --env-file deploy/lingneng/.env.example \
  -f deploy/lingneng/docker-compose.yml \
  -p lingneng-hermes-smoke up -d --build
```

Then:

```bash
scripts/lingneng-health-check.sh http://127.0.0.1:18083
```

Expected:

- `/internal/agent/health` returns `{"status":"ok"}`.
- `/internal/agent/ready` reports `status: ready`.
- SSE smoke receives `run_started`, at least one `answer_delta`, and `final`.

Cleanup:

```bash
docker compose --env-file deploy/lingneng/.env.example \
  -f deploy/lingneng/docker-compose.yml \
  -p lingneng-hermes-smoke down
```

## Acceptance Criteria

This phase is complete when:

1. `deploy/lingneng/Dockerfile` exists and builds a LingNeng API image.
2. `deploy/lingneng/docker-compose.yml` starts only `lingneng-hermes-api`.
3. `deploy/lingneng/.env.example` supports no-secret fake-mode smoke and does
   not contain real secret values.
4. `deploy/lingneng/README.md` documents manual build/start/health/log/stop
   operations and real Hermes-mode LLM configuration.
5. `scripts/lingneng-health-check.sh` verifies health, ready, and minimal SSE.
6. Static deployment tests pass.
7. `docker compose config` passes with `.env.example`.
8. `docker build` passes for the dedicated Dockerfile.
9. A fake-mode Compose smoke run passes locally, or any inability to run Docker
   in the current environment is explicitly reported with the exact failed
   command and reason.
10. No CI/CD workflow files are created.
11. No Java code is modified.
12. The upstream Hermes root Docker assets remain unchanged.

## User Confirmations Before Plan

No additional confirmation is required before writing the Phase 7 minimal Docker
implementation plan. The user has already confirmed:

- CI/CD is not needed.
- The requirement is the simplest Docker deployment that can run the project.

If the user wants a different default host bind, port, runtime directory, or
auth behavior, those changes should be requested during review of this spec
before plan execution begins.
