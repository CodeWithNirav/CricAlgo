#!/usr/bin/env bash
set -euo pipefail
# IMPROVED BOT TEST PREP SCRIPT
# Enhanced version with better error handling, schema validation, and service checks

TS=$(date -u +%Y%m%dT%H%M%SZ)
ART="artifacts/bot_test_prep_${TS}"
mkdir -p "$ART"

# ====== CONFIG - edit if your setup differs ======
# Provide values by exporting them first or editing here:
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"    # e.g. 8257... (or export beforehand)
TELEGRAM_TEST_ID1="${TELEGRAM_TEST_ID1:-693173957}"  # default from your message
TELEGRAM_TEST_ID2="${TELEGRAM_TEST_ID2:-815804123}"     # leave blank to be prompted
DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/cricalgo}"
RUN_BOT_SCRIPT="./app/bot/run_polling.py"       # path to bot runner Python script
VENV="${VENV:-.venv}"                          # venv path if you use it
USE_SYSTEMD="${USE_SYSTEMD:-false}"            # set true if you prefer systemd service instead of nohup
BOT_LOG="$ART/bot_polling.log"
HTTP_BASE_URL="${HTTP_BASE_URL:-http://localhost:8000}"  # Fixed: Added missing HTTP variable
REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
# =================================================

log(){ echo ">>> $*" | tee -a "$ART/run.log"; }
error(){ echo "ERROR: $*" | tee -a "$ART/run.log"; exit 1; }

log "Starting improved bot test prep at $TS"

# Validate minimal config — get second ID if missing
if [ -z "$TELEGRAM_TEST_ID2" ]; then
  read -p "Enter second Telegram numeric ID (TEST_USER_ID2) and press enter: " TELEGRAM_TEST_ID2
fi
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
  error "TELEGRAM_BOT_TOKEN not set. Export TELEGRAM_BOT_TOKEN or edit the script."
fi

log "Config summary: TEST_ID1=$TELEGRAM_TEST_ID1 TEST_ID2=$TELEGRAM_TEST_ID2 DB=$DATABASE_URL HTTP=$HTTP_BASE_URL"

# 0) Pre-flight checks
log "0) Running pre-flight checks..."

# Check if required services are running
if ! command -v psql >/dev/null 2>&1; then
  log "WARNING: psql not found - database operations will use fallback methods"
fi

# Check if Redis is accessible
if command -v redis-cli >/dev/null 2>&1; then
  if redis-cli -u "$REDIS_URL" ping >/dev/null 2>&1; then
    log "Redis is accessible"
  else
    log "WARNING: Redis not accessible at $REDIS_URL - some features may not work"
  fi
else
  log "WARNING: redis-cli not found - cannot verify Redis connectivity"
fi

# Check if the bot script exists
if [ ! -f "$RUN_BOT_SCRIPT" ]; then
  error "Bot script not found at $RUN_BOT_SCRIPT"
fi

# 1) Create/Upsert two users and chat_map entries directly in DB (safe non-destructive)
log "1) Ensure users and chat_map are present in DB (upsert)"

# Fixed: Corrected schema to match your actual models
SQL_UPSERT_USERS=$(cat <<SQL
-- use standard functions; adjust for your DB if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
DO \$\$
BEGIN
  -- users table upsert with correct schema
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='users') THEN
    -- upsert user 1
    INSERT INTO users (id, telegram_id, username, status, created_at)
    VALUES (uuid_generate_v4(), $TELEGRAM_TEST_ID1, 'test_user_1', 'ACTIVE', now())
    ON CONFLICT (telegram_id) DO UPDATE SET username = EXCLUDED.username, status = EXCLUDED.status;
    -- upsert user 2
    INSERT INTO users (id, telegram_id, username, status, created_at)
    VALUES (uuid_generate_v4(), $TELEGRAM_TEST_ID2, 'test_user_2', 'ACTIVE', now())
    ON CONFLICT (telegram_id) DO UPDATE SET username = EXCLUDED.username, status = EXCLUDED.status;
  END IF;
END
\$\$;
-- Upsert chat_map table with correct schema (chat_id as string)
DO \$\$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='chat_map') THEN
    INSERT INTO chat_map (id, user_id, chat_id)
    SELECT uuid_generate_v4()::text, u.id::text, u.telegram_id::text
    FROM users u WHERE u.telegram_id IN ($TELEGRAM_TEST_ID1, $TELEGRAM_TEST_ID2)
    ON CONFLICT (chat_id) DO UPDATE SET user_id = EXCLUDED.user_id;
  END IF;
END
\$\$;
SQL
)

# Try to run the SQL via psql
if command -v psql >/dev/null 2>&1; then
  export PGPASSWORD="${PGPASSWORD:-postgres}" # if you have .pgpass, it's fine too
  echo "$SQL_UPSERT_USERS" > "$ART/upsert_users.sql"
  log "Running SQL upsert to DB (psql)..."
  if psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$ART/upsert_users.sql" > "$ART/psql_upsert_out.txt" 2>&1; then
    log "Database upsert successful"
  else
    log "psql upsert returned non-zero. See $ART/psql_upsert_out.txt"
    # Continue anyway - the Python fallback might work
  fi
else
  log "psql not found - attempting fallback via admin HTTP API (requires admin token)."
  # fallback: attempt to create users via admin API (requires admin token)
  if [ -z "${ADMIN_TOKEN:-}" ]; then
    log "No ADMIN_TOKEN provided, skipping HTTP fallback. Please ensure DB has users."
  else
    for ID in "$TELEGRAM_TEST_ID1" "$TELEGRAM_TEST_ID2"; do
      curl -s -X POST "$HTTP_BASE_URL/api/v1/admin/users" -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        -d "{\"telegram_id\":$ID, \"username\":\"bot_seed_$ID\", \"status\":\"ACTIVE\"}" -o "$ART/user_seed_$ID.json" || true
    done
  fi
fi

# 2) Ensure chat_map entries exist (if chat_map table absent, warn)
log "2) Verifying chat_map rows exist"
python3 - <<PY > "$ART/check_chatmap.json" 2>&1 || true
import os,sys
from urllib.parse import urlparse
url=os.environ.get("DATABASE_URL", "$DATABASE_URL")
out={"database_url": url, "chatmap_ok": False}
try:
    import sqlalchemy as sa
    engine=sa.create_engine(url)
    with engine.connect() as conn:
        q = "SELECT count(*) FROM information_schema.tables WHERE table_name='chat_map'"
        if conn.execute(sa.text(q)).scalar():
            res = conn.execute(sa.text("SELECT count(*) FROM chat_map WHERE chat_id IN (:a,:b)"), {"a":str($TELEGRAM_TEST_ID1),"b":str($TELEGRAM_TEST_ID2)}).scalar()
            out["chatmap_count"] = int(res)
            out["chatmap_ok"] = (res>=1)
        else:
            out["chatmap_exists"]=False
except Exception as e:
    out["error"]=str(e)
print(out)
PY

log "Check chat_map results:"
cat "$ART/check_chatmap.json" | tee -a "$ART/run.log"

# 3) Export TELEGRAM_BOT_TOKEN to .env (for run script)
ENV_FILE=".env.local.bot"
echo "TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN" > "$ENV_FILE"
echo "DATABASE_URL=$DATABASE_URL" >> "$ENV_FILE"
echo "REDIS_URL=$REDIS_URL" >> "$ENV_FILE"
log "Wrote environment variables to $ENV_FILE"

# 4) Start bot in background (use venv if available)
log "4) Starting bot in polling mode (background). Logs -> $BOT_LOG"

# Attempt to stop existing background instance (best-effort)
pkill -f run_polling.py || true
sleep 1

if [ "$USE_SYSTEMD" = "true" ]; then
  log "USE_SYSTEMD=true - attempting systemctl restart cricalgo-bot.service"
  sudo systemctl restart cricalgo-bot.service || log "systemctl restart failed (service may not exist)"
else
  # Start with nohup in background, use venv python if present
  if [ -f "$VENV/bin/python" ]; then
    nohup "$VENV/bin/python" "$RUN_BOT_SCRIPT" > "$BOT_LOG" 2>&1 &
  else
    nohup python3 "$RUN_BOT_SCRIPT" > "$BOT_LOG" 2>&1 &
  fi
  sleep 2
fi

# 5) Wait and tail a few lines to confirm bot started
sleep 4
if [ -s "$BOT_LOG" ]; then
  log "Bot log (last 40 lines):"
  tail -n 40 "$BOT_LOG" | sed -n '1,200p' | tee -a "$ART/run.log"
else
  log "Bot log empty or not created yet; check $BOT_LOG"
fi

# 6) Quick bot API sanity: call getMe via Telegram REST to confirm token
TG_ME=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe" || true)
echo "$TG_ME" > "$ART/tg_getme.json"
if echo "$TG_ME" | grep -q '"ok":true'; then
  log "Telegram token valid — getMe OK"
  BOT_USERNAME=$(echo "$TG_ME" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['username'])" 2>/dev/null || echo "unknown")
  log "Bot username: @$BOT_USERNAME"
else
  log "Warning: Telegram token appears invalid; see $ART/tg_getme.json"
fi

# 7) Test webhook endpoint (if server is running)
log "7) Testing webhook endpoint..."
WEBHOOK_TEST=$(curl -s -X POST "$HTTP_BASE_URL/api/v1/webhooks/bep20" \
  -H "Content-Type: application/json" \
  -d "{\"tx_hash\":\"test-${TS}\",\"telegram_id\":$TELEGRAM_TEST_ID1,\"amount\":\"20.0\",\"confirmations\":12}" \
  -w "HTTP_STATUS:%{http_code}" || echo "HTTP_STATUS:000")
echo "$WEBHOOK_TEST" > "$ART/webhook_test.json"

if echo "$WEBHOOK_TEST" | grep -q "HTTP_STATUS:202\|HTTP_STATUS:200"; then
  log "Webhook endpoint is responding"
else
  log "WARNING: Webhook endpoint not responding (server may not be running)"
fi

# 8) Provide test instructions
cat > "$ART/next_steps.txt" <<EOF
Bot test prep finished at $TS.

How to test from two Telegram accounts:
- From each Telegram account (IDs: $TELEGRAM_TEST_ID1 and $TELEGRAM_TEST_ID2):
  1) Open chat with @$BOT_USERNAME (if available)
  2) Send: /start
  3) Send: /balance (to check wallet)
  4) Send: /contests (to see available contests)
  5) Use inline buttons to join contests

Test deposit notification (simulates blockchain webhook):
curl -X POST '$HTTP_BASE_URL/api/v1/webhooks/bep20' -H "Content-Type: application/json" -d \
'{"tx_hash":"test-${TS}-deposit","telegram_id":'"$TELEGRAM_TEST_ID1"',"amount":"20.0","confirmations":12}'

Test withdrawal notification:
curl -X POST '$HTTP_BASE_URL/api/v1/webhooks/bep20' -H "Content-Type: application/json" -d \
'{"tx_hash":"test-${TS}-withdrawal","telegram_id":'"$TELEGRAM_TEST_ID1"',"amount":"5.0","confirmations":12,"status":"confirmed"}'

Check logs:
- Bot runtime log: $BOT_LOG
- DB check output: $ART/psql_upsert_out.txt (if psql used)
- Webhook test results: $ART/webhook_test.json
- Diagnostic artifacts: $ART

Troubleshooting:
- If bot doesn't respond: Check $BOT_LOG for errors
- If webhook fails: Ensure main server is running on $HTTP_BASE_URL
- If database issues: Check $ART/psql_upsert_out.txt
- If Redis issues: Check Redis is running on $REDIS_URL

EOF

log "Wrote next_steps to $ART/next_steps.txt"

# 9) Final artifact packaging
tar -czf "${ART}.tar.gz" -C "$(dirname "$ART")" "$(basename "$ART")" || true
log "Artifacts packaged: ${ART}.tar.gz"

echo "IMPROVED BOT TEST PREP COMPLETE. Artifacts: ${ART}.tar.gz"
echo "Follow the instructions in $ART/next_steps.txt to test on your two Telegram accounts."
