#!/bin/bash
# Nginx Rollback Script
# This script rolls back nginx canary deployment to stable version

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

log_info "Starting Nginx rollback for namespace: $NAMESPACE"
log_warning "Rollback reason: $ROLLBACK_REASON"

# Step 1: Delete canary nginx deployments
log_info "Deleting canary nginx deployments..."
kubectl -n "$NAMESPACE" delete deployment nginx-canary-10 --ignore-not-found=true
kubectl -n "$NAMESPACE" delete deployment nginx-canary-25 --ignore-not-found=true
kubectl -n "$NAMESPACE" delete deployment nginx-canary-50 --ignore-not-found=true
kubectl -n "$NAMESPACE" delete deployment nginx-canary-100 --ignore-not-found=true

# Step 2: Delete canary nginx services
log_info "Deleting canary nginx services..."
kubectl -n "$NAMESPACE" delete service nginx-canary-10-service --ignore-not-found=true
kubectl -n "$NAMESPACE" delete service nginx-canary-25-service --ignore-not-found=true
kubectl -n "$NAMESPACE" delete service nginx-canary-50-service --ignore-not-found=true
kubectl -n "$NAMESPACE" delete service nginx-canary-100-service --ignore-not-found=true

# Step 3: Delete canary nginx configmaps
log_info "Deleting canary nginx configmaps..."
kubectl -n "$NAMESPACE" delete configmap nginx-upstream-canary-10 --ignore-not-found=true
kubectl -n "$NAMESPACE" delete configmap nginx-upstream-canary-25 --ignore-not-found=true
kubectl -n "$NAMESPACE" delete configmap nginx-upstream-canary-50 --ignore-not-found=true
kubectl -n "$NAMESPACE" delete configmap nginx-upstream-canary-100 --ignore-not-found=true

# Step 4: Apply stable nginx configuration
log_info "Applying stable nginx configuration..."
kubectl -n "$NAMESPACE" apply -f k8s/nginx/upstream-stable.yaml || {
    log_warning "Stable nginx configuration not found, creating basic stable configuration..."
    cat <<EOF | kubectl -n "$NAMESPACE" apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: nginx-upstream-stable
  namespace: $NAMESPACE
data:
  nginx.conf: |
    upstream cricalgo_backend {
        # Stable backend (100% traffic)
        server app-stable.cricalgo-staging.svc.cluster.local:8000 weight=100 max_fails=3 fail_timeout=30s;
        
        # Health check configuration
        keepalive 32;
        keepalive_requests 100;
        keepalive_timeout 60s;
    }
    
    server {
        listen 80;
        server_name api.cricalgo-staging.example.com;
        
        # Rate limiting
        limit_req_zone \$binary_remote_addr zone=api:10m rate=100r/s;
        limit_req zone=api burst=200 nodelay;
        
        # Health check endpoint
        location /nginx-health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }
        
        # Main API proxy
        location / {
            proxy_pass http://cricalgo_backend;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            
            # Timeouts
            proxy_connect_timeout 5s;
            proxy_send_timeout 30s;
            proxy_read_timeout 30s;
            
            # Retry configuration
            proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504;
            proxy_next_upstream_tries 3;
            proxy_next_upstream_timeout 10s;
            
            # Buffer configuration
            proxy_buffering on;
            proxy_buffer_size 4k;
            proxy_buffers 8 4k;
            proxy_busy_buffers_size 8k;
        }
        
        # Metrics endpoint for monitoring
        location /nginx-metrics {
            access_log off;
            return 200 "nginx_up 1\n";
            add_header Content-Type text/plain;
        }
    }
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-stable
  namespace: $NAMESPACE
spec:
  replicas: 2
  selector:
    matchLabels:
      app: nginx-stable
  template:
    metadata:
      labels:
        app: nginx-stable
    spec:
      containers:
      - name: nginx
        image: nginx:1.21-alpine
        ports:
        - containerPort: 80
        volumeMounts:
        - name: nginx-config
          mountPath: /etc/nginx/conf.d
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "128Mi"
            cpu: "100m"
        livenessProbe:
          httpGet:
            path: /nginx-health
            port: 80
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /nginx-health
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: nginx-config
        configMap:
          name: nginx-upstream-stable
---
apiVersion: v1
kind: Service
metadata:
  name: nginx-stable-service
  namespace: $NAMESPACE
spec:
  selector:
    app: nginx-stable
  ports:
  - port: 80
    targetPort: 80
  type: ClusterIP
EOF
}

# Step 5: Scale down canary deployment
log_info "Scaling down canary deployment..."
kubectl -n "$NAMESPACE" scale deployment app-canary --replicas=0 || log_warning "Canary deployment not found or already scaled down"

# Step 6: Verify stable deployment is healthy
log_info "Verifying stable deployment health..."
kubectl -n "$NAMESPACE" rollout status deployment/app --timeout=120s || {
    log_error "Stable deployment is not healthy. Manual intervention required."
    exit 1
}

# Step 7: Check pod status
log_info "Checking pod status..."
kubectl -n "$NAMESPACE" get pods -l app=cricalgo -o wide
kubectl -n "$NAMESPACE" get pods -l app=nginx-stable -o wide

# Step 8: Verify nginx configuration
log_info "Verifying nginx configuration..."
kubectl -n "$NAMESPACE" get configmap nginx-upstream-stable

# Step 9: Run basic health check
log_info "Running basic health check..."
HEALTH_ENDPOINT="https://api.cricalgo-staging.example.com/api/v1/health"
if curl -sS "$HEALTH_ENDPOINT" > /dev/null; then
    log_success "Health check passed"
else
    log_warning "Health check failed - manual verification recommended"
fi

log_success "Nginx rollback completed successfully"
log_info "All traffic is now routed to stable deployment through nginx"
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
