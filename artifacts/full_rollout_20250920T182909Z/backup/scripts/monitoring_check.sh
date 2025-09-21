#!/bin/bash
set -euo pipefail

# Monitoring Check Script for CricAlgo
# Version: 2.0.0

readonly SCRIPT_VERSION="2.0.0"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
TIMEOUT="${TIMEOUT:-30}"

# Color codes
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

# Results
declare -A RESULTS

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check Prometheus
check_prometheus() {
    local response
    response=$(curl -s --max-time "$TIMEOUT" "$PROMETHEUS_URL/api/v1/status/config" 2>/dev/null) || {
        RESULTS["prometheus"]="FAIL"
        log_error "Prometheus: Connection failed"
        return 1
    }
    
    local status
    if command_exists "jq"; then
        status=$(echo "$response" | jq -r '.status // "unknown"' 2>/dev/null || echo "unknown")
    else
        status=$(echo "$response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4 2>/dev/null || echo "unknown")
    fi
    if [ "$status" = "success" ]; then
        RESULTS["prometheus"]="PASS"
        log_success "Prometheus: OK"
    else
        RESULTS["prometheus"]="FAIL"
        log_error "Prometheus: Status $status"
    fi
}

# Check Grafana
check_grafana() {
    local response
    response=$(curl -s --max-time "$TIMEOUT" "$GRAFANA_URL/api/health" 2>/dev/null) || {
        RESULTS["grafana"]="FAIL"
        log_error "Grafana: Connection failed"
        return 1
    }
    
    local status
    if command_exists "jq"; then
        status=$(echo "$response" | jq -r '.database // "unknown"' 2>/dev/null || echo "unknown")
    else
        status=$(echo "$response" | grep -o '"database":"[^"]*"' | cut -d'"' -f4 2>/dev/null || echo "unknown")
    fi
    if [ "$status" = "ok" ]; then
        RESULTS["grafana"]="PASS"
        log_success "Grafana: OK"
    else
        RESULTS["grafana"]="FAIL"
        log_error "Grafana: Status $status"
    fi
}

# Check application metrics
check_app_metrics() {
    local target="${1:-http://localhost:8000}"
    local response
    response=$(curl -s --max-time "$TIMEOUT" "$target/metrics" 2>/dev/null) || {
        RESULTS["app_metrics"]="FAIL"
        log_error "App metrics: Connection failed"
        return 1
    }
    
    local metric_count=$(echo "$response" | grep -c "^[^#]" 2>/dev/null || echo "0")
    if [ "$metric_count" -gt 10 ]; then
        RESULTS["app_metrics"]="PASS"
        log_success "App metrics: OK ($metric_count metrics)"
    else
        RESULTS["app_metrics"]="WARN"
        log_warning "App metrics: Limited ($metric_count metrics)"
    fi
}

# Generate report
generate_report() {
    echo "============================================================================="
    echo "  CricAlgo Monitoring Check Report"
    echo "============================================================================="
    echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "Script Version: $SCRIPT_VERSION"
    echo "============================================================================="
    echo ""
    
    for check in "${!RESULTS[@]}"; do
        local status="${RESULTS[$check]}"
        case "$status" in
            "PASS") echo -e "${GREEN}✓${NC} $check" ;;
            "WARN") echo -e "${YELLOW}⚠${NC} $check" ;;
            "FAIL") echo -e "${RED}✗${NC} $check" ;;
        esac
    done
    
    echo ""
    echo "============================================================================="
}

# Main function
main() {
    log_info "Starting monitoring checks..."
    
    check_prometheus
    check_grafana
    check_app_metrics
    
    generate_report
    
    # Exit code based on results
    local has_failures=false
    for status in "${RESULTS[@]}"; do
        if [ "$status" = "FAIL" ]; then
            has_failures=true
            break
        fi
    done
    
    if [ "$has_failures" = "true" ]; then
        exit 2
    else
        exit 0
    fi
}

main "$@"