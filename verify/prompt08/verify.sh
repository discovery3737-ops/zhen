#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${DIR}/../.." && pwd)"
source "${ROOT}/verify/common.sh"

need_cmd curl
wait_health

log "This prompt assumes GeoService is implemented and amap_key configured."
log "Run a daily job for dt=${DT} then verify addresses/caches."

if curl -fsS "${API_BASE}/geo/cache/stats" >/dev/null 2>&1; then
  curl_json_must "${API_BASE}/geo/cache/stats" '.ok==true'
else
  log "No /geo/cache/stats endpoint (OK)."
fi

psql_exec "${DIR}/verify.sql"
log "Prompt08 verification finished."
