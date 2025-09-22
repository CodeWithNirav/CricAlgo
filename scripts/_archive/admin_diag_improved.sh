#!/bin/bash
# Improved Admin Diagnostic Script
# Tests all admin endpoints and provides detailed error reporting

set -e

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-admin123}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="artifacts/admin_diag_${TIMESTAMP}"
LOG_FILE="${OUTPUT_DIR}/diagnostic.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Logging function
log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

log "${GREEN}=== CricAlgo Admin Diagnostic - $(date) ===${NC}"

# Test 1: Health check
log "\n${YELLOW}1. Testing health endpoint...${NC}"
if curl -s -f "$BASE_URL/health" > /dev/null; then
    log "${GREEN}✓ Health endpoint responding${NC}"
else
    log "${RED}✗ Health endpoint failed${NC}"
fi

# Test 2: Admin login
log "\n${YELLOW}2. Testing admin login...${NC}"
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/admin/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" || echo "LOGIN_FAILED")

if [[ "$LOGIN_RESPONSE" == "LOGIN_FAILED" ]]; then
    log "${RED}✗ Admin login failed - check credentials${NC}"
    ADMIN_TOKEN=""
else
    ADMIN_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token // empty' 2>/dev/null || echo "")
    if [[ -n "$ADMIN_TOKEN" && "$ADMIN_TOKEN" != "null" ]]; then
        log "${GREEN}✓ Admin login successful${NC}"
        echo "$ADMIN_TOKEN" > "$OUTPUT_DIR/admin_token.txt"
    else
        log "${RED}✗ Admin login response invalid: $LOGIN_RESPONSE${NC}"
        ADMIN_TOKEN=""
    fi
fi

# Test 3: Admin endpoints (if token available)
if [[ -n "$ADMIN_TOKEN" ]]; then
    AUTH_HEADER="Authorization: Bearer $ADMIN_TOKEN"
    
    # Test invite codes endpoint (canonical)
    log "\n${YELLOW}3. Testing invite codes endpoint (canonical)...${NC}"
    INVITE_RESPONSE=$(curl -s -w "\n%{http_code}" -H "$AUTH_HEADER" "$BASE_URL/api/v1/admin/invite_codes" || echo "ENDPOINT_FAILED")
    HTTP_CODE=$(echo "$INVITE_RESPONSE" | tail -n1)
    RESPONSE_BODY=$(echo "$INVITE_RESPONSE" | head -n -1)
    
    if [[ "$HTTP_CODE" == "200" ]]; then
        log "${GREEN}✓ Invite codes endpoint working${NC}"
        echo "$RESPONSE_BODY" | jq '.' > "$OUTPUT_DIR/invite_codes.json" 2>/dev/null || echo "$RESPONSE_BODY" > "$OUTPUT_DIR/invite_codes.txt"
    else
        log "${RED}✗ Invite codes endpoint failed: HTTP $HTTP_CODE${NC}"
        echo "$RESPONSE_BODY" > "$OUTPUT_DIR/invite_codes_error.txt"
    fi
    
    # Test invite codes endpoint (alias)
    log "\n${YELLOW}4. Testing invite codes endpoint (alias)...${NC}"
    INVITE_ALIAS_RESPONSE=$(curl -s -w "\n%{http_code}" -H "$AUTH_HEADER" "$BASE_URL/api/v1/admin/invitecodes" || echo "ENDPOINT_FAILED")
    HTTP_CODE_ALIAS=$(echo "$INVITE_ALIAS_RESPONSE" | tail -n1)
    RESPONSE_BODY_ALIAS=$(echo "$INVITE_ALIAS_RESPONSE" | head -n -1)
    
    if [[ "$HTTP_CODE_ALIAS" == "200" ]]; then
        log "${GREEN}✓ Invite codes alias endpoint working${NC}"
    else
        log "${RED}✗ Invite codes alias endpoint failed: HTTP $HTTP_CODE_ALIAS${NC}"
        echo "$RESPONSE_BODY_ALIAS" > "$OUTPUT_DIR/invite_codes_alias_error.txt"
    fi
    
    # Test users endpoint
    log "\n${YELLOW}5. Testing users endpoint...${NC}"
    USERS_RESPONSE=$(curl -s -w "\n%{http_code}" -H "$AUTH_HEADER" "$BASE_URL/api/v1/admin/users?limit=10" || echo "ENDPOINT_FAILED")
    HTTP_CODE_USERS=$(echo "$USERS_RESPONSE" | tail -n1)
    RESPONSE_BODY_USERS=$(echo "$USERS_RESPONSE" | head -n -1)
    
    if [[ "$HTTP_CODE_USERS" == "200" ]]; then
        log "${GREEN}✓ Users endpoint working${NC}"
        echo "$RESPONSE_BODY_USERS" | jq '.' > "$OUTPUT_DIR/users.json" 2>/dev/null || echo "$RESPONSE_BODY_USERS" > "$OUTPUT_DIR/users.txt"
    else
        log "${RED}✗ Users endpoint failed: HTTP $HTTP_CODE_USERS${NC}"
        echo "$RESPONSE_BODY_USERS" > "$OUTPUT_DIR/users_error.txt"
    fi
    
    # Test admin UI static files
    log "\n${YELLOW}6. Testing admin UI static files...${NC}"
    if curl -s -f "$BASE_URL/static/admin/index.html" > /dev/null; then
        log "${GREEN}✓ Admin UI static files accessible${NC}"
    else
        log "${RED}✗ Admin UI static files not accessible${NC}"
    fi
    
else
    log "${RED}✗ Skipping admin endpoint tests - no valid token${NC}"
fi

# Test 7: Database connectivity (if possible)
log "\n${YELLOW}7. Testing database connectivity...${NC}"
if command -v psql >/dev/null 2>&1; then
    # Try to connect to database
    if psql "$DATABASE_URL" -c "SELECT 1;" >/dev/null 2>&1; then
        log "${GREEN}✓ Database connection successful${NC}"
        
        # Check if invite_codes table exists
        TABLE_EXISTS=$(psql "$DATABASE_URL" -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'invitation_codes');" 2>/dev/null | tr -d ' \n' || echo "false")
        if [[ "$TABLE_EXISTS" == "t" ]]; then
            log "${GREEN}✓ invitation_codes table exists${NC}"
            
            # Count records
            RECORD_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM invitation_codes;" 2>/dev/null | tr -d ' \n' || echo "0")
            log "  - Records in invitation_codes: $RECORD_COUNT"
        else
            log "${RED}✗ invitation_codes table does not exist${NC}"
        fi
    else
        log "${RED}✗ Database connection failed${NC}"
    fi
else
    log "${YELLOW}⚠ psql not available, skipping database tests${NC}"
fi

# Generate summary
log "\n${YELLOW}=== DIAGNOSTIC SUMMARY ===${NC}"
log "Output directory: $OUTPUT_DIR"
log "Log file: $LOG_FILE"

# Create tarball
cd artifacts
tar -czf "admin_diag_${TIMESTAMP}.tar.gz" "admin_diag_${TIMESTAMP}/"
cd ..

log "\n${GREEN}✓ Diagnostic complete. Results saved to: artifacts/admin_diag_${TIMESTAMP}.tar.gz${NC}"
log "\nTo view results:"
log "  tar -tzf artifacts/admin_diag_${TIMESTAMP}.tar.gz"
log "  tar -xzf artifacts/admin_diag_${TIMESTAMP}.tar.gz"