#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${DIR}/../.." && pwd)"
source "${ROOT}/verify/common.sh"

need_cmd curl
wait_health

log "Retention cleanup is typically run via Celery Beat scheduled task."
log "Template: verify that cleanup task runs and deletes dt < today-365/730 as configured."
log "If you add an admin trigger endpoint, call it here."

psql_exec "${DIR}/verify.sql"
log "Prompt07 verification finished (template)."
