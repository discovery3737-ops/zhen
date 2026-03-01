#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${DIR}/../.." && pwd)"
source "${ROOT}/verify/common.sh"

need_cmd curl
wait_health

log "NOTE: This prompt assumes you've run daily job at least once for dt=${DT}."
log "If not, run: curl -X POST ${API_BASE}/jobs/daily/run?dt=${DT}"

TMP="${ROOT}/.tmp"
mkdir -p "${TMP}"
if curl -fsS "${API_BASE}/reports/daily/download?dt=${DT}" >/dev/null 2>&1; then
  download_must "${API_BASE}/reports/daily/download?dt=${DT}" "${TMP}/daily_${DT}.xlsx"
else
  log "Report not found yet (run daily job first)."
fi

minio_ls_must_exist "reports/${DT}"

psql_exec "${DIR}/verify.sql"
log "Prompt04 verification finished."
