#!/bin/bash
set -euo pipefail

# =============================================================================
# Consolidated Rollback Script for CricAlgo
# =============================================================================
# 
# This script provides comprehensive rollback capabilities for:
# - Istio canary deployments
# - Nginx canary deployments
# - Kubernetes resource cleanup
# - Database rollbacks (if applicable)
#
# Author: CricAlgo DevOps Team
# Version: 3.0.0
# =============================================================================

readonly SCRIPT_VERSION="3.0.0"
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

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Rollback Istio canary deployment
rollback_istio() {
    local namespace="$1"
    
    log_info "Rolling back Istio canary deployment in namespace: $namespace"
    
    if ! command_exists "kubectl"; then
        log_error "kubectl not found, cannot perform Istio rollback"
        return 1
    fi
    
    # Check if Istio is available
    if ! kubectl get crd virtualservices.networking.istio.io >/dev/null 2>&1; then
        log_error "Istio VirtualService CRD not found, Istio may not be installed"
        return 1
    fi
    
    # Get current VirtualService
    local vs_name="app"
    local current_vs
    current_vs=$(kubectl -n "$namespace" get virtualservice "$vs_name" -o yaml 2>/dev/null || echo "")
    
    if [ -z "$current_vs" ]; then
        log_warning "VirtualService $vs_name not found in namespace $namespace"
        return 0
    fi
    
    # Check if it's a canary deployment
    if echo "$current_vs" | grep -q "canary"; then
        log_info "Detected canary deployment, rolling back to stable version"
        
        if [ "$DRY_RUN" = "true" ]; then
            log_info "DRY RUN: Would rollback Istio canary deployment"
            return 0
        fi
        
        # Remove canary VirtualService
        if kubectl -n "$namespace" delete virtualservice "$vs_name" --ignore-not-found=true; then
            log_success "Removed canary VirtualService"
        else
            log_error "Failed to remove canary VirtualService"
            return 1
        fi
        
        # Scale down canary deployment
        if kubectl -n "$namespace" scale deployment app-canary --replicas=0 --ignore-not-found=true; then
            log_success "Scaled down canary deployment"
        else
            log_warning "Canary deployment not found or already scaled down"
        fi
        
        # Scale up stable deployment
        if kubectl -n "$namespace" scale deployment app --replicas=3; then
            log_success "Scaled up stable deployment"
        else
            log_error "Failed to scale up stable deployment"
            return 1
        fi
        
        # Wait for rollout to complete
        if kubectl -n "$namespace" rollout status deployment/app --timeout=300s; then
            log_success "Stable deployment rollout completed"
        else
            log_error "Stable deployment rollout failed"
            return 1
        fi
    else
        log_info "No canary deployment detected, nothing to rollback"
    fi
}

# Rollback Nginx canary deployment
rollback_nginx() {
    local namespace="$1"
    
    log_info "Rolling back Nginx canary deployment in namespace: $namespace"
    
    if ! command_exists "kubectl"; then
        log_error "kubectl not found, cannot perform Nginx rollback"
        return 1
    fi
    
    # Check if Nginx ingress controller is available
    if ! kubectl get pods -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx >/dev/null 2>&1; then
        log_warning "Nginx ingress controller not found, skipping Nginx rollback"
        return 0
    fi
    
    # Get current ingress
    local ingress_name="app"
    local current_ingress
    current_ingress=$(kubectl -n "$namespace" get ingress "$ingress_name" -o yaml 2>/dev/null || echo "")
    
    if [ -z "$current_ingress" ]; then
        log_warning "Ingress $ingress_name not found in namespace $namespace"
        return 0
    fi
    
    # Check if it's a canary deployment
    if echo "$current_ingress" | grep -q "canary"; then
        log_info "Detected canary ingress, rolling back to stable version"
        
        if [ "$DRY_RUN" = "true" ]; then
            log_info "DRY RUN: Would rollback Nginx canary deployment"
            return 0
        fi
        
        # Remove canary ingress
        if kubectl -n "$namespace" delete ingress "$ingress_name" --ignore-not-found=true; then
            log_success "Removed canary ingress"
        else
            log_error "Failed to remove canary ingress"
            return 1
        fi
        
        # Scale down canary deployment
        if kubectl -n "$namespace" scale deployment app-canary --replicas=0 --ignore-not-found=true; then
            log_success "Scaled down canary deployment"
        else
            log_warning "Canary deployment not found or already scaled down"
        fi
        
        # Scale up stable deployment
        if kubectl -n "$namespace" scale deployment app --replicas=3; then
            log_success "Scaled up stable deployment"
        else
            log_error "Failed to scale up stable deployment"
            return 1
        fi
        
        # Wait for rollout to complete
        if kubectl -n "$namespace" rollout status deployment/app --timeout=300s; then
            log_success "Stable deployment rollout completed"
        else
            log_error "Stable deployment rollout failed"
            return 1
        fi
    else
        log_info "No canary deployment detected, nothing to rollback"
    fi
}

# Clean up Kubernetes resources
cleanup_k8s_resources() {
    local namespace="$1"
    
    log_info "Cleaning up Kubernetes resources in namespace: $namespace"
    
    if ! command_exists "kubectl"; then
        log_error "kubectl not found, cannot clean up resources"
        return 1
    fi
    
    if [ "$DRY_RUN" = "true" ]; then
        log_info "DRY RUN: Would clean up resources in namespace $namespace"
        return 0
    fi
    
    # Delete canary deployments
    if kubectl -n "$namespace" delete deployment app-canary --ignore-not-found=true; then
        log_success "Deleted canary deployment"
    fi
    
    # Delete canary services
    if kubectl -n "$namespace" delete service app-canary --ignore-not-found=true; then
        log_success "Deleted canary service"
    fi
    
    # Delete canary configmaps
    if kubectl -n "$namespace" delete configmap app-canary-config --ignore-not-found=true; then
        log_success "Deleted canary configmap"
    fi
    
    # Delete canary secrets
    if kubectl -n "$namespace" delete secret app-canary-secrets --ignore-not-found=true; then
        log_success "Deleted canary secrets"
    fi
}

# Verify rollback
verify_rollback() {
    local namespace="$1"
    
    log_info "Verifying rollback in namespace: $namespace"
    
    if ! command_exists "kubectl"; then
        log_warning "kubectl not found, cannot verify rollback"
        return 0
    fi
    
    # Check if stable deployment is running
    local ready_replicas
    local desired_replicas
    
    ready_replicas=$(kubectl -n "$namespace" get deployment app -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    desired_replicas=$(kubectl -n "$namespace" get deployment app -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    
    if [ "$ready_replicas" -eq "$desired_replicas" ] && [ "$desired_replicas" -gt 0 ]; then
        log_success "Stable deployment is running ($ready_replicas/$desired_replicas replicas)"
    else
        log_error "Stable deployment is not running properly ($ready_replicas/$desired_replicas replicas)"
        return 1
    fi
    
    # Check if canary deployment is scaled down
    local canary_replicas
    canary_replicas=$(kubectl -n "$namespace" get deployment app-canary -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
    
    if [ "$canary_replicas" -eq 0 ]; then
        log_success "Canary deployment is scaled down"
    else
        log_warning "Canary deployment still has $canary_replicas replicas"
    fi
}

# Main rollback function
run_rollback() {
    local namespace="$1"
    
    log_info "Starting rollback process for namespace: $namespace"
    log_info "Strategy: $CANARY_STRATEGY"
    log_info "Dry run: $DRY_RUN"
    log_info "Force: $FORCE"
    echo ""
    
    # Perform rollback based on strategy
    case "$CANARY_STRATEGY" in
        "istio")
            rollback_istio "$namespace"
            ;;
        "nginx")
            rollback_nginx "$namespace"
            ;;
        "both")
            rollback_istio "$namespace"
            rollback_nginx "$namespace"
            ;;
        *)
            log_error "Unknown canary strategy: $CANARY_STRATEGY"
            return 1
            ;;
    esac
    
    # Clean up resources
    cleanup_k8s_resources "$namespace"
    
    # Verify rollback
    verify_rollback "$namespace"
    
    log_success "Rollback completed successfully"
}

# Help function
show_help() {
    cat << EOF
Usage: $SCRIPT_NAME [OPTIONS] NAMESPACE

Consolidated rollback script for CricAlgo.

ARGUMENTS:
    NAMESPACE            Kubernetes namespace to rollback

OPTIONS:
    --strategy STRATEGY  Canary strategy: istio|nginx|both (default: $CANARY_STRATEGY)
    --dry-run           Show what would be done without making changes
    --force             Force rollback even if checks fail
    --help              Show this help message

ENVIRONMENT VARIABLES:
    K8S_NS_PROD         Production namespace (default: $K8S_NS_PROD)
    K8S_NS_STAGING      Staging namespace (default: $K8S_NS_STAGING)
    CANARY_STRATEGY      Canary strategy (default: $CANARY_STRATEGY)
    DRY_RUN              Dry run mode (default: $DRY_RUN)
    FORCE                Force mode (default: $FORCE)

EXAMPLES:
    $SCRIPT_NAME prod
    $SCRIPT_NAME --strategy istio --dry-run staging
    $SCRIPT_NAME --strategy both --force prod

EOF
}

# Main function
main() {
    local namespace=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --strategy)
                CANARY_STRATEGY="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN="true"
                shift
                ;;
            --force)
                FORCE="true"
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            -*)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
            *)
                if [ -z "$namespace" ]; then
                    namespace="$1"
                else
                    log_error "Multiple namespaces specified: $namespace and $1"
                    exit 1
                fi
                shift
                ;;
        esac
    done
    
    # Validate arguments
    if [ -z "$namespace" ]; then
        log_error "Namespace is required"
        show_help
        exit 1
    fi
    
    # Run rollback
    run_rollback "$namespace"
}

# Run main function
main "$@"
