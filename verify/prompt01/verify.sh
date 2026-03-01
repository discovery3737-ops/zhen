#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${DIR}/../.." && pwd)"
source "${ROOT}/verify/common.sh"

need_cmd curl
wait_health

curl_json_must "${API_BASE}/health" '.ok==true'
curl_json_must "${API_BASE}/runs?page=1&page_size=5" '.ok==true'

log "NOTE: Not auto-triggering /jobs/daily/run. If you want, run:"
log "curl -X POST ${API_BASE}/jobs/daily/run?dt=${DT}"

TMP="${ROOT}/.tmp"
mkdir -p "${TMP}"
if curl -fsS "${API_BASE}/reports/daily/download?dt=${DT}" >/dev/null 2>&1; then
  download_must "${API_BASE}/reports/daily/download?dt=${DT}" "${TMP}/daily_${DT}.xlsx"
else
  log "Report not found for dt=${DT} (OK if you haven't run daily job yet)."
fi

psql_exec "${DIR}/verify.sql"
log "Prompt01 verification finished."
