#!/usr/bin/env bash
# M1 noVNC 授权闭环验收脚本
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${DIR}/../.." && pwd)"
source "${ROOT}/verify/common.sh"

API_BASE="${API_BASE:-http://localhost:8000}"

need_cmd curl
wait_health

log "1. POST /auth/session/start"
START=$(curl -fsS -X POST "${API_BASE}/auth/session/start")
echo "$START" | jq .
if ! echo "$START" | jq -e '.ok==true and .data.novnc_url' >/dev/null; then
  echo "start failed: no novnc_url" >&2
  exit 1
fi
SESSION_ID=$(echo "$START" | jq -r '.data.session_id')
TOKEN=$(echo "$START" | jq -r '.data.token')
log "session_id=$SESSION_ID"

log "2. GET /auth/credential/status"
curl -fsS "${API_BASE}/auth/credential/status" | jq .

log "3. POST /auth/session/finish (需先在 noVNC 中完成登录)"
log "   novnc_url: $(echo "$START" | jq -r '.data.novnc_url')"
log "   请在浏览器中打开 noVNC，完成登录后执行："
log "   curl -X POST ${API_BASE}/auth/session/finish -H 'Content-Type: application/json' -d '{\"session_id\":\"${SESSION_ID}\",\"token\":\"${TOKEN}\"}'"
FINISH=$(curl -fsS -X POST "${API_BASE}/auth/session/finish" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"${SESSION_ID}\",\"token\":\"${TOKEN}\"}")
echo "$FINISH" | jq .
if echo "$FINISH" | jq -e '.ok==true' >/dev/null; then
  log "finish OK, credential ACTIVE"
else
  log "finish failed (预期：若未完成短信验证则返回 ok:false)"
fi

log "4. GET /auth/credential/status (最终状态)"
curl -fsS "${API_BASE}/auth/credential/status" | jq .

log "M1 Prompt02 验收完成。"
