#!/bin/bash
# Preflight Checklist Script
# Run this before executing the full rollout automation

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_check() {
    echo -e "${BLUE}[CHECK]${NC} $1"
}

# Check results
CHECKS_PASSED=0
CHECKS_FAILED=0
TOTAL_CHECKS=0

# Function to run a check
run_check() {
    local check_name="$1"
    local check_command="$2"
    local required="$3"  # "required" or "optional"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    log_check "$check_name"
    
    if eval "$check_command" >/dev/null 2>&1; then
        log_success "$check_name"
        CHECKS_PASSED=$((CHECKS_PASSED + 1))
        return 0
    else
        if [ "$required" = "required" ]; then
            log_error "$check_name (REQUIRED)"
            CHECKS_FAILED=$((CHECKS_FAILED + 1))
            return 1
        else
            log_warning "$check_name (optional)"
            return 1
        fi
    fi
}

log_info "🚀 CricAlgo Rollout Preflight Checklist"
log_info "======================================"

echo
log_info "Checking environment and prerequisites..."

# 1. Environment Variables
log_info "=== Environment Variables ==="

run_check "GITHUB_TOKEN is set" "[ -n \"\${GITHUB_TOKEN:-}\" ]" "required"
run_check "STAGING_HOST is set" "[ -n \"\${STAGING_HOST:-}\" ]" "required"
run_check "KUBECONFIG is set" "[ -n \"\${KUBECONFIG:-}\" ] || [ -f ~/.kube/config ]" "required"

# Optional environment variables
run_check "DATABASE_URL is set" "[ -n \"\${DATABASE_URL:-}\" ]" "optional"
run_check "REDIS_URL is set" "[ -n \"\${REDIS_URL:-}\" ]" "optional"
run_check "PROM_HOST is set" "[ -n \"\${PROM_HOST:-}\" ]" "optional"

# 2. Required Tools
log_info "=== Required Tools ==="

run_check "kubectl is installed" "command -v kubectl" "required"
run_check "curl is installed" "command -v curl" "required"
run_check "jq is installed" "command -v jq" "required"
run_check "git is installed" "command -v git" "required"

# Optional tools
run_check "k6 is installed" "command -v k6" "optional"
run_check "gh CLI is installed" "command -v gh" "optional"
run_check "pandoc is installed" "command -v pandoc" "optional"

# 3. Kubernetes Access
log_info "=== Kubernetes Access ==="

run_check "kubectl can connect to cluster" "kubectl cluster-info" "required"
run_check "kubectl can list namespaces" "kubectl get namespaces" "required"
run_check "kubectl can access prod namespace" "kubectl -n prod get pods" "required"

# 4. GitHub Access
log_info "=== GitHub Access ==="

run_check "GitHub token is valid" "curl -s -H \"Authorization: token \$GITHUB_TOKEN\" https://api.github.com/user | jq -r .login" "required"
run_check "GitHub token has repo access" "curl -s -H \"Authorization: token \$GITHUB_TOKEN\" https://api.github.com/repos/CodeWithNirav/CricAlgo | jq -r .name" "required"

# 5. Application Health
log_info "=== Application Health ==="

if [ -n "${STAGING_HOST:-}" ]; then
    run_check "Staging host is reachable" "curl -s --max-time 10 \$STAGING_HOST/api/v1/health" "required"
    run_check "Health endpoint returns 200" "curl -s -w '%{http_code}' -o /dev/null \$STAGING_HOST/api/v1/health | grep -q 200" "required"
else
    log_warning "STAGING_HOST not set - skipping application health checks"
fi

# 6. Monitoring Systems
log_info "=== Monitoring Systems ==="

if [ -n "${PROM_HOST:-}" ]; then
    run_check "Prometheus is reachable" "curl -s --max-time 10 \$PROM_HOST/-/healthy" "optional"
    run_check "Prometheus targets are healthy" "curl -s --max-time 10 \$PROM_HOST/api/v1/targets | jq -r '.data.activeTargets[] | select(.health != \"up\")' | wc -l | grep -q 0" "optional"
else
    log_warning "PROM_HOST not set - skipping monitoring checks"
fi

# 7. File System Checks
log_info "=== File System Checks ==="

run_check "Automation script exists" "[ -f scripts/full_rollout_automation.sh ]" "required"
run_check "PR body template exists" "[ -f .github/PR_BODY.md ]" "required"
run_check "Istio configs exist" "[ -f k8s/istio/virtualservice-canary-10.yaml ]" "required"
run_check "Nginx configs exist" "[ -f k8s/nginx/upstream-canary-10.yaml ]" "required"
run_check "Load test script exists" "[ -f load/k6/webhook_test.js ]" "required"

# 8. Git Status
log_info "=== Git Status ==="

run_check "Git repository is clean" "git status --porcelain | wc -l | grep -q 0" "required"
run_check "Git remote is configured" "git remote -v | grep -q origin" "required"
run_check "Git branch is main" "git branch --show-current | grep -q main" "required"

# 9. Disk Space
log_info "=== Disk Space ==="

run_check "Sufficient disk space (>1GB)" "[ \$(df . | awk 'NR==2 {print \$4}') -gt 1048576 ]" "required"

# 10. Network Connectivity
log_info "=== Network Connectivity ==="

run_check "Can reach GitHub API" "curl -s --max-time 10 https://api.github.com" "required"
run_check "Can reach Kubernetes API" "kubectl get nodes" "required"

# Summary
echo
log_info "=== Preflight Check Summary ==="
log_info "Total checks: $TOTAL_CHECKS"
log_success "Passed: $CHECKS_PASSED"
if [ $CHECKS_FAILED -gt 0 ]; then
    log_error "Failed: $CHECKS_FAILED"
else
    log_success "Failed: $CHECKS_FAILED"
fi

# Calculate success rate
SUCCESS_RATE=$((CHECKS_PASSED * 100 / TOTAL_CHECKS))
log_info "Success rate: $SUCCESS_RATE%"

# Generate preflight report
REPORT_FILE="artifacts/preflight_check_$(date -u +%Y%m%dT%H%M%SZ).json"
mkdir -p "$(dirname "$REPORT_FILE")"

cat > "$REPORT_FILE" <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "total_checks": $TOTAL_CHECKS,
  "passed_checks": $CHECKS_PASSED,
  "failed_checks": $CHECKS_FAILED,
  "success_rate": $SUCCESS_RATE,
  "status": "$([ $CHECKS_FAILED -eq 0 ] && echo "ready" || echo "not_ready")",
  "environment": {
    "github_token_set": $([ -n "${GITHUB_TOKEN:-}" ] && echo "true" || echo "false"),
    "staging_host_set": $([ -n "${STAGING_HOST:-}" ] && echo "true" || echo "false"),
    "kubeconfig_set": $([ -n "${KUBECONFIG:-}" ] || [ -f ~/.kube/config ] && echo "true" || echo "false")
  }
}
EOF

log_info "Preflight report saved to: $REPORT_FILE"

# Final recommendation
echo
if [ $CHECKS_FAILED -eq 0 ]; then
    log_success "🎉 All preflight checks passed! You're ready to run the automation."
    log_info "Next steps:"
    echo "1. Review the preflight report: $REPORT_FILE"
    echo "2. Run: ./scripts/full_rollout_automation.sh"
    echo "3. Or run dry-run first: DRY_RUN=true ./scripts/full_rollout_automation.sh"
    exit 0
else
    log_error "❌ Some preflight checks failed. Please fix the issues before running the automation."
    log_info "Review the failed checks above and:"
    echo "1. Fix any required checks that failed"
    echo "2. Consider if optional checks are needed for your environment"
    echo "3. Re-run this preflight check: ./scripts/preflight_check.sh"
    exit 1
fi
