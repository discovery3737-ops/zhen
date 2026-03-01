#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${DIR}/../.." && pwd)"
source "${ROOT}/verify/common.sh"

need_cmd curl
wait_health

curl_json_must "${API_BASE}/config/global" '.ok==true'
curl_json_must "${API_BASE}/datasets/config" '.ok==true'
curl_json_must "${API_BASE}/schedule/daily" '.ok==true'
curl_json_must "${API_BASE}/delivery" '.ok==true'

psql_exec "${DIR}/verify.sql"
log "Prompt03 verification finished."
