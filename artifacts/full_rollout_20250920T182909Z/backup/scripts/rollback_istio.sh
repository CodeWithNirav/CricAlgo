#!/bin/bash
# Istio Rollback Script
# This script rolls back canary deployment to stable version

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
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

NAMESPACE=${1:-prod}
ROLLBACK_REASON=${2:-"Manual rollback triggered"}

log_info "Starting Istio rollback for namespace: $NAMESPACE"
log_warning "Rollback reason: $ROLLBACK_REASON"

# Step 1: Delete canary VirtualService
log_info "Deleting canary VirtualService..."
kubectl -n "$NAMESPACE" delete virtualservice app-virtualservice-canary-10 --ignore-not-found=true
kubectl -n "$NAMESPACE" delete virtualservice app-virtualservice-canary-25 --ignore-not-found=true
kubectl -n "$NAMESPACE" delete virtualservice app-virtualservice-canary-50 --ignore-not-found=true
kubectl -n "$NAMESPACE" delete virtualservice app-virtualservice-canary-100 --ignore-not-found=true

# Step 2: Apply stable VirtualService (100% traffic to stable)
log_info "Applying stable VirtualService..."
kubectl -n "$NAMESPACE" apply -f k8s/istio/virtualservice-stable.yaml || {
    log_warning "Stable VirtualService not found, creating basic stable routing..."
    cat <<EOF | kubectl -n "$NAMESPACE" apply -f -
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: app-virtualservice-stable
  namespace: $NAMESPACE
spec:
  hosts:
  - "api.cricalgo-staging.example.com"
  http:
  - route:
    - destination:
        host: app.cricalgo-staging.svc.cluster.local
        subset: stable
      weight: 100
    retries:
      attempts: 2
      perTryTimeout: 2s
      retryOn: gateway-error,connect-failure,refused-stream
    timeout: 30s
EOF
}

# Step 3: Scale down canary deployment
log_info "Scaling down canary deployment..."
kubectl -n "$NAMESPACE" scale deployment app-canary --replicas=0 || log_warning "Canary deployment not found or already scaled down"

# Step 4: Verify stable deployment is healthy
log_info "Verifying stable deployment health..."
kubectl -n "$NAMESPACE" rollout status deployment/app --timeout=120s || {
    log_error "Stable deployment is not healthy. Manual intervention required."
    exit 1
}

# Step 5: Check pod status
log_info "Checking pod status..."
kubectl -n "$NAMESPACE" get pods -l app=cricalgo -o wide

# Step 6: Verify traffic routing
log_info "Verifying traffic routing..."
kubectl -n "$NAMESPACE" get virtualservice | grep app

# Step 7: Run basic health check
log_info "Running basic health check..."
HEALTH_ENDPOINT="https://api.cricalgo-staging.example.com/api/v1/health"
if curl -sS "$HEALTH_ENDPOINT" > /dev/null; then
    log_success "Health check passed"
else
    log_warning "Health check failed - manual verification recommended"
fi

log_success "Istio rollback completed successfully"
log_info "All traffic is now routed to stable deployment"
log_info "Canary deployment has been scaled down"

# Optional: Clean up canary resources
read -p "Do you want to delete canary deployment completely? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "Deleting canary deployment..."
    kubectl -n "$NAMESPACE" delete deployment app-canary --ignore-not-found=true
    log_success "Canary deployment deleted"
fi

log_success "Rollback process completed"
