#!/bin/bash
set -euo pipefail

# =============================================================================
# CricAlgo Full Rollout Automation - Enhanced Version
# =============================================================================
# 
# This script provides comprehensive automation for:
# - PR Creation and CI validation
# - Canary deployment with progressive rollout
# - Automated testing and validation
# - Release creation and artifact management
# - Comprehensive rollback capabilities
#
# Author: CricAlgo DevOps Team
# Version: 2.0.0
# =============================================================================

# -------------------------
# Configuration & Defaults
# -------------------------
readonly SCRIPT_VERSION="2.0.0"
readonly SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Timestamp for unique artifact directories
readonly TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
readonly ARTIFACT_DIR="artifacts/full_rollout_${TIMESTAMP}"

# Branch and PR configuration
BRANCH="${BRANCH:-perf/full-rollout-$(git rev-parse --short=8 HEAD)-${TIMESTAMP}}"
PR_TITLE="${PR_TITLE:-perf: full rollout — webhook quick-return + instrumentation + nginx LB + HPA + alerts}"
PR_BODY_FILE="${PR_BODY_FILE:-.github/PR_BODY.md}"
PR_BASE="${PR_BASE:-main}"
PR_REVIEWERS="${PR_REVIEWERS:-backend-lead,devops}"
PR_LABELS="${PR_LABELS:-perf,staging-tested,infrastructure}"

# Release configuration
RELEASE_TAG="${RELEASE_TAG:-v1.0.0}"
GITHUB_REPO="${GITHUB_REPO:-CodeWithNirav/CricAlgo}"

# Deployment configuration
CANARY_STRATEGY="${CANARY_STRATEGY:-istio}"  # istio or nginx
CANARY_WEIGHTS=(10 25 50 100)
K8S_NS_PROD="${K8S_NS_PROD:-prod}"
K8S_NS_STAGING="${K8S_NS_STAGING:-cricalgo-staging}"

# Testing configuration
SMOKE_VUS="${SMOKE_VUS:-20}"
SMOKE_DURATION="${SMOKE_DURATION:-60s}"
LONG_K6_VUS="${LONG_K6_VUS:-100}"
LONG_K6_DURATION="${LONG_K6_DURATION:-5m}"
TIMEOUT_CI="${TIMEOUT_CI:-1800}"  # 30 minutes

# Safety and operational flags
DRY_RUN="${DRY_RUN:-false}"
APPLY_K8S="${APPLY_K8S:-false}"
OPEN_PR="${OPEN_PR:-true}"
SKIP_CI_WAIT="${SKIP_CI_WAIT:-false}"
FORCE_PROMOTION="${FORCE_PROMOTION:-false}"

# Target hosts
STAGING_HOST="${STAGING_HOST:-http://localhost:8000}"
PROD_HOST="${PROD_HOST:-https://api.cricalgo.com}"

# -------------------------
# Logging and Output
# -------------------------
mkdir -p "$ARTIFACT_DIR"
readonly LOG_FILE="$ARTIFACT_DIR/automation.log"
exec > >(tee -a "$LOG_FILE") 2>&1

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date -u +%Y-%m-%dT%H:%M:%SZ) $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date -u +%Y-%m-%dT%H:%M:%SZ) $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date -u +%Y-%m-%dT%H:%M:%SZ) $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date -u +%Y-%m-%dT%H:%M:%SZ) $1" | tee -a "$LOG_FILE"
}

log_debug() {
    if [ "${DEBUG:-false}" = "true" ]; then
        echo -e "${PURPLE}[DEBUG]${NC} $(date -u +%Y-%m-%dT%H:%M:%SZ) $1" | tee -a "$LOG_FILE"
    fi
}

# Banner function
print_banner() {
    echo -e "${CYAN}"
    echo "============================================================================="
    echo "  CricAlgo Full Rollout Automation v${SCRIPT_VERSION}"
    echo "============================================================================="
    echo -e "${NC}"
    echo "Branch: $BRANCH"
    echo "Strategy: $CANARY_STRATEGY"
    echo "Dry Run: $DRY_RUN"
    echo "Apply K8s: $APPLY_K8S"
    echo "Artifacts: $ARTIFACT_DIR"
    echo "============================================================================="
}

# -------------------------
# Utility Functions
# -------------------------

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if we're in a git repository
is_git_repo() {
    git rev-parse --git-dir >/dev/null 2>&1
}

# Get current git branch
get_current_branch() {
    git branch --show-current 2>/dev/null || echo "unknown"
}

# Get current git commit hash
get_current_commit() {
    git rev-parse --short=8 HEAD 2>/dev/null || echo "unknown"
}

# Check if working tree is clean
is_working_tree_clean() {
    git diff --quiet && git diff --cached --quiet
}

# Validate environment variables
validate_environment() {
    local errors=0
    
    log_info "Validating environment..."
    
    # Check required tools
    local required_tools=("git" "curl")
    for tool in "${required_tools[@]}"; do
        if ! command_exists "$tool"; then
            log_error "Required tool '$tool' not found"
            ((errors++))
        fi
    done
    
    # Check jq separately as it's optional for basic functionality
    if ! command_exists "jq"; then
        log_warning "jq not found - some JSON parsing will be limited"
    fi
    
    # Check optional tools
    local optional_tools=("kubectl" "k6" "gh" "pandoc")
    for tool in "${optional_tools[@]}"; do
        if command_exists "$tool"; then
            log_debug "Optional tool '$tool' found"
        else
            log_warning "Optional tool '$tool' not found"
        fi
    done
    
    # Check environment variables
    if [ "$DRY_RUN" != "true" ] && [ -z "${GITHUB_TOKEN:-}" ]; then
        log_error "GITHUB_TOKEN is required when DRY_RUN=false"
        ((errors++))
    fi
    
    if [ "$APPLY_K8S" = "true" ] && ! command_exists "kubectl"; then
        log_error "kubectl is required when APPLY_K8S=true"
        ((errors++))
    fi
    
    # Validate canary strategy
    if [[ ! "$CANARY_STRATEGY" =~ ^(istio|nginx)$ ]]; then
        log_error "CANARY_STRATEGY must be 'istio' or 'nginx', got: $CANARY_STRATEGY"
        ((errors++))
    fi
    
    # Validate canary weights
    for weight in "${CANARY_WEIGHTS[@]}"; do
        if ! [[ "$weight" =~ ^[0-9]+$ ]] || [ "$weight" -lt 0 ] || [ "$weight" -gt 100 ]; then
            log_error "Invalid canary weight: $weight (must be 0-100)"
            ((errors++))
        fi
    done
    
    if [ $errors -gt 0 ]; then
        log_error "Environment validation failed with $errors errors"
        return 1
    fi
    
    log_success "Environment validation passed"
    return 0
}

# Pre-flight checks
preflight_checks() {
    log_info "Running pre-flight checks..."
    
    # Check if we're in a git repository
    if ! is_git_repo; then
        log_error "Not in a git repository"
        return 1
    fi
    
    # Check if working tree is clean
    if ! is_working_tree_clean; then
        log_error "Working tree is not clean. Please commit or stash changes."
        git status --porcelain
        return 1
    fi
    
    # Check if we're on the correct branch
    local current_branch=$(get_current_branch)
    if [ "$current_branch" != "$PR_BASE" ]; then
        log_warning "Not on $PR_BASE branch (current: $current_branch). Switching..."
        git checkout "$PR_BASE" || {
            log_error "Failed to checkout $PR_BASE branch"
            return 1
        }
    fi
    
    # Check if branch already exists
    if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
        log_error "Branch '$BRANCH' already exists"
        return 1
    fi
    
    # Check if remote exists
    if ! git remote get-url origin >/dev/null 2>&1; then
        log_error "No remote 'origin' configured"
        return 1
    fi
    
    # Check if PR body file exists
    if [ ! -f "$PR_BODY_FILE" ]; then
        log_error "PR body file not found: $PR_BODY_FILE"
        return 1
    fi
    
    # Check if k8s manifests exist
    if [ "$APPLY_K8S" = "true" ]; then
        local manifest_dir="k8s/$CANARY_STRATEGY"
        if [ ! -d "$manifest_dir" ]; then
            log_error "K8s manifest directory not found: $manifest_dir"
            return 1
        fi
        
        # Check for required manifest files
        local required_manifests=("canary-10.yaml" "canary-25.yaml" "canary-50.yaml" "canary-100.yaml")
        for manifest in "${required_manifests[@]}"; do
            if [ ! -f "$manifest_dir/$manifest" ]; then
                log_warning "K8s manifest not found: $manifest_dir/$manifest"
            fi
        done
    fi
    
    log_success "Pre-flight checks passed"
    return 0
}

# Create backup of important files
create_backup() {
    log_info "Creating backup of important files..."
    
    local backup_dir="$ARTIFACT_DIR/backup"
    mkdir -p "$backup_dir"
    
    # Backup k8s manifests
    if [ -d "k8s" ]; then
        cp -r k8s "$backup_dir/" || log_warning "Failed to backup k8s directory"
    fi
    
    # Backup docker-compose files
    for file in docker-compose*.yml; do
        if [ -f "$file" ]; then
            cp "$file" "$backup_dir/" || log_warning "Failed to backup $file"
        fi
    done
    
    # Backup scripts
    if [ -d "scripts" ]; then
        cp -r scripts "$backup_dir/" || log_warning "Failed to backup scripts directory"
    fi
    
    log_success "Backup created in $backup_dir"
}

# -------------------------
# Git Operations
# -------------------------

# Create and push branch
create_branch() {
    log_info "Creating feature branch: $BRANCH"
    
    # Create branch from current HEAD
    git checkout -b "$BRANCH" || {
        log_error "Failed to create branch $BRANCH"
        return 1
    }
    
    # Add all changes
    git add -A || {
        log_warning "Some files could not be added to git"
    }
    
    # Commit changes
    git commit -m "chore(perf): prepare full rollout automation artifacts

- Branch: $BRANCH
- Strategy: $CANARY_STRATEGY
- Timestamp: $TIMESTAMP
- Script Version: $SCRIPT_VERSION" || {
        log_warning "No changes to commit"
    }
    
    # Push branch
    git push -u origin "$BRANCH" || {
        log_error "Failed to push branch $BRANCH"
        return 1
    }
    
    log_success "Branch $BRANCH created and pushed"
}

# -------------------------
# PR Operations
# -------------------------

# Create PR
create_pr() {
    log_info "Creating pull request..."
    
    if [ "$DRY_RUN" = "true" ]; then
        log_info "DRY RUN: Would create PR with title: $PR_TITLE"
        echo "$PR_TITLE" > "$ARTIFACT_DIR/pr_intent.txt"
        return 0
    fi
    
    local pr_url=""
    
    if command_exists "gh" && [ "$OPEN_PR" = "true" ]; then
        # Use GitHub CLI
        pr_url=$(gh pr create \
            --title "$PR_TITLE" \
            --body-file "$PR_BODY_FILE" \
            --base "$PR_BASE" \
            --head "$BRANCH" \
            --label $(echo "$PR_LABELS" | sed 's/,/ --label /g') \
            --reviewer $(echo "$PR_REVIEWERS" | sed 's/,/ --reviewer /g') \
            --repo "$GITHUB_REPO" 2>/dev/null) || {
            log_error "Failed to create PR using GitHub CLI"
            return 1
        }
    else
        # Use GitHub API
        local body_content
        body_content=$(cat "$PR_BODY_FILE" | sed 's/"/\\"/g' | awk '{printf "%s\\n", $0}')
        
        local api_payload
        if command_exists "jq"; then
            api_payload=$(jq -n \
                --arg title "$PR_TITLE" \
                --arg head "$BRANCH" \
                --arg base "$PR_BASE" \
                --arg body "$body_content" \
                --argjson labels "$(echo "$PR_LABELS" | tr ',' '\n' | jq -R . | jq -s .)" \
                '{
                    title: $title,
                    head: $head,
                    base: $base,
                    body: $body,
                    labels: $labels
                }')
        else
            # Fallback without jq
            api_payload="{\"title\":\"$PR_TITLE\",\"head\":\"$BRANCH\",\"base\":\"$PR_BASE\",\"body\":\"$body_content\"}"
        fi
        
        local response
        response=$(curl -s -X POST \
            -H "Authorization: token $GITHUB_TOKEN" \
            -H "Accept: application/vnd.github+json" \
            "https://api.github.com/repos/$GITHUB_REPO/pulls" \
            -d "$api_payload") || {
            log_error "Failed to create PR using GitHub API"
            return 1
        }
        
        pr_url=$(echo "$response" | jq -r '.html_url // empty')
        echo "$response" > "$ARTIFACT_DIR/pr_create.json"
        
        if [ -z "$pr_url" ] || [ "$pr_url" = "null" ]; then
            log_error "Failed to extract PR URL from API response"
            echo "$response" | jq '.' > "$ARTIFACT_DIR/pr_error.json"
            return 1
        fi
    fi
    
    log_success "PR created: $pr_url"
    echo "$pr_url" > "$ARTIFACT_DIR/pr_info.txt"
    echo "$pr_url"
}

# Wait for CI
wait_for_ci() {
    local pr_url="$1"
    local timeout="${2:-$TIMEOUT_CI}"
    
    if [ "$SKIP_CI_WAIT" = "true" ]; then
        log_info "Skipping CI wait (SKIP_CI_WAIT=true)"
        return 0
    fi
    
    log_info "Waiting for CI to pass (timeout: ${timeout}s)..."
    
    local start_time=$(date +%s)
    local ci_passed=false
    local pr_num=""
    
    # Extract PR number from URL
    if [[ "$pr_url" =~ /pull/([0-9]+) ]]; then
        pr_num="${BASH_REMATCH[1]}"
    fi
    
    while true; do
        local checks_status=""
        
        if command_exists "gh" && [ -n "$pr_num" ]; then
            # Use GitHub CLI
            checks_status=$(gh pr checks "$pr_num" --repo "$GITHUB_REPO" --json conclusion -q '.[0].conclusion' 2>/dev/null || echo "")
        else
            # Use GitHub API
            local sha=$(git rev-parse HEAD)
            local state
            if command_exists "jq"; then
                state=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
                    "https://api.github.com/repos/$GITHUB_REPO/commits/$sha/status" \
                    | jq -r '.state // "unknown"' 2>/dev/null || echo "unknown")
            else
                state=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
                    "https://api.github.com/repos/$GITHUB_REPO/commits/$sha/status" \
                    | grep -o '"state":"[^"]*"' | cut -d'"' -f4 2>/dev/null || echo "unknown")
            fi
            
            if [ "$state" = "success" ]; then
                checks_status="SUCCESS"
            elif [ "$state" = "failure" ]; then
                checks_status="FAILURE"
            elif [ "$state" = "pending" ]; then
                checks_status="PENDING"
            fi
        fi
        
        if [ "$checks_status" = "SUCCESS" ] || [ "$checks_status" = "COMPLETED" ]; then
            ci_passed=true
            break
        elif [ "$checks_status" = "FAILURE" ]; then
            log_error "CI checks failed"
            break
        fi
        
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        if [ $elapsed -ge $timeout ]; then
            log_warning "CI wait timed out after ${timeout}s"
            break
        fi
        
        log_info "CI status: $checks_status (elapsed: ${elapsed}s)"
        sleep 10
    done
    
    echo "$ci_passed" > "$ARTIFACT_DIR/ci_status.txt"
    
    if [ "$ci_passed" = "true" ]; then
        log_success "CI checks passed"
        return 0
    else
        log_warning "CI checks did not pass or timed out"
        return 1
    fi
}

# -------------------------
# Canary Deployment
# -------------------------

# Apply canary configuration
apply_canary() {
    local weight="$1"
    local strategy="$2"
    
    log_info "Applying canary configuration: $weight% traffic using $strategy"
    
    if [ "$DRY_RUN" = "true" ]; then
        log_info "DRY RUN: Would apply $strategy canary with $weight% traffic"
        return 0
    fi
    
    if [ "$APPLY_K8S" != "true" ]; then
        log_info "Skipping K8s canary (APPLY_K8S=false)"
        return 0
    fi
    
    case "$strategy" in
        "istio")
            apply_istio_canary "$weight"
            ;;
        "nginx")
            apply_nginx_canary "$weight"
            ;;
        *)
            log_error "Unknown canary strategy: $strategy"
            return 1
            ;;
    esac
}

# Apply Istio canary configuration
apply_istio_canary() {
    local weight="$1"
    local stable_weight=$((100 - weight))
    
    log_info "Applying Istio canary: $weight% canary, $stable_weight% stable"
    
    # Check if template exists
    local template_file="k8s/istio/virtualservice-canary-template.yaml"
    if [ -f "$template_file" ]; then
        # Use template with weight substitution
        sed "s/WEIGHT_PLACEHOLDER/$weight/g; s/WEIGHT_STABLE_PLACEHOLDER/$stable_weight/g; s/WEIGHT_CANARY_PLACEHOLDER/$weight/g" \
            "$template_file" | kubectl -n "$K8S_NS_PROD" apply -f - || {
            log_error "Failed to apply Istio canary template"
            return 1
        }
    else
        # Use pre-configured files
        local manifest_file="k8s/istio/virtualservice-canary-${weight}.yaml"
        if [ -f "$manifest_file" ]; then
            kubectl -n "$K8S_NS_PROD" apply -f "$manifest_file" || {
                log_error "Failed to apply Istio canary manifest: $manifest_file"
                return 1
            }
        else
            log_error "Istio canary manifest not found: $manifest_file"
            return 1
        fi
    fi
    
    # Wait for canary deployment to be ready
    log_info "Waiting for canary deployment to be ready..."
    kubectl -n "$K8S_NS_PROD" rollout status deploy/app-canary --timeout=180s || {
        log_warning "Canary deployment may not be ready"
    }
    
    log_success "Istio canary applied: $weight% traffic"
}

# Apply Nginx canary configuration
apply_nginx_canary() {
    local weight="$1"
    
    log_info "Applying Nginx canary: $weight% traffic"
    
    local manifest_file="k8s/nginx/upstream-canary-${weight}.yaml"
    if [ -f "$manifest_file" ]; then
        kubectl -n "$K8S_NS_PROD" apply -f "$manifest_file" || {
            log_error "Failed to apply Nginx canary manifest: $manifest_file"
            return 1
        }
    else
        log_error "Nginx canary manifest not found: $manifest_file"
        return 1
    fi
    
    log_success "Nginx canary applied: $weight% traffic"
}

# Rollback canary
rollback_canary() {
    local strategy="$1"
    
    log_info "Rolling back canary deployment using $strategy"
    
    if [ "$DRY_RUN" = "true" ]; then
        log_info "DRY RUN: Would rollback canary deployment"
        return 0
    fi
    
    if [ "$APPLY_K8S" != "true" ]; then
        log_info "Skipping K8s rollback (APPLY_K8S=false)"
        return 0
    fi
    
    case "$strategy" in
        "istio")
            kubectl -n "$K8S_NS_PROD" delete -f k8s/istio/virtualservice-canary-10.yaml 2>/dev/null || true
            ;;
        "nginx")
            kubectl -n "$K8S_NS_PROD" apply -f k8s/nginx/upstream-canary-0.yaml 2>/dev/null || true
            ;;
    esac
    
    log_success "Canary rollback completed"
}

# -------------------------
# Testing Functions
# -------------------------

# Run k6 test
run_k6_test() {
    local vus="$1"
    local duration="$2"
    local script="$3"
    local output_file="$4"
    local target="${5:-$STAGING_HOST}"
    
    log_info "Running k6 test: VUs=$vus, duration=$duration, target=$target"
    
    # Set environment variables for k6
    export STAGING_HOST="$target"
    
    if command_exists "k6"; then
        k6 run --vus "$vus" --duration "$duration" "$script" \
            --summary-export="${output_file%.txt}.json" \
            --out json="${output_file%.txt}_raw.json" | tee "$output_file"
    else
        log_info "k6 not found, using Docker fallback"
        docker run --rm -i \
            -v "$(pwd)":/scripts \
            -w /scripts \
            -e STAGING_HOST="$target" \
            loadimpact/k6 run \
            --vus "$vus" \
            --duration "$duration" \
            "/scripts/$script" | tee "$output_file"
    fi
}

# Run smoke test
run_smoke_test() {
    local target="$1"
    local output_dir="$2"
    
    log_info "Running smoke test against $target"
    
    mkdir -p "$output_dir"
    
    # Health check
    log_info "Testing health endpoint..."
    curl -sS "$target/api/v1/health" -o "$output_dir/health.json" || {
        log_warning "Health check failed"
    }
    
    # Run k6 smoke test
    run_k6_test "$SMOKE_VUS" "$SMOKE_DURATION" "load/k6/webhook_test.js" \
        "$output_dir/k6_smoke.txt" "$target"
    
    # Check for errors in k6 output
    if grep -qi "error" "$output_dir/k6_smoke.txt" >/dev/null 2>&1; then
        log_error "Smoke test detected errors"
        return 1
    fi
    
    log_success "Smoke test passed"
    return 0
}

# -------------------------
# Release Operations
# -------------------------

# Merge PR and create release
merge_and_release() {
    local pr_url="$1"
    
    if [ "$DRY_RUN" = "true" ]; then
        log_info "DRY RUN: Would merge PR and create release"
        return 0
    fi
    
    log_info "Merging PR and creating release..."
    
    # Merge branch
    git checkout "$PR_BASE" || {
        log_error "Failed to checkout $PR_BASE branch"
        return 1
    }
    
    git pull origin "$PR_BASE" || {
        log_error "Failed to pull latest $PR_BASE"
        return 1
    }
    
    git merge --no-ff "$BRANCH" -m "merge: perf rollout $(date -u)

- Branch: $BRANCH
- Strategy: $CANARY_STRATEGY
- Timestamp: $TIMESTAMP" || {
        log_error "Failed to merge branch $BRANCH"
        return 1
    }
    
    git push origin "$PR_BASE" || {
        log_error "Failed to push merged changes"
        return 1
    }
    
    # Create release tag
    log_info "Creating release tag: $RELEASE_TAG"
    git tag -a "$RELEASE_TAG" -m "Release $RELEASE_TAG - performance rollout

- Branch: $BRANCH
- Strategy: $CANARY_STRATEGY
- Timestamp: $TIMESTAMP
- Script Version: $SCRIPT_VERSION"
    
    git push origin "$RELEASE_TAG" || {
        log_error "Failed to push release tag"
        return 1
    }
    
    # Create GitHub release
    create_github_release
    
    log_success "Release $RELEASE_TAG created"
}

# Create GitHub release
create_github_release() {
    log_info "Creating GitHub release: $RELEASE_TAG"
    
    local release_notes="Performance rollout release

## Changes
- Webhook quick-return optimization
- Enhanced instrumentation and monitoring
- Nginx load balancing configuration
- Horizontal Pod Autoscaling (HPA)
- Comprehensive alerting rules

## Deployment Details
- Branch: $BRANCH
- Strategy: $CANARY_STRATEGY
- Timestamp: $TIMESTAMP
- Script Version: $SCRIPT_VERSION

## Artifacts
See attached automation artifacts for detailed logs and metrics.

## Rollback
If issues are detected, use the rollback scripts in the artifacts directory."
    
    if command_exists "gh"; then
        gh release create "$RELEASE_TAG" \
            --title "$RELEASE_TAG" \
            --notes "$release_notes" \
            --repo "$GITHUB_REPO" || {
            log_error "Failed to create GitHub release using CLI"
            return 1
        }
    else
        # Use GitHub API
        local api_payload
        if command_exists "jq"; then
            api_payload=$(jq -n \
                --arg tag_name "$RELEASE_TAG" \
                --arg name "$RELEASE_TAG" \
                --arg body "$release_notes" \
                '{
                    tag_name: $tag_name,
                    name: $name,
                    body: $body,
                    draft: false,
                    prerelease: false
                }')
        else
            # Fallback without jq
            api_payload="{\"tag_name\":\"$RELEASE_TAG\",\"name\":\"$RELEASE_TAG\",\"body\":\"$release_notes\",\"draft\":false,\"prerelease\":false}"
        fi
        
        curl -s -X POST \
            -H "Authorization: token $GITHUB_TOKEN" \
            -H "Accept: application/vnd.github+json" \
            "https://api.github.com/repos/$GITHUB_REPO/releases" \
            -d "$api_payload" > "$ARTIFACT_DIR/release_create.json" || {
            log_error "Failed to create GitHub release using API"
            return 1
        }
    fi
    
    log_success "GitHub release created"
}

# -------------------------
# Artifact Collection
# -------------------------

# Collect final artifacts
collect_artifacts() {
    log_info "Collecting final artifacts..."
    
    # System information
    {
        echo "=== System Information ==="
        echo "OS: $(uname -a)"
        echo "Date: $(date -u)"
        echo "User: $(whoami)"
        echo "Working Directory: $(pwd)"
        echo ""
        echo "=== Git Information ==="
        echo "Branch: $(get_current_branch)"
        echo "Commit: $(get_current_commit)"
        echo "Remote: $(git remote get-url origin 2>/dev/null || echo 'N/A')"
        echo ""
        echo "=== Environment Variables ==="
        env | grep -E '^(GITHUB_|STAGING_|PROD_|K8S_|CANARY_|SMOKE_|LONG_K6_|TIMEOUT_|DRY_RUN|APPLY_K8S|OPEN_PR)' | sort
    } > "$ARTIFACT_DIR/system_info.txt"
    
    # Kubernetes information (if available)
    if command_exists "kubectl" && [ "$APPLY_K8S" = "true" ]; then
        {
            echo "=== Kubernetes Information ==="
            echo "Context: $(kubectl config current-context 2>/dev/null || echo 'N/A')"
            echo "Namespace: $K8S_NS_PROD"
            echo ""
            echo "=== Pods ==="
            kubectl -n "$K8S_NS_PROD" get pods -o wide 2>/dev/null || echo "Failed to get pods"
            echo ""
            echo "=== Services ==="
            kubectl -n "$K8S_NS_PROD" get services 2>/dev/null || echo "Failed to get services"
            echo ""
            echo "=== Deployments ==="
            kubectl -n "$K8S_NS_PROD" get deployments 2>/dev/null || echo "Failed to get deployments"
        } > "$ARTIFACT_DIR/k8s_info.txt"
        
        # Application logs
        kubectl -n "$K8S_NS_PROD" logs -l app=cricalgo --tail=500 > "$ARTIFACT_DIR/app_logs.txt" 2>/dev/null || true
    fi
    
    # Database information (if available)
    if [ -n "${DATABASE_URL:-}" ] && command_exists "psql"; then
        {
            echo "=== Database Information ==="
            echo "Connection Count:"
            echo "SELECT count(*) FROM pg_stat_activity;" | psql "$DATABASE_URL" 2>/dev/null || echo "Failed to query database"
        } > "$ARTIFACT_DIR/db_info.txt"
    fi
    
    # Create final status JSON
    cat > "$ARTIFACT_DIR/final_status.json" <<EOF
{
  "script_version": "$SCRIPT_VERSION",
  "timestamp": "$TIMESTAMP",
  "branch": "$BRANCH",
  "pr_url": "$PR_URL",
  "release_tag": "$RELEASE_TAG",
  "canary_strategy": "$CANARY_STRATEGY",
  "dry_run": "$DRY_RUN",
  "apply_k8s": "$APPLY_K8S",
  "artifact_directory": "$ARTIFACT_DIR",
  "success": true
}
EOF
    
    # Create runbook PDF if pandoc is available
    local runbook_md="docs/runbook_prod_rollout.md"
    if [ -f "$runbook_md" ]; then
        if command_exists "pandoc"; then
            pandoc "$runbook_md" -o "$ARTIFACT_DIR/runbook_prod_rollout.pdf" || {
                log_warning "Failed to create PDF runbook"
            }
        else
            cp "$runbook_md" "$ARTIFACT_DIR/runbook_prod_rollout.md"
        fi
    fi
    
    # Create tarball
    log_info "Creating artifact tarball..."
    tar -czf "$ARTIFACT_DIR.tar.gz" -C "$(dirname "$ARTIFACT_DIR")" "$(basename "$ARTIFACT_DIR")" || {
        log_warning "Failed to create tarball"
    }
    
    log_success "Artifacts collected in $ARTIFACT_DIR"
}

# -------------------------
# Main Execution
# -------------------------

# Main function
main() {
    print_banner
    
    # Validate environment
    if ! validate_environment; then
        log_error "Environment validation failed"
        exit 1
    fi
    
    # Run pre-flight checks
    if ! preflight_checks; then
        log_error "Pre-flight checks failed"
        exit 1
    fi
    
    # Create backup
    create_backup
    
    # Create branch
    if ! create_branch; then
        log_error "Failed to create branch"
        exit 1
    fi
    
    # Create PR
    PR_URL=$(create_pr) || {
        log_error "Failed to create PR"
        exit 1
    }
    
    # Wait for CI
    if ! wait_for_ci "$PR_URL"; then
        if [ "$FORCE_PROMOTION" != "true" ]; then
            log_error "CI checks failed and FORCE_PROMOTION is not enabled"
            exit 1
        else
            log_warning "Proceeding despite CI failure (FORCE_PROMOTION=true)"
        fi
    fi
    
    # Safety confirmation for production changes
    if [ "$DRY_RUN" != "true" ]; then
        log_warning "**** PRODUCTION SAFETY PROMPT ****"
        log_warning "This will modify production traffic. Type 'I ACCEPT' to proceed:"
        read -r confirmation
        if [ "$confirmation" != "I ACCEPT" ]; then
            log_error "User did not accept. Aborting."
            exit 1
        fi
    fi
    
    # Progressive canary deployment
    local canary_success=true
    
    for weight in "${CANARY_WEIGHTS[@]}"; do
        log_info "=== Canary Deployment: $weight% ==="
        
        # Apply canary configuration
        if ! apply_canary "$weight" "$CANARY_STRATEGY"; then
            log_error "Failed to apply canary configuration for $weight%"
            canary_success=false
            break
        fi
        
        # Wait for deployment to stabilize
        log_info "Waiting for deployment to stabilize..."
        sleep 30
        
        # Run smoke test
        local target="$STAGING_HOST"
        if [ "$CANARY_STRATEGY" = "istio" ] && [ "$APPLY_K8S" = "true" ]; then
            target="$PROD_HOST"
        fi
        
        local smoke_dir="$ARTIFACT_DIR/smoke_${weight}"
        if ! run_smoke_test "$target" "$smoke_dir"; then
            log_error "Smoke test failed at $weight% canary"
            rollback_canary "$CANARY_STRATEGY"
            canary_success=false
            break
        fi
        
        log_success "Canary deployment successful at $weight%"
    done
    
    if [ "$canary_success" = "false" ]; then
        log_error "Canary deployment failed. Check artifacts for details."
        exit 1
    fi
    
    # Merge and create release
    if ! merge_and_release "$PR_URL"; then
        log_error "Failed to merge and create release"
        exit 1
    fi
    
    # Collect final artifacts
    collect_artifacts
    
    log_success "=== Full rollout automation completed successfully ==="
    log_info "Artifacts: $ARTIFACT_DIR"
    log_info "Tarball: $ARTIFACT_DIR.tar.gz"
    log_info "Final status: $ARTIFACT_DIR/final_status.json"
}

# -------------------------
# Script Entry Point
# -------------------------

# Handle script arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="true"
            shift
            ;;
        --apply-k8s)
            APPLY_K8S="true"
            shift
            ;;
        --skip-ci)
            SKIP_CI_WAIT="true"
            shift
            ;;
        --force)
            FORCE_PROMOTION="true"
            shift
            ;;
        --debug)
            DEBUG="true"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run      Run without making production changes"
            echo "  --apply-k8s    Apply Kubernetes configurations"
            echo "  --skip-ci      Skip waiting for CI checks"
            echo "  --force        Force promotion despite CI failures"
            echo "  --debug        Enable debug logging"
            echo "  --help         Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  GITHUB_TOKEN   GitHub token for API access"
            echo "  STAGING_HOST   Staging environment URL"
            echo "  PROD_HOST      Production environment URL"
            echo "  CANARY_STRATEGY Canary strategy (istio|nginx)"
            echo "  DRY_RUN        Enable dry run mode"
            echo "  APPLY_K8S      Apply Kubernetes configurations"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run main function
main "$@"
