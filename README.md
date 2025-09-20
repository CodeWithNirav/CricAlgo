# CricAlgo

Cricket Algorithm Trading Platform with Performance Optimizations

## Overview

CricAlgo is a comprehensive cricket trading platform that combines real-time data processing, algorithmic trading strategies, and high-performance webhook handling.

## Features

- **High-Performance Webhooks**: Quick-return pattern with async processing
- **Horizontal Scaling**: Nginx load balancing with multiple app instances
- **Database Optimization**: Environment-configured connection pooling
- **Monitoring & Alerting**: Prometheus metrics and alert rules
- **Kubernetes Ready**: HPA manifests for auto-scaling
- **Comprehensive Testing**: Smoke tests and load testing with k6

## Quick Start

### Local Development

1. **Start the services:**
   ```bash
   docker-compose up -d
   ```

2. **Run smoke tests:**
   ```bash
   ./scripts/smoke_and_checks.sh
   ```

3. **Load testing:**
   ```bash
   k6 run --vus 100 --duration 5m load/k6/webhook_test.js
   ```

### Staging Environment

1. **Start with load balancing:**
   ```bash
   docker-compose -f docker-compose.staging.yml up -d --build nginx app1 app2 app3
   docker-compose -f docker-compose.staging.yml up -d --scale worker=4
   ```

## Performance Optimizations

This repository includes comprehensive performance optimizations:

- Webhook quick-return pattern
- Horizontal scaling with nginx
- Database connection pooling
- Celery task instrumentation
- Kubernetes HPA configuration
- Prometheus monitoring and alerting

## Documentation

- [Performance Rollout Summary](PERFORMANCE_ROLLOUT_SUMMARY.md)
- [Bot Documentation](docs/bot.md)
- [Runbook](docs/runbook.md)
- [Production Rollout Guide](docs/runbook_prod_rollout.md)

## License

[Add your license here]