#!/usr/bin/env bash
set -euo pipefail

# ---------- Defaults ----------
API_BASE="${API_BASE:-http://localhost:8000}"
DT="${DT:-$(date -d 'yesterday' +%F 2>/dev/null || python - <<'PY'
import datetime
print((datetime.date.today()-datetime.timedelta(days=1)).isoformat())
PY
)}"

# docker compose service names (change if yours differs)
PG_SERVICE="${PG_SERVICE:-postgres}"
PG_DB="${PG_DB:-ucdb}"
PG_USER="${PG_USER:-uc}"

# MinIO (optional)
MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
MINIO_BUCKET="${MINIO_BUCKET:-uc-artifacts}"
MINIO_AK="${MINIO_AK:-minio}"
MINIO_SK="${MINIO_SK:-minio123456}"
MINIO_ALIAS="${MINIO_ALIAS:-ucminio}"

# ---------- Helpers ----------
log() { echo "[$(date '+%F %T')] $*"; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing command: $1" >&2
    return 1
  }
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

wait_health() {
  local retries="${1:-30}"
  local i=0
  log "Waiting for API health: ${API_BASE}/health"
  while (( i < retries )); do
    if curl -fsS "${API_BASE}/health" >/dev/null 2>&1; then
      log "API is healthy."
      return 0
    fi
    i=$((i+1))
    sleep 1
  done
  echo "API health check failed after ${retries}s" >&2
  exit 2
}

psql_exec() {
  # Usage: psql_exec <sqlfile>
  local sqlfile="$1"
  if has_cmd docker && (docker compose version >/dev/null 2>&1); then
    log "Running SQL via docker compose exec (${PG_SERVICE})"
    docker compose exec -T "${PG_SERVICE}" psql -U "${PG_USER}" -d "${PG_DB}" -v ON_ERROR_STOP=1 -f "${sqlfile}"
  elif has_cmd psql; then
    log "Running SQL via local psql"
    psql -U "${PG_USER}" -d "${PG_DB}" -v ON_ERROR_STOP=1 -f "${sqlfile}"
  else
    echo "No way to run psql (docker compose or local psql required)" >&2
    exit 3
  fi
}

minio_prepare() {
  if ! has_cmd mc; then
    log "mc not found, skipping MinIO checks."
    return 1
  fi
  mc alias set "${MINIO_ALIAS}" "${MINIO_ENDPOINT}" "${MINIO_AK}" "${MINIO_SK}" >/dev/null 2>&1 || true
  return 0
}

minio_ls_must_exist() {
  # Usage: minio_ls_must_exist <key_prefix_or_object>
  local key="$1"
  if ! minio_prepare; then
    return 0
  fi
  log "MinIO check: s3://${MINIO_BUCKET}/${key}"
  if ! mc ls "${MINIO_ALIAS}/${MINIO_BUCKET}/${key}" >/dev/null 2>&1; then
    echo "MinIO object/prefix not found: ${key}" >&2
    exit 4
  fi
  log "MinIO object/prefix exists."
}

curl_json_must() {
  # Usage: curl_json_must <url> [jq_filter]
  local url="$1"
  local filter="${2:-.}"
  log "curl: ${url}"
  if has_cmd jq; then
    curl -fsS "${url}" | jq -e "${filter}" >/dev/null
  else
    curl -fsS "${url}" >/dev/null
  fi
}

download_must() {
  # Usage: download_must <url> <outfile>
  local url="$1"
  local out="$2"
  log "Download: ${url} -> ${out}"
  curl -fSL "${url}" -o "${out}"
  test -s "${out}"
  log "Downloaded OK: $(ls -lh "${out}" | awk '{print $5}')"
}
