# CricAlgo Full Automation Guide

## Overview

This guide covers the comprehensive automation system for CricAlgo's deployment pipeline, including PR creation, canary deployments, progressive rollouts, and release management.

## 🚀 Quick Start

### Prerequisites

1. **Required Tools:**
   - `git` - Version control
   - `curl` - HTTP client
   - `jq` - JSON processor
   - `kubectl` - Kubernetes CLI (for K8s deployments)
   - `k6` - Load testing (optional, Docker fallback available)

2. **Environment Variables:**
   ```bash
   export GITHUB_TOKEN="your_github_token"
   export STAGING_HOST="http://localhost:8000"
   export PROD_HOST="https://api.cricalgo.com"
   export DATABASE_URL="postgresql://user:pass@host:port/db"
   export REDIS_URL="redis://host:port"
   ```

3. **Optional Tools:**
   - `gh` - GitHub CLI (for enhanced PR management)
   - `pandoc` - For PDF generation
   - `psql` - For database health checks

### Basic Usage

```bash
# Dry run (recommended first)
./scripts/full_rollout_automation_enhanced.sh --dry-run

# Full deployment with Istio canary
./scripts/full_rollout_automation_enhanced.sh --apply-k8s

# Full deployment with Nginx canary
CANARY_STRATEGY=nginx ./scripts/full_rollout_automation_enhanced.sh --apply-k8s
```

## 📋 Scripts Overview

### 1. Full Rollout Automation (`full_rollout_automation_enhanced.sh`)

**Purpose:** Complete end-to-end deployment automation

**Features:**
- PR creation and CI validation
- Canary deployment with progressive rollout
- Automated testing and validation
- Release creation and artifact management
- Comprehensive rollback capabilities

**Usage:**
```bash
# Basic usage
./scripts/full_rollout_automation_enhanced.sh

# With options
./scripts/full_rollout_automation_enhanced.sh \
  --dry-run \
  --apply-k8s \
  --debug
```

**Options:**
- `--dry-run` - Run without making production changes
- `--apply-k8s` - Apply Kubernetes configurations
- `--skip-ci` - Skip waiting for CI checks
- `--force` - Force promotion despite CI failures
- `--debug` - Enable debug logging

### 2. Universal Rollback (`rollback_universal.sh`)

**Purpose:** Comprehensive rollback capabilities

**Features:**
- Istio canary rollback
- Nginx canary rollback
- Kubernetes resource cleanup
- Database rollbacks (if applicable)

**Usage:**
```bash
# Rollback Istio canary
./scripts/rollback_universal.sh istio

# Rollback Nginx canary
./scripts/rollback_universal.sh nginx

# Rollback all canary deployments
./scripts/rollback_universal.sh all

# Dry run
./scripts/rollback_universal.sh --dry-run istio
```

### 3. Enhanced Health Check (`health_check_enhanced.sh`)

**Purpose:** Comprehensive system health validation

**Features:**
- Application endpoint checks
- Database connectivity validation
- Redis connectivity validation
- Kubernetes resource status
- Load balancer health verification

**Usage:**
```bash
# Basic health check
./scripts/health_check_enhanced.sh

# JSON output
./scripts/health_check_enhanced.sh --format json

# Verbose logging
./scripts/health_check_enhanced.sh --verbose
```

### 4. Monitoring Check (`monitoring_check.sh`)

**Purpose:** Monitoring system validation

**Features:**
- Prometheus availability and targets
- Grafana dashboard validation
- Alert rule verification
- Application metrics endpoint checks

**Usage:**
```bash
# Basic monitoring check
./scripts/monitoring_check.sh

# Custom Prometheus URL
PROMETHEUS_URL=http://prometheus:9090 ./scripts/monitoring_check.sh
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GITHUB_TOKEN` | GitHub API token | - | Yes (for PR/Release) |
| `STAGING_HOST` | Staging environment URL | `http://localhost:8000` | No |
| `PROD_HOST` | Production environment URL | `https://api.cricalgo.com` | No |
| `DATABASE_URL` | Database connection string | - | No |
| `REDIS_URL` | Redis connection string | - | No |
| `K8S_NS_PROD` | Production namespace | `prod` | No |
| `K8S_NS_STAGING` | Staging namespace | `cricalgo-staging` | No |
| `CANARY_STRATEGY` | Canary strategy | `istio` | No |
| `DRY_RUN` | Enable dry run mode | `false` | No |
| `APPLY_K8S` | Apply Kubernetes configs | `false` | No |

### Canary Strategies

#### Istio Strategy
- Uses Istio VirtualService for traffic splitting
- Supports progressive rollout (10% → 25% → 50% → 100%)
- Requires Istio service mesh in cluster
- Configuration files: `k8s/istio/virtualservice-canary-*.yaml`

#### Nginx Strategy
- Uses Nginx upstream configuration for load balancing
- Supports progressive rollout (10% → 25% → 50% → 100%)
- Requires Nginx ingress controller
- Configuration files: `k8s/nginx/upstream-canary-*.yaml`

## 🚦 Deployment Process

### Phase 1: Pre-deployment
1. **Environment Validation**
   - Check required tools and dependencies
   - Validate environment variables
   - Verify git repository state

2. **Pre-flight Checks**
   - Ensure working tree is clean
   - Check branch existence
   - Validate manifest files
   - Verify remote configuration

3. **Backup Creation**
   - Backup Kubernetes manifests
   - Backup Docker Compose files
   - Backup automation scripts

### Phase 2: PR Creation
1. **Branch Creation**
   - Create feature branch from main
   - Commit current changes
   - Push branch to remote

2. **PR Creation**
   - Create pull request with automated title and body
   - Add appropriate labels and reviewers
   - Wait for CI validation

### Phase 3: Canary Deployment
1. **Initial Canary (10%)**
   - Apply canary configuration
   - Wait for deployment readiness
   - Run smoke tests

2. **Progressive Rollout**
   - Increase to 25% traffic
   - Run validation tests
   - Increase to 50% traffic
   - Run validation tests
   - Increase to 100% traffic
   - Run final validation

3. **Rollback on Failure**
   - Automatic rollback on test failures
   - Manual rollback capability
   - Comprehensive logging

### Phase 4: Release Management
1. **PR Merge**
   - Merge feature branch to main
   - Push merged changes

2. **Release Creation**
   - Create git tag
   - Push tag to remote
   - Create GitHub release

3. **Artifact Collection**
   - Collect deployment logs
   - Generate system information
   - Create runbook PDF
   - Package all artifacts

## 🧪 Testing

### Smoke Tests
- **Purpose:** Quick validation of basic functionality
- **Duration:** 60 seconds
- **Virtual Users:** 20
- **Targets:** Health endpoints, webhook submission

### Load Tests
- **Purpose:** Performance validation under load
- **Duration:** 5 minutes
- **Virtual Users:** 100
- **Targets:** All critical endpoints
- **Thresholds:** p95 < 2s, p99 < 5s, error rate < 0.5%

### Health Checks
- **Application:** HTTP endpoint validation
- **Database:** Connection and query validation
- **Redis:** Connection and ping validation
- **Kubernetes:** Resource status validation
- **Load Balancer:** Traffic distribution validation

## 📊 Monitoring

### Metrics Collection
- **Application Metrics:** Response times, error rates, throughput
- **Infrastructure Metrics:** CPU, memory, disk I/O, network
- **Database Metrics:** Connection pool, query performance
- **Kubernetes Metrics:** Pod status, resource utilization

### Alerting
- **Critical:** Error rate > 1%, p99 latency > 10s
- **Warning:** Error rate > 0.5%, p95 latency > 5s
- **Info:** CPU > 80%, Memory > 85%

### Dashboards
- **Application Dashboard:** Real-time application metrics
- **Infrastructure Dashboard:** System resource utilization
- **Database Dashboard:** Database performance metrics
- **Kubernetes Dashboard:** Cluster and pod status

## 🔄 Rollback Procedures

### Automatic Rollback
- Triggered on test failures
- Immediate traffic reversion
- Canary deployment cleanup
- Resource scaling

### Manual Rollback
```bash
# Rollback Istio canary
./scripts/rollback_universal.sh istio

# Rollback Nginx canary
./scripts/rollback_universal.sh nginx

# Rollback all canary deployments
./scripts/rollback_universal.sh all
```

### Rollback Verification
- Verify canary pods are terminated
- Confirm stable pods are running
- Check traffic routing
- Validate application health

## 📁 Artifacts

### Generated Artifacts
- **Automation Logs:** Complete execution logs
- **System Information:** Environment and configuration details
- **Kubernetes Information:** Pod status, services, deployments
- **Database Information:** Connection counts and status
- **Test Results:** Smoke test and load test results
- **Runbook PDF:** Generated deployment documentation

### Artifact Structure
```
artifacts/full_rollout_YYYYMMDDTHHMMSSZ/
├── automation.log
├── system_info.txt
├── k8s_info.txt
├── db_info.txt
├── pr_info.txt
├── ci_status.txt
├── smoke_*/
├── k6_promote_*/
├── final_status.json
└── runbook_prod_rollout.pdf
```

## 🛠️ Troubleshooting

### Common Issues

1. **CI Timeout**
   - Check CI pipeline status
   - Use `--skip-ci` flag if needed
   - Verify GitHub token permissions

2. **Canary Deployment Failure**
   - Check Kubernetes cluster connectivity
   - Verify manifest files exist
   - Check namespace permissions

3. **Test Failures**
   - Review test logs in artifacts
   - Check application health
   - Verify load balancer configuration

4. **Rollback Issues**
   - Use universal rollback script
   - Check Kubernetes resource status
   - Verify traffic routing

### Debug Mode
```bash
# Enable debug logging
DEBUG=true ./scripts/full_rollout_automation_enhanced.sh --debug

# Verbose health checks
./scripts/health_check_enhanced.sh --verbose
```

### Log Analysis
```bash
# View automation logs
tail -f artifacts/full_rollout_*/automation.log

# Check specific test results
cat artifacts/full_rollout_*/smoke_*/k6_smoke.txt
```

## 🔒 Security Considerations

### Access Control
- GitHub token with minimal required permissions
- Kubernetes RBAC for namespace access
- Database credentials in environment variables

### Secrets Management
- Use Kubernetes secrets for sensitive data
- Avoid hardcoding credentials in scripts
- Rotate tokens regularly

### Audit Logging
- Complete automation logs
- Git commit history
- Kubernetes audit logs
- Application access logs

## 📚 Best Practices

### Pre-deployment
- Always run dry-run first
- Verify all prerequisites
- Check backup procedures
- Review rollback plans

### During Deployment
- Monitor metrics continuously
- Watch for alert notifications
- Be prepared for manual intervention
- Document any issues

### Post-deployment
- Verify all systems healthy
- Update monitoring baselines
- Document lessons learned
- Update runbooks if needed

### Regular Maintenance
- Update automation scripts
- Review and test rollback procedures
- Update monitoring thresholds
- Conduct disaster recovery drills

## 🤝 Contributing

### Script Development
- Follow existing code style
- Add comprehensive error handling
- Include detailed logging
- Write clear documentation

### Testing
- Test all script variations
- Validate error scenarios
- Test rollback procedures
- Verify artifact generation

### Documentation
- Update this guide for changes
- Add inline code comments
- Create troubleshooting guides
- Maintain runbook accuracy

## 📞 Support

### Getting Help
- Check automation logs first
- Review troubleshooting section
- Consult team documentation
- Escalate to DevOps team

### Emergency Procedures
- Use universal rollback script
- Check system health status
- Verify backup procedures
- Contact on-call engineer

---

**Note:** This automation system is designed for production use with comprehensive safety features. Always test in staging environments before production deployment.
