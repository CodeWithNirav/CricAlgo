# CricAlgo Full Rollout Automation

This document describes the comprehensive automation system for CricAlgo's PR → Canary → Merge → Release → Runbook flow.

## 🚀 Overview

The automation system provides a complete end-to-end solution for deploying performance improvements with canary rollouts, automated testing, and comprehensive monitoring.

## 📁 File Structure

```
scripts/
├── full_rollout_automation.sh    # Main automation script
├── health_check.sh               # Comprehensive health checks
├── monitoring_check.sh           # Monitoring validation
├── performance_monitor.sh        # Real-time performance monitoring
├── rollback_universal.sh         # Universal rollback script
├── rollback_istio.sh            # Istio-specific rollback
├── rollback_nginx.sh            # Nginx-specific rollback
└── istio_weight_replacer.sh     # Dynamic Istio configuration

k8s/
├── istio/
│   ├── virtualservice-canary-template.yaml  # Dynamic Istio template
│   ├── virtualservice-canary-10.yaml       # 10% canary traffic
│   ├── virtualservice-canary-25.yaml       # 25% canary traffic
│   ├── virtualservice-canary-50.yaml       # 50% canary traffic
│   └── virtualservice-canary-100.yaml      # 100% canary traffic
└── nginx/
    ├── upstream-canary-10.yaml             # 10% nginx canary
    ├── upstream-canary-25.yaml             # 25% nginx canary
    ├── upstream-canary-50.yaml             # 50% nginx canary
    └── upstream-canary-100.yaml            # 100% nginx canary

.github/
└── PR_BODY.md                    # Automated PR description template
```

## 🔧 Prerequisites

### Required Tools
- `kubectl` - Kubernetes CLI
- `curl` - HTTP client
- `jq` - JSON processor
- `k6` - Load testing tool (or Docker)
- `git` - Version control
- `gh` - GitHub CLI (optional, falls back to API)

### Environment Variables
```bash
export GITHUB_TOKEN="your_github_token"           # Required for PR/Release automation
export STAGING_HOST="https://api.example.com"     # Target endpoint for testing
export KUBECONFIG="~/.kube/config"                # Kubernetes configuration
```

### Kubernetes Permissions
The automation requires the following Kubernetes permissions:
- `get`, `list`, `watch` on pods, services, deployments
- `create`, `update`, `delete` on configmaps, virtualservices, destinationrules
- `patch` on deployments for scaling

## 🚀 Quick Start

### 1. Basic Automated Rollout
```bash
# Set environment variables
export GITHUB_TOKEN="your_github_token"
export STAGING_HOST="https://api.cricalgo-staging.example.com"

# Run the full automation
./scripts/full_rollout_automation.sh
```

### 2. Customized Rollout
```bash
# Customize parameters
BRANCH="perf/custom-rollout-$(date -u +%Y%m%dT%H%M%SZ)" \
PR_TITLE="Custom Performance Rollout" \
CANARY_STRATEGY="nginx" \
SMOKE_VUS=50 \
LONG_K6_VUS=200 \
TIMEOUT_CI=3600 \
./scripts/full_rollout_automation.sh
```

## 📋 Automation Flow

### Phase 1: PR Creation
1. Creates feature branch from main
2. Commits current changes
3. Pushes branch to remote
4. Creates PR with automated description
5. Waits for CI to pass (configurable timeout)

### Phase 2: Canary Deployment
1. Prompts for production confirmation
2. Deploys canary version
3. Routes 10% traffic to canary
4. Waits for pods to be ready

### Phase 3: Testing & Validation
1. Runs comprehensive health checks
2. Executes smoke tests with k6
3. Monitors performance metrics
4. Validates monitoring systems

### Phase 4: Progressive Rollout
1. Increases traffic to 25% (if healthy)
2. Increases traffic to 50% (if healthy)
3. Increases traffic to 100% (if healthy)
4. Runs tests at each stage

### Phase 5: Release & Cleanup
1. Merges PR to main
2. Creates release tag
3. Generates GitHub release
4. Creates runbook documentation
5. Packages artifacts

## 🔍 Health Checks

### Application Health
- Pod readiness and liveness
- Service availability
- HTTP endpoint responses
- Database connectivity
- Redis connectivity

### Performance Metrics
- P95/P99 latency thresholds
- Error rate monitoring
- CPU/Memory utilization
- Throughput validation

### Monitoring Systems
- Prometheus server health
- Grafana dashboard availability
- AlertManager configuration
- ServiceMonitor validation

## 🚨 Rollback Procedures

### Automatic Rollback Triggers
- Error rate > 1% for 5 consecutive minutes
- P99 latency > 10s for 5 consecutive minutes
- Any critical alerts firing
- Health check failures

### Rollback Commands
```bash
# Universal rollback (auto-detects strategy)
./scripts/rollback_universal.sh prod "Performance issues detected"

# Strategy-specific rollback
./scripts/rollback_istio.sh prod "High error rate detected"
./scripts/rollback_nginx.sh prod "High latency detected"
```

## 📊 Monitoring & Alerting

### Key Metrics
- **Application**: Response time, error rate, throughput
- **Infrastructure**: CPU, memory, disk I/O, network
- **Database**: Connection pool, query performance
- **Celery**: Queue depth, task processing time

### Alert Thresholds
- **Critical**: Error rate > 1%, P99 latency > 10s
- **Warning**: Error rate > 0.5%, P95 latency > 5s
- **Info**: CPU > 80%, Memory > 85%

## 🛠️ Configuration Options

### Environment Variables
```bash
# Branch and PR configuration
BRANCH="perf/full-rollout-$(date -u +%Y%m%dT%H%M%SZ)"
PR_TITLE="Performance Rollout"
PR_REVIEWERS="backend-lead,devops"
PR_LABELS="perf,staging-tested"

# Release configuration
RELEASE_TAG="v1.0.0"

# Canary strategy
CANARY_STRATEGY="istio"  # or "nginx"

# Testing configuration
SMOKE_VUS=20
SMOKE_DURATION="60s"
LONG_K6_VUS=100
LONG_K6_DURATION="5m"

# Timeout configuration
TIMEOUT_CI=1800  # 30 minutes
```

### Kubernetes Namespaces
- **Staging**: `cricalgo-staging`
- **Production**: `prod`
- **Monitoring**: `monitoring`

## 📈 Performance Targets

### Latency Targets
- P95 latency: < 2 seconds
- P99 latency: < 5 seconds
- Health check: < 100ms

### Throughput Targets
- Webhook processing: > 1000 RPS
- Health checks: > 5000 RPS

### Error Rate Targets
- Overall error rate: < 0.5%
- 5xx errors: < 0.1%

## 🔧 Troubleshooting

### Common Issues

#### Authentication Errors
```bash
# Check GitHub token
echo $GITHUB_TOKEN

# Check kubectl configuration
kubectl auth can-i get pods
```

#### Health Check Failures
```bash
# Run detailed health check
./scripts/health_check.sh prod https://api.example.com 30 true

# Check pod logs
kubectl -n prod logs -l app=cricalgo --tail=100
```

#### Performance Issues
```bash
# Run performance monitoring
./scripts/performance_monitor.sh prod https://api.example.com 600

# Check resource utilization
kubectl -n prod top pods
```

### Log Locations
- **Automation logs**: `artifacts/full_rollout_*/automation.log`
- **Health check reports**: `artifacts/health_check_*.json`
- **Performance reports**: `artifacts/performance_report_*.json`
- **Rollback reports**: `artifacts/rollback_report_*.txt`

## 🚀 Advanced Usage

### Custom Canary Weights
```bash
# Modify canary weights in the script
CANARY_WEIGHTS=(5 15 35 100)  # Custom progression
```

### Custom Health Checks
```bash
# Add custom health checks to health_check.sh
# Modify the run_health_check function calls
```

### Custom Monitoring
```bash
# Add custom metrics to performance_monitor.sh
# Modify the get_current_metrics function
```

## 📚 Related Documentation

- [Production Rollout Runbook](./docs/runbook_prod_rollout.md)
- [Performance Rollout README](./PERFORMANCE_ROLLOUT_README.md)
- [Load Testing Guide](./load/k6/README.md)
- [Monitoring Setup](./monitoring/README.md)

## 🤝 Contributing

When adding new features to the automation:

1. Update this README
2. Add appropriate error handling
3. Include logging and reporting
4. Test with both Istio and nginx strategies
5. Update the runbook documentation

## 📄 License

This automation system is part of the CricAlgo project and follows the same licensing terms.
