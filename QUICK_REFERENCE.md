# CricAlgo Automation Quick Reference

## 🚀 One-Command Rollout

```bash
# Set environment variables
export GITHUB_TOKEN="ghp_…"
export STAGING_HOST="https://staging.cricalgo.com"

# Run full automation
./scripts/full_rollout_automation.sh
```

## 🔍 Preflight Check

```bash
# Run preflight checks before automation
./scripts/preflight_check.sh
```

## 🧪 Dry Run

```bash
# Test automation without production changes
DRY_RUN=true ./scripts/full_rollout_automation.sh
```

## 🚨 Emergency Rollback

```bash
# Universal rollback (auto-detects strategy)
./scripts/rollback_universal.sh prod "Critical issue detected"

# Strategy-specific rollback
./scripts/rollback_istio.sh prod "High error rate"
./scripts/rollback_nginx.sh prod "High latency"
```

## 📊 Health & Monitoring

```bash
# Comprehensive health check
./scripts/health_check.sh prod https://api.example.com 30 true

# Monitoring validation
./scripts/monitoring_check.sh prod

# Performance monitoring
./scripts/performance_monitor.sh prod https://api.example.com 600
```

## ⚙️ Configuration Options

### Environment Variables
```bash
export GITHUB_TOKEN="ghp_…"                    # Required
export STAGING_HOST="https://api.example.com"  # Required
export CANARY_STRATEGY="istio"                 # "istio" or "nginx"
export SMOKE_VUS=20                            # Smoke test VUs
export LONG_K6_VUS=100                         # Load test VUs
export DRY_RUN=true                            # Dry run mode
```

### Custom Rollout
```bash
BRANCH="perf/custom-$(date -u +%Y%m%dT%H%M%SZ)" \
PR_TITLE="Custom Performance Rollout" \
CANARY_STRATEGY="nginx" \
SMOKE_VUS=50 \
./scripts/full_rollout_automation.sh
```

## 📁 Artifacts Location

All artifacts are saved to:
```
artifacts/full_rollout_<TIMESTAMP>/
├── automation.log              # Complete automation log
├── pr_info.txt                 # PR URL and details
├── ci_status.txt               # CI status
├── canary_smoke/               # Smoke test results
├── k6_promote_*.txt            # Progressive rollout tests
├── health_promote_*.json       # Health check results
├── final_status.json           # Final status summary
└── runbook_prod_rollout.pdf    # Generated runbook
```

## 🎯 Performance Targets

- **P95 Latency**: < 2 seconds
- **P99 Latency**: < 5 seconds
- **Error Rate**: < 0.5%
- **Health Check**: < 100ms
- **Throughput**: > 1000 RPS

## 🚨 Rollback Triggers

Automatic rollback occurs when:
- Error rate > 1% for 5 consecutive minutes
- P99 latency > 10s for 5 consecutive minutes
- Any critical alerts firing
- Health check failures

## 📋 Preflight Checklist

- [ ] `GITHUB_TOKEN` set and valid
- [ ] `STAGING_HOST` reachable
- [ ] `kubectl` configured and working
- [ ] Required tools installed (curl, jq, git)
- [ ] Git repository clean
- [ ] Monitoring systems accessible
- [ ] On-call engineer available
- [ ] Rollback plan ready

## 🔧 Troubleshooting

### Common Issues
```bash
# Check GitHub token
echo $GITHUB_TOKEN

# Check kubectl access
kubectl auth can-i get pods

# Check staging connectivity
curl -s $STAGING_HOST/api/v1/health

# View automation logs
tail -f artifacts/full_rollout_*/automation.log
```

### Manual Rollback Commands
```bash
# Istio rollback
kubectl -n prod delete -f k8s/istio/virtualservice-canary-10.yaml
kubectl -n prod rollout undo deploy/app

# Nginx rollback
kubectl -n prod apply -f k8s/nginx/upstream-canary-0.yaml
kubectl -n prod rollout undo deploy/app
```

## 📚 Documentation

- [Full Automation Guide](./AUTOMATION_README.md)
- [Production Runbook](./docs/runbook_prod_rollout.md)
- [Demo Script](./scripts/demo_automation.sh)

## 🆘 Support

For issues with the automation:
1. Check the preflight checklist
2. Review automation logs
3. Verify environment variables
4. Test with dry run mode
5. Check rollback scripts
