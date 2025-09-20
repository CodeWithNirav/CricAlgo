#!/bin/bash

# CricAlgo Secret Rotation Script
# This script helps rotate secrets in the CricAlgo application

set -euo pipefail

# Configuration
NAMESPACE="cricalgo-staging"
SECRET_NAME="cricalgo-secrets"
BACKUP_DIR="./secret-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if kubectl is available
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
}

# Check if namespace exists
check_namespace() {
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_error "Namespace $NAMESPACE does not exist"
        exit 1
    fi
}

# Backup current secret
backup_secret() {
    log_info "Backing up current secret..."
    mkdir -p "$BACKUP_DIR"
    
    kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o yaml > "$BACKUP_DIR/${SECRET_NAME}_${TIMESTAMP}.yaml"
    log_info "Secret backed up to $BACKUP_DIR/${SECRET_NAME}_${TIMESTAMP}.yaml"
}

# Generate new secret value
generate_secret() {
    local secret_type="$1"
    case "$secret_type" in
        "jwt")
            openssl rand -base64 32
            ;;
        "database")
            openssl rand -base64 32
            ;;
        "redis")
            openssl rand -base64 32
            ;;
        "webhook")
            openssl rand -base64 32
            ;;
        "telegram")
            log_warn "Telegram bot token must be obtained from @BotFather"
            read -p "Enter new Telegram bot token: " -s new_token
            echo "$new_token" | base64 -w 0
            ;;
        *)
            log_error "Unknown secret type: $secret_type"
            exit 1
            ;;
    esac
}

# Update secret in Kubernetes
update_secret() {
    local key="$1"
    local value="$2"
    
    log_info "Updating secret key: $key"
    
    # Check if secret exists
    if kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" &> /dev/null; then
        # Update existing secret
        kubectl patch secret "$SECRET_NAME" -n "$NAMESPACE" -p="{\"data\":{\"$key\":\"$value\"}}"
    else
        log_error "Secret $SECRET_NAME does not exist in namespace $NAMESPACE"
        exit 1
    fi
}

# Restart deployments that use the secret
restart_deployments() {
    log_info "Restarting deployments to pick up new secret..."
    
    # List of deployments that use secrets
    local deployments=("cricalgo-app" "cricalgo-worker" "cricalgo-bot")
    
    for deployment in "${deployments[@]}"; do
        if kubectl get deployment "$deployment" -n "$NAMESPACE" &> /dev/null; then
            log_info "Restarting deployment: $deployment"
            kubectl rollout restart deployment "$deployment" -n "$NAMESPACE"
            kubectl rollout status deployment "$deployment" -n "$NAMESPACE" --timeout=300s
        else
            log_warn "Deployment $deployment not found, skipping..."
        fi
    done
}

# Verify secret update
verify_secret() {
    local key="$1"
    
    log_info "Verifying secret update..."
    
    # Get the secret value
    local secret_value
    secret_value=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath="{.data.$key}")
    
    if [ -n "$secret_value" ]; then
        log_info "Secret $key has been updated successfully"
    else
        log_error "Failed to verify secret $key update"
        exit 1
    fi
}

# Rollback function
rollback() {
    log_warn "Rolling back to previous secret..."
    
    if [ -f "$BACKUP_DIR/${SECRET_NAME}_${TIMESTAMP}.yaml" ]; then
        kubectl apply -f "$BACKUP_DIR/${SECRET_NAME}_${TIMESTAMP}.yaml"
        restart_deployments
        log_info "Rollback completed"
    else
        log_error "Backup file not found, cannot rollback"
        exit 1
    fi
}

# Main rotation function
rotate_secret() {
    local secret_type="$1"
    local key="$2"
    
    log_info "Starting rotation for $secret_type ($key)"
    
    # Pre-checks
    check_kubectl
    check_namespace
    
    # Backup current secret
    backup_secret
    
    # Generate new secret
    local new_secret
    new_secret=$(generate_secret "$secret_type")
    
    # Update secret
    update_secret "$key" "$new_secret"
    
    # Verify update
    verify_secret "$key"
    
    # Restart deployments
    restart_deployments
    
    log_info "Secret rotation completed successfully"
}

# Interactive mode
interactive_mode() {
    echo "CricAlgo Secret Rotation Tool"
    echo "============================="
    echo ""
    echo "Available secret types:"
    echo "1. JWT Secret Key"
    echo "2. Database Password"
    echo "3. Redis Password"
    echo "4. Webhook Secret"
    echo "5. Telegram Bot Token"
    echo "6. All secrets (full rotation)"
    echo ""
    
    read -p "Select secret type (1-6): " choice
    
    case $choice in
        1)
            rotate_secret "jwt" "JWT_SECRET_KEY"
            ;;
        2)
            rotate_secret "database" "DATABASE_URL"
            ;;
        3)
            rotate_secret "redis" "REDIS_URL"
            ;;
        4)
            rotate_secret "webhook" "WEBHOOK_SECRET"
            ;;
        5)
            rotate_secret "telegram" "TELEGRAM_BOT_TOKEN"
            ;;
        6)
            log_info "Performing full secret rotation..."
            rotate_secret "jwt" "JWT_SECRET_KEY"
            sleep 5
            rotate_secret "webhook" "WEBHOOK_SECRET"
            sleep 5
            rotate_secret "redis" "REDIS_URL"
            ;;
        *)
            log_error "Invalid choice"
            exit 1
            ;;
    esac
}

# Command line mode
cmd_mode() {
    local secret_type="$1"
    local key="$2"
    
    if [ -z "$secret_type" ] || [ -z "$key" ]; then
        log_error "Usage: $0 <secret_type> <key_name>"
        log_error "Example: $0 jwt JWT_SECRET_KEY"
        exit 1
    fi
    
    rotate_secret "$secret_type" "$key"
}

# Main script
main() {
    # Check if running in interactive mode
    if [ $# -eq 0 ]; then
        interactive_mode
    else
        cmd_mode "$@"
    fi
}

# Trap errors and provide rollback option
trap 'log_error "Script failed. Run rollback? (y/n)"; read -p "Rollback? " rollback_choice; if [ "$rollback_choice" = "y" ]; then rollback; fi' ERR

# Run main function
main "$@"
