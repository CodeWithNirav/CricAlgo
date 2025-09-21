#!/bin/bash
set -euo pipefail

# =============================================================================
# Enhanced Health Check Script for CricAlgo
# =============================================================================
# 
# This script provides comprehensive health checks for:
# - Application endpoints
# - Database connectivity
# - Redis connectivity
# - Kubernetes resources
# - Load balancer status
# - Monitoring systems
#
# Author: CricAlgo DevOps Team
# Version: 2.0.0
# =============================================================================

readonly SCRIPT_VERSION="2.0.0"
readonly SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
STAGING_HOST="${STAGING_HOST:-http://localhost:8000}"
PROD_HOST="${PROD_HOST:-https://api.cricalgo.com}"
K8S_NS_PROD="${K8S_NS_PROD:-prod}"
K8S_NS_STAGING="${K8S_NS_STAGING:-cricalgo-staging}"
TIMEOUT="${TIMEOUT:-30}"
VERBOSE="${VERBOSE:-false}"
OUTPUT_FORMAT="${OUTPUT_FORMAT:-text}"  # text, json, yaml

# Color codes
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m'

# Health check results
declare -A HEALTH_RESULTS
declare -A HEALTH_DETAILS

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

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# HTTP health check
check_http_endpoint() {
    local url="$1"
    local name="$2"
    local expected_status="${3:-200}"
    
    log_info "Checking HTTP endpoint: $name ($url)"
    
    local response
    local status_code
    local response_time
    
    response=$(curl -s -w "\n%{http_code}\n%{time_total}" "$url" --max-time "$TIMEOUT" 2>/dev/null) || {
        HEALTH_RESULTS["$name"]="FAIL"
        HEALTH_DETAILS["$name"]="Connection failed"
        log_error "$name: Connection failed"
        return 1
    }
    
    status_code=$(echo "$response" | tail -n 2 | head -n 1)
    response_time=$(echo "$response" | tail -n 1)
    response_body=$(echo "$response" | head -n -2)
    
    if [ "$status_code" = "$expected_status" ]; then
        HEALTH_RESULTS["$name"]="PASS"
        HEALTH_DETAILS["$name"]="Status: $status_code, Time: ${response_time}s"
        log_success "$name: OK (${response_time}s)"
        return 0
    else
        HEALTH_RESULTS["$name"]="FAIL"
        HEALTH_DETAILS["$name"]="Expected status $expected_status, got $status_code"
        log_error "$name: Expected status $expected_status, got $status_code"
        return 1
    fi
}

# Database health check
check_database() {
    local name="$1"
    local connection_string="$2"
    
    log_info "Checking database: $name"
    
    if ! command_exists "psql"; then
        HEALTH_RESULTS["$name"]="SKIP"
        HEALTH_DETAILS["$name"]="psql not available"
        log_warning "$name: psql not available, skipping"
        return 0
    fi
    
    local query="SELECT 1 as health_check;"
    local result
    
    result=$(echo "$query" | psql "$connection_string" -t -A 2>/dev/null) || {
        HEALTH_RESULTS["$name"]="FAIL"
        HEALTH_DETAILS["$name"]="Connection failed"
        log_error "$name: Connection failed"
        return 1
    }
    
    if [ "$result" = "1" ]; then
        HEALTH_RESULTS["$name"]="PASS"
        HEALTH_DETAILS["$name"]="Connection successful"
        log_success "$name: OK"
        return 0
    else
        HEALTH_RESULTS["$name"]="FAIL"
        HEALTH_DETAILS["$name"]="Unexpected result: $result"
        log_error "$name: Unexpected result: $result"
        return 1
    fi
}

# Redis health check
check_redis() {
    local name="$1"
    local connection_string="$2"
    
    log_info "Checking Redis: $name"
    
    if ! command_exists "redis-cli"; then
        HEALTH_RESULTS["$name"]="SKIP"
        HEALTH_DETAILS["$name"]="redis-cli not available"
        log_warning "$name: redis-cli not available, skipping"
        return 0
    fi
    
    local result
    
    result=$(redis-cli -u "$connection_string" ping 2>/dev/null) || {
        HEALTH_RESULTS["$name"]="FAIL"
        HEALTH_DETAILS["$name"]="Connection failed"
        log_error "$name: Connection failed"
        return 1
    }
    
    if [ "$result" = "PONG" ]; then
        HEALTH_RESULTS["$name"]="PASS"
        HEALTH_DETAILS["$name"]="PONG received"
        log_success "$name: OK"
        return 0
    else
        HEALTH_RESULTS["$name"]="FAIL"
        HEALTH_DETAILS["$name"]="Unexpected response: $result"
        log_error "$name: Unexpected response: $result"
        return 1
    fi
}

# Kubernetes health check
check_kubernetes() {
    local namespace="$1"
    local resource_type="$2"
    local name="$3"
    
    log_info "Checking Kubernetes $resource_type: $name in namespace $namespace"
    
    if ! command_exists "kubectl"; then
        HEALTH_RESULTS["$name"]="SKIP"
        HEALTH_DETAILS["$name"]="kubectl not available"
        log_warning "$name: kubectl not available, skipping"
        return 0
    fi
    
    local status
    local ready_replicas
    local desired_replicas
    
    case "$resource_type" in
        "deployment")
            status=$(kubectl -n "$namespace" get deployment "$name" -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' 2>/dev/null || echo "Unknown")
            ready_replicas=$(kubectl -n "$namespace" get deployment "$name" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
            desired_replicas=$(kubectl -n "$namespace" get deployment "$name" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
            ;;
        "service")
            status=$(kubectl -n "$namespace" get service "$name" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
            ;;
        "pod")
            status=$(kubectl -n "$namespace" get pod "$name" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
            ;;
        *)
            HEALTH_RESULTS["$name"]="SKIP"
            HEALTH_DETAILS["$name"]="Unknown resource type: $resource_type"
            log_warning "$name: Unknown resource type: $resource_type"
            return 0
            ;;
    esac
    
    if [ "$status" = "True" ] || [ "$status" = "Running" ]; then
        if [ "$resource_type" = "deployment" ] && [ "$ready_replicas" -eq "$desired_replicas" ]; then
            HEALTH_RESULTS["$name"]="PASS"
            HEALTH_DETAILS["$name"]="Ready ($ready_replicas/$desired_replicas)"
            log_success "$name: OK ($ready_replicas/$desired_replicas)"
        elif [ "$resource_type" != "deployment" ]; then
            HEALTH_RESULTS["$name"]="PASS"
            HEALTH_DETAILS["$name"]="Status: $status"
            log_success "$name: OK"
        else
            HEALTH_RESULTS["$name"]="WARN"
            HEALTH_DETAILS["$name"]="Not all replicas ready ($ready_replicas/$desired_replicas)"
            log_warning "$name: Not all replicas ready ($ready_replicas/$desired_replicas)"
        fi
    else
        HEALTH_RESULTS["$name"]="FAIL"
        HEALTH_DETAILS["$name"]="Status: $status"
        log_error "$name: Status: $status"
    fi
}

# Load balancer health check
check_load_balancer() {
    local name="$1"
    local target="$2"
    
    log_info "Checking load balancer: $name"
    
    # Check if target is reachable
    if ! curl -s --max-time "$TIMEOUT" "$target/api/v1/health" >/dev/null 2>&1; then
        HEALTH_RESULTS["$name"]="FAIL"
        HEALTH_DETAILS["$name"]="Target not reachable"
        log_error "$name: Target not reachable"
        return 1
    fi
    
    # Check multiple endpoints to verify load balancing
    local endpoints=(
        "/api/v1/health"
        "/api/v1/health"
        "/api/v1/health"
    )
    
    local success_count=0
    local total_count=${#endpoints[@]}
    
    for endpoint in "${endpoints[@]}"; do
        if curl -s --max-time "$TIMEOUT" "$target$endpoint" >/dev/null 2>&1; then
            ((success_count++))
        fi
    done
    
    local success_rate=$((success_count * 100 / total_count))
    
    if [ "$success_rate" -ge 90 ]; then
        HEALTH_RESULTS["$name"]="PASS"
        HEALTH_DETAILS["$name"]="Success rate: ${success_rate}%"
        log_success "$name: OK (${success_rate}%)"
    else
        HEALTH_RESULTS["$name"]="WARN"
        HEALTH_DETAILS["$name"]="Success rate: ${success_rate}%"
        log_warning "$name: Success rate: ${success_rate}%"
    fi
}

# Generate output in different formats
generate_output() {
    case "$OUTPUT_FORMAT" in
        "json")
            generate_json_output
            ;;
        "yaml")
            generate_yaml_output
            ;;
        *)
            generate_text_output
            ;;
    esac
}

# Generate JSON output
generate_json_output() {
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    
    echo "{"
    echo "  \"timestamp\": \"$timestamp\","
    echo "  \"script_version\": \"$SCRIPT_VERSION\","
    echo "  \"overall_status\": \"$(get_overall_status)\","
    echo "  \"checks\": {"
    
    local first=true
    for check in "${!HEALTH_RESULTS[@]}"; do
        if [ "$first" = "true" ]; then
            first=false
        else
            echo ","
        fi
        echo "    \"$check\": {"
        echo "      \"status\": \"${HEALTH_RESULTS[$check]}\","
        echo "      \"details\": \"${HEALTH_DETAILS[$check]}\""
        echo -n "    }"
    done
    
    echo ""
    echo "  }"
    echo "}"
}

# Generate YAML output
generate_yaml_output() {
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    
    echo "timestamp: $timestamp"
    echo "script_version: $SCRIPT_VERSION"
    echo "overall_status: $(get_overall_status)"
    echo "checks:"
    
    for check in "${!HEALTH_RESULTS[@]}"; do
        echo "  $check:"
        echo "    status: ${HEALTH_RESULTS[$check]}"
        echo "    details: ${HEALTH_DETAILS[$check]}"
    done
}

# Generate text output
generate_text_output() {
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    
    echo "============================================================================="
    echo "  CricAlgo Health Check Report"
    echo "============================================================================="
    echo "Timestamp: $timestamp"
    echo "Script Version: $SCRIPT_VERSION"
    echo "Overall Status: $(get_overall_status)"
    echo "============================================================================="
    echo ""
    
    for check in "${!HEALTH_RESULTS[@]}"; do
        local status="${HEALTH_RESULTS[$check]}"
        local details="${HEALTH_DETAILS[$check]}"
        
        case "$status" in
            "PASS")
                echo -e "${GREEN}✓${NC} $check: $details"
                ;;
            "WARN")
                echo -e "${YELLOW}⚠${NC} $check: $details"
                ;;
            "FAIL")
                echo -e "${RED}✗${NC} $check: $details"
                ;;
            "SKIP")
                echo -e "${BLUE}⊘${NC} $check: $details"
                ;;
        esac
    done
    
    echo ""
    echo "============================================================================="
}

# Get overall status
get_overall_status() {
    local has_failures=false
    local has_warnings=false
    
    for status in "${HEALTH_RESULTS[@]}"; do
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

# Main health check function
run_health_checks() {
    log_info "Starting comprehensive health checks..."
    
    # Application health checks
    check_http_endpoint "$STAGING_HOST/api/v1/health" "staging_health" "200"
    check_http_endpoint "$PROD_HOST/api/v1/health" "prod_health" "200"
    
    # Database health checks
    if [ -n "${DATABASE_URL:-}" ]; then
        check_database "database" "$DATABASE_URL"
    fi
    
    # Redis health checks
    if [ -n "${REDIS_URL:-}" ]; then
        check_redis "redis" "$REDIS_URL"
    fi
    
    # Kubernetes health checks
    if command_exists "kubectl"; then
        check_kubernetes "$K8S_NS_PROD" "deployment" "app"
        check_kubernetes "$K8S_NS_PROD" "deployment" "worker"
        check_kubernetes "$K8S_NS_PROD" "service" "app"
        check_kubernetes "$K8S_NS_STAGING" "deployment" "app"
    fi
    
    # Load balancer health checks
    check_load_balancer "staging_lb" "$STAGING_HOST"
    check_load_balancer "prod_lb" "$PROD_HOST"
    
    log_info "Health checks completed"
}

# Help function
show_help() {
    cat << EOF
Usage: $SCRIPT_NAME [OPTIONS]

Enhanced health check script for CricAlgo.

OPTIONS:
    --staging-host URL    Staging environment URL (default: $STAGING_HOST)
    --prod-host URL       Production environment URL (default: $PROD_HOST)
    --namespace NS        Kubernetes namespace (default: $K8S_NS_PROD)
    --timeout SECONDS     Request timeout in seconds (default: $TIMEOUT)
    --format FORMAT       Output format: text|json|yaml (default: $OUTPUT_FORMAT)
    --verbose             Enable verbose logging
    --help                Show this help message

ENVIRONMENT VARIABLES:
    STAGING_HOST          Staging environment URL
    PROD_HOST             Production environment URL
    K8S_NS_PROD           Production namespace
    K8S_NS_STAGING        Staging namespace
    DATABASE_URL           Database connection string
    REDIS_URL              Redis connection string
    TIMEOUT                Request timeout
    OUTPUT_FORMAT          Output format
    VERBOSE                Enable verbose logging

EXAMPLES:
    $SCRIPT_NAME
    $SCRIPT_NAME --format json
    $SCRIPT_NAME --staging-host http://localhost:8000 --verbose
    $SCRIPT_NAME --prod-host https://api.cricalgo.com --format yaml

EOF
}

# Main function
main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --staging-host)
                STAGING_HOST="$2"
                shift 2
                ;;
            --prod-host)
                PROD_HOST="$2"
                shift 2
                ;;
            --namespace)
                K8S_NS_PROD="$2"
                shift 2
                ;;
            --timeout)
                TIMEOUT="$2"
                shift 2
                ;;
            --format)
                OUTPUT_FORMAT="$2"
                shift 2
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
    
    # Run health checks
    run_health_checks
    
    # Generate output
    generate_output
    
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
