#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${DIR}/../.." && pwd)"
source "${ROOT}/verify/common.sh"

need_cmd curl
wait_health

log "NOTE: Run daily job first to generate track blobs for dt=${DT}."
log "curl -X POST ${API_BASE}/jobs/daily/run?dt=${DT}"

minio_ls_must_exist "track/dt=${DT}"

psql_exec "${DIR}/verify.sql"
log "Prompt05 verification finished."
