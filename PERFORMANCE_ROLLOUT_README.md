# CricAlgo Performance Rollout

This directory contains the complete performance and resilience rollout for CricAlgo, implementing horizontal scaling, comprehensive monitoring, and production-ready deployment practices.

## 🚀 Quick Start

### Run Smoke Test
```bash
# Linux/Mac
./scripts/smoke_and_checks.sh

# Windows PowerShell
.\scripts\smoke_and_checks.ps1
```

### Run Load Test
```bash
# Light test (20 VUs, 1 minute)
k6 run --vus 20 --duration 1m load/k6/webhook_test.js

# Full test (100 VUs, 5 minutes)
k6 run --vus 100 --duration 5m load/k6/webhook_test.js
```

### Deploy with Docker Compose
```bash
# Start staging environment with load balancer
docker-compose -f docker-compose.staging.yml up -d

# Check status
docker-compose -f docker-compose.staging.yml ps
```

## 📁 Directory Structure

```
├── app/
│   ├── api/v1/webhooks.py          # Quick-return webhook handler
│   ├── tasks/deposits.py           # Enhanced deposit processing with timing
│   └── db/session.py               # Environment-driven DB pool config
├── k8s/
│   ├── hpa/                        # Horizontal Pod Autoscaler manifests
│   ├── istio/                      # Istio canary deployment configs
│   └── nginx/                      # Nginx canary configuration
├── monitoring/
│   └── prometheus/alerts/          # Enhanced alert rules
├── scripts/
│   ├── smoke_and_checks.sh         # Linux/Mac smoke test
│   └── smoke_and_checks.ps1       # Windows PowerShell smoke test
├── load/k6/
│   └── webhook_test.js             # Enhanced load test with custom metrics
├── docs/
│   └── runbook_prod_rollout.md     # Production deployment guide
└── deploy/
    └── nginx.conf                  # Load balancer configuration
```

## 🎯 Key Features

### Webhook Optimization
- **Quick-return pattern**: Sub-second webhook responses
- **Canonical response**: `{"ok": true, "tx_id": "..."}` format
- **Resilient processing**: Graceful error handling

### Horizontal Scaling
- **Docker Compose**: 3 app instances with nginx load balancer
- **Kubernetes HPA**: Auto-scaling based on CPU utilization
- **Load balancing**: Health checks and failover

### Comprehensive Monitoring
- **15+ alert rules**: Latency, error rates, queue depth, resources
- **Custom metrics**: Webhook and deposit processing performance
- **Performance thresholds**: p95 < 2s, p99 < 5s, error rate < 0.5%

### Canary Deployment
- **Istio VirtualService**: Progressive traffic routing (10% → 25% → 50% → 100%)
- **Nginx upstream**: Weight-based canary for non-Istio environments
- **Rollback procedures**: Quick rollback commands and monitoring

## 🔧 Configuration

### Environment Variables
```bash
# Database pool configuration
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30

# Celery worker configuration
CELERY_WORKER_CONCURRENCY=8

# Application environment
APP_ENV=staging
DEBUG=false
```

### Docker Compose Services
- **app1, app2, app3**: Application instances (ports 8001, 8002, 8003)
- **nginx**: Load balancer (port 8000)
- **postgres**: Database
- **redis**: Cache and message broker
- **worker**: Celery worker for background tasks

## 📊 Monitoring & Alerting

### Key Metrics
- **HTTP Latency**: p95 < 2s, p99 < 5s
- **Error Rate**: < 0.5% 5xx errors
- **Queue Depth**: < 50 Celery tasks
- **DB Pool**: < 90% utilization
- **System Resources**: < 80% CPU, < 85% memory

### Alert Rules
- HTTP latency alerts (p95, p99, average)
- Error rate monitoring (critical and warning thresholds)
- Celery queue depth monitoring
- Database connection pool alerts
- Webhook processing performance
- System resource utilization

## 🚦 Testing

### Smoke Test
Validates basic functionality:
- Health endpoint
- Webhook submission
- User registration (if available)
- Transaction queries (if available)
- Metrics endpoint (if available)

### Load Test
Performance validation with k6:
- Custom metrics for webhook and health endpoints
- Performance thresholds validation
- Detailed reporting and artifact generation
- Configurable VUs and duration

## 🚀 Deployment

### Staging Deployment
```bash
# Start with Docker Compose
docker-compose -f docker-compose.staging.yml up -d

# Run smoke test
./scripts/smoke_and_checks.sh

# Run load test
k6 run --vus 100 --duration 5m load/k6/webhook_test.js
```

### Canary Deployment
```bash
# Deploy canary
kubectl -n cricalgo-staging apply -f k8s/istio/virtualservice-canary-10.yaml

# Monitor for 30-60 minutes
# Progressively increase traffic: 25% → 50% → 100%

# Rollback if needed
kubectl -n cricalgo-staging rollout undo deployment/app
```

## 🔄 Rollback Procedures

### Immediate Rollback
```bash
# Kubernetes
kubectl -n cricalgo-staging rollout undo deployment/app
kubectl -n cricalgo-staging rollout undo deployment/worker

# Docker Compose
docker-compose -f docker-compose.staging.yml down
mv docker-compose.staging.yml.bak docker-compose.staging.yml
docker-compose -f docker-compose.staging.yml up -d
```

### Monitoring Rollback
- Restore previous Prometheus alert rules
- Revert monitoring configuration changes
- Update dashboard configurations

## 📚 Documentation

- **Production Runbook**: `docs/runbook_prod_rollout.md`
- **Performance Summary**: `PERFORMANCE_ROLLOUT_SUMMARY.md`
- **API Documentation**: See individual service documentation

## 🆘 Troubleshooting

### High Latency
- Check database connection pool utilization
- Verify Celery worker capacity
- Review application logs for bottlenecks
- Consider scaling up app replicas

### High Error Rate
- Check application logs for error patterns
- Verify database connectivity
- Check Redis connectivity
- Review Celery task failures

### Celery Queue Backlog
- Scale up worker replicas
- Check worker health and logs
- Verify task processing isn't stuck
- Review database locks

### Database Issues
- Check connection pool settings
- Verify database performance
- Review slow query logs
- Consider read replica scaling

## 📞 Support

- **Primary on-call**: @ops-oncall
- **Backend lead**: @backend-lead
- **DB admin**: @db-admin
- **DevOps lead**: @devops-lead

## 🎉 Success Criteria

- [ ] p95 latency < 2s
- [ ] p99 latency < 5s
- [ ] error rate < 0.5%
- [ ] No sustained Celery queue growth
- [ ] DB CPU not pegged > 80%
- [ ] All monitoring dashboards showing green
- [ ] Smoke tests passing
- [ ] Load tests meeting thresholds

This rollout provides a solid foundation for production-ready performance and monitoring, with comprehensive testing and rollback procedures.
