#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   scripts/upload_real_file_test.sh /absolute/path/to/file.csv [dummy_directory]

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${PROJECT_ROOT}/server-local"
PHP_BIN="${PHP_BIN:-/opt/homebrew/bin/php}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"
HOST="127.0.0.1"
PORT="${PORT:-8000}"
BASE_URL="http://${HOST}:${PORT}"
API_KEY="${API_KEY:-local-test-key}"
UPLOAD_ROOT="${UPLOAD_ROOT:-/tmp/csv-sync-upload}"
REAL_FILE_PATH="${1:-}"
DUMMY_DIRECTORY="${2:-dummy-server-inbox}"

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

if [[ -z "$REAL_FILE_PATH" ]]; then
  echo "Usage: scripts/upload_real_file_test.sh /absolute/path/to/file.csv [dummy_directory]"
  exit 1
fi

if [[ ! -f "$REAL_FILE_PATH" ]]; then
  echo "ERROR: file not found: $REAL_FILE_PATH"
  exit 1
fi

if [[ "${REAL_FILE_PATH##*.}" != "csv" && "${REAL_FILE_PATH##*.}" != "CSV" ]]; then
  echo "ERROR: file must be .csv"
  exit 1
fi

if [[ ! -x "$PHP_BIN" ]]; then
  echo "ERROR: PHP binary not found at $PHP_BIN"
  exit 1
fi

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: python3 is required for JSON parsing"
  exit 1
fi

if [[ ! -f "${APP_DIR}/artisan" ]]; then
  echo "ERROR: Laravel app not found at ${APP_DIR}"
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

mkdir -p "$UPLOAD_ROOT/$DUMMY_DIRECTORY"
TARGET_PATH="$UPLOAD_ROOT/$DUMMY_DIRECTORY/$(basename "$REAL_FILE_PATH")"
rm -f "$TARGET_PATH"

cd "$APP_DIR"

if curl -fsS "${BASE_URL}/up" >/dev/null 2>&1; then
  echo "Using existing Laravel server on ${BASE_URL}"
else
  "$PHP_BIN" artisan serve --host="$HOST" --port="$PORT" >/tmp/laravel-real-upload.log 2>&1 &
  SERVER_PID=$!
  STARTED_SERVER="1"

  for _ in {1..60}; do
    if curl -fsS "${BASE_URL}/up" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  if ! curl -fsS "${BASE_URL}/up" >/dev/null 2>&1; then
    echo "ERROR: Laravel server did not become ready on ${BASE_URL}"
    echo "See log: /tmp/laravel-real-upload.log"
    exit 1
  fi
fi

LOCAL_SHA="$(shasum -a 256 "$REAL_FILE_PATH" | awk '{print $1}')"

echo "Uploading file: $REAL_FILE_PATH"
echo "Dummy destination: $UPLOAD_ROOT/$DUMMY_DIRECTORY"

RESPONSE="$(curl -sS -X POST "${BASE_URL}/api/v1/upload-csv" -H "X-API-Key: ${API_KEY}" -F "directory=${DUMMY_DIRECTORY}" -F "file=@${REAL_FILE_PATH};type=text/csv")"
STATUS="$(json_field "$RESPONSE" status)"
SERVER_SHA="$(json_field "$RESPONSE" sha256)"

if [[ "$STATUS" != "success" && "$STATUS" != "already_exists" ]]; then
  echo "FAIL: upload status is not success/already_exists"
  echo "Response: $RESPONSE"
  exit 1
fi

if [[ "$SERVER_SHA" != "$LOCAL_SHA" ]]; then
  echo "FAIL: checksum mismatch"
  echo "Local SHA256:  $LOCAL_SHA"
  echo "Server SHA256: $SERVER_SHA"
  echo "Response: $RESPONSE"
  exit 1
fi

if [[ ! -f "$TARGET_PATH" ]]; then
  echo "FAIL: file was not stored in dummy directory"
  echo "Expected: $TARGET_PATH"
  exit 1
fi

STORED_SHA="$(shasum -a 256 "$TARGET_PATH" | awk '{print $1}')"
if [[ "$STORED_SHA" != "$LOCAL_SHA" ]]; then
  echo "FAIL: stored file checksum mismatch"
  echo "Stored SHA256: $STORED_SHA"
  echo "Local SHA256:  $LOCAL_SHA"
  exit 1
fi

echo "PASS: file uploaded and stored in dummy directory"
echo "Status: $STATUS"
echo "SHA256: $LOCAL_SHA"
echo "Stored path: $TARGET_PATH"
