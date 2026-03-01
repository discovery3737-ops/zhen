#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${DIR}/../.." && pwd)"
source "${ROOT}/verify/common.sh"

need_cmd curl
wait_health

log "This prompt requires WeCom delivery implementation."
log "Run daily job for dt=${DT} and verify send status in /runs/{run_id} or send_log."

psql_exec "${DIR}/verify.sql"
log "Prompt09 verification finished (template)."
