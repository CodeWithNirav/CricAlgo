# CricAlgo Service Management

Simple scripts to manage CricAlgo services (database, Redis, application server).

## Quick Start

### Windows (Batch File)
```bash
# Start all services
.\manage_services.bat start

# Stop all services  
.\manage_services.bat stop

# Restart all services
.\manage_services.bat restart

# Check service status
.\manage_services.bat status

# View recent logs
.\manage_services.bat logs
```

### Windows (PowerShell)
```powershell
# Start all services
.\manage_services.ps1 start

# Stop all services
.\manage_services.ps1 stop

# Restart all services
.\manage_services.ps1 restart

# Check service status
.\manage_services.ps1 status

# View recent logs
.\manage_services.ps1 logs
```

## Service URLs

After starting services, you can access:

- **Admin Dashboard**: http://localhost:8000/admin
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/v1/health
- **Database**: localhost:5432
- **Redis**: localhost:6379

## Services Included

- **app**: Main FastAPI application server
- **postgres**: PostgreSQL database
- **redis**: Redis cache and message broker
- **worker**: Celery background worker
- **bot**: Telegram bot (if enabled)

## Troubleshooting

If services fail to start:

1. Check Docker is running
2. Check ports 8000, 5432, 6379 are available
3. Run `.\manage_services.bat logs` to see error messages
4. Try `.\manage_services.bat restart` to restart everything

## Manual Commands

If you prefer to use Docker Compose directly:

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs

# Check status
docker-compose ps
```
