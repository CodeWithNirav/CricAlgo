#!/bin/bash
# Comprehensive Health Check Script
# This script performs thorough health checks on the CricAlgo application

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE=${1:-prod}
STAGING_HOST=${2:-"https://api.cricalgo-staging.example.com"}
TIMEOUT=${3:-30}
VERBOSE=${4:-false}

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Health check results
HEALTH_CHECKS_PASSED=0
HEALTH_CHECKS_FAILED=0
TOTAL_CHECKS=0

# Function to run a health check
run_health_check() {
    local check_name="$1"
    local check_command="$2"
    local expected_result="$3"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    log_info "Running check: $check_name"
    
    if eval "$check_command" >/dev/null 2>&1; then
        if [ "$expected_result" = "success" ]; then
            log_success "✓ $check_name"
            HEALTH_CHECKS_PASSED=$((HEALTH_CHECKS_PASSED + 1))
            return 0
        else
            log_error "✗ $check_name (unexpected success)"
            HEALTH_CHECKS_FAILED=$((HEALTH_CHECKS_FAILED + 1))
            return 1
        fi
    else
        if [ "$expected_result" = "failure" ]; then
            log_success "✓ $check_name (expected failure)"
            HEALTH_CHECKS_PASSED=$((HEALTH_CHECKS_PASSED + 1))
            return 0
        else
            log_error "✗ $check_name"
            HEALTH_CHECKS_FAILED=$((HEALTH_CHECKS_FAILED + 1))
            return 1
        fi
    fi
}

# Function to check HTTP endpoint
check_http_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    local timeout="$3"
    
    local response
    response=$(curl -s -w "%{http_code}" -o /dev/null --max-time "$timeout" "$endpoint" 2>/dev/null || echo "000")
    
    if [ "$response" = "$expected_status" ]; then
        return 0
    else
        if [ "$VERBOSE" = "true" ]; then
            log_warning "HTTP check failed: $endpoint (expected: $expected_status, got: $response)"
        fi
        return 1
    fi
}

# Function to check Kubernetes resource
check_k8s_resource() {
    local resource_type="$1"
    local resource_name="$2"
    local namespace="$3"
    
    kubectl -n "$namespace" get "$resource_type" "$resource_name" >/dev/null 2>&1
}

# Function to check pod readiness
check_pod_readiness() {
    local app_label="$1"
    local namespace="$2"
    
    local ready_pods
    local total_pods
    
    ready_pods=$(kubectl -n "$namespace" get pods -l app="$app_label" --field-selector=status.phase=Running -o jsonpath='{.items[?(@.status.conditions[?(@.type=="Ready")].status=="True")].metadata.name}' | wc -w)
    total_pods=$(kubectl -n "$namespace" get pods -l app="$app_label" --field-selector=status.phase=Running -o jsonpath='{.items[*].metadata.name}' | wc -w)
    
    if [ "$total_pods" -gt 0 ] && [ "$ready_pods" -eq "$total_pods" ]; then
        return 0
    else
        if [ "$VERBOSE" = "true" ]; then
            log_warning "Pod readiness check failed: $ready_pods/$total_pods pods ready"
        fi
        return 1
    fi
}

# Function to check resource utilization
check_resource_utilization() {
    local namespace="$1"
    local resource_type="$2"
    local threshold="$3"
    
    local utilization
    utilization=$(kubectl -n "$namespace" top "$resource_type" --no-headers 2>/dev/null | awk '{sum+=$3} END {print sum/NR}' || echo "0")
    
    if (( $(echo "$utilization < $threshold" | bc -l) )); then
        return 0
    else
        if [ "$VERBOSE" = "true" ]; then
            log_warning "Resource utilization check failed: $resource_type utilization is $utilization% (threshold: $threshold%)"
        fi
        return 1
    fi
}

log_info "Starting comprehensive health check for namespace: $NAMESPACE"
log_info "Target endpoint: $STAGING_HOST"
log_info "Timeout: ${TIMEOUT}s"

# 1. Kubernetes Cluster Health
log_info "=== Kubernetes Cluster Health ==="

run_health_check "Kubernetes API server" "kubectl cluster-info" "success"
run_health_check "Namespace exists" "check_k8s_resource namespace $NAMESPACE $NAMESPACE" "success"

# 2. Application Pods Health
log_info "=== Application Pods Health ==="

run_health_check "App pods running" "check_pod_readiness cricalgo $NAMESPACE" "success"
run_health_check "Worker pods running" "check_pod_readiness worker $NAMESPACE" "success"

# 3. Services Health
log_info "=== Services Health ==="

run_health_check "App service exists" "check_k8s_resource service app $NAMESPACE" "success"
run_health_check "Worker service exists" "check_k8s_resource service worker $NAMESPACE" "success"

# 4. HTTP Endpoints Health
log_info "=== HTTP Endpoints Health ==="

run_health_check "Health endpoint" "check_http_endpoint $STAGING_HOST/api/v1/health 200 $TIMEOUT" "success"
run_health_check "Metrics endpoint" "check_http_endpoint $STAGING_HOST/metrics 200 $TIMEOUT" "success"

# 5. Database Health (if accessible)
log_info "=== Database Health ==="

run_health_check "Database connectivity" "kubectl -n $NAMESPACE exec -it \$(kubectl -n $NAMESPACE get pods -l app=cricalgo -o jsonpath='{.items[0].metadata.name}') -- python -c 'from app.db.session import engine; engine.connect().close()'" "success" || log_warning "Database health check skipped (not accessible)"

# 6. Redis Health (if accessible)
log_info "=== Redis Health ==="

run_health_check "Redis connectivity" "kubectl -n $NAMESPACE exec -it \$(kubectl -n $NAMESPACE get pods -l app=cricalgo -o jsonpath='{.items[0].metadata.name}') -- python -c 'from app.core.redis_client import redis_client; redis_client.ping()'" "success" || log_warning "Redis health check skipped (not accessible)"

# 7. Resource Utilization (if metrics-server is available)
log_info "=== Resource Utilization ==="

if kubectl top nodes >/dev/null 2>&1; then
    run_health_check "Node CPU utilization" "check_resource_utilization $NAMESPACE nodes 80" "success"
    run_health_check "Node memory utilization" "check_resource_utilization $NAMESPACE nodes 85" "success"
else
    log_warning "Metrics server not available - skipping resource utilization checks"
fi

# 8. Network Connectivity
log_info "=== Network Connectivity ==="

run_health_check "Internal service communication" "kubectl -n $NAMESPACE exec -it \$(kubectl -n $NAMESPACE get pods -l app=cricalgo -o jsonpath='{.items[0].metadata.name}') -- curl -s http://app:8000/api/v1/health" "success" || log_warning "Internal service communication check skipped"

# 9. Deployment Status
log_info "=== Deployment Status ==="

run_health_check "App deployment ready" "kubectl -n $NAMESPACE rollout status deployment/app --timeout=30s" "success"
run_health_check "Worker deployment ready" "kubectl -n $NAMESPACE rollout status deployment/worker --timeout=30s" "success"

# 10. ConfigMaps and Secrets
log_info "=== Configuration Health ==="

run_health_check "App configmap exists" "check_k8s_resource configmap app-config $NAMESPACE" "success"
run_health_check "App secrets exist" "check_k8s_resource secret app-secrets $NAMESPACE" "success"

# Summary
log_info "=== Health Check Summary ==="
log_info "Total checks: $TOTAL_CHECKS"
log_success "Passed: $HEALTH_CHECKS_PASSED"
if [ $HEALTH_CHECKS_FAILED -gt 0 ]; then
    log_error "Failed: $HEALTH_CHECKS_FAILED"
else
    log_success "Failed: $HEALTH_CHECKS_FAILED"
fi

# Calculate health score
HEALTH_SCORE=$((HEALTH_CHECKS_PASSED * 100 / TOTAL_CHECKS))
log_info "Health Score: $HEALTH_SCORE%"

# Generate health report
REPORT_FILE="artifacts/health_check_$(date -u +%Y%m%dT%H%M%SZ).json"
mkdir -p "$(dirname "$REPORT_FILE")"

cat > "$REPORT_FILE" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "namespace": "$NAMESPACE",
  "target_endpoint": "$STAGING_HOST",
  "total_checks": $TOTAL_CHECKS,
  "passed_checks": $HEALTH_CHECKS_PASSED,
  "failed_checks": $HEALTH_CHECKS_FAILED,
  "health_score": $HEALTH_SCORE,
  "status": "$([ $HEALTH_CHECKS_FAILED -eq 0 ] && echo "healthy" || echo "unhealthy")"
}
EOF

log_info "Health check report saved to: $REPORT_FILE"

# Exit with appropriate code
if [ $HEALTH_CHECKS_FAILED -eq 0 ]; then
    log_success "All health checks passed!"
    exit 0
else
    log_error "Some health checks failed!"
    exit 1
fi
