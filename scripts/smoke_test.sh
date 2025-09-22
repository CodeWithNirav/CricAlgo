#!/bin/bash
set -euo pipefail

# =============================================================================
# Consolidated Smoke Test Script for CricAlgo
# =============================================================================
# 
# This script performs comprehensive smoke tests for:
# - Application endpoints
# - Database connectivity
# - Redis connectivity
# - Admin UI functionality
# - Core business logic flows
#
# Author: CricAlgo DevOps Team
# Version: 2.0.0
# =============================================================================

readonly SCRIPT_VERSION="2.0.0"
readonly SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
STAGING_HOST="${STAGING_HOST:-http://localhost:8000}"
ARTIFACT_DIR="${ARTIFACT_DIR:-artifacts/smoke_$(date -u +%Y%m%dT%H%M%SZ)}"
TIMEOUT="${TIMEOUT:-30}"
VERBOSE="${VERBOSE:-false}"
CLEANUP="${CLEANUP:-true}"

# Color codes
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

# Test results
declare -A TEST_RESULTS
declare -A TEST_DETAILS

# Logging functions
log_info() {
    if [ "$VERBOSE" = "true" ]; then
        echo -e "${BLUE}[INFO]${NC} $(date -u +%Y-%m-%dT%H:%M:%SZ) $1"
    fi
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date -u +%Y-%m-%dT%H:%M:%SZ) $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date -u +%Y-%m-%dT%H:%M:%SZ) $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date -u +%Y-%m-%dT%H:%M:%SZ) $1"
}

# Create artifact directory
mkdir -p "$ARTIFACT_DIR"

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_result="${3:-success}"
    
    log_info "Running test: $test_name"
    
    if eval "$test_command" >/dev/null 2>&1; then
        if [ "$expected_result" = "success" ]; then
            TEST_RESULTS["$test_name"]="PASS"
            TEST_DETAILS["$test_name"]="Test passed"
            log_success "✓ $test_name"
            return 0
        else
            TEST_RESULTS["$test_name"]="FAIL"
            TEST_DETAILS["$test_name"]="Unexpected success"
            log_error "✗ $test_name (unexpected success)"
            return 1
        fi
    else
        if [ "$expected_result" = "failure" ]; then
            TEST_RESULTS["$test_name"]="PASS"
            TEST_DETAILS["$test_name"]="Expected failure"
            log_success "✓ $test_name (expected failure)"
            return 0
        else
            TEST_RESULTS["$test_name"]="FAIL"
            TEST_DETAILS["$test_name"]="Test failed"
            log_error "✗ $test_name"
            return 1
        fi
    fi
}

# Function to check HTTP endpoint
check_http_endpoint() {
    local url="$1"
    local expected_status="$2"
    local description="$3"
    local output_file="$4"
    
    log_info "Testing HTTP endpoint: $description ($url)"
    
    local response
    local http_code
    
    if response=$(curl -sS -w "\nHTTP_CODE:%{http_code}\n" "$url" -o "$output_file" --max-time "$TIMEOUT" 2>&1); then
        http_code=$(echo "$response" | grep "HTTP_CODE:" | cut -d: -f2)
        if [ "$http_code" = "$expected_status" ]; then
            TEST_RESULTS["$description"]="PASS"
            TEST_DETAILS["$description"]="Status: $http_code"
            log_success "✓ $description - Status: $http_code"
            return 0
        else
            TEST_RESULTS["$description"]="FAIL"
            TEST_DETAILS["$description"]="Expected: $expected_status, Got: $http_code"
            log_error "✗ $description - Expected: $expected_status, Got: $http_code"
            return 1
        fi
    else
        TEST_RESULTS["$description"]="FAIL"
        TEST_DETAILS["$description"]="Request failed: $response"
        log_error "✗ $description - Request failed: $response"
        return 1
    fi
}

# Function to check admin UI
check_admin_ui() {
    local description="Admin UI"
    
    log_info "Testing admin UI: $description"
    
    # Check if admin UI is accessible
    if check_http_endpoint "$STAGING_HOST/admin" "200" "$description" "$ARTIFACT_DIR/admin.html"; then
        # Check if it's not just a 404 page
        if grep -q "Admin UI not built" "$ARTIFACT_DIR/admin.html" 2>/dev/null; then
            TEST_RESULTS["$description"]="WARN"
            TEST_DETAILS["$description"]="Admin UI not built"
            log_warning "⚠ $description - Admin UI not built"
            return 1
        else
            TEST_RESULTS["$description"]="PASS"
            TEST_DETAILS["$description"]="Admin UI accessible"
            log_success "✓ $description - Admin UI accessible"
            return 0
        fi
    else
        return 1
    fi
}

# Function to check database connectivity
check_database() {
    local description="Database Connectivity"
    
    log_info "Testing database connectivity: $description"
    
    # Try to run a simple database check
    if command -v psql >/dev/null 2>&1; then
        if [ -n "${DATABASE_URL:-}" ]; then
            if echo "SELECT 1;" | psql "$DATABASE_URL" -t -A >/dev/null 2>&1; then
                TEST_RESULTS["$description"]="PASS"
                TEST_DETAILS["$description"]="Database accessible"
                log_success "✓ $description - Database accessible"
                return 0
            else
                TEST_RESULTS["$description"]="FAIL"
                TEST_DETAILS["$description"]="Database connection failed"
                log_error "✗ $description - Database connection failed"
                return 1
            fi
        else
            TEST_RESULTS["$description"]="SKIP"
            TEST_DETAILS["$description"]="DATABASE_URL not set"
            log_warning "⚠ $description - DATABASE_URL not set, skipping"
            return 0
        fi
    else
        TEST_RESULTS["$description"]="SKIP"
        TEST_DETAILS["$description"]="psql not available"
        log_warning "⚠ $description - psql not available, skipping"
        return 0
    fi
}

# Function to check Redis connectivity
check_redis() {
    local description="Redis Connectivity"
    
    log_info "Testing Redis connectivity: $description"
    
    if command -v redis-cli >/dev/null 2>&1; then
        if [ -n "${REDIS_URL:-}" ]; then
            if redis-cli -u "$REDIS_URL" ping >/dev/null 2>&1; then
                TEST_RESULTS["$description"]="PASS"
                TEST_DETAILS["$description"]="Redis accessible"
                log_success "✓ $description - Redis accessible"
                return 0
            else
                TEST_RESULTS["$description"]="FAIL"
                TEST_DETAILS["$description"]="Redis connection failed"
                log_error "✗ $description - Redis connection failed"
                return 1
            fi
        else
            TEST_RESULTS["$description"]="SKIP"
            TEST_DETAILS["$description"]="REDIS_URL not set"
            log_warning "⚠ $description - REDIS_URL not set, skipping"
            return 0
        fi
    else
        TEST_RESULTS["$description"]="SKIP"
        TEST_DETAILS["$description"]="redis-cli not available"
        log_warning "⚠ $description - redis-cli not available, skipping"
        return 0
    fi
}

# Function to run Python smoke tests
run_python_smoke_tests() {
    local description="Python Smoke Tests"
    
    log_info "Running Python smoke tests: $description"
    
    if [ -f "$SCRIPT_DIR/smoke_test.py" ]; then
        if python3 "$SCRIPT_DIR/smoke_test.py" --nocleanup > "$ARTIFACT_DIR/python_smoke.log" 2>&1; then
            TEST_RESULTS["$description"]="PASS"
            TEST_DETAILS["$description"]="Python smoke tests passed"
            log_success "✓ $description - Python smoke tests passed"
            return 0
        else
            TEST_RESULTS["$description"]="FAIL"
            TEST_DETAILS["$description"]="Python smoke tests failed"
            log_error "✗ $description - Python smoke tests failed"
            return 1
        fi
    else
        TEST_RESULTS["$description"]="SKIP"
        TEST_DETAILS["$description"]="smoke_test.py not found"
        log_warning "⚠ $description - smoke_test.py not found, skipping"
        return 0
    fi
}

# Generate test report
generate_report() {
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    local report_file="$ARTIFACT_DIR/smoke_test_report.json"
    
    echo "{" > "$report_file"
    echo "  \"timestamp\": \"$timestamp\"," >> "$report_file"
    echo "  \"script_version\": \"$SCRIPT_VERSION\"," >> "$report_file"
    echo "  \"target_host\": \"$STAGING_HOST\"," >> "$report_file"
    echo "  \"overall_status\": \"$(get_overall_status)\"," >> "$report_file"
    echo "  \"tests\": {" >> "$report_file"
    
    local first=true
    for test in "${!TEST_RESULTS[@]}"; do
        if [ "$first" = "true" ]; then
            first=false
        else
            echo "," >> "$report_file"
        fi
        echo "    \"$test\": {" >> "$report_file"
        echo "      \"status\": \"${TEST_RESULTS[$test]}\"," >> "$report_file"
        echo "      \"details\": \"${TEST_DETAILS[$test]}\"" >> "$report_file"
        echo -n "    }" >> "$report_file"
    done
    
    echo "" >> "$report_file"
    echo "  }" >> "$report_file"
    echo "}" >> "$report_file"
    
    log_info "Test report saved to: $report_file"
}

# Get overall status
get_overall_status() {
    local has_failures=false
    local has_warnings=false
    
    for status in "${TEST_RESULTS[@]}"; do
        case "$status" in
            "FAIL")
                has_failures=true
                ;;
            "WARN")
                has_warnings=true
                ;;
        esac
    done
    
    if [ "$has_failures" = "true" ]; then
        echo "FAIL"
    elif [ "$has_warnings" = "true" ]; then
        echo "WARN"
    else
        echo "PASS"
    fi
}

# Main smoke test function
run_smoke_tests() {
    log_info "Starting comprehensive smoke tests..."
    log_info "Target: $STAGING_HOST"
    log_info "Artifacts: $ARTIFACT_DIR"
    echo ""
    
    # 1. Basic HTTP endpoints
    log_info "=== HTTP Endpoints ==="
    check_http_endpoint "$STAGING_HOST/api/v1/health" "200" "Health Check" "$ARTIFACT_DIR/health.json"
    check_http_endpoint "$STAGING_HOST/metrics" "200" "Metrics Endpoint" "$ARTIFACT_DIR/metrics.txt"
    check_http_endpoint "$STAGING_HOST/docs" "200" "API Documentation" "$ARTIFACT_DIR/docs.html"
    
    # 2. Admin UI
    log_info "=== Admin UI ==="
    check_admin_ui
    
    # 3. Database connectivity
    log_info "=== Database ==="
    check_database
    
    # 4. Redis connectivity
    log_info "=== Redis ==="
    check_redis
    
    # 5. Python smoke tests
    log_info "=== Python Tests ==="
    run_python_smoke_tests
    
    log_info "Smoke tests completed"
}

# Help function
show_help() {
    cat << EOF
Usage: $SCRIPT_NAME [OPTIONS]

Consolidated smoke test script for CricAlgo.

OPTIONS:
    --host URL           Target host URL (default: $STAGING_HOST)
    --artifact-dir DIR   Artifact directory (default: $ARTIFACT_DIR)
    --timeout SECONDS    Request timeout (default: $TIMEOUT)
    --no-cleanup         Don't cleanup test data
    --verbose            Enable verbose logging
    --help               Show this help message

ENVIRONMENT VARIABLES:
    STAGING_HOST         Target host URL
    DATABASE_URL         Database connection string
    REDIS_URL            Redis connection string
    TIMEOUT              Request timeout
    VERBOSE              Enable verbose logging
    CLEANUP              Cleanup test data (default: true)

EXAMPLES:
    $SCRIPT_NAME
    $SCRIPT_NAME --host http://localhost:8000 --verbose
    $SCRIPT_NAME --artifact-dir /tmp/smoke_test --no-cleanup

EOF
}

# Main function
main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --host)
                STAGING_HOST="$2"
                shift 2
                ;;
            --artifact-dir)
                ARTIFACT_DIR="$2"
                shift 2
                ;;
            --timeout)
                TIMEOUT="$2"
                shift 2
                ;;
            --no-cleanup)
                CLEANUP="false"
                shift
                ;;
            --verbose)
                VERBOSE="true"
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Run smoke tests
    run_smoke_tests
    
    # Generate report
    generate_report
    
    # Print summary
    echo ""
    echo "============================================================================="
    echo "  Smoke Test Summary"
    echo "============================================================================="
    echo "Overall Status: $(get_overall_status)"
    echo "Artifacts: $ARTIFACT_DIR"
    echo "============================================================================="
    
    # Exit with appropriate code
    local overall_status=$(get_overall_status)
    case "$overall_status" in
        "PASS")
            exit 0
            ;;
        "WARN")
            exit 1
            ;;
        "FAIL")
            exit 2
            ;;
    esac
}

# Run main function
main "$@"
