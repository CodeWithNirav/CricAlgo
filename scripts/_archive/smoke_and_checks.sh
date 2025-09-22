#!/usr/bin/env bash
set -euo pipefail

# Configuration
STAGING_HOST="${STAGING_HOST:-http://localhost:8000}"
ARTIFACT_DIR="${ARTIFACT_DIR:-artifacts/smoke_$(date -u +%Y%m%dT%H%M%SZ)}"

# Create artifact directory
mkdir -p "$ARTIFACT_DIR"

echo "=== CricAlgo Smoke Test ==="
echo "Target: $STAGING_HOST"
echo "Artifacts: $ARTIFACT_DIR"
echo ""

# Function to log with timestamp
log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1"
}

# Function to check HTTP response
check_http() {
    local url="$1"
    local expected_status="$2"
    local description="$3"
    local output_file="$4"
    
    log "Testing: $description"
    
    local response
    local http_code
    
    if response=$(curl -sS -w "\nHTTP_CODE:%{http_code}\n" "$url" -o "$output_file" 2>&1); then
        http_code=$(echo "$response" | grep "HTTP_CODE:" | cut -d: -f2)
        if [ "$http_code" = "$expected_status" ]; then
            log "✓ $description - Status: $http_code"
            return 0
        else
            log "✗ $description - Expected: $expected_status, Got: $http_code"
            return 1
        fi
    else
        log "✗ $description - Request failed: $response"
        return 1
    fi
}

# Test 1: Health check
log "1) Testing health endpoint"
if ! check_http "$STAGING_HOST/api/v1/health" "200" "Health check" "$ARTIFACT_DIR/health.json"; then
    log "Health check failed - aborting smoke test"
    exit 2
fi

# Display health response
if [ -f "$ARTIFACT_DIR/health.json" ]; then
    log "Health response:"
    cat "$ARTIFACT_DIR/health.json" | jq -r . 2>/dev/null || cat "$ARTIFACT_DIR/health.json"
fi

# Test 2: Create test user (if API supports it)
log ""
log "2) Testing user registration (if supported)"
REG_RESP=$(curl -sS -X POST "$STAGING_HOST/api/v1/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"telegram_id":999999999,"username":"smoke_test_user"}' \
    -w "\nHTTP_CODE:%{http_code}\n" 2>/dev/null || echo "HTTP_CODE:000")

echo "$REG_RESP" > "$ARTIFACT_DIR/register_resp.json"

if echo "$REG_RESP" | grep -q "HTTP_CODE:200\|HTTP_CODE:201\|HTTP_CODE:409"; then
    log "✓ User registration endpoint accessible"
else
    log "⚠ User registration not available or failed (this may be expected)"
fi

# Test 3: Send webhook
log ""
log "3) Testing webhook endpoint"
WEBHOOK_PAYLOAD='{"tx_hash":"smoke-'"$(date +%s)"'","amount":"0.001","metadata":{"note":"smoke_test"}}'

if check_http "$STAGING_HOST/api/v1/webhooks/bep20" "202" "Webhook submission" "$ARTIFACT_DIR/webhook_resp.json" \
    -X POST \
    -H "Content-Type: application/json" \
    -d "$WEBHOOK_PAYLOAD"; then
    
    log "✓ Webhook submitted successfully"
    
    # Display webhook response
    if [ -f "$ARTIFACT_DIR/webhook_resp.json" ]; then
        log "Webhook response:"
        cat "$ARTIFACT_DIR/webhook_resp.json" | jq -r . 2>/dev/null || cat "$ARTIFACT_DIR/webhook_resp.json"
    fi
else
    log "✗ Webhook submission failed"
    exit 3
fi

# Test 4: Wait and check for processing
log ""
log "4) Waiting 10s for deposit processing..."
sleep 10

# Test 5: Check if we can query transactions (if endpoint exists)
log ""
log "5) Testing transaction query (if available)"
if check_http "$STAGING_HOST/api/v1/transactions" "200" "Transaction query" "$ARTIFACT_DIR/transactions.json" 2>/dev/null; then
    log "✓ Transaction endpoint accessible"
    if [ -f "$ARTIFACT_DIR/transactions.json" ]; then
        log "Transaction count: $(cat "$ARTIFACT_DIR/transactions.json" | jq '. | length' 2>/dev/null || echo "unknown")"
    fi
else
    log "⚠ Transaction endpoint not available (this may be expected)"
fi

# Test 6: Check system metrics (if available)
log ""
log "6) Testing metrics endpoint (if available)"
if check_http "$STAGING_HOST/metrics" "200" "Metrics endpoint" "$ARTIFACT_DIR/metrics.txt" 2>/dev/null; then
    log "✓ Metrics endpoint accessible"
    # Count some key metrics
    if [ -f "$ARTIFACT_DIR/metrics.txt" ]; then
        local http_requests=$(grep -c "http_requests_total" "$ARTIFACT_DIR/metrics.txt" 2>/dev/null || echo "0")
        local celery_tasks=$(grep -c "celery_task" "$ARTIFACT_DIR/metrics.txt" 2>/dev/null || echo "0")
        log "Metrics: HTTP requests=$http_requests, Celery tasks=$celery_tasks"
    fi
else
    log "⚠ Metrics endpoint not available"
fi

# Summary
log ""
log "=== Smoke Test Summary ==="
log "✓ Health check passed"
log "✓ Webhook submission passed"
log "⚠ User registration: $(echo "$REG_RESP" | grep -q "HTTP_CODE:200\|HTTP_CODE:201\|HTTP_CODE:409" && echo "available" || echo "not available")"
log "⚠ Transaction query: $(check_http "$STAGING_HOST/api/v1/transactions" "200" "Transaction query" "/dev/null" 2>/dev/null && echo "available" || echo "not available")"
log "⚠ Metrics: $(check_http "$STAGING_HOST/metrics" "200" "Metrics endpoint" "/dev/null" 2>/dev/null && echo "available" || echo "not available")"

log ""
log "Artifacts saved to: $ARTIFACT_DIR"
log "Smoke test completed successfully!"

# List artifacts
log ""
log "Generated artifacts:"
ls -la "$ARTIFACT_DIR" | while read -r line; do
    log "  $line"
done
