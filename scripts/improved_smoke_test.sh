#!/usr/bin/env bash
set -euo pipefail

# Enhanced Smoke Test Script for CricAlgo Telegram Bot System
# This script tests the complete flow from user registration to contest settlement

TS=$(date -u +"%Y%m%dT%H%M%SZ")
ARTDIR="artifacts/bot_live_smoke_${TS}"
mkdir -p "$ARTDIR"
LOG="$ARTDIR/run.log"

# Environment validation
: "${HTTP:?Need to set HTTP (e.g. http://localhost:8000)}"
: "${TELEGRAM_BOT_TOKEN:?Need TELEGRAM_BOT_TOKEN}"
: "${ADMIN_TOKEN:?Need ADMIN_TOKEN for admin operations}"
: "${USER1_TELEGRAM_ID:?Need USER1_TELEGRAM_ID}"
: "${USER2_TELEGRAM_ID:?Need USER2_TELEGRAM_ID}"

# Optional environment variables with defaults
DEPOSIT_AMOUNT="${DEPOSIT_AMOUNT:-20.0}"
ENTRY_FEE="${ENTRY_FEE:-5.0}"
WITHDRAWAL_AMOUNT="${WITHDRAWAL_AMOUNT:-2.0}"

echo "Enhanced Smoke Test started at $TS" | tee "$LOG"
echo "Artifacts -> $ARTDIR" | tee -a "$LOG"
echo "Configuration:" | tee -a "$LOG"
echo "  HTTP: $HTTP" | tee -a "$LOG"
echo "  Deposit Amount: $DEPOSIT_AMOUNT" | tee -a "$LOG"
echo "  Entry Fee: $ENTRY_FEE" | tee -a "$LOG"
echo "  Withdrawal Amount: $WITHDRAWAL_AMOUNT" | tee -a "$LOG"

# Enhanced helper functions
curlj() {
  # $1: method, $2: url, $3: data(optional), $4: auth(optional bearer)
  local method="$1"
  local url="$2"
  local data="${3:-}"
  local auth="${4:-}"
  local curl_args=(-sS -X "$method" "$url")
  
  if [ -n "$data" ]; then
    curl_args+=(-H "Content-Type: application/json" -d "$data")
  fi
  
  if [ -n "$auth" ]; then
    curl_args+=(-H "Authorization: Bearer $auth")
  fi
  
  curl "${curl_args[@]}"
}

record_step() {
  echo "---- $1 ----" | tee -a "$LOG"
}

validate_response() {
  local response="$1"
  local step_name="$2"
  
  if echo "$response" | grep -qi "error\|failed\|exception"; then
    echo "ERROR in $step_name: $response" | tee -a "$LOG"
    return 1
  fi
  return 0
}

extract_id() {
  local response="$1"
  local field="$2"
  echo "$response" | sed -n "s/.*\"$field\"[[:space:]]*:[[:space:]]*\"\([^"]*\)\".*/\1/p" || true
}

# 0) Enhanced Health Check
record_step "Health Check"
HEALTH=$(curl -sS "$HTTP/api/v1/health" || true)
echo "$HEALTH" | tee -a "$LOG" > "$ARTDIR/health.json"

if ! validate_response "$HEALTH" "Health Check"; then
  echo "Health check failed. Exiting." | tee -a "$LOG"
  exit 1
fi

# 1) Enhanced User Management
record_step "User Management and Chat Mapping"

# Check if users exist, create if needed
create_user_if_needed() {
  local telegram_id="$1"
  local username="$2"
  local user_var="$3"
  
  echo "Checking user $telegram_id..." | tee -a "$LOG"
  
  # Try to find existing user
  local lookup_res=$(curlj GET "$HTTP/api/v1/admin/users?telegram_id=${telegram_id}" "" "$ADMIN_TOKEN" || true)
  echo "$lookup_res" | tee -a "$LOG" > "$ARTDIR/${user_var}_lookup.json"
  
  local user_uuid=$(extract_id "$lookup_res" "id")
  
  if [ -z "$user_uuid" ]; then
    echo "User not found, creating new user..." | tee -a "$LOG"
    local create_payload="{\"telegram_id\": ${telegram_id}, \"username\": \"${username}\"}"
    local create_res=$(curlj POST "$HTTP/api/v1/admin/users" "$create_payload" "$ADMIN_TOKEN" || true)
    echo "$create_res" | tee -a "$LOG" > "$ARTDIR/${user_var}_create.json"
    
    if ! validate_response "$create_res" "User Creation"; then
      echo "Failed to create user $telegram_id" | tee -a "$LOG"
      return 1
    fi
    
    user_uuid=$(extract_id "$create_res" "id")
  fi
  
  echo "${user_var}_UUID=$user_uuid" | tee -a "$LOG"
  eval "${user_var}_UUID=$user_uuid"
}

create_user_if_needed "$USER1_TELEGRAM_ID" "test_user_1" "USER1"
create_user_if_needed "$USER2_TELEGRAM_ID" "test_user_2" "USER2"

# 2) Enhanced Match and Contest Creation
record_step "Match and Contest Creation"

# Create match
MATCH_PAYLOAD="{\"title\":\"Smoke Test Match ${TS}\",\"external_id\":\"smoke-match-${TS}\",\"start_time\":\"2025-12-31T12:00:00Z\"}"
MATCH_RES=$(curlj POST "$HTTP/api/v1/admin/matches" "$MATCH_PAYLOAD" "$ADMIN_TOKEN" || true)
echo "$MATCH_RES" | tee -a "$LOG" > "$ARTDIR/match_create.json"

if ! validate_response "$MATCH_RES" "Match Creation"; then
  echo "Failed to create match, trying to find existing match..." | tee -a "$LOG"
  MATCH_LIST=$(curlj GET "$HTTP/api/v1/admin/matches" "" "$ADMIN_TOKEN" || true)
  echo "$MATCH_LIST" | tee -a "$LOG" > "$ARTDIR/matches_list.json"
  MATCH_ID=$(extract_id "$MATCH_LIST" "id" | head -1)
else
  MATCH_ID=$(extract_id "$MATCH_RES" "id")
fi

if [ -z "$MATCH_ID" ]; then
  echo "ERROR: No match ID found" | tee -a "$LOG"
  exit 1
fi

echo "MATCH_ID=$MATCH_ID" | tee -a "$LOG"

# Create contest for the match
CONTEST_PAYLOAD=$(cat <<EOF
{
  "title": "Smoke Test Contest ${TS}",
  "entry_fee": "${ENTRY_FEE}",
  "max_players": 10,
  "prize_structure": [
    {"pos": 1, "share": 0.8},
    {"pos": 2, "share": 0.2}
  ]
}
EOF
)

CONTEST_RES=$(curlj POST "$HTTP/api/v1/admin/matches/${MATCH_ID}/contests" "$CONTEST_PAYLOAD" "$ADMIN_TOKEN" || true)
echo "$CONTEST_RES" | tee -a "$LOG" > "$ARTDIR/contest_create.json"

if ! validate_response "$CONTEST_RES" "Contest Creation"; then
  echo "Failed to create contest, trying to find existing contest..." | tee -a "$LOG"
  CONTEST_LIST=$(curlj GET "$HTTP/api/v1/admin/matches/${MATCH_ID}/contests" "" "$ADMIN_TOKEN" || true)
  echo "$CONTEST_LIST" | tee -a "$LOG" > "$ARTDIR/contest_list.json"
  CONTEST_ID=$(extract_id "$CONTEST_LIST" "id" | head -1)
else
  CONTEST_ID=$(extract_id "$CONTEST_RES" "id")
fi

if [ -z "$CONTEST_ID" ]; then
  echo "ERROR: No contest ID found" | tee -a "$LOG"
  exit 1
fi

echo "CONTEST_ID=$CONTEST_ID" | tee -a "$LOG"

# 3) Enhanced Deposit Simulation
record_step "Deposit Simulation"

DEPOSIT_REF="smoke-dep-${TS}-u1"
WEBHOOK_PAYLOAD=$(cat <<EOF
{
  "tx_hash": "tx-${TS}-u1",
  "confirmations": 12,
  "amount": "${DEPOSIT_AMOUNT}",
  "currency": "USDT",
  "status": "confirmed",
  "user_id": "${USER1_UUID}",
  "metadata": {
    "deposit_ref": "${DEPOSIT_REF}",
    "user_id": "${USER1_UUID}",
    "to": "test-gateway",
    "token_symbol": "USDT"
  }
}
EOF
)

echo "$WEBHOOK_PAYLOAD" > "$ARTDIR/deposit_webhook_payload_u1.json"
WEBHOOK_RES=$(curlj POST "$HTTP/api/v1/webhooks/bep20" "$WEBHOOK_PAYLOAD" || true)
echo "$WEBHOOK_RES" | tee -a "$LOG" > "$ARTDIR/deposit_webhook_resp_u1.json"

if ! validate_response "$WEBHOOK_RES" "Deposit Webhook"; then
  echo "WARNING: Deposit webhook may have failed" | tee -a "$LOG"
fi

# Wait for background processing
echo "Waiting 8s for background processing..." | tee -a "$LOG"
sleep 8

# Verify deposit was processed
TX_SEARCH=$(curlj GET "$HTTP/api/v1/admin/transactions?user_id=${USER1_UUID}" "" "$ADMIN_TOKEN" || true)
echo "$TX_SEARCH" | tee -a "$LOG" > "$ARTDIR/user1_transactions.json"

# 4) Enhanced Contest Joining
record_step "Contest Joining"

# Try multiple join methods
JOIN_METHODS=(
  "POST $HTTP/api/v1/contests/${CONTEST_ID}/join {\"user_id\":\"${USER1_UUID}\"}"
  "POST $HTTP/api/v1/admin/contests/${CONTEST_ID}/force_join {\"user_id\":\"${USER1_UUID}\"}"
)

JOIN_SUCCESS=false
for i in "${!JOIN_METHODS[@]}"; do
  IFS=' ' read -r method url data <<< "${JOIN_METHODS[$i]}"
  echo "Trying join method $((i+1)): $method $url" | tee -a "$LOG"
  
  JOIN_RESP=$(curlj "$method" "$url" "$data" "$ADMIN_TOKEN" || true)
  echo "$JOIN_RESP" | tee -a "$LOG" > "$ARTDIR/join_response_method$((i+1)).json"
  
  if validate_response "$JOIN_RESP" "Contest Join Method $((i+1))"; then
    echo "Join successful with method $((i+1))" | tee -a "$LOG"
    JOIN_SUCCESS=true
    break
  else
    echo "Join method $((i+1)) failed" | tee -a "$LOG"
  fi
done

if [ "$JOIN_SUCCESS" = false ]; then
  echo "WARNING: All join methods failed" | tee -a "$LOG"
fi

# 5) Enhanced Contest Settlement
record_step "Contest Settlement"

SETTLE_RES=$(curlj POST "$HTTP/api/v1/admin/contests/${CONTEST_ID}/settle" "" "$ADMIN_TOKEN" || true)
echo "$SETTLE_RES" | tee -a "$LOG" > "$ARTDIR/settle_response.json"

if ! validate_response "$SETTLE_RES" "Contest Settlement"; then
  echo "WARNING: Contest settlement may have failed" | tee -a "$LOG"
fi

# Wait for payouts
echo "Waiting 6s for payout processing..." | tee -a "$LOG"
sleep 6

# Verify wallet balances
BAL_U1=$(curlj GET "$HTTP/api/v1/admin/users/${USER1_UUID}/wallet" "" "$ADMIN_TOKEN" || true)
echo "$BAL_U1" | tee -a "$LOG" > "$ARTDIR/user1_wallet_after_settle.json"

# 6) Enhanced Withdrawal Flow
record_step "Withdrawal Flow"

# Try multiple withdrawal creation methods
WITHDRAWAL_METHODS=(
  "POST $HTTP/api/v1/withdrawals {\"user_id\":\"${USER1_UUID}\",\"amount\":\"${WITHDRAWAL_AMOUNT}\",\"address\":\"0xdeadbeef\"}"
  "POST $HTTP/api/v1/admin/withdrawals {\"user_id\":\"${USER1_UUID}\",\"amount\":\"${WITHDRAWAL_AMOUNT}\",\"address\":\"0xdeadbeef\"}"
)

WD_SUCCESS=false
for i in "${!WITHDRAWAL_METHODS[@]}"; do
  IFS=' ' read -r method url data <<< "${WITHDRAWAL_METHODS[$i]}"
  echo "Trying withdrawal method $((i+1)): $method $url" | tee -a "$LOG"
  
  WD_CREATE=$(curlj "$method" "$url" "$data" "$ADMIN_TOKEN" || true)
  echo "$WD_CREATE" | tee -a "$LOG" > "$ARTDIR/withdraw_create_method$((i+1)).json"
  
  if validate_response "$WD_CREATE" "Withdrawal Creation Method $((i+1))"; then
    WD_ID=$(extract_id "$WD_CREATE" "id")
    if [ -n "$WD_ID" ]; then
      echo "Withdrawal created successfully with method $((i+1))" | tee -a "$LOG"
      WD_SUCCESS=true
      break
    fi
  else
    echo "Withdrawal method $((i+1)) failed" | tee -a "$LOG"
  fi
done

if [ "$WD_SUCCESS" = true ] && [ -n "$WD_ID" ]; then
  echo "WD_ID=$WD_ID" | tee -a "$LOG"
  
  # Approve withdrawal
  record_step "Withdrawal Approval"
  APPROVE_RES=$(curlj POST "$HTTP/api/v1/admin/withdrawals/${WD_ID}/approve" "" "$ADMIN_TOKEN" || true)
  echo "$APPROVE_RES" | tee -a "$LOG" > "$ARTDIR/withdraw_approve_resp.json"
  
  if ! validate_response "$APPROVE_RES" "Withdrawal Approval"; then
    echo "WARNING: Withdrawal approval may have failed" | tee -a "$LOG"
  fi
else
  echo "WARNING: No withdrawal ID found, skipping approval" | tee -a "$LOG"
fi

# 7) Enhanced Log Collection
record_step "Log Collection"

# Collect Docker logs with better error handling
for service in bot worker app; do
  echo "Collecting logs for $service..." | tee -a "$LOG"
  if docker-compose logs --tail=500 "$service" > "$ARTDIR/${service}_log.txt" 2>&1; then
    echo "Successfully collected $service logs" | tee -a "$LOG"
  else
    echo "WARNING: Failed to collect $service logs" | tee -a "$LOG"
  fi
done

# 8) Enhanced Telegram Integration Test
record_step "Telegram Integration Test"

TG_UPDATES=$(curl -sS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates" || true)
echo "$TG_UPDATES" > "$ARTDIR/telegram_getUpdates.json"

if echo "$TG_UPDATES" | grep -q '"ok":true'; then
  echo "Telegram API is accessible" | tee -a "$LOG"
else
  echo "WARNING: Telegram API may not be accessible" | tee -a "$LOG"
fi

# 9) Enhanced Summary and Reporting
record_step "Test Summary"

# Create comprehensive summary
SUMMARY=$(cat <<EOF
{
  "timestamp": "$TS",
  "test_status": "completed",
  "configuration": {
    "http_endpoint": "$HTTP",
    "deposit_amount": "$DEPOSIT_AMOUNT",
    "entry_fee": "$ENTRY_FEE",
    "withdrawal_amount": "$WITHDRAWAL_AMOUNT"
  },
  "test_results": {
    "match_id": "$MATCH_ID",
    "contest_id": "$CONTEST_ID",
    "user1_uuid": "$USER1_UUID",
    "user2_uuid": "$USER2_UUID",
    "withdrawal_id": "${WD_ID:-null}"
  },
  "artifacts": {
    "health_check": "$ARTDIR/health.json",
    "deposit_webhook": "$ARTDIR/deposit_webhook_resp_u1.json",
    "contest_join": "$ARTDIR/join_response_method1.json",
    "contest_settle": "$ARTDIR/settle_response.json",
    "withdrawal_create": "$ARTDIR/withdraw_create_method1.json",
    "withdrawal_approve": "$ARTDIR/withdraw_approve_resp.json",
    "bot_logs": "$ARTDIR/bot_log.txt",
    "worker_logs": "$ARTDIR/worker_log.txt",
    "app_logs": "$ARTDIR/app_log.txt"
  },
  "success_indicators": {
    "health_check_ok": $(echo "$HEALTH" | grep -q "ok" && echo "true" || echo "false"),
    "users_created": $(echo "$USER1_UUID" | grep -q "." && echo "true" || echo "false"),
    "match_created": $(echo "$MATCH_ID" | grep -q "." && echo "true" || echo "false"),
    "contest_created": $(echo "$CONTEST_ID" | grep -q "." && echo "true" || echo "false"),
    "deposit_processed": $(echo "$WEBHOOK_RES" | grep -q "ok" && echo "true" || echo "false"),
    "telegram_accessible": $(echo "$TG_UPDATES" | grep -q '"ok":true' && echo "true" || echo "false")
  }
}
EOF
)

echo "$SUMMARY" | tee "$ARTDIR/smoke_test_summary.json" | jq . > "$ARTDIR/smoke_test_summary_pretty.json" 2>/dev/null || echo "$SUMMARY" > "$ARTDIR/smoke_test_summary.json"

# Final status
echo "Enhanced Smoke Test completed at $(date -u +"%Y%m%dT%H%M%SZ")" | tee -a "$LOG"
echo "Artifacts saved to $ARTDIR" | tee -a "$LOG"
echo "Summary: $ARTDIR/smoke_test_summary.json" | tee -a "$LOG"

# Exit with appropriate code
if grep -q "ERROR" "$LOG"; then
  echo "Test completed with errors. Check $LOG for details." | tee -a "$LOG"
  exit 1
else
  echo "Test completed successfully!" | tee -a "$LOG"
  exit 0
fi
