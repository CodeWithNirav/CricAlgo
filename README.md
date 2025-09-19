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
- `make dev` - Start development environment (includes worker)
- `make build` - Build Docker image
- `make test` - Run tests
- `make test-unit` - Run unit tests only
- `make test-integration` - Run integration tests with PostgreSQL
- `make test-e2e` - Run end-to-end tests with full stack
- `make test-coverage` - Run tests with coverage report
- `make lint` - Run linting
- `make format` - Format code
- `make clean` - Clean up Docker resources

### Database
- `make migrate` - Run database migrations
- `make migrate-create` - Create new migration
- `make shell` - Open shell in app container

### Worker
- `make worker` - Start Celery worker
- `make worker-logs` - View worker logs

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login user (admin requires TOTP)
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user info

### Wallet
- `GET /api/v1/wallet/` - Get wallet balances
- `POST /api/v1/wallet/withdraw` - Create withdrawal request
- `GET /api/v1/wallet/transactions` - Get wallet transactions

### Contests
- `GET /api/v1/contest/` - List contests
- `GET /api/v1/contest/{id}` - Get contest details
- `POST /api/v1/contest/{id}/join` - Join contest
- `POST /api/v1/contest/admin/contest` - Create contest (admin)
- `POST /api/v1/contest/admin/{id}/settle` - Settle contest (admin)

### Admin
- `GET /api/v1/admin/users` - List users (admin)
- `GET /api/v1/admin/users/{id}` - Get user details (admin)
- `POST /api/v1/admin/transactions/{id}/approve` - Approve withdrawal (admin)
- `GET /api/v1/admin/audit-logs` - Get audit logs (admin)
- `GET /api/v1/admin/stats` - Get admin statistics (admin)

### Webhooks
- `POST /api/v1/webhooks/bep20` - BEP20 transaction confirmations
- `GET /api/v1/webhooks/health` - Webhook health check

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

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# JWT Authentication
JWT_SECRET_KEY=your-jwt-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Rate Limiting
RATE_LIMIT_REQUESTS=30
RATE_LIMIT_WINDOW_SECONDS=60

# Business Settings
PLATFORM_COMMISSION_PCT=5.0
CONFIRMATION_THRESHOLD=3
CURRENCY=USDT

# Webhooks
WEBHOOK_SECRET=your-webhook-secret-key

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

### Background Worker

The application uses Celery for background task processing:

```bash
# Start worker with Docker Compose
docker-compose up worker

# Or start worker manually
celery -A app.celery_app.celery worker --loglevel=info

# Start worker with specific queues
celery -A app.celery_app.celery worker --loglevel=info -Q deposits,withdrawals,payouts
```

### Background Tasks

The application includes several background tasks:

- **`process_deposit`** - Processes deposit confirmations and credits wallets
- **`process_withdrawal`** - Handles withdrawal requests and external transfers
- **`compute_and_distribute_payouts`** - Calculates and distributes contest prizes

### Rate Limiting

The application includes rate limiting middleware:

- **Webhook endpoints**: 10 requests per minute per IP
- **Contest joins**: 5 joins per 5 minutes per user
- **Auth endpoints**: 10 attempts per 5 minutes per IP
- **Withdrawals**: 3 withdrawals per hour per user

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

The project includes comprehensive testing with unit, integration, and end-to-end tests.

### Test Types

- **Unit Tests** - Fast, isolated tests using SQLite in-memory database
- **Integration Tests** - Tests with real PostgreSQL database and Redis
- **E2E Tests** - Full application flow tests with fake blockchain service

### Running Tests

#### Quick Test Commands

```bash
# Run all tests (unit tests only by default)
make test

# Run unit tests only (fast, SQLite)
make test-unit

# Run integration tests (PostgreSQL + Redis)
make test-integration

# Run E2E tests (full stack with fake blockchain)
make test-e2e

# Run tests with coverage report
make test-coverage
```

#### Manual Test Execution

```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/ -m "not integration and not e2e"  # Unit tests only
pytest tests/integration/                       # Integration tests only
pytest tests/e2e/                              # E2E tests only

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/test_health.py
pytest tests/integration/test_wallet_repo_integration.py
```

#### Test Environment Setup

For integration and E2E tests, you can start the test services manually:

```bash
# Start test database and Redis
make test-services

# Run tests with custom database URL
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5433/cricalgo_test \
REDIS_URL=redis://localhost:6380/1 \
pytest tests/integration/

# Stop test services
make test-services-stop
```

#### E2E Test Requirements

E2E tests require the `RUN_E2E=1` environment variable to run:

```bash
# Enable E2E tests
RUN_E2E=1 pytest tests/e2e/

# Or use the make command (automatically sets the flag)
make test-e2e
```

### Test Configuration

#### Database URLs

- **Unit Tests**: `sqlite+aiosqlite:///:memory:` (fast, in-memory)
- **Integration Tests**: `postgresql+asyncpg://postgres:password@localhost:5433/cricalgo_test`
- **E2E Tests**: Same as integration tests

#### Test Markers

Tests are marked with pytest markers for easy filtering:

- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.slow` - Slow running tests
- `@pytest.mark.requires_docker` - Tests requiring Docker

#### Test Fixtures

The test suite includes comprehensive fixtures in `tests/conftest.py`:

- `async_session` - Database session with transaction rollback
- `redis_client` - Redis client with test database isolation
- `test_app` - FastAPI app with test dependencies
- `test_client` - HTTP test client
- `test_user` - Sample user with wallet
- `test_user_with_balance` - User with pre-loaded balances

### CI/CD Testing

The project uses GitHub Actions for automated testing:

- **Unit Tests** - Run on every push (fast, ~2 minutes)
- **Integration Tests** - Run on every push (PostgreSQL + Redis, ~5 minutes)
- **E2E Tests** - Run on PRs and main branch (full stack, ~10 minutes)
- **Docker Build Test** - Verify Docker image builds and runs
- **Security Scan** - Safety and Bandit security checks

View the [CI workflow](.github/workflows/ci.yml) for detailed configuration.

### Test Data and Fixtures

#### Database Fixtures (`tests/fixtures/database.py`)

```python
# Create test user with wallet
user = await create_test_user_with_wallet(session, 12345, "testuser")

# Create user with specific balances
user = await create_test_user_with_balance(
    session, 12345, "richuser",
    deposit_balance=Decimal('100.00'),
    bonus_balance=Decimal('50.00')
)

# Create test transaction
tx = await create_test_transaction(
    session, user.id, "deposit", Decimal('100.00')
)
```

#### Redis Fixtures (`tests/fixtures/redis.py`)

```python
# Redis test helper
helper = RedisTestHelper(redis_client)

# Set idempotency key
await helper.set_idempotency_key("tx_hash_123")

# Check if processed
is_processed = await helper.check_idempotency_key("tx_hash_123")
```

#### Webhook Fixtures (`tests/fixtures/webhooks.py`)

```python
# Create webhook payload
payload = create_deposit_webhook_payload(
    tx_hash="0x123...",
    amount="100.00",
    confirmations=12
)

# Send webhook
webhook_helper = WebhookTestHelper(test_client)
response = await webhook_helper.send_deposit_webhook(
    tx_hash="0x123...",
    amount="100.00"
)
```

### Fake Blockchain Service

E2E tests use a fake blockchain service (`tests/e2e/fake_blockchain_service.py`) that simulates blockchain webhook callbacks:

```bash
# Start fake blockchain service manually
python tests/e2e/fake_blockchain_service.py

# Service runs on http://localhost:8081
curl http://localhost:8081/  # Health check
curl http://localhost:8081/webhooks  # List received webhooks
```

### Troubleshooting Tests

#### Common Issues

1. **Port conflicts**: Test services use different ports (5433, 6380, 8001, 8081)
2. **Database not ready**: Wait for health checks before running tests
3. **Redis connection**: Ensure Redis is running and accessible
4. **E2E tests skipped**: Set `RUN_E2E=1` environment variable

#### Debug Commands

```bash
# Check test services status
docker-compose -f docker-compose.test.yml ps

# View test logs
docker-compose -f docker-compose.test.yml logs

# Run tests with verbose output
pytest tests/ -v -s

# Run single test with debugging
pytest tests/integration/test_wallet_repo_integration.py::test_atomic_balance_updates -v -s
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
