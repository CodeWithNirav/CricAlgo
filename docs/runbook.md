# CricAlgo Incident Response Runbook

## Emergency Contacts

- **On-call Engineer**: +1-XXX-XXX-XXXX
- **DevOps Lead**: +1-XXX-XXX-XXXX
- **Security Team**: security@cricalgo.com
- **Management**: management@cricalgo.com

## Incident Severity Levels

### P0 - Critical (Response: 15 minutes)
- Complete service outage
- Data loss or corruption
- Security breach
- Financial impact > $1000

### P1 - High (Response: 1 hour)
- Partial service outage
- Performance degradation > 50%
- Bot not responding
- Database connectivity issues

### P2 - Medium (Response: 4 hours)
- Minor performance issues
- Non-critical feature failures
- Monitoring alerts

### P3 - Low (Response: 24 hours)
- Cosmetic issues
- Documentation updates
- Feature requests

## Common Incidents and Responses

### 1. Complete Service Outage

**Symptoms:**
- All endpoints returning 5xx errors
- Health checks failing
- Monitoring showing 0% uptime

**Immediate Actions:**
1. Check service status: `kubectl get pods -n cricalgo-staging`
2. Check logs: `kubectl logs -f deployment/cricalgo-app -n cricalgo-staging`
3. Check database connectivity: `kubectl exec -it postgres-pod -- psql -U postgres -d cricalgo`
4. Check Redis connectivity: `kubectl exec -it redis-pod -- redis-cli ping`

**Resolution Steps:**
1. If pods are down, restart: `kubectl rollout restart deployment/cricalgo-app -n cricalgo-staging`
2. If database issues, check connection strings and credentials
3. If Redis issues, check memory usage and restart if needed
4. If persistent issues, rollback to previous version

**Rollback Procedure:**
```bash
# Get previous deployment
kubectl rollout history deployment/cricalgo-app -n cricalgo-staging

# Rollback to previous version
kubectl rollout undo deployment/cricalgo-app -n cricalgo-staging

# Verify rollback
kubectl rollout status deployment/cricalgo-app -n cricalgo-staging
```

### 2. Bot Not Responding

**Symptoms:**
- Telegram bot not responding to commands
- Bot status showing as down in monitoring

**Immediate Actions:**
1. Check bot pod status: `kubectl get pods -l app=cricalgo-bot -n cricalgo-staging`
2. Check bot logs: `kubectl logs -f deployment/cricalgo-bot -n cricalgo-staging`
3. Verify bot token is valid
4. Check Redis connectivity for bot

**Resolution Steps:**
1. Restart bot deployment: `kubectl rollout restart deployment/cricalgo-bot -n cricalgo-staging`
2. Verify bot token in secrets: `kubectl get secret cricalgo-secrets -n cricalgo-staging -o yaml`
3. Test bot token with Telegram API
4. Check webhook configuration if using webhook mode

### 3. Database Connectivity Issues

**Symptoms:**
- Database connection errors in logs
- 5xx errors on database-dependent endpoints
- Database pod not ready

**Immediate Actions:**
1. Check database pod status: `kubectl get pods -l app=postgres -n cricalgo-staging`
2. Check database logs: `kubectl logs -f deployment/postgres -n cricalgo-staging`
3. Check database disk space: `kubectl exec -it postgres-pod -- df -h`
4. Check database connections: `kubectl exec -it postgres-pod -- psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"`

**Resolution Steps:**
1. If disk full, clean up old data or increase storage
2. If connection limit reached, restart database or increase max connections
3. If database corrupted, restore from backup
4. If persistent issues, scale database or migrate to new instance

### 4. High Error Rate

**Symptoms:**
- Error rate > 5% for 5+ minutes
- Multiple 5xx errors in logs
- User complaints about failures

**Immediate Actions:**
1. Check error logs: `kubectl logs -f deployment/cricalgo-app -n cricalgo-staging | grep ERROR`
2. Check resource usage: `kubectl top pods -n cricalgo-staging`
3. Check database performance: `kubectl exec -it postgres-pod -- psql -U postgres -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"`
4. Check Redis performance: `kubectl exec -it redis-pod -- redis-cli info stats`

**Resolution Steps:**
1. If resource limits hit, scale up pods or increase limits
2. If database slow, check for long-running queries and optimize
3. If Redis slow, check memory usage and restart if needed
4. If application errors, check recent deployments and rollback if needed

### 5. Security Incident

**Symptoms:**
- Unusual access patterns
- Failed authentication attempts
- Data access from unknown sources
- Security alerts from monitoring

**Immediate Actions:**
1. **DO NOT** attempt to fix without security team approval
2. Document all evidence
3. Preserve logs and system state
4. Contact security team immediately
5. If data breach suspected, notify management and legal

**Resolution Steps:**
1. Follow security team guidance
2. Implement recommended security measures
3. Update security policies if needed
4. Conduct post-incident review

## Monitoring and Alerting

### Key Metrics to Monitor
- HTTP request rate and response time
- Error rate (should be < 5%)
- Database connection count
- Redis memory usage
- Bot response time
- Queue depth for background jobs

### Alert Thresholds
- Error rate > 5% for 5 minutes
- Response time > 2 seconds for 5 minutes
- Database connections > 80% of max
- Redis memory > 80% of limit
- Bot down for > 5 minutes

### Escalation Procedures
1. **First 15 minutes**: On-call engineer investigates
2. **15-30 minutes**: Escalate to DevOps lead
3. **30+ minutes**: Escalate to management
4. **Security incidents**: Immediate escalation to security team

## Maintenance Procedures

### Regular Maintenance
- **Daily**: Check monitoring dashboards
- **Weekly**: Review logs for errors and performance issues
- **Monthly**: Update dependencies and security patches
- **Quarterly**: Review and update runbook

### Scheduled Maintenance
- **Database backups**: Daily at 2 AM UTC
- **Log rotation**: Weekly
- **Security updates**: Monthly
- **Dependency updates**: Quarterly

### Pre-maintenance Checklist
- [ ] Notify users of maintenance window
- [ ] Verify backups are current
- [ ] Test rollback procedures
- [ ] Have on-call engineer available
- [ ] Monitor during maintenance

## Recovery Procedures

### Database Recovery
1. Stop application services
2. Restore database from backup
3. Verify data integrity
4. Restart application services
5. Run smoke tests

### Application Recovery
1. Identify last known good version
2. Rollback to that version
3. Verify all services are healthy
4. Run integration tests
5. Monitor for 1 hour

### Bot Recovery
1. Verify bot token is valid
2. Restart bot service
3. Test bot commands
4. Verify webhook configuration (if applicable)
5. Monitor bot activity

## Post-Incident Procedures

### Immediate Post-Incident
1. Verify all services are healthy
2. Notify stakeholders of resolution
3. Document incident details
4. Update monitoring if needed

### Within 24 Hours
1. Conduct post-incident review
2. Identify root cause
3. Document lessons learned
4. Update runbook if needed
5. Implement preventive measures

### Within 1 Week
1. Complete incident report
2. Review and update procedures
3. Train team on new procedures
4. Update documentation

## Emergency Contacts and Escalation

### Internal Contacts
- **On-call Engineer**: Primary responder
- **DevOps Lead**: Technical escalation
- **Security Team**: Security incidents
- **Management**: Business impact

### External Contacts
- **Cloud Provider Support**: Infrastructure issues
- **Database Support**: Database issues
- **Monitoring Service**: Alerting issues
- **Legal Team**: Data breach incidents

### Communication Channels
- **Slack**: #incidents channel
- **Email**: incidents@cricalgo.com
- **Phone**: Emergency hotline
- **Status Page**: status.cricalgo.com

## Appendix

### Useful Commands
```bash
# Check pod status
kubectl get pods -n cricalgo-staging

# Check logs
kubectl logs -f deployment/cricalgo-app -n cricalgo-staging

# Restart deployment
kubectl rollout restart deployment/cricalgo-app -n cricalgo-staging

# Check service status
kubectl get services -n cricalgo-staging

# Check ingress
kubectl get ingress -n cricalgo-staging

# Check secrets
kubectl get secrets -n cricalgo-staging

# Scale deployment
kubectl scale deployment cricalgo-app --replicas=3 -n cricalgo-staging
```

### Monitoring URLs
- **Grafana**: https://grafana-staging.cricalgo.com
- **Prometheus**: https://prometheus-staging.cricalgo.com
- **Kibana**: https://kibana-staging.cricalgo.com
- **Status Page**: https://status.cricalgo.com
