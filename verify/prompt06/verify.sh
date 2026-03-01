#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${DIR}/../.." && pwd)"
source "${ROOT}/verify/common.sh"

need_cmd curl
wait_health

log "This prompt needs a vehicle_no that has track data for dt=${DT}."
log "Set VEHICLE_NO env var or the script will try to guess from DB."
VEHICLE_NO="${VEHICLE_NO:-}"

if [[ -z "${VEHICLE_NO}" ]]; then
  if command -v docker >/dev/null 2>&1 && (docker compose version >/dev/null 2>&1); then
    VEHICLE_NO="$(docker compose exec -T ${PG_SERVICE} psql -U ${PG_USER} -d ${PG_DB} -t -A -c "SELECT vehicle_no FROM fact_track_day_summary WHERE dt='${DT}' LIMIT 1;" | tr -d '[:space:]')"
  fi
fi

if [[ -z "${VEHICLE_NO}" ]]; then
  echo "VEHICLE_NO not found. Set it: export VEHICLE_NO='粤Bxxxx' after you have track data." >&2
  exit 6
fi

log "Using VEHICLE_NO=${VEHICLE_NO}"
curl_json_must "${API_BASE}/track/summary?dt=${DT}&vehicle_no=${VEHICLE_NO}" '.ok==true'
curl_json_must "${API_BASE}/track/points?dt=${DT}&vehicle_no=${VEHICLE_NO}&step_seconds=30" '.ok==true'

psql_exec "${DIR}/verify.sql"
log "Prompt06 verification finished."
