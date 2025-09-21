#!/bin/bash
set -euo pipefail
TS=$(date -u +%Y%m%dT%H%M%SZ)
ART="artifacts/e2e_run_${TS}"
mkdir -p "$ART"
log(){ echo ">>> $*" | tee -a "$ART/run.log"; }

BR="test/e2e-bot-admin-${TS}"
git checkout -b "$BR" || git switch -c "$BR"

log "1) Seed admin"
export SEED_ADMIN_USERNAME="${SEED_ADMIN_USERNAME:-admin}"
export SEED_ADMIN_PASSWORD="${SEED_ADMIN_PASSWORD:-admin123}"
export SEED_ADMIN_NO_2FA="${SEED_ADMIN_NO_2FA:-true}"
if [ -f app/scripts/seed_admin_static.py ]; then
  python app/scripts/seed_admin_static.py >> "$ART/seed_admin.log" 2>&1 || true
fi

log "2) Bring up services"
if [ -f docker-compose.staging.yml ]; then
  docker-compose -f docker-compose.staging.yml up -d --build >> "$ART/docker_up.log" 2>&1 || true
else
  docker-compose up -d --build >> "$ART/docker_up.log" 2>&1 || true
fi
sleep 6

log "3) Wait for app ready (health)"
HTTP="http://localhost:8000"
for i in $(seq 1 20); do
  if curl -sS "$HTTP/api/v1/health" >/dev/null 2>&1; then
    log "app healthy"
    break
  fi
  log "waiting for app... ($i/20)"
  sleep 3
done

log "4) Seed test match & contest via admin API"
TOKEN=$(curl -s -X POST "$HTTP/api/v1/admin/login" -H "Content-Type: application/json" -d "{\"username\":\"${SEED_ADMIN_USERNAME}\",\"password\":\"${SEED_ADMIN_PASSWORD}\"}" | jq -r .access_token 2>/dev/null || echo "")
if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  log "admin login failed; check $ART/seed_admin.log"
else
  # create match
  MATCH_RESP=$(curl -s -X POST "$HTTP/api/v1/admin/matches" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"title":"E2E Test Match","start_time":"2030-01-01T00:00:00Z"}')
  echo "$MATCH_RESP" > "$ART/match_create.json"
  MATCH_ID=$(echo "$MATCH_RESP" | jq -r .id)
  # create contest
  CONTEST_RESP=$(curl -s -X POST "$HTTP/api/v1/admin/contests" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"match_id\":\"$MATCH_ID\",\"title\":\"E2E Contest\",\"entry_fee\":5.0,\"max_players\":100,\"prize_structure\":{\"1\":4.5}}")
  echo "$CONTEST_RESP" > "$ART/contest_create.json"
  CONTEST_ID=$(echo "$CONTEST_RESP" | jq -r .id)
  log "created match $MATCH_ID contest $CONTEST_ID"
fi

log "5) Create test user via bot simulation (/start)"
# If real Telegram token set, instruct user to send /start. Otherwise create user in DB
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
  log "Real Telegram mode: you must send /start from your test Telegram account."
  log "Sleeping 10s to allow manual /start..."
  sleep 10
else
  log "Simulated user: inserting test user directly into DB"
  python - <<'PY' >> "$ART/create_user.log" 2>&1
import os, asyncio
from app.db.session import async_session
from app.models.user import User
import uuid
async def run():
    async with async_session() as db:
        u = User(telegram_id=693173957, username="e2e_test_user", status="ACTIVE")
        db.add(u)
        await db.commit()
        print("created user", u.id)
asyncio.run(run())
PY
fi

log "6) Ensure wallet credit for test user (simulate deposit)"
# Use app endpoint to create deposit txn and process it
curl -s -X POST "$HTTP/api/v1/admin/deposits" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"telegram_id\":693173957,\"amount\":20.0,\"tx_hash\":\"e2e-tx-$TS\"}" > "$ART/create_deposit.json" || true
# optionally call webhook endpoint to simulate confirmations
curl -s -X POST "$HTTP/api/v1/webhooks/bep20" -H "Content-Type: application/json" -d "{\"tx_hash\":\"e2e-tx-$TS\",\"telegram_id\":693173957,\"amount\":20.0,\"confirmations\":12}" > "$ART/webhook_resp.json" || true

log "7) Simulate bot join flow via server-side callback (no Telegram)"
# Call contest join API directly to simulate callback (this bypasses Telegram UI but validates DB logic)
curl -s -X POST "$HTTP/api/v1/contests/$CONTEST_ID/join" -H "Content-Type: application/json" -d "{\"telegram_id\":693173957}" > "$ART/join_resp.json" || true

log "8) Settle contest via admin API"
curl -s -X POST "$HTTP/api/v1/admin/contests/$CONTEST_ID/settle" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{}' > "$ART/settle_resp.json" || true

log "9) Create withdrawal request via API and approve"
WD_REQ=$(curl -s -X POST "$HTTP/api/v1/withdrawals" -H "Content-Type: application/json" -d "{\"telegram_id\":693173957,\"amount\":2.0,\"address\":\"0xdeadbeef\"}" )
echo "$WD_REQ" > "$ART/wd_request.json"
WD_ID=$(echo "$WD_REQ" | jq -r .id || echo "")
if [ -n "$WD_ID" ] && [ -n "$TOKEN" ]; then
  curl -s -X POST "$HTTP/api/v1/admin/withdrawals/$WD_ID/approve" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{}' > "$ART/wd_approve.json" || true
fi

log "10) Collect logs"
docker-compose -f docker-compose.staging.yml logs --no-color > "$ART/docker_logs.txt" 2>&1 || true
curl -s "$HTTP/api/v1/health" > "$ART/health.json" || true

log "E2E artifacts saved to $ART"
tar -czf "$ART.tar.gz" -C "$(dirname "$ART")" "$(basename "$ART")" || true
echo "$ART" > "$ART/ARTIFACT_DIR_PATH.txt"
log "Done. Artifacts: $ART"
