# CricAlgo Smoke Test Documentation

## Overview

The CricAlgo smoke test suite provides comprehensive testing of the Telegram bot system, including user management, contest creation, deposit processing, contest participation, settlement, and withdrawal flows.

## Scripts Available

### 1. Original Script (`smoke_test.sh`)
- Basic smoke test implementation
- Limited error handling
- Some API endpoint mismatches
- Basic logging and artifact collection

### 2. Improved Script (`improved_smoke_test.sh`)
- Enhanced error handling and validation
- Corrected API endpoints based on actual codebase
- Multiple fallback strategies for critical operations
- Comprehensive logging and reporting
- Better artifact organization

## Prerequisites

### Environment Variables Required
```bash
# Required
HTTP=http://localhost:8000                    # API base URL
TELEGRAM_BOT_TOKEN=your_bot_token           # Telegram bot token
ADMIN_TOKEN=your_admin_token                # Admin authentication token
USER1_TELEGRAM_ID=815804123                 # Test user 1 Telegram ID
USER2_TELEGRAM_ID=693173957                 # Test user 2 Telegram ID

# Optional (with defaults)
DEPOSIT_AMOUNT=20.0                         # Deposit amount for testing
ENTRY_FEE=5.0                              # Contest entry fee
WITHDRAWAL_AMOUNT=2.0                      # Withdrawal amount for testing
```

### System Requirements
- Docker and Docker Compose
- `curl` command-line tool
- `jq` for JSON processing (optional, for pretty output)
- Access to Telegram API

## Running the Tests

### Using the Improved Script (Recommended)

```bash
# Set environment variables
export HTTP="http://localhost:8000"
export TELEGRAM_BOT_TOKEN="your_bot_token"
export ADMIN_TOKEN="your_admin_token"
export USER1_TELEGRAM_ID="815804123"
export USER2_TELEGRAM_ID="693173957"

# Run the improved smoke test
./scripts/improved_smoke_test.sh
```

### Using the Original Script

```bash
# Set environment variables
export HTTP="http://localhost:8000"
export TELEGRAM_BOT_TOKEN="your_bot_token"
export ADMIN_TOKEN="your_admin_token"
export USER1_TELEGRAM_ID="815804123"
export USER2_TELEGRAM_ID="693173957"

# Run the original smoke test
./scripts/smoke_test.sh
```

## Test Flow

### 1. Health Check
- Verifies API is running and accessible
- Tests `/api/v1/health` endpoint
- Validates response format

### 2. User Management
- Checks for existing users by Telegram ID
- Creates users if they don't exist
- Uses admin API endpoints:
  - `GET /api/v1/admin/users?telegram_id={id}`
  - `POST /api/v1/admin/users`

### 3. Match and Contest Creation
- Creates a test match with unique timestamp
- Creates a contest for the match
- Uses admin API endpoints:
  - `POST /api/v1/admin/matches`
  - `POST /api/v1/admin/matches/{match_id}/contests`

### 4. Deposit Simulation
- Simulates a blockchain deposit via webhook
- Tests deposit processing pipeline
- Uses webhook endpoint:
  - `POST /api/v1/webhooks/bep20`

### 5. Contest Participation
- Attempts to join contest with multiple methods
- Tests both user and admin endpoints:
  - `POST /api/v1/contests/{id}/join`
  - `POST /api/v1/admin/contests/{id}/force_join`

### 6. Contest Settlement
- Settles the contest and distributes prizes
- Tests settlement endpoint:
  - `POST /api/v1/admin/contests/{id}/settle`

### 7. Withdrawal Flow
- Creates withdrawal request
- Approves withdrawal
- Tests endpoints:
  - `POST /api/v1/withdrawals`
  - `POST /api/v1/admin/withdrawals`
  - `POST /api/v1/admin/withdrawals/{id}/approve`

### 8. Log Collection
- Collects Docker logs from all services
- Gathers Telegram API status
- Creates comprehensive test report

## Artifacts Generated

The test creates a timestamped directory `artifacts/bot_live_smoke_{timestamp}/` containing:

### API Responses
- `health.json` - Health check response
- `match_create.json` - Match creation response
- `contest_create.json` - Contest creation response
- `deposit_webhook_resp_u1.json` - Deposit webhook response
- `join_response_method*.json` - Contest join responses
- `settle_response.json` - Contest settlement response
- `withdraw_create_method*.json` - Withdrawal creation responses
- `withdraw_approve_resp.json` - Withdrawal approval response

### User Data
- `user1_lookup.json` - User 1 lookup response
- `user1_create.json` - User 1 creation response
- `user1_transactions.json` - User 1 transaction history
- `user1_wallet_after_settle.json` - User 1 wallet balance

### System Logs
- `bot_log.txt` - Telegram bot logs
- `worker_log.txt` - Celery worker logs
- `app_log.txt` - FastAPI application logs

### Test Reports
- `smoke_test_summary.json` - Comprehensive test summary
- `smoke_test_summary_pretty.json` - Pretty-formatted summary
- `run.log` - Complete test execution log

## Key Improvements in Enhanced Script

### 1. Better Error Handling
- Validates responses at each step
- Provides clear error messages
- Continues testing even if some steps fail
- Multiple fallback strategies

### 2. Corrected API Endpoints
- Fixed endpoint paths based on actual codebase
- Proper authentication headers
- Correct request payloads

### 3. Enhanced Validation
- Response validation functions
- Success/failure indicators
- Comprehensive status reporting

### 4. Better Logging
- Structured logging with timestamps
- Clear step identification
- Detailed error reporting
- Progress indicators

### 5. Flexible Configuration
- Environment variable defaults
- Configurable test amounts
- Optional parameters

## Troubleshooting

### Common Issues

1. **Health Check Fails**
   - Verify API is running on correct port
   - Check Docker containers are up
   - Ensure network connectivity

2. **User Creation Fails**
   - Verify admin token is valid
   - Check database connectivity
   - Ensure admin user exists

3. **Deposit Webhook Fails**
   - Check webhook endpoint is accessible
   - Verify payload format
   - Check worker service is running

4. **Contest Join Fails**
   - Verify user has sufficient balance
   - Check contest is in correct state
   - Ensure user is properly authenticated

5. **Withdrawal Fails**
   - Check user has sufficient balance
   - Verify withdrawal endpoints
   - Check admin permissions

### Debug Steps

1. Check Docker container status:
   ```bash
   docker-compose ps
   ```

2. View container logs:
   ```bash
   docker-compose logs app
   docker-compose logs bot
   docker-compose logs worker
   ```

3. Test API endpoints manually:
   ```bash
   curl -X GET "$HTTP/api/v1/health"
   curl -X GET "$HTTP/api/v1/admin/users" -H "Authorization: Bearer $ADMIN_TOKEN"
   ```

4. Check database connectivity:
   ```bash
   docker-compose exec postgres psql -U postgres -d cricalgo -c "SELECT COUNT(*) FROM users;"
   ```

## Integration with CI/CD

The smoke test can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Smoke Tests
  run: |
    export HTTP="http://localhost:8000"
    export TELEGRAM_BOT_TOKEN="${{ secrets.TELEGRAM_BOT_TOKEN }}"
    export ADMIN_TOKEN="${{ secrets.ADMIN_TOKEN }}"
    export USER1_TELEGRAM_ID="815804123"
    export USER2_TELEGRAM_ID="693173957"
    ./scripts/improved_smoke_test.sh
```

## Monitoring and Alerting

The test generates comprehensive reports that can be used for:
- Automated monitoring dashboards
- Alert systems for test failures
- Performance trend analysis
- System health indicators

## Best Practices

1. **Run tests regularly** - Schedule automated runs
2. **Monitor artifacts** - Review generated reports
3. **Update test data** - Keep test user IDs current
4. **Version control** - Track test script changes
5. **Document failures** - Maintain failure logs
6. **Clean up** - Remove old artifact directories

## Contributing

When modifying the smoke test:
1. Test changes thoroughly
2. Update documentation
3. Ensure backward compatibility
4. Add new test scenarios as needed
5. Maintain clear error messages
