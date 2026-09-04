#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${PROJECT_ROOT}/server-local"
PHP_BIN="${PHP_BIN:-/opt/homebrew/bin/php}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"
HOST="127.0.0.1"
PORT="${PORT:-8000}"
BASE_URL="http://${HOST}:${PORT}"
API_KEY="${API_KEY:-local-test-key}"
UPLOAD_DIR="${UPLOAD_DIR:-csv}"
TEST_FILE="/tmp/test-sync.csv"

json_field() {
  local payload="$1"
  local field="$2"

  printf '%s' "$payload" | "$PYTHON_BIN" -c '
import json
import re
import sys

text = sys.stdin.read()
field = sys.argv[1]

match = re.search(r"\{.*\}", text, re.DOTALL)
if not match:
  print("")
  raise SystemExit(0)

try:
  data = json.loads(match.group(0))
except json.JSONDecodeError:
  print("")
  raise SystemExit(0)

value = data.get(field, "")
if value is None:
  value = ""
print(value)
' "$field"
}

if [[ ! -x "$PHP_BIN" ]]; then
  echo "ERROR: PHP binary not found at $PHP_BIN"
  exit 1
fi

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: python3 is required for JSON parsing."
  exit 1
fi

if [[ ! -f "${APP_DIR}/artisan" ]]; then
  echo "ERROR: Laravel app not found at ${APP_DIR}."
  echo "Create it first with Composer, then re-run this script."
  exit 1
fi

SERVER_PID=""
STARTED_SERVER="0"
cleanup() {
  if [[ "$STARTED_SERVER" == "1" && -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

cd "$APP_DIR"

# Ensure local upload root exists (matches local .env setup).
mkdir -p /tmp/csv-sync-upload
mkdir -p "/tmp/csv-sync-upload/${UPLOAD_DIR}"
rm -f "/tmp/csv-sync-upload/${UPLOAD_DIR}/test-sync.csv"

if curl -fsS "${BASE_URL}/up" >/dev/null 2>&1; then
  echo "Using existing Laravel server on ${BASE_URL}"
else
  # Start Laravel dev server in background for smoke test.
  "$PHP_BIN" artisan serve --host="$HOST" --port="$PORT" >/tmp/laravel-smoke.log 2>&1 &
  SERVER_PID=$!
  STARTED_SERVER="1"

  for _ in {1..60}; do
    if curl -fsS "${BASE_URL}/up" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  if ! curl -fsS "${BASE_URL}/up" >/dev/null 2>&1; then
    echo "ERROR: Laravel server did not become ready on ${BASE_URL}."
    echo "See log: /tmp/laravel-smoke.log"
    exit 1
  fi
fi

echo "[1/4] Upload new CSV and validate checksum"
printf "id,name\n1,alice\n" > "$TEST_FILE"
LOCAL_SHA_1="$(shasum -a 256 "$TEST_FILE" | awk '{print $1}')"
RESP_1="$(curl -sS -X POST "${BASE_URL}/api/v1/upload-csv" -H "X-API-Key: ${API_KEY}" -F "directory=${UPLOAD_DIR}" -F "file=@${TEST_FILE};type=text/csv")"
SERVER_SHA_1="$(json_field "$RESP_1" sha256)"
STATUS_1="$(json_field "$RESP_1" status)"

if [[ "$STATUS_1" != "success" || "$SERVER_SHA_1" != "$LOCAL_SHA_1" ]]; then
  echo "FAIL: first upload mismatch"
  echo "Local:  $LOCAL_SHA_1"
  echo "Server: $SERVER_SHA_1"
  echo "Resp:   $RESP_1"
  exit 1
fi

echo "PASS: success + checksum match"

echo "[2/4] Upload same file again and expect already_exists"
RESP_2="$(curl -sS -X POST "${BASE_URL}/api/v1/upload-csv" -H "X-API-Key: ${API_KEY}" -F "directory=${UPLOAD_DIR}" -F "file=@${TEST_FILE};type=text/csv")"
STATUS_2="$(json_field "$RESP_2" status)"

if [[ "$STATUS_2" != "already_exists" ]]; then
  echo "FAIL: expected already_exists"
  echo "Resp: $RESP_2"
  exit 1
fi

echo "PASS: idempotency works"

echo "[3/4] Upload same filename with different content and expect conflict"
printf "id,name\n1,bob\n" > "$TEST_FILE"
HTTP_3="$(curl -sS -o /tmp/smoke-conflict.json -w '%{http_code}' -X POST "${BASE_URL}/api/v1/upload-csv" -H "X-API-Key: ${API_KEY}" -F "directory=${UPLOAD_DIR}" -F "file=@${TEST_FILE};type=text/csv")"
STATUS_3="$(json_field "$(cat /tmp/smoke-conflict.json)" status)"

if [[ "$HTTP_3" != "409" || "$STATUS_3" != "conflict" ]]; then
  echo "FAIL: expected HTTP 409 conflict"
  echo "HTTP: $HTTP_3"
  echo "Resp: $(cat /tmp/smoke-conflict.json)"
  exit 1
fi

echo "PASS: conflict handling works"

echo "[4/4] Smoke test complete"
echo "All checks passed."
