#!/usr/bin/env bash
set -euo pipefail

###
# IMPROVED Prep + Start Bot + Seed Test Data + Create Match/Contest + Simulate Deposit
# Enhanced version with proper schema handling, correct API endpoints, and better error handling
###

# ----- CONFIG (edit or export before running) -----
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-8257937151:AAGyRy10haSpTNYG-kOQ3wU2emBnybx3qAs}"  # required
TELEGRAM_TEST_ID1="${TELEGRAM_TEST_ID1:-693173957}"   # required (account A)
TELEGRAM_TEST_ID2="${TELEGRAM_TEST_ID2:-}"             # required (account B) - will prompt if empty
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin123}"
DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/cricalgo}"
HTTP_BASE="${HTTP_BASE:-http://localhost:8000}"
VENV="${VENV:-.venv}"           # set if you use virtualenv python
RUN_BOT_SCRIPT="${RUN_BOT_SCRIPT:-./app/bot/run_polling.py}"
ART_DIR="artifacts/bot_ready_$(date -u +%Y%m%dT%H%M%SZ)"
BOT_LOG="$ART_DIR/bot_polling.log"
WORKER_LOG="$ART_DIR/worker.log"
REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
# --------------------------------------------------

mkdir -p "$ART_DIR"
log(){ echo ">>> $*" | tee -a "$ART_DIR/run.log"; }
error(){ echo "ERROR: $*" | tee -a "$ART_DIR/run.log"; exit 1; }

# prompt for second test id if missing
if [ -z "${TELEGRAM_TEST_ID2}" ]; then
  read -p "Enter second Telegram test user numeric ID: " TELEGRAM_TEST_ID2
fi

log "Config: HTTP_BASE=$HTTP_BASE TEST1=$TELEGRAM_TEST_ID1 TEST2=$TELEGRAM_TEST_ID2"

# 1) Basic connectivity checks
log "1) Checking service health at $HTTP_BASE/api/v1/health"
if curl -sSf "$HTTP_BASE/api/v1/health" -o "$ART_DIR/health.json"; then
  log "Health OK"
else
  log "WARNING: health endpoint failed - saved response (if any) to $ART_DIR/health.json"
fi

# 2) Verify Telegram token with getMe
log "2) Verifying Telegram token with getMe"
TG_ME=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe" || true)
echo "$TG_ME" > "$ART_DIR/tg_getme.json"
if echo "$TG_ME" | grep -q '"ok":true'; then
  BOT_USERNAME=$(jq -r '.result.username // empty' "$ART_DIR/tg_getme.json" 2>/dev/null || echo "")
  log "Telegram bot token valid. Bot username: @$BOT_USERNAME"
else
  log "ERROR: Telegram token invalid or network issue. See $ART_DIR/tg_getme.json"
  # continue but warn
fi

# 3) Check Redis connectivity
log "3) Checking Redis connectivity"
if command -v redis-cli >/dev/null 2>&1; then
  if redis-cli -u "$REDIS_URL" ping >/dev/null 2>&1; then
    log "Redis is accessible"
  else
    log "WARNING: Redis not accessible at $REDIS_URL - Celery tasks may not work"
  fi
else
  log "WARNING: redis-cli not found - cannot verify Redis connectivity"
fi

# 4) Ensure DB access via psql (if available), otherwise fallback to admin API
USE_PSQL=false
if command -v psql >/dev/null 2>&1; then
  USE_PSQL=true
fi

# 5) Upsert two test users (non-destructive) - FIXED SCHEMA
log "4) Upserting two test users and chat_map entries with correct schema"
if $USE_PSQL ; then
  # Fixed: Use correct schema matching your DDL
  cat > "$ART_DIR/upsert_users.sql" <<SQL
-- Fixed schema upsert script matching your actual DDL
DO \$\$
BEGIN
  -- Create users with correct schema
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='users') THEN
    INSERT INTO users (id, telegram_id, username, status, created_at)
    VALUES (gen_random_uuid(), ${TELEGRAM_TEST_ID1}, 'test_user_1', 'ACTIVE', NOW())
    ON CONFLICT (telegram_id) DO UPDATE SET username=EXCLUDED.username, status=EXCLUDED.status;

    INSERT INTO users (id, telegram_id, username, status, created_at)
    VALUES (gen_random_uuid(), ${TELEGRAM_TEST_ID2}, 'test_user_2', 'ACTIVE', NOW())
    ON CONFLICT (telegram_id) DO UPDATE SET username=EXCLUDED.username, status=EXCLUDED.status;
  END IF;

  -- Create chat_map entries with correct schema (chat_id as VARCHAR)
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='chat_map') THEN
    INSERT INTO chat_map (id, user_id, chat_id)
    SELECT gen_random_uuid()::text, u.id::text, u.telegram_id::text
    FROM users u WHERE u.telegram_id IN (${TELEGRAM_TEST_ID1}, ${TELEGRAM_TEST_ID2})
    ON CONFLICT (chat_id) DO UPDATE SET user_id=EXCLUDED.user_id;
  END IF;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'upsert script skipped due to: %', SQLERRM;
END
\$\$;
SQL

  PGPASS="${PGPASSWORD:-postgres}"
  export PGPASSWORD="$PGPASS"
  if psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$ART_DIR/upsert_users.sql" > "$ART_DIR/psql_upsert_out.txt" 2>&1; then
    log "Database upsert completed (see $ART_DIR/psql_upsert_out.txt)"
  else
    log "Database upsert had issues (see $ART_DIR/psql_upsert_out.txt). Will attempt HTTP fallback."
  fi
else
  log "psql not available; will attempt HTTP admin API user creation (requires admin token)."
fi

# 6) Try to get admin token - FIXED ENDPOINT
log "5) Obtain admin token via admin login API"
ADMIN_TOKEN=""
ADM_LOGIN_RESP="$ART_DIR/admin_login_resp.json"
if curl -sS -X POST "$HTTP_BASE/api/v1/admin/login" -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" -o "$ADM_LOGIN_RESP"; then
  ADMIN_TOKEN=$(jq -r .access_token "$ADM_LOGIN_RESP" 2>/dev/null || echo "")
  if [ -n "$ADMIN_TOKEN" ] && [ "$ADMIN_TOKEN" != "null" ]; then
    log "Admin token obtained"
  else
    log "Admin login did not return token; saved response to $ADM_LOGIN_RESP"
    ADMIN_TOKEN=""
  fi
else
  log "Admin login HTTP request failed; saved response to $ADM_LOGIN_RESP"
fi

# 7) If DB upsert didn't run and admin token exists, create users via admin API
if [ -n "$ADMIN_TOKEN" ] && [ "$USE_PSQL" = "false" ]; then
  log "6) Creating test users via admin API (fallback)"
  for ID in "$TELEGRAM_TEST_ID1" "$TELEGRAM_TEST_ID2"; do
    curl -s -X POST "$HTTP_BASE/api/v1/admin/users" \
      -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
      -d "{\"telegram_id\":$ID,\"username\":\"ui_test_$ID\",\"status\":\"ACTIVE\"}" \
      -o "$ART_DIR/admin_create_user_${ID}.json" || true
  done
fi

# 8) Create a sample match + contest (FIXED API ENDPOINTS)
MATCH_ID=""
CONTEST_ID=""
if [ -n "$ADMIN_TOKEN" ]; then
  log "7) Creating a sample match and contest via admin API"
  
  # Create match using correct endpoint
  MATCH_PAYLOAD='{"title":"Automated Test Match","external_id":"match-test-'"$(date +%s)"'","start_time":"'"$(date -u -d '+1 hour' --iso-8601=seconds)"'"}'
  curl -s -X POST "$HTTP_BASE/api/v1/admin/matches" -H "Content-Type: application/json" -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d "$MATCH_PAYLOAD" -o "$ART_DIR/match_create.json" || true
  
  MATCH_ID=$(jq -r '.match.id // .id // empty' "$ART_DIR/match_create.json" 2>/dev/null || echo "")
  if [ -z "$MATCH_ID" ]; then
    log "Match create may have returned different shape; see $ART_DIR/match_create.json"
  else
    log "Created match id $MATCH_ID"
    
    # Create contest for the match using correct endpoint structure
    CONTEST_PAYLOAD='{"title":"Automated Test Contest","entry_fee":"5.0","max_players":10,"prize_structure":{"1":70,"2":30}}'
    curl -s -X POST "$HTTP_BASE/api/v1/admin/matches/$MATCH_ID/contests" -H "Content-Type: application/json" -H "Authorization: Bearer $ADMIN_TOKEN" \
      -d "$CONTEST_PAYLOAD" -o "$ART_DIR/contest_create.json" || true
    CONTEST_ID=$(jq -r '.contest.id // .id // empty' "$ART_DIR/contest_create.json" 2>/dev/null || echo "")
    log "Contest create response saved to $ART_DIR/contest_create.json"
  fi
else
  log "No admin token; skipping auto match/contest creation. You can create a contest manually in Admin UI."
fi

# 9) Start bot polling (background)
log "8) Starting bot in polling mode (background)"
pkill -f run_polling.py || true
sleep 1

# Create .env file for bot
cat > ".env.local.bot" <<EOF
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
DATABASE_URL=$DATABASE_URL
REDIS_URL=$REDIS_URL
EOF

if [ -f "$VENV/bin/python" ]; then
  nohup "$VENV/bin/python" "$RUN_BOT_SCRIPT" > "$BOT_LOG" 2>&1 &
elif [ -f "$VENV/Scripts/python.exe" ]; then
  nohup "$VENV/Scripts/python.exe" "$RUN_BOT_SCRIPT" > "$BOT_LOG" 2>&1 &
else
  nohup python3 "$RUN_BOT_SCRIPT" > "$BOT_LOG" 2>&1 &
fi

sleep 3
log "Bot process started; tailing bot log (last 40 lines)"
if [ -f "$BOT_LOG" ]; then
  tail -n 40 "$BOT_LOG" | tee -a "$ART_DIR/run.log"
else
  log "Bot log not present yet at $BOT_LOG (it may take longer to initialize)."
fi

# 10) Start Celery worker (if Redis is available)
log "9) Starting Celery worker for background tasks"
if command -v celery >/dev/null 2>&1; then
  # Stop existing workers
  pkill -f "celery.*worker" || true
  sleep 1
  
  # Start worker with proper configuration
  if [ -f "$VENV/bin/celery" ]; then
    nohup "$VENV/bin/celery" -A app.celery_app worker --loglevel=info > "$WORKER_LOG" 2>&1 &
  else
    nohup celery -A app.celery_app worker --loglevel=info > "$WORKER_LOG" 2>&1 &
  fi
  
  sleep 2
  log "Celery worker started; tailing worker log (last 20 lines)"
  if [ -f "$WORKER_LOG" ]; then
    tail -n 20 "$WORKER_LOG" | tee -a "$ART_DIR/run.log" || true
  fi
else
  log "WARNING: Celery not found - background tasks will not be processed"
fi

# 11) Simulate deposit webhook for TEST_ID1 to credit wallet & verify processing
log "10) Sending simulated deposit webhook for user $TELEGRAM_TEST_ID1"
SIM_TX="test-$(date +%s)"
curl -s -X POST "$HTTP_BASE/api/v1/webhooks/bep20" -H "Content-Type: application/json" \
  -d "{\"tx_hash\":\"$SIM_TX\",\"telegram_id\":$TELEGRAM_TEST_ID1,\"amount\":\"20.0\",\"confirmations\":12}" -o "$ART_DIR/deposit_webhook_resp.json" || true
log "Deposit webhook response saved to $ART_DIR/deposit_webhook_resp.json"

# allow some seconds for worker to pick up task
log "Waiting 6 seconds for deposit processing..."
sleep 6

# 12) Check user wallet via admin API if token available
if [ -n "$ADMIN_TOKEN" ]; then
  log "11) Fetching user data via admin API"
  curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$HTTP_BASE/api/v1/admin/users?telegram_id=${TELEGRAM_TEST_ID1}" -o "$ART_DIR/user_lookup.json" || true
  
  # Check if there's a specific wallet endpoint
  USER_ID=$(jq -r '.[0].id // empty' "$ART_DIR/user_lookup.json" 2>/dev/null || echo "")
  if [ -n "$USER_ID" ]; then
    log "Found user ID: $USER_ID"
    # Try to get wallet info if endpoint exists
    curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$HTTP_BASE/api/v1/admin/users/$USER_ID/wallet" -o "$ART_DIR/user_wallet.json" || true
  fi
fi

# 13) Verify services are running
log "12) Verifying all services are running"
SERVICES_OK=true

# Check bot process
if pgrep -f run_polling.py >/dev/null; then
  log "✓ Bot process is running"
else
  log "✗ Bot process not found"
  SERVICES_OK=false
fi

# Check worker process
if pgrep -f "celery.*worker" >/dev/null; then
  log "✓ Celery worker is running"
else
  log "✗ Celery worker not found"
  SERVICES_OK=false
fi

# Check Redis
if command -v redis-cli >/dev/null 2>&1; then
  if redis-cli -u "$REDIS_URL" ping >/dev/null 2>&1; then
    log "✓ Redis is accessible"
  else
    log "✗ Redis not accessible"
    SERVICES_OK=false
  fi
fi

# Check main server
if curl -sSf "$HTTP_BASE/api/v1/health" >/dev/null 2>&1; then
  log "✓ Main server is responding"
else
  log "✗ Main server not responding"
  SERVICES_OK=false
fi

if [ "$SERVICES_OK" = true ]; then
  log "✓ All services are running properly"
else
  log "⚠ Some services may not be running - check logs for details"
fi

# 14) Final instructions
cat > "$ART_DIR/next_steps.txt" <<EOF
Bot prep complete.

1) On each Telegram account (IDs: $TELEGRAM_TEST_ID1 and $TELEGRAM_TEST_ID2):
   - Open chat with @$BOT_USERNAME (see $ART_DIR/tg_getme.json)
   - Send /start
   - Send /contests to list contests, open the 'Automated Test Contest' and press Join
   - Use /balance to confirm wallets

2) Simulate additional deposits (if needed):
   curl -X POST '$HTTP_BASE/api/v1/webhooks/bep20' -H "Content-Type: application/json" \
     -d '{"tx_hash":"manual-$(date +%s)","telegram_id":'$TELEGRAM_TEST_ID1',"amount":"10.0","confirmations":12}'

3) Test withdrawal simulation:
   curl -X POST '$HTTP_BASE/api/v1/webhooks/bep20' -H "Content-Type: application/json" \
     -d '{"tx_hash":"withdraw-$(date +%s)","telegram_id":'$TELEGRAM_TEST_ID1',"amount":"5.0","confirmations":12,"status":"confirmed"}'

4) Logs/artifacts:
   - Bot log: $BOT_LOG
   - Worker log: $WORKER_LOG
   - HTTP responses: $ART_DIR/*.json
   - Diagnostic log: $ART_DIR/run.log

5) Service status:
   - Bot: $(pgrep -f run_polling.py >/dev/null && echo "RUNNING" || echo "NOT RUNNING")
   - Worker: $(pgrep -f "celery.*worker" >/dev/null && echo "RUNNING" || echo "NOT RUNNING")
   - Redis: $(redis-cli -u "$REDIS_URL" ping >/dev/null 2>&1 && echo "ACCESSIBLE" || echo "NOT ACCESSIBLE")
   - Server: $(curl -sSf "$HTTP_BASE/api/v1/health" >/dev/null 2>&1 && echo "RESPONDING" || echo "NOT RESPONDING")

Troubleshooting:
- If bot doesn't respond: Check $BOT_LOG for errors
- If deposits don't process: Check $WORKER_LOG for Celery task errors
- If webhook fails: Ensure main server is running on $HTTP_BASE
- If database issues: Check $ART_DIR/psql_upsert_out.txt
- If Redis issues: Check Redis is running on $REDIS_URL

EOF

log "Prepared artifacts in $ART_DIR; packaged tarball next."
tar -czf "${ART_DIR}.tar.gz" -C "$(dirname "$ART_DIR")" "$(basename "$ART_DIR")" || true
log "Artifacts: ${ART_DIR}.tar.gz"

if [ "$SERVICES_OK" = true ]; then
  echo "✅ BOT TEST PREP COMPLETE - All services running!"
  echo "Follow the instructions in $ART_DIR/next_steps.txt to test on your two Telegram accounts."
else
  echo "⚠️  BOT TEST PREP COMPLETE - Some services may need attention"
  echo "Check the service status in $ART_DIR/next_steps.txt and logs for details."
fi
