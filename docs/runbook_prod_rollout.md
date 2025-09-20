# CricAlgo — Production Rollout Runbook (canary → full)

## Before you begin
- Ensure on-call person available and Slack/phone reachable.
- Have rollback commands at hand.
- Confirm monitoring dashboards and alerting are functional.
- Verify staging environment is healthy and performance tests pass.

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

### 1. Deploy canary deployment
```bash
# Create canary deployment with label version=canary
kubectl -n cricalgo-staging apply -f k8s/deploy/app-canary.yaml

# Verify canary is running
kubectl -n cricalgo-staging get pods -l version=canary
```

### 2. Route 10% traffic to canary (Istio)
```bash
# Apply 10% canary routing
kubectl -n cricalgo-staging apply -f k8s/istio/virtualservice-canary-10.yaml

# Verify routing is active
kubectl -n cricalgo-staging get virtualservice app-virtualservice-canary-10
```

### 3. Run smoke tests against canary
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

### Kubernetes
```bash
# Rollback deployments
kubectl -n cricalgo-staging rollout undo deployment/app
kubectl -n cricalgo-staging rollout undo deployment/worker

# Scale down canary
kubectl -n cricalgo-staging scale deployment app-canary --replicas=0

# Restore stable routing
kubectl -n cricalgo-staging apply -f k8s/istio/virtualservice-stable.yaml
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

## Troubleshooting

### High latency
- Check database connection pool utilization
- Verify Celery worker capacity
- Review application logs for bottlenecks
- Consider scaling up app replicas

### High error rate
- Check application logs for error patterns
- Verify database connectivity
- Check Redis connectivity
- Review Celery task failures

### Celery queue backlog
- Scale up worker replicas
- Check worker health and logs
- Verify task processing isn't stuck
- Review database locks

### Database issues
- Check connection pool settings
- Verify database performance
- Review slow query logs
- Consider read replica scaling
