# CricAlgo — Production Rollout Runbook (canary → full)

## 🚀 Automated Rollout Process

This runbook now supports **fully automated** PR → Canary → Merge → Release → Runbook flow using the `scripts/full_rollout_automation.sh` script.

### Quick Start (Automated)
```bash
# Set required environment variables
export GITHUB_TOKEN="your_github_token"
export STAGING_HOST="https://api.cricalgo-staging.example.com"

# Run the full automation
./scripts/full_rollout_automation.sh
```

### Manual Override Options
```bash
# Customize the automation
BRANCH="perf/custom-rollout-$(date -u +%Y%m%dT%H%M%SZ)" \
PR_TITLE="Custom Performance Rollout" \
CANARY_STRATEGY="nginx" \
SMOKE_VUS=50 \
LONG_K6_VUS=200 \
./scripts/full_rollout_automation.sh
```

## Before you begin
- Ensure on-call person available and Slack/phone reachable.
- Have rollback commands at hand.
- Confirm monitoring dashboards and alerting are functional.
- Verify staging environment is healthy and performance tests pass.
- **For automated rollout**: Ensure `GITHUB_TOKEN` is set and `kubectl` is configured.

## Pre-deployment Checklist
- [ ] All CI/CD checks pass (unit, integration, migration)
- [ ] Security scan completed successfully
- [ ] Secrets are stored in secret manager (no secrets in repo)
- [ ] Staging environment variables configured:
  - `DB_POOL_SIZE=20`
  - `DB_MAX_OVERFLOW=30`
  - `CELERY_WORKER_CONCURRENCY=8`
  - `ENABLE_TEST_TOTP_BYPASS=false` (if needed)
- [ ] Performance tests completed successfully
- [ ] Monitoring dashboards accessible
- [ ] Alert channels configured and tested

## Steps: Canary rollout (recommended)

### Automated Canary Rollout
The automation script handles all steps below automatically. For manual execution:

### 1. Deploy canary deployment
```bash
# Create canary deployment with label version=canary
kubectl -n cricalgo-staging apply -f k8s/deploy/app-canary.yaml

# Verify canary is running
kubectl -n cricalgo-staging get pods -l version=canary
```

### 2. Route traffic to canary

#### Istio Strategy (Default)
```bash
# Apply 10% canary routing
kubectl -n cricalgo-staging apply -f k8s/istio/virtualservice-canary-10.yaml

# Verify routing is active
kubectl -n cricalgo-staging get virtualservice app-virtualservice-canary-10
```

#### Nginx Strategy
```bash
# Apply nginx canary configuration
kubectl -n cricalgo-staging apply -f k8s/nginx/upstream-canary-10.yaml

# Verify nginx configuration
kubectl -n cricalgo-staging get configmap nginx-upstream-canary-10
```

### 3. Run comprehensive health checks
```bash
# Run comprehensive health check
./scripts/health_check.sh cricalgo-staging https://api.cricalgo-staging.example.com

# Run monitoring check
./scripts/monitoring_check.sh cricalgo-staging

# Run performance monitoring
./scripts/performance_monitor.sh cricalgo-staging https://api.cricalgo-staging.example.com 300
```

### 4. Run smoke tests against canary
```bash
# Run smoke test
STAGING_HOST=https://api.cricalgo-staging.example.com ./scripts/smoke_and_checks.sh

# Run light load test
k6 run --vus 20 --duration 1m load/k6/webhook_test.js --env STAGING_HOST=https://api.cricalgo-staging.example.com
```

### 4. Monitor (30–60 minutes)
Monitor the following metrics:
- **p95, p99 latency** (target: p95 < 2s, p99 < 5s)
- **error rate** (target: < 0.5% 5xx errors)
- **DB connections** (target: < 90% pool utilization)
- **Celery queue depth** (target: < 50 tasks)
- **CPU/Memory usage** (target: < 80% CPU, < 85% memory)

### 5. Progressive rollout
If healthy after 30 minutes:

#### 25% traffic
```bash
kubectl -n cricalgo-staging apply -f k8s/istio/virtualservice-canary-25.yaml
# Monitor for 30 minutes
```

#### 50% traffic
```bash
kubectl -n cricalgo-staging apply -f k8s/istio/virtualservice-canary-50.yaml
# Monitor for 30 minutes
```

#### 100% traffic (promote canary to stable)
```bash
kubectl -n cricalgo-staging apply -f k8s/istio/virtualservice-canary-100.yaml
# Update stable deployment to use canary image
kubectl -n cricalgo-staging set image deployment/app app=your-registry/cricalgo:vX.Y.Z
kubectl -n cricalgo-staging rollout status deployment/app
```

### 6. If issues detected → rollback
```bash
# Immediate rollback to stable
kubectl -n cricalgo-staging rollout undo deployment/app
kubectl -n cricalgo-staging rollout undo deployment/worker

# Restore 100% traffic to stable
kubectl -n cricalgo-staging apply -f k8s/istio/virtualservice-stable.yaml

# Scale down canary
kubectl -n cricalgo-staging scale deployment app-canary --replicas=0
```

## Alternative: Nginx-based canary (for non-Istio environments)

### 1. Update nginx configuration
```bash
# Copy appropriate upstream configuration
cp k8s/nginx/upstream-weight.conf /etc/nginx/conf.d/cricalgo-upstream.conf

# Reload nginx
nginx -s reload
```

### 2. Adjust weights progressively
- 10% canary: `weight=90` stable, `weight=10` canary
- 25% canary: `weight=75` stable, `weight=25` canary
- 50% canary: `weight=50` stable, `weight=50` canary
- 100% canary: `weight=100` canary

## Rollback quick commands

### Automated Rollback (Recommended)
```bash
# Universal rollback (auto-detects strategy)
./scripts/rollback_universal.sh cricalgo-staging "Performance issues detected"

# Istio-specific rollback
./scripts/rollback_istio.sh cricalgo-staging "High error rate detected"

# Nginx-specific rollback
./scripts/rollback_nginx.sh cricalgo-staging "High latency detected"
```

### Manual Rollback Commands

#### Kubernetes
```bash
# Rollback deployments
kubectl -n cricalgo-staging rollout undo deployment/app
kubectl -n cricalgo-staging rollout undo deployment/worker

# Scale down canary
kubectl -n cricalgo-staging scale deployment app-canary --replicas=0

# Restore stable routing
kubectl -n cricalgo-staging apply -f k8s/istio/virtualservice-stable.yaml
```

#### Istio Rollback
```bash
# Delete canary VirtualService
kubectl -n cricalgo-staging delete virtualservice app-virtualservice-canary-10
kubectl -n cricalgo-staging delete virtualservice app-virtualservice-canary-25
kubectl -n cricalgo-staging delete virtualservice app-virtualservice-canary-50
kubectl -n cricalgo-staging delete virtualservice app-virtualservice-canary-100

# Apply stable VirtualService
kubectl -n cricalgo-staging apply -f k8s/istio/virtualservice-stable.yaml
```

#### Nginx Rollback
```bash
# Delete canary nginx deployments
kubectl -n cricalgo-staging delete deployment nginx-canary-10
kubectl -n cricalgo-staging delete deployment nginx-canary-25
kubectl -n cricalgo-staging delete deployment nginx-canary-50
kubectl -n cricalgo-staging delete deployment nginx-canary-100

# Apply stable nginx configuration
kubectl -n cricalgo-staging apply -f k8s/nginx/upstream-stable.yaml
```

### Docker Compose
```bash
# Stop current deployment
docker-compose -f docker-compose.prod.yml down

# Restore backup configuration
mv docker-compose.prod.yml.bak docker-compose.prod.yml

# Start with stable configuration
docker-compose -f docker-compose.prod.yml up -d
```

## Escalation contacts
- **Primary on-call**: @ops-oncall (pager: +1-XXX-XXX-XXXX)
- **Backend lead**: @backend-lead
- **DB admin**: @db-admin
- **DevOps lead**: @devops-lead

## Post-deploy checks (first 60 minutes)

### Performance metrics
- [ ] p95 latency < 2s
- [ ] p99 latency < 5s
- [ ] error rate < 0.5%
- [ ] No sustained Celery queue growth
- [ ] DB CPU not pegged > 80%

### Functional checks
- [ ] Health endpoint responds correctly
- [ ] Webhook submission works
- [ ] Deposit processing completes
- [ ] User registration works (if applicable)
- [ ] All critical user flows functional

### Monitoring alerts
- [ ] No critical alerts firing
- [ ] Warning alerts within acceptable limits
- [ ] All monitoring dashboards showing green

## Roll out final promotion if all checks green

Once all post-deploy checks pass:
1. Update production deployment to use the new image
2. Remove canary deployment
3. Update monitoring to reflect new baseline metrics
4. Document any configuration changes
5. Notify team of successful deployment

## 🔧 Automation Scripts Reference

### Main Automation Script
- **`scripts/full_rollout_automation.sh`** - Complete PR → Canary → Merge → Release flow
- **`scripts/health_check.sh`** - Comprehensive health checks
- **`scripts/monitoring_check.sh`** - Monitoring and alerting validation
- **`scripts/performance_monitor.sh`** - Real-time performance monitoring

### Rollback Scripts
- **`scripts/rollback_universal.sh`** - Auto-detects strategy and rolls back
- **`scripts/rollback_istio.sh`** - Istio-specific rollback
- **`scripts/rollback_nginx.sh`** - Nginx-specific rollback

### Configuration Scripts
- **`scripts/istio_weight_replacer.sh`** - Dynamic Istio weight configuration
- **`.github/PR_BODY.md`** - Automated PR description template

### Usage Examples
```bash
# Full automated rollout
export GITHUB_TOKEN="your_token"
export STAGING_HOST="https://api.example.com"
./scripts/full_rollout_automation.sh

# Health check only
./scripts/health_check.sh prod https://api.example.com 30 true

# Performance monitoring
./scripts/performance_monitor.sh prod https://api.example.com 600

# Emergency rollback
./scripts/rollback_universal.sh prod "Critical issue detected"
```

## Troubleshooting

### High latency
- Check database connection pool utilization
- Verify Celery worker capacity
- Review application logs for bottlenecks
- Consider scaling up app replicas
- **Use**: `./scripts/performance_monitor.sh` to identify bottlenecks

### High error rate
- Check application logs for error patterns
- Verify database connectivity
- Check Redis connectivity
- Review Celery task failures
- **Use**: `./scripts/health_check.sh` for comprehensive diagnostics

### Celery queue backlog
- Scale up worker replicas
- Check worker health and logs
- Verify task processing isn't stuck
- Review database locks
- **Use**: `./scripts/monitoring_check.sh` to verify Celery metrics

### Database issues
- Check connection pool settings
- Verify database performance
- Review slow query logs
- Consider read replica scaling
- **Use**: `./scripts/health_check.sh` for database connectivity tests

### Automation Script Issues
- Verify `GITHUB_TOKEN` is set correctly
- Check `kubectl` configuration and permissions
- Ensure all required tools are installed (jq, curl, k6)
- Review script logs in `artifacts/` directory
