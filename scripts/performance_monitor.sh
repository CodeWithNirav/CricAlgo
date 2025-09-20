#!/bin/bash
# Performance Monitoring Script
# This script monitors key performance metrics during canary deployments

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
MONITORING_DURATION=${3:-300}  # 5 minutes default
PROMETHEUS_URL=${4:-"http://prometheus.monitoring.svc.cluster.local:9090"}

# Performance thresholds
P95_LATENCY_THRESHOLD=2000  # 2 seconds
P99_LATENCY_THRESHOLD=5000  # 5 seconds
ERROR_RATE_THRESHOLD=0.005  # 0.5%
CPU_THRESHOLD=80            # 80%
MEMORY_THRESHOLD=85         # 85%

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

# Performance metrics
declare -A METRICS
METRICS[P95_LATENCY]=0
METRICS[P99_LATENCY]=0
METRICS[ERROR_RATE]=0
METRICS[CPU_USAGE]=0
METRICS[MEMORY_USAGE]=0
METRICS[THROUGHPUT]=0

# Function to get Prometheus metric
get_prometheus_metric() {
    local query="$1"
    local result
    result=$(curl -s "$PROMETHEUS_URL/api/v1/query" --data-urlencode "query=$query" | jq -r '.data.result[0].value[1]' 2>/dev/null || echo "null")
    echo "$result"
}

# Function to get current metrics
get_current_metrics() {
    log_info "Collecting current performance metrics..."
    
    # Get latency metrics
    METRICS[P95_LATENCY]=$(get_prometheus_metric "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))")
    METRICS[P99_LATENCY]=$(get_prometheus_metric "histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))")
    
    # Get error rate
    local total_requests
    local error_requests
    total_requests=$(get_prometheus_metric "sum(rate(http_requests_total[5m]))")
    error_requests=$(get_prometheus_metric "sum(rate(http_requests_total{status=~\"5..\"}[5m]))")
    
    if [ "$total_requests" != "null" ] && [ "$total_requests" != "0" ]; then
        METRICS[ERROR_RATE]=$(echo "scale=4; $error_requests / $total_requests" | bc -l)
    else
        METRICS[ERROR_RATE]=0
    fi
    
    # Get resource usage
    METRICS[CPU_USAGE]=$(get_prometheus_metric "avg(rate(container_cpu_usage_seconds_total[5m])) * 100")
    METRICS[MEMORY_USAGE]=$(get_prometheus_metric "avg(container_memory_usage_bytes / container_spec_memory_limit_bytes) * 100")
    
    # Get throughput
    METRICS[THROUGHPUT]=$(get_prometheus_metric "sum(rate(http_requests_total[1m]))")
}

# Function to check if metrics are within thresholds
check_metrics() {
    local all_good=true
    
    log_info "Checking performance thresholds..."
    
    # Check P95 latency
    if (( $(echo "${METRICS[P95_LATENCY]} > $P95_LATENCY_THRESHOLD" | bc -l) )); then
        log_error "P95 latency exceeds threshold: ${METRICS[P95_LATENCY]}ms > ${P95_LATENCY_THRESHOLD}ms"
        all_good=false
    else
        log_success "P95 latency OK: ${METRICS[P95_LATENCY]}ms"
    fi
    
    # Check P99 latency
    if (( $(echo "${METRICS[P99_LATENCY]} > $P99_LATENCY_THRESHOLD" | bc -l) )); then
        log_error "P99 latency exceeds threshold: ${METRICS[P99_LATENCY]}ms > ${P99_LATENCY_THRESHOLD}ms"
        all_good=false
    else
        log_success "P99 latency OK: ${METRICS[P99_LATENCY]}ms"
    fi
    
    # Check error rate
    if (( $(echo "${METRICS[ERROR_RATE]} > $ERROR_RATE_THRESHOLD" | bc -l) )); then
        log_error "Error rate exceeds threshold: $(echo "${METRICS[ERROR_RATE]} * 100" | bc -l)% > $(echo "$ERROR_RATE_THRESHOLD * 100" | bc -l)%"
        all_good=false
    else
        log_success "Error rate OK: $(echo "${METRICS[ERROR_RATE]} * 100" | bc -l)%"
    fi
    
    # Check CPU usage
    if (( $(echo "${METRICS[CPU_USAGE]} > $CPU_THRESHOLD" | bc -l) )); then
        log_warning "CPU usage exceeds threshold: ${METRICS[CPU_USAGE]}% > ${CPU_THRESHOLD}%"
        all_good=false
    else
        log_success "CPU usage OK: ${METRICS[CPU_USAGE]}%"
    fi
    
    # Check memory usage
    if (( $(echo "${METRICS[MEMORY_USAGE]} > $MEMORY_THRESHOLD" | bc -l) )); then
        log_warning "Memory usage exceeds threshold: ${METRICS[MEMORY_USAGE]}% > ${MEMORY_THRESHOLD}%"
        all_good=false
    else
        log_success "Memory usage OK: ${METRICS[MEMORY_USAGE]}%"
    fi
    
    return $([ "$all_good" = true ] && echo 0 || echo 1)
}

# Function to run load test
run_load_test() {
    local duration="$1"
    local vus="$2"
    
    log_info "Running load test for ${duration}s with ${vus} VUs..."
    
    if command -v k6 >/dev/null 2>&1; then
        k6 run --vus "$vus" --duration "${duration}s" load/k6/webhook_test.js --summary-export="artifacts/performance_test_$(date -u +%Y%m%dT%H%M%SZ).json"
    else
        docker run -i --rm -v "$(pwd)":/scripts -w /scripts loadimpact/k6 run --vus "$vus" --duration "${duration}s" /scripts/load/k6/webhook_test.js
    fi
}

# Function to generate performance report
generate_report() {
    local report_file="artifacts/performance_report_$(date -u +%Y%m%dT%H%M%SZ).json"
    mkdir -p "$(dirname "$report_file")"
    
    cat > "$report_file" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "namespace": "$NAMESPACE",
  "target_endpoint": "$STAGING_HOST",
  "monitoring_duration": $MONITORING_DURATION,
  "metrics": {
    "p95_latency_ms": ${METRICS[P95_LATENCY]},
    "p99_latency_ms": ${METRICS[P99_LATENCY]},
    "error_rate": ${METRICS[ERROR_RATE]},
    "cpu_usage_percent": ${METRICS[CPU_USAGE]},
    "memory_usage_percent": ${METRICS[MEMORY_USAGE]},
    "throughput_rps": ${METRICS[THROUGHPUT]}
  },
  "thresholds": {
    "p95_latency_ms": $P95_LATENCY_THRESHOLD,
    "p99_latency_ms": $P99_LATENCY_THRESHOLD,
    "error_rate": $ERROR_RATE_THRESHOLD,
    "cpu_usage_percent": $CPU_THRESHOLD,
    "memory_usage_percent": $MEMORY_THRESHOLD
  },
  "status": "$([ $? -eq 0 ] && echo "healthy" || echo "unhealthy")"
}
EOF
    
    log_info "Performance report saved to: $report_file"
}

# Main monitoring loop
log_info "Starting performance monitoring for $MONITORING_DURATION seconds..."
log_info "Target endpoint: $STAGING_HOST"
log_info "Prometheus URL: $PROMETHEUS_URL"

# Initial metrics collection
get_current_metrics

# Display initial metrics
log_info "=== Initial Performance Metrics ==="
log_info "P95 Latency: ${METRICS[P95_LATENCY]}ms"
log_info "P99 Latency: ${METRICS[P99_LATENCY]}ms"
log_info "Error Rate: $(echo "${METRICS[ERROR_RATE]} * 100" | bc -l)%"
log_info "CPU Usage: ${METRICS[CPU_USAGE]}%"
log_info "Memory Usage: ${METRICS[MEMORY_USAGE]}%"
log_info "Throughput: ${METRICS[THROUGHPUT]} RPS"

# Check initial metrics
if ! check_metrics; then
    log_error "Initial metrics check failed!"
    generate_report
    exit 1
fi

# Monitoring loop
START_TIME=$(date +%s)
END_TIME=$((START_TIME + MONITORING_DURATION))
CHECK_INTERVAL=30

while [ $(date +%s) -lt $END_TIME ]; do
    sleep $CHECK_INTERVAL
    
    log_info "Collecting metrics at $(date -u +%Y-%m-%dT%H:%M:%SZ)..."
    get_current_metrics
    
    if ! check_metrics; then
        log_error "Performance metrics check failed during monitoring!"
        generate_report
        exit 1
    fi
    
    # Display current metrics
    log_info "Current metrics - P95: ${METRICS[P95_LATENCY]}ms, P99: ${METRICS[P99_LATENCY]}ms, Error Rate: $(echo "${METRICS[ERROR_RATE]} * 100" | bc -l)%, CPU: ${METRICS[CPU_USAGE]}%, Memory: ${METRICS[MEMORY_USAGE]}%"
done

# Final metrics collection
log_info "Final metrics collection..."
get_current_metrics

# Final check
if check_metrics; then
    log_success "Performance monitoring completed successfully!"
    generate_report
    exit 0
else
    log_error "Performance monitoring failed final check!"
    generate_report
    exit 1
fi
