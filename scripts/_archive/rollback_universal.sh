#!/bin/bash
set -euo pipefail

# =============================================================================
# Universal Rollback Script for CricAlgo
# =============================================================================
# 
# This script provides comprehensive rollback capabilities for:
# - Istio canary deployments
# - Nginx canary deployments
# - Kubernetes resource cleanup
# - Database rollbacks (if applicable)
#
# Author: CricAlgo DevOps Team
# Version: 2.0.0
# =============================================================================

readonly SCRIPT_VERSION="2.0.0"
readonly SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
K8S_NS_PROD="${K8S_NS_PROD:-prod}"
K8S_NS_STAGING="${K8S_NS_STAGING:-cricalgo-staging}"
CANARY_STRATEGY="${CANARY_STRATEGY:-istio}"
DRY_RUN="${DRY_RUN:-false}"
FORCE="${FORCE:-false}"

# Color codes
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date -u +%Y-%m-%dT%H:%M:%SZ) $1"
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

# Help function
show_help() {
    cat << EOF
Usage: $SCRIPT_NAME [OPTIONS] [STRATEGY]

Universal rollback script for CricAlgo deployments.

OPTIONS:
    --dry-run          Show what would be rolled back without making changes
    --force            Skip confirmation prompts
    --namespace NS      Kubernetes namespace (default: $K8S_NS_PROD)
    --strategy STRAT    Canary strategy: istio|nginx (default: $CANARY_STRATEGY)
    --help             Show this help message

STRATEGY:
    istio              Rollback Istio canary deployment
    nginx              Rollback Nginx canary deployment
    all                Rollback both Istio and Nginx (if applicable)

EXAMPLES:
    $SCRIPT_NAME --dry-run istio
    $SCRIPT_NAME --force nginx
    $SCRIPT_NAME --namespace prod all

ENVIRONMENT VARIABLES:
    K8S_NS_PROD        Production namespace (default: $K8S_NS_PROD)
    CANARY_STRATEGY    Default canary strategy (default: $CANARY_STRATEGY)
    DRY_RUN            Enable dry run mode
    FORCE              Skip confirmation prompts

EOF
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Confirm action
confirm_action() {
    local message="$1"
    
    if [ "$FORCE" = "true" ]; then
        log_info "Force mode enabled, skipping confirmation"
        return 0
    fi
    
    echo -e "${YELLOW}$message${NC}"
    read -p "Continue? (y/N): " -r
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Operation cancelled by user"
        return 1
    fi
    return 0
}

# Rollback Istio canary
rollback_istio() {
    log_info "Rolling back Istio canary deployment..."
    
    if [ "$DRY_RUN" = "true" ]; then
        log_info "DRY RUN: Would delete Istio VirtualService canary configurations"
        return 0
    fi
    
    # Delete canary VirtualService
    local vs_files=(
        "k8s/istio/virtualservice-canary-10.yaml"
        "k8s/istio/virtualservice-canary-25.yaml"
        "k8s/istio/virtualservice-canary-50.yaml"
        "k8s/istio/virtualservice-canary-100.yaml"
    )
    
    for vs_file in "${vs_files[@]}"; do
        if [ -f "$vs_file" ]; then
            log_info "Deleting VirtualService: $vs_file"
            kubectl -n "$K8S_NS_PROD" delete -f "$vs_file" --ignore-not-found=true || {
                log_warning "Failed to delete $vs_file"
            }
        fi
    done
    
    # Scale down canary deployment
    log_info "Scaling down canary deployment..."
    kubectl -n "$K8S_NS_PROD" scale deployment app-canary --replicas=0 --ignore-not-found=true || {
        log_warning "Failed to scale down canary deployment"
    }
    
    # Wait for canary pods to terminate
    log_info "Waiting for canary pods to terminate..."
    kubectl -n "$K8S_NS_PROD" wait --for=delete pod -l app=cricalgo,version=canary --timeout=60s || {
        log_warning "Timeout waiting for canary pods to terminate"
    }
    
    log_success "Istio canary rollback completed"
}

# Rollback Nginx canary
rollback_nginx() {
    log_info "Rolling back Nginx canary deployment..."
    
    if [ "$DRY_RUN" = "true" ]; then
        log_info "DRY RUN: Would restore Nginx stable configuration"
        return 0
    fi
    
    # Restore stable upstream configuration
    local stable_config="k8s/nginx/upstream-stable.yaml"
    if [ -f "$stable_config" ]; then
        log_info "Applying stable Nginx configuration..."
        kubectl -n "$K8S_NS_PROD" apply -f "$stable_config" || {
            log_error "Failed to apply stable Nginx configuration"
            return 1
        }
    else
        log_warning "Stable Nginx configuration not found: $stable_config"
    fi
    
    # Delete canary upstream configurations
    local canary_files=(
        "k8s/nginx/upstream-canary-10.yaml"
        "k8s/nginx/upstream-canary-25.yaml"
        "k8s/nginx/upstream-canary-50.yaml"
        "k8s/nginx/upstream-canary-100.yaml"
    )
    
    for canary_file in "${canary_files[@]}"; do
        if [ -f "$canary_file" ]; then
            log_info "Deleting canary configuration: $canary_file"
            kubectl -n "$K8S_NS_PROD" delete -f "$canary_file" --ignore-not-found=true || {
                log_warning "Failed to delete $canary_file"
            }
        fi
    done
    
    # Scale down canary deployment
    log_info "Scaling down canary deployment..."
    kubectl -n "$K8S_NS_PROD" scale deployment app-canary --replicas=0 --ignore-not-found=true || {
        log_warning "Failed to scale down canary deployment"
    }
    
    log_success "Nginx canary rollback completed"
}

# Rollback all canary deployments
rollback_all() {
    log_info "Rolling back all canary deployments..."
    
    rollback_istio
    rollback_nginx
    
    log_success "All canary rollbacks completed"
}

# Verify rollback
verify_rollback() {
    log_info "Verifying rollback..."
    
    if [ "$DRY_RUN" = "true" ]; then
        log_info "DRY RUN: Would verify rollback status"
        return 0
    fi
    
    # Check canary pods
    local canary_pods
    canary_pods=$(kubectl -n "$K8S_NS_PROD" get pods -l app=cricalgo,version=canary --no-headers 2>/dev/null | wc -l)
    
    if [ "$canary_pods" -eq 0 ]; then
        log_success "No canary pods running"
    else
        log_warning "$canary_pods canary pods still running"
    fi
    
    # Check stable pods
    local stable_pods
    stable_pods=$(kubectl -n "$K8S_NS_PROD" get pods -l app=cricalgo,version=stable --no-headers 2>/dev/null | wc -l)
    
    if [ "$stable_pods" -gt 0 ]; then
        log_success "$stable_pods stable pods running"
    else
        log_warning "No stable pods running"
    fi
    
    # Check VirtualService (Istio)
    if command_exists "kubectl"; then
        local vs_count
        vs_count=$(kubectl -n "$K8S_NS_PROD" get virtualservice -l app=cricalgo --no-headers 2>/dev/null | wc -l)
        
        if [ "$vs_count" -eq 0 ]; then
            log_info "No VirtualService resources found"
        else
            log_info "$vs_count VirtualService resources found"
        fi
    fi
}

# Main function
main() {
    local strategy=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN="true"
                shift
                ;;
            --force)
                FORCE="true"
                shift
                ;;
            --namespace)
                K8S_NS_PROD="$2"
                shift 2
                ;;
            --strategy)
                CANARY_STRATEGY="$2"
                shift 2
                ;;
            --help)
                show_help
                exit 0
                ;;
            istio|nginx|all)
                strategy="$1"
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Use default strategy if none specified
    if [ -z "$strategy" ]; then
        strategy="$CANARY_STRATEGY"
    fi
    
    # Validate kubectl availability
    if [ "$DRY_RUN" != "true" ] && ! command_exists "kubectl"; then
        log_error "kubectl not found but required for rollback"
        exit 1
    fi
    
    # Show configuration
    log_info "=== Universal Rollback Script v$SCRIPT_VERSION ==="
    log_info "Strategy: $strategy"
    log_info "Namespace: $K8S_NS_PROD"
    log_info "Dry Run: $DRY_RUN"
    log_info "Force: $FORCE"
    
    # Confirm action
    if ! confirm_action "This will rollback canary deployment using $strategy strategy"; then
        exit 0
    fi
    
    # Execute rollback based on strategy
    case "$strategy" in
        "istio")
            rollback_istio
            ;;
        "nginx")
            rollback_nginx
            ;;
        "all")
            rollback_all
            ;;
        *)
            log_error "Unknown strategy: $strategy"
            exit 1
            ;;
    esac
    
    # Verify rollback
    verify_rollback
    
    log_success "=== Rollback completed successfully ==="
}

# Run main function
main "$@"