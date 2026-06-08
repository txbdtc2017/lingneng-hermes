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
