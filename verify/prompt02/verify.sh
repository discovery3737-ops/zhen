#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${DIR}/../.." && pwd)"
source "${ROOT}/verify/common.sh"

need_cmd curl
wait_health

log "MANUAL STEP REQUIRED:"
log "1) Open front-end AuthCenter and click '创建授权会话' (noVNC iframe should open)."
log "2) Complete login: password -> puzzle -> SMS OTP."
log "3) Click '完成授权' in UI (calls /auth/session/finish)."
log "Then re-run this script to verify credential status."

curl_json_must "${API_BASE}/auth/credential/status" '.ok==true'

if has_cmd jq; then
  status="$(curl -fsS "${API_BASE}/auth/credential/status" | jq -r '.data.status // .status // empty')"
  log "Credential status: ${status}"
  if [[ "${status}" != "ACTIVE" ]]; then
    echo "Credential status is not ACTIVE (got: ${status}). Complete authorization first." >&2
    exit 5
  fi
else
  log "jq not installed; cannot assert ACTIVE. Install jq for stronger checks."
fi

psql_exec "${DIR}/verify.sql"
log "Prompt02 verification finished."
