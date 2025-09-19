# CricAlgo - Cricket Algorithm Trading Bot

A FastAPI-based cricket algorithm trading bot with Telegram integration, built for automated contest management and trading strategies.

## Features

- 🏏 **Cricket Contest Management** - Automated contest creation and management
- 💰 **Multi-Currency Support** - USDT (BEP20) integration
- 🤖 **Telegram Bot** - User-friendly Telegram interface
- 🗄️ **PostgreSQL Database** - Robust data storage with Alembic migrations
- ⚡ **Redis Caching** - High-performance caching layer
- 🐳 **Docker Support** - Easy deployment and development
- 🧪 **Testing & CI/CD** - Comprehensive testing and automated CI

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Git

### Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd CricAlgo
   ```

2. **Copy environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start development environment**
   ```bash
   make dev
   # or
   docker-compose up --build
   ```

4. **Access the application**
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Health Check: http://localhost:8000/api/v1/health

### Local Development (without Docker)

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start PostgreSQL and Redis**
   ```bash
   # Using Docker Compose for services only
   docker-compose up postgres redis
   ```

3. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

4. **Start the application**
   ```bash
   python -m app.main
   # or
   uvicorn app.main:app --reload
   ```

## Project Structure

```
/
├── app/                    # Application code
│   ├── api/               # API endpoints
│   ├── bot/               # Telegram bot
│   ├── core/              # Core configuration
│   └── db/                # Database models and connections
├── alembic/               # Database migrations
├── tests/                 # Test suite
├── scripts/               # Utility scripts
├── .github/workflows/     # CI/CD workflows
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Development environment
└── requirements.txt       # Python dependencies
```

## Available Commands

### Development
- `make dev` - Start development environment
- `make build` - Build Docker image
- `make test` - Run tests
- `make lint` - Run linting
- `make format` - Format code
- `make clean` - Clean up Docker resources

### Database
- `make migrate` - Run database migrations
- `make migrate-create` - Create new migration
- `make shell` - Open shell in app container

## API Endpoints

### Health Check
- `GET /api/v1/health` - Application health status

### Documentation
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)

## Configuration

The application uses environment variables for configuration. Copy `.env.example` to `.env` and update the values:

```env
# Application
APP_NAME=CricAlgo
APP_ENV=development
DEBUG=true

# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/cricalgo
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# Redis
REDIS_URL=redis://localhost:6379/0

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/webhook

# Security
SECRET_KEY=your-secret-key-change-in-production
```

### Database Configuration

The application uses PostgreSQL with connection pooling for optimal performance:

- **DB_POOL_SIZE**: Number of persistent connections to maintain (default: 10)
- **DB_MAX_OVERFLOW**: Additional connections that can be created on demand (default: 20)
- **Pool Pre-ping**: Enabled to verify connections before use
- **Pool Recycle**: Connections are recycled every 3600 seconds (1 hour)

## Database Schema

The application uses PostgreSQL with the following main entities:

- **Users** - Telegram users and their profiles
- **Wallets** - Multi-bucket wallet system (deposit, winning, bonus)
- **Contests** - Trading contests and competitions
- **Entries** - User participation in contests
- **Transactions** - Complete transaction ledger
- **Deposit/Withdraw Requests** - Financial operations

### Database Migrations

The application uses Alembic for database migrations:

```bash
# Run migrations
make migrate

# Create new migration
make migrate-create message="description of changes"

# Check migration status
alembic current

# View migration history
alembic history
```

### Creating Admin User

To create an initial admin user for the application:

```bash
# Set required environment variables
export SEED_ADMIN_USERNAME="admin"
export SEED_ADMIN_EMAIL="admin@cricalgo.com"
export SEED_ADMIN_PASSWORD="your_secure_password"  # Optional - will generate if not provided

# Run the admin creation script
python scripts/create_admin.py
```

The script will:
- Create an admin user with hashed password
- Generate a TOTP secret for 2FA
- Print QR code URL for authenticator app setup
- Create a regular user account and wallet for the admin

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_health.py

# Run database model tests
pytest tests/test_db_models.py

# Run tests with PostgreSQL (requires running database)
docker-compose up -d postgres
pytest tests/test_db_models.py
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions, please open an issue in the GitHub repository.
