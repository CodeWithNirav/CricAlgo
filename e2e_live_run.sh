#!/bin/bash
set -euo pipefail
TS=$(date -u +%Y%m%dT%H%M%SZ)
ART="artifacts/e2e_live_${TS}"
mkdir -p "$ART"
log(){ echo ">>> $*" | tee -a "$ART/run.log"; }

BR="test/e2e-live-${TS}"
git checkout -b "$BR" || git switch -c "$BR"

HTTP="http://localhost:8000"

log "1) Check health"
for i in $(seq 1 20); do
  if curl -s "$HTTP/api/v1/health" >/dev/null 2>&1; then
    log "app healthy"
    break
  fi
  log "waiting... ($i/20)"
  sleep 3
done

log "2) Admin login"
TOKEN=$(curl -s -X POST "$HTTP/api/v1/admin/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${SEED_ADMIN_USERNAME}\",\"password\":\"${SEED_ADMIN_PASSWORD}\"}" \
  | jq -r .access_token)
echo "$TOKEN" > "$ART/admin_token.txt"

log "3) Create match & contest"
MRESP=$(curl -s -X POST "$HTTP/api/v1/admin/matches" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"E2E Live Match","start_time":"2030-01-01T00:00:00Z"}')
echo "$MRESP" > "$ART/match.json"
MID=$(echo "$MRESP" | jq -r .id)

CRESP=$(curl -s -X POST "$HTTP/api/v1/admin/contests" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"match_id\":\"$MID\",\"title\":\"E2E Live Contest\",\"entry_fee\":5.0,\"max_players\":100,\"prize_structure\":{\"1\":4.5}}")
echo "$CRESP" > "$ART/contest.json"
CID=$(echo "$CRESP" | jq -r .id)

log "4) Prompt user: please open Telegram and send /start to bot now"
echo ">>> Open your Telegram client, send /start to the bot. Waiting 20s..." | tee -a "$ART/run.log"
sleep 20

log "5) Create deposit via webhook"
TX="e2e-live-${TS}"
curl -s -X POST "$HTTP/api/v1/webhooks/bep20" \
  -H "Content-Type: application/json" \
  -d "{\"tx_hash\":\"$TX\",\"telegram_id\":693173957,\"amount\":20.0,\"confirmations\":12}" \
  > "$ART/webhook.json"

sleep 10  # allow Celery worker to process

log "6) Join contest (simulate bot callback via API)"
JOIN=$(curl -s -X POST "$HTTP/api/v1/contests/$CID/join" \
  -H "Content-Type: application/json" \
  -d "{\"telegram_id\":693173957}")
echo "$JOIN" > "$ART/join.json"

log "7) Settle contest"
SETTLE=$(curl -s -X POST "$HTTP/api/v1/admin/contests/$CID/settle" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{}')
echo "$SETTLE" > "$ART/settle.json"

log "8) Create withdrawal & approve"
WDR=$(curl -s -X POST "$HTTP/api/v1/withdrawals" \
  -H "Content-Type: application/json" \
  -d '{"telegram_id":693173957,"amount":2.0,"address":"0xdeadbeef"}')
echo "$WDR" > "$ART/withdrawal_req.json"
WID=$(echo "$WDR" | jq -r .id)
curl -s -X POST "$HTTP/api/v1/admin/withdrawals/$WID/approve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{}' \
  > "$ART/withdrawal_approve.json"

log "9) Collect logs"
curl -s "$HTTP/api/v1/health" > "$ART/health.json"
docker-compose -f docker-compose.staging.yml logs --no-color > "$ART/docker_logs.txt" || true

tar -czf "$ART.tar.gz" -C "$(dirname "$ART")" "$(basename "$ART")"
echo "$ART" > "$ART/ARTIFACT_DIR_PATH.txt"
log "Done. Artifacts saved in $ART"
