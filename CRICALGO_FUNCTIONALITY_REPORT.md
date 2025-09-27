# CricAlgo - Comprehensive Functionality Report

## Executive Summary

CricAlgo is a sophisticated cricket trading platform that combines real-time data processing, algorithmic trading strategies, and high-performance webhook handling. The platform is built using modern technologies including FastAPI, PostgreSQL, Redis, Celery, and Telegram Bot API, with comprehensive monitoring and deployment capabilities.

## System Architecture

### Core Technologies
- **Backend**: FastAPI with async/await support
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Caching**: Redis for session management and rate limiting
- **Message Queue**: Celery with Redis broker
- **Bot Framework**: aiogram 3.x for Telegram integration
- **Monitoring**: Prometheus metrics and Sentry error tracking
- **Deployment**: Docker, Kubernetes, Nginx load balancing

### Project Structure
```
CricAlgo/
├── app/                    # Main application code
│   ├── api/               # API endpoints and routes
│   ├── bot/               # Telegram bot handlers
│   ├── core/              # Core configuration and utilities
│   ├── db/                # Database configuration
│   ├── models/            # SQLAlchemy data models
│   ├── repos/             # Repository pattern for data access
│   ├── services/          # Business logic services
│   ├── tasks/             # Celery background tasks
│   └── middleware/        # Custom middleware
├── web/admin/             # React admin dashboard
├── k8s/                   # Kubernetes deployment manifests
├── monitoring/            # Prometheus and Grafana configs
└── scripts/               # Deployment and testing scripts
```

## Core Functionality

### 1. User Management System

#### User Registration & Authentication
- **JWT-based authentication** with access and refresh tokens
- **Telegram ID integration** for seamless bot access
- **Invitation code system** for controlled user access
- **Multi-factor authentication** (TOTP) for admin users
- **User status management** (ACTIVE, FROZEN, DISABLED)

#### User Data Model
```python
class User:
    id: UUID (Primary Key)
    telegram_id: BigInteger (Unique)
    username: String(48) (Unique)
    status: UserStatus (ACTIVE/FROZEN/DISABLED)
    created_at: DateTime
```

### 2. Wallet & Financial System

#### Multi-Balance Wallet Architecture
- **Deposit Balance**: User-deposited funds (withdrawable)
- **Winning Balance**: Contest winnings (withdrawable)
- **Bonus Balance**: Promotional credits (non-withdrawable)
- **Held Balance**: Funds pending withdrawal approval

#### Financial Operations
- **Atomic balance updates** with database transactions
- **Deposit processing** with blockchain verification
- **Withdrawal requests** with admin approval workflow
- **Contest entry fee deduction** with balance validation
- **Prize distribution** to winning balance

#### Wallet Data Model
```python
class Wallet:
    user_id: UUID (Foreign Key)
    deposit_balance: Decimal(30,8)
    winning_balance: Decimal(30,8)
    bonus_balance: Decimal(30,8)
    held_balance: Decimal(30,8)
    updated_at: DateTime
```

### 3. Contest System

#### Contest Management
- **Dynamic contest creation** with configurable parameters
- **Prize structure configuration** with percentage-based distribution
- **Entry fee management** with currency support
- **Player limit controls** with automatic closure
- **Contest status tracking** (OPEN, CLOSED, SETTLED, CANCELLED)

#### Contest Data Model
```python
class Contest:
    id: UUID (Primary Key)
    match_id: UUID (Foreign Key)
    code: String(56) (Unique)
    title: String(255)
    entry_fee: Decimal(30,8)
    max_players: Integer
    prize_structure: JSON
    commission_pct: Decimal(5,2)
    status: ContestStatus
    created_at: DateTime
```

#### Contest Entry System
- **Atomic contest joining** with wallet debit
- **Duplicate entry prevention** with database constraints
- **Entry validation** with balance and capacity checks
- **Entry tracking** with unique entry codes

### 4. Match Management

#### Match Data Model
```python
class Match:
    id: UUID (Primary Key)
    external_id: String(128)
    title: String(255)
    start_time: DateTime
    status: MatchStatus (SCHEDULED/LIVE/FINISHED)
    created_at: DateTime
```

### 5. Transaction System

#### Transaction Types
- **Deposit transactions** with blockchain verification
- **Withdrawal transactions** with admin approval
- **Contest entry fees** with automatic deduction
- **Prize payouts** with winning balance credit
- **Internal transfers** for system operations

#### Transaction Data Model
```python
class Transaction:
    id: UUID (Primary Key)
    user_id: UUID (Foreign Key)
    tx_type: String(64)
    amount: Decimal(30,8)
    currency: String(16)
    related_entity: String(64)
    related_id: UUID
    tx_metadata: JSON
    created_at: DateTime
```

## API Endpoints

### Authentication Endpoints
- `POST /api/v1/register` - User registration
- `POST /api/v1/login` - User login with JWT tokens
- `POST /api/v1/refresh` - Token refresh
- `GET /api/v1/me` - Current user information

### Wallet Endpoints
- `GET /api/v1/wallet/` - Get wallet balance
- `POST /api/v1/wallet/withdraw` - Create withdrawal request
- `GET /api/v1/wallet/transactions` - Get transaction history
- `POST /api/v1/wallet/admin/credit-deposit` - Admin credit deposit
- `POST /api/v1/wallet/admin/credit-winning` - Admin credit winning
- `POST /api/v1/wallet/admin/update-balances` - Admin update balances

### Contest Endpoints
- `POST /api/v1/admin/contest` - Create contest (admin only)
- `POST /api/v1/contest/{contest_id}/join` - Join contest
- `POST /api/v1/admin/{contest_id}/settle` - Settle contest (admin only)
- `POST /api/v1/admin/{contest_id}/cancel` - Cancel contest (admin only)
- `GET /api/v1/` - List contests
- `GET /api/v1/contest/{contest_id}` - Get contest details

### Webhook Endpoints
- `POST /api/v1/webhooks/deposit` - Deposit webhook processing
- `POST /api/v1/webhooks/withdrawal` - Withdrawal webhook processing

### Admin Endpoints
- `GET /api/v1/admin/users` - List users
- `GET /api/v1/admin/contests` - List all contests
- `GET /api/v1/admin/transactions` - List all transactions
- `POST /api/v1/admin/matches` - Create match
- `GET /api/v1/admin/matches` - List matches

## Telegram Bot Functionality

### User Commands
- `/start [invite_code]` - Register or login with invitation code
- `/balance` - Check wallet balance
- `/deposit` - Get deposit instructions
- `/contests` - View available contests
- `/withdraw` - Request withdrawal
- `/menu` - Show main menu
- `/help` - Show available commands

### Bot Features
- **Interactive menus** with inline keyboards
- **State management** for multi-step processes
- **Rate limiting** to prevent abuse
- **Error handling** with user-friendly messages
- **Real-time notifications** for important events
- **Admin commands** for contest management

### Bot States
- `waiting_for_invite_code` - Invitation code input
- `waiting_for_deposit_amount` - Deposit amount input
- `waiting_for_deposit_tx_hash` - Transaction hash input
- `waiting_for_withdrawal_amount` - Withdrawal amount input
- `waiting_for_withdrawal_address` - Withdrawal address input

## Background Tasks & Automation

### Celery Task Queue
- **Deposit processing** with blockchain verification
- **Withdrawal processing** with external API calls
- **Contest settlement** with prize distribution
- **Webhook processing** for async operations
- **Notification sending** for user alerts

### Task Types
1. **Deposit Tasks**
   - `process_deposit` - Verify and credit deposits
   - `process_deposit_async` - Async deposit processing

2. **Withdrawal Tasks**
   - `process_withdrawal` - Process withdrawal requests
   - External API integration for actual transfers

3. **Contest Tasks**
   - `compute_and_distribute_payouts` - Calculate and distribute prizes
   - Contest settlement with winner ranking

4. **Webhook Tasks**
   - `process_webhook_async` - Process incoming webhooks
   - Idempotency handling for duplicate webhooks

## Business Logic Services

### Blockchain Service
- **Transaction verification** with BSC integration
- **Confirmation tracking** with configurable thresholds
- **Mock provider** for testing and development
- **Real BSC provider** for production use

### Settlement Service
- **Deterministic payout calculation** based on prize structure
- **Commission handling** with platform fees
- **Winner ranking** with admin-selected results
- **Atomic settlement** with rollback capabilities
- **Audit logging** for all settlement operations

## Database Schema

### Core Tables
1. **users** - User accounts and authentication
2. **wallets** - Multi-balance wallet system
3. **contests** - Contest configuration and management
4. **entries** - Contest participation records
5. **matches** - Cricket match information
6. **transactions** - Financial transaction history
7. **withdrawals** - Withdrawal request tracking
8. **invitation_codes** - Access control system
9. **audit_logs** - System activity logging
10. **admins** - Admin user management

### Key Relationships
- Users have one Wallet
- Contests belong to Matches
- Users can have multiple Contest Entries
- Transactions track all financial activities
- Audit logs record all system actions

## Security Features

### Authentication & Authorization
- **JWT tokens** with configurable expiration
- **Role-based access control** (User/Admin)
- **TOTP authentication** for admin users
- **Rate limiting** on API endpoints and bot commands
- **Invitation code system** for controlled access

### Data Protection
- **Password hashing** with bcrypt
- **SQL injection prevention** with SQLAlchemy ORM
- **Input validation** with Pydantic models
- **CORS configuration** for web security
- **Environment-based configuration** for secrets

## Monitoring & Observability

### Metrics Collection
- **Prometheus metrics** for system monitoring
- **Request counting** by endpoint and status
- **Response time tracking** with histograms
- **Active connection monitoring** with gauges
- **Custom business metrics** for deposits, contests, etc.

### Error Tracking
- **Sentry integration** for error monitoring
- **Structured logging** with configurable levels
- **Audit trail** for all financial operations
- **Health check endpoints** for system status

### Performance Monitoring
- **Database query optimization** with connection pooling
- **Redis caching** for session and rate limiting
- **Async processing** with Celery workers
- **Load balancing** with Nginx configuration

## Deployment & Infrastructure

### Containerization
- **Docker containers** for all services
- **Multi-stage builds** for optimized images
- **Environment-specific configurations**
- **Health checks** and restart policies

### Kubernetes Deployment
- **Horizontal Pod Autoscaling** (HPA)
- **Service mesh** with Istio
- **ConfigMaps** for configuration management
- **Secrets** for sensitive data
- **Ingress** for external access

### Load Balancing
- **Nginx load balancer** with multiple app instances
- **Sticky sessions** for bot state management
- **Health checks** for backend services
- **SSL termination** and security headers

## Testing & Quality Assurance

### Test Coverage
- **Unit tests** for business logic
- **Integration tests** for API endpoints
- **End-to-end tests** for complete workflows
- **Load testing** with k6 for performance validation

### Development Tools
- **Ruff** for code linting and formatting
- **Black** for code formatting
- **Pytest** for test execution
- **Coverage reporting** for test metrics

## Admin Dashboard

### React-based Admin UI
- **User management** with search and filtering
- **Contest management** with creation and settlement
- **Transaction monitoring** with status tracking
- **Financial reporting** with balance summaries
- **Match management** with scheduling
- **Audit log viewing** for system activity

### Admin Features
- **Real-time data updates** with WebSocket connections
- **Bulk operations** for efficient management
- **Export functionality** for reports
- **Role-based permissions** for different admin levels

## Key Features Summary

### User Experience
1. **Seamless Telegram integration** with interactive menus
2. **Multi-balance wallet system** with clear fund separation
3. **Contest participation** with real-time updates
4. **Withdrawal requests** with admin approval workflow
5. **Invitation-based access** for controlled user growth

### Admin Experience
1. **Comprehensive dashboard** for system management
2. **Contest creation and settlement** with flexible prize structures
3. **User management** with balance adjustments
4. **Transaction monitoring** with detailed audit trails
5. **Match scheduling** with contest association

### Technical Excellence
1. **High-performance architecture** with async processing
2. **Scalable infrastructure** with Kubernetes deployment
3. **Comprehensive monitoring** with Prometheus and Sentry
4. **Robust error handling** with retry mechanisms
5. **Security-first design** with multiple protection layers

## Conclusion

CricAlgo represents a sophisticated, production-ready cricket trading platform with comprehensive functionality covering user management, financial operations, contest systems, and administrative controls. The system is built with modern best practices, scalable architecture, and robust security measures, making it suitable for handling real-world trading operations with high reliability and performance.

The platform successfully combines the convenience of Telegram bot interaction with the power of a full-featured web application, providing users with an intuitive interface while maintaining the flexibility and control needed for complex financial operations.
