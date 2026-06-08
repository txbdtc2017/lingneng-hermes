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
