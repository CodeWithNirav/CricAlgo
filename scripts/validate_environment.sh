#!/bin/bash
set -euo pipefail

# Environment Validation Script for CricAlgo Automation
# Version: 2.0.0

readonly SCRIPT_VERSION="2.0.0"
readonly SCRIPT_NAME="$(basename "$0")"

# Color codes
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

# Validation results
declare -A VALIDATION_RESULTS
declare -A VALIDATION_DETAILS

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Validate required tools
validate_required_tools() {
    local tools=("git" "curl")
    local all_passed=true
    
    for tool in "${tools[@]}"; do
        if command_exists "$tool"; then
            VALIDATION_RESULTS["tool_$tool"]="PASS"
            VALIDATION_DETAILS["tool_$tool"]="Available"
            log_success "Tool $tool: Available"
        else
            VALIDATION_RESULTS["tool_$tool"]="FAIL"
            VALIDATION_DETAILS["tool_$tool"]="Not found"
            log_error "Tool $tool: Not found"
            all_passed=false
        fi
    done
    
    # Check jq separately as it's optional for basic functionality
    if command_exists "jq"; then
        VALIDATION_RESULTS["tool_jq"]="PASS"
        VALIDATION_DETAILS["tool_jq"]="Available"
        log_success "Tool jq: Available"
    else
        VALIDATION_RESULTS["tool_jq"]="WARN"
        VALIDATION_DETAILS["tool_jq"]="Not found (some JSON parsing will be limited)"
        log_warning "Tool jq: Not found (some JSON parsing will be limited)"
    fi
    
    return $([ "$all_passed" = "true" ] && echo 0 || echo 1)
}

# Validate optional tools
validate_optional_tools() {
    local tools=("kubectl" "k6" "gh" "pandoc" "psql" "redis-cli")
    
    for tool in "${tools[@]}"; do
        if command_exists "$tool"; then
            VALIDATION_RESULTS["tool_$tool"]="PASS"
            VALIDATION_DETAILS["tool_$tool"]="Available"
            log_success "Tool $tool: Available"
        else
            VALIDATION_RESULTS["tool_$tool"]="WARN"
            VALIDATION_DETAILS["tool_$tool"]="Not found (optional)"
            log_warning "Tool $tool: Not found (optional)"
        fi
    done
}

# Validate environment variables
validate_environment_variables() {
    local required_vars=("GITHUB_TOKEN")
    local optional_vars=("STAGING_HOST" "PROD_HOST" "DATABASE_URL" "REDIS_URL" "K8S_NS_PROD" "K8S_NS_STAGING" "CANARY_STRATEGY")
    
    # Check required variables
    for var in "${required_vars[@]}"; do
        if [ -n "${!var:-}" ]; then
            VALIDATION_RESULTS["env_$var"]="PASS"
            VALIDATION_DETAILS["env_$var"]="Set"
            log_success "Environment $var: Set"
        else
            VALIDATION_RESULTS["env_$var"]="FAIL"
            VALIDATION_DETAILS["env_$var"]="Not set"
            log_error "Environment $var: Not set"
        fi
    done
    
    # Check optional variables
    for var in "${optional_vars[@]}"; do
        if [ -n "${!var:-}" ]; then
            VALIDATION_RESULTS["env_$var"]="PASS"
            VALIDATION_DETAILS["env_$var"]="Set"
            log_success "Environment $var: Set"
        else
            VALIDATION_RESULTS["env_$var"]="WARN"
            VALIDATION_DETAILS["env_$var"]="Not set (using default)"
            log_warning "Environment $var: Not set (using default)"
        fi
    done
}

# Validate git repository
validate_git_repository() {
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
        VALIDATION_RESULTS["git_repo"]="FAIL"
        VALIDATION_DETAILS["git_repo"]="Not a git repository"
        log_error "Git: Not a git repository"
        return 1
    fi
    
    VALIDATION_RESULTS["git_repo"]="PASS"
    VALIDATION_DETAILS["git_repo"]="Valid git repository"
    log_success "Git: Valid repository"
    
    # Check if working tree is clean
    if git diff --quiet && git diff --cached --quiet; then
        VALIDATION_RESULTS["git_clean"]="PASS"
        VALIDATION_DETAILS["git_clean"]="Working tree is clean"
        log_success "Git: Working tree is clean"
    else
        VALIDATION_RESULTS["git_clean"]="WARN"
        VALIDATION_DETAILS["git_clean"]="Working tree has uncommitted changes"
        log_warning "Git: Working tree has uncommitted changes"
    fi
    
    # Check remote
    if git remote get-url origin >/dev/null 2>&1; then
        VALIDATION_RESULTS["git_remote"]="PASS"
        VALIDATION_DETAILS["git_remote"]="Origin remote configured"
        log_success "Git: Origin remote configured"
    else
        VALIDATION_RESULTS["git_remote"]="FAIL"
        VALIDATION_DETAILS["git_remote"]="No origin remote"
        log_error "Git: No origin remote"
    fi
}

# Validate Kubernetes connectivity
validate_kubernetes() {
    if ! command_exists "kubectl"; then
        VALIDATION_RESULTS["k8s_available"]="SKIP"
        VALIDATION_DETAILS["k8s_available"]="kubectl not available"
        log_warning "Kubernetes: kubectl not available, skipping"
        return 0
    fi
    
    if kubectl cluster-info >/dev/null 2>&1; then
        VALIDATION_RESULTS["k8s_available"]="PASS"
        VALIDATION_DETAILS["k8s_available"]="Cluster accessible"
        log_success "Kubernetes: Cluster accessible"
        
        # Check namespaces
        local prod_ns="${K8S_NS_PROD:-prod}"
        local staging_ns="${K8S_NS_STAGING:-cricalgo-staging}"
        
        if kubectl get namespace "$prod_ns" >/dev/null 2>&1; then
            VALIDATION_RESULTS["k8s_prod_ns"]="PASS"
            VALIDATION_DETAILS["k8s_prod_ns"]="Production namespace exists"
            log_success "Kubernetes: Production namespace exists"
        else
            VALIDATION_RESULTS["k8s_prod_ns"]="WARN"
            VALIDATION_DETAILS["k8s_prod_ns"]="Production namespace not found"
            log_warning "Kubernetes: Production namespace not found"
        fi
        
        if kubectl get namespace "$staging_ns" >/dev/null 2>&1; then
            VALIDATION_RESULTS["k8s_staging_ns"]="PASS"
            VALIDATION_DETAILS["k8s_staging_ns"]="Staging namespace exists"
            log_success "Kubernetes: Staging namespace exists"
        else
            VALIDATION_RESULTS["k8s_staging_ns"]="WARN"
            VALIDATION_DETAILS["k8s_staging_ns"]="Staging namespace not found"
            log_warning "Kubernetes: Staging namespace not found"
        fi
    else
        VALIDATION_RESULTS["k8s_available"]="FAIL"
        VALIDATION_DETAILS["k8s_available"]="Cluster not accessible"
        log_error "Kubernetes: Cluster not accessible"
    fi
}

# Validate manifest files
validate_manifests() {
    local canary_strategy="${CANARY_STRATEGY:-istio}"
    local manifest_dir="k8s/$canary_strategy"
    
    if [ ! -d "$manifest_dir" ]; then
        VALIDATION_RESULTS["manifests_dir"]="FAIL"
        VALIDATION_DETAILS["manifests_dir"]="Manifest directory not found: $manifest_dir"
        log_error "Manifests: Directory not found: $manifest_dir"
        return 1
    fi
    
    VALIDATION_RESULTS["manifests_dir"]="PASS"
    VALIDATION_DETAILS["manifests_dir"]="Manifest directory exists"
    log_success "Manifests: Directory exists"
    
    # Check for required manifest files
    local required_files=("canary-10.yaml" "canary-25.yaml" "canary-50.yaml" "canary-100.yaml")
    local all_files_exist=true
    
    for file in "${required_files[@]}"; do
        if [ -f "$manifest_dir/$file" ]; then
            VALIDATION_RESULTS["manifest_$file"]="PASS"
            VALIDATION_DETAILS["manifest_$file"]="File exists"
            log_success "Manifest $file: Exists"
        else
            VALIDATION_RESULTS["manifest_$file"]="WARN"
            VALIDATION_DETAILS["manifest_$file"]="File not found"
            log_warning "Manifest $file: Not found"
            all_files_exist=false
        fi
    done
    
    return $([ "$all_files_exist" = "true" ] && echo 0 || echo 1)
}

# Generate validation report
generate_report() {
    echo "============================================================================="
    echo "  CricAlgo Environment Validation Report"
    echo "============================================================================="
    echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "Script Version: $SCRIPT_VERSION"
    echo "============================================================================="
    echo ""
    
    local has_failures=false
    local has_warnings=false
    
    for check in "${!VALIDATION_RESULTS[@]}"; do
        local status="${VALIDATION_RESULTS[$check]}"
        local details="${VALIDATION_DETAILS[$check]}"
        
        case "$status" in
            "PASS")
                echo -e "${GREEN}✓${NC} $check: $details"
                ;;
            "WARN")
                echo -e "${YELLOW}⚠${NC} $check: $details"
                has_warnings=true
                ;;
            "FAIL")
                echo -e "${RED}✗${NC} $check: $details"
                has_failures=true
                ;;
            "SKIP")
                echo -e "${BLUE}⊘${NC} $check: $details"
                ;;
        esac
    done
    
    echo ""
    echo "============================================================================="
    
    if [ "$has_failures" = "true" ]; then
        echo "Overall Status: FAIL"
        return 2
    elif [ "$has_warnings" = "true" ]; then
        echo "Overall Status: WARN"
        return 1
    else
        echo "Overall Status: PASS"
        return 0
    fi
}

# Main validation function
main() {
    log_info "Starting environment validation..."
    
    validate_required_tools
    validate_optional_tools
    validate_environment_variables
    validate_git_repository
    validate_kubernetes
    validate_manifests
    
    log_info "Environment validation completed"
    
    generate_report
}

# Run main function
main "$@"
