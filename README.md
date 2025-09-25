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

2. **Start the application:**
   ```bash
   python cli.py app start
   ```

3. **Start the bot:**
   ```bash
   python cli.py bot polling
   ```

4. **Run smoke tests:**
   ```bash
   python cli.py test smoke
   ```

5. **Load testing:**
   ```bash
   python cli.py test load
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

## Admin UI (server-served React + Tailwind)

- Admin frontend lives in `web/admin`. To develop:
```
cd web/admin
npm install
npm run dev
```
- To build static assets (served by FastAPI from `app/static/admin`):
```
cd web/admin
npm install
npm run build
```
- Seed a static super-admin (for staging/laptop server):
```
ADMIN_USERNAME=${ADMIN_USERNAME} ADMIN_PASSWORD=${ADMIN_PASSWORD} python app/scripts/seed_admin.py
```
- To disable Telegram admin commands in production, set `DISABLE_TELEGRAM_ADMIN_CMDS=true` in the environment.

## CLI Usage

The CricAlgo project now includes a unified CLI for all operations:

```bash
# Bot management
python cli.py bot polling          # Start bot in polling mode
python cli.py bot webhook          # Start bot in webhook mode
python cli.py bot managed          # Start bot with process management
python cli.py bot stop             # Stop running bot
python cli.py bot restart          # Restart bot
python cli.py bot status           # Check bot status

# Application management
python cli.py app start            # Start FastAPI application
python cli.py app dev              # Start in development mode

# Database management
python cli.py db migrate           # Run database migrations
python cli.py db upgrade           # Upgrade database

# Testing
python cli.py test smoke           # Run smoke tests
python cli.py test load             # Run load tests

# Help
python cli.py help                 # Show all available commands
```

## Documentation

- [Bot Documentation](docs/bot.md)
- [Runbook](docs/runbook.md)
- [Production Rollout Guide](docs/runbook_prod_rollout.md)
- [Development Rules](docs/DEVELOPMENT_RULES.md)

## License

[Add your license here]