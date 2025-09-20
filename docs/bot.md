# CricAlgo Telegram Bot Documentation

## Overview

The CricAlgo Telegram Bot provides a user-friendly interface for managing cricket algorithm trading contests. Users can check balances, join contests, and manage their accounts through simple Telegram commands.

## Features

### User Commands
- `/start` - Register or login to your account
- `/balance` - Check wallet balance (deposit, winning, bonus)
- `/deposit` - Get deposit instructions
- `/contests` - View available contests
- `/help` - Show available commands

### Admin Commands
- `/create_contest` - Create a new contest (admin only)
- `/settle` - Settle a contest (admin only)
- `/approve_withdraw` - Approve user withdrawal (admin only)
- `/admin_help` - Show admin commands

### Interactive Features
- Inline keyboards for quick actions
- Idempotent contest joining (prevents duplicate entries)
- Rate limiting to prevent spam
- Real-time balance updates

## Architecture

### Components

1. **Bot Core** (`app/bot/telegram_bot.py`)
   - Bot and Dispatcher factory functions
   - Rate limiting middleware
   - Redis storage for FSM states

2. **Handlers**
   - `app/bot/handlers/commands.py` - User command handlers
   - `app/bot/handlers/admin_commands.py` - Admin command handlers
   - `app/bot/handlers/callbacks.py` - Callback query handlers

3. **Security**
   - Telegram user ID mapping to internal user IDs
   - Admin privilege checking
   - Rate limiting per user
   - Idempotent operations

## Setup and Deployment

### Prerequisites

- Python 3.8+
- Redis server
- PostgreSQL database
- Telegram Bot Token

### Environment Variables

```bash
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_here
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/cricalgo
REDIS_URL=redis://localhost:6379/0

# Optional
TELEGRAM_WEBHOOK_URL=https://yourdomain.com
WEBHOOK_SECRET=your_webhook_secret
RATE_LIMIT_REQUESTS=30
RATE_LIMIT_WINDOW_SECONDS=60
```

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run database migrations:
```bash
alembic upgrade head
```

### Running the Bot

#### Polling Mode (Development)
```bash
python run_polling.py
```

#### Webhook Mode (Production)
```bash
python run_webhook.py
```

### Docker Deployment

#### Using docker-compose.bot.yml
```bash
# Create docker-compose.bot.yml
version: '3.8'
services:
  bot:
    build:
      context: .
      dockerfile: Dockerfile.bot
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=cricalgo
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    restart: unless-stopped
```

#### Run with Docker Compose
```bash
docker-compose -f docker-compose.bot.yml up -d
```

## Bot Token Management

### Getting a Bot Token

1. Message @BotFather on Telegram
2. Use `/newbot` command
3. Follow prompts to create bot
4. Save the token securely

### Token Rotation

1. Generate new token with @BotFather
2. Update `TELEGRAM_BOT_TOKEN` environment variable
3. Restart bot service
4. Update webhook if using webhook mode

### Security Best Practices

- Store tokens in environment variables, never in code
- Use different tokens for development/staging/production
- Rotate tokens regularly
- Monitor bot usage for suspicious activity

## User Flow Examples

### New User Registration
1. User sends `/start`
2. Bot creates user account and wallet
3. Bot sends welcome message with instructions

### Joining a Contest
1. User sends `/contests`
2. Bot shows available contests with join buttons
3. User clicks join button
4. Bot checks balance and processes payment
5. Bot creates contest entry and confirms

### Admin Creating Contest
1. Admin sends `/create_contest`
2. Bot prompts for contest details step by step
3. Bot creates contest in database
4. Bot confirms creation with contest details

## Error Handling

### Common Errors
- **User not found**: Prompt to use `/start`
- **Insufficient balance**: Show current balance and deposit instructions
- **Contest full**: Inform user and suggest other contests
- **Rate limit exceeded**: Ask user to wait before sending more commands

### Logging
- All bot interactions are logged
- Errors are logged with context
- Admin actions are audited

## Monitoring and Maintenance

### Health Checks
- Bot responds to `/help` command
- Database connectivity verified
- Redis connectivity verified

### Metrics
- Commands per minute
- User registration rate
- Contest join success rate
- Error rate by command type

### Troubleshooting

#### Bot Not Responding
1. Check if bot is running
2. Verify token is correct
3. Check database connectivity
4. Check Redis connectivity

#### Users Can't Join Contests
1. Check contest status
2. Verify user balance
3. Check for duplicate entries
4. Review error logs

## Development

### Adding New Commands

1. Create handler function in appropriate file
2. Register with router
3. Add tests
4. Update documentation

### Testing

Run unit tests:
```bash
pytest tests/unit/test_bot_commands.py
pytest tests/unit/test_callbacks.py
```

Run integration tests:
```bash
pytest tests/integration/test_bot_integration.py
```

### Code Style

- Follow PEP 8
- Use type hints
- Add docstrings
- Write tests for new features

## Security Considerations

### Data Protection
- User data encrypted in transit and at rest
- No sensitive data in logs
- Regular security audits

### Access Control
- Admin commands require admin privileges
- Rate limiting prevents abuse
- Input validation on all commands

### Compliance
- GDPR compliance for EU users
- Data retention policies
- User consent for data processing

## Support

### User Support
- In-app help commands
- Support email: support@cricalgo.com
- Telegram: @CricAlgoSupport

### Developer Support
- Documentation: This file
- Code comments and docstrings
- Issue tracking in repository
