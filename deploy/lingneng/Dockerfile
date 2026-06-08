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
