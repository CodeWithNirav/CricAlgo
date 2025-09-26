# Contest Cancellation Implementation

## Overview

This document describes the implementation of contest cancellation functionality that allows administrators to cancel contests and automatically refund all participants.

## Features

- **Admin-only cancellation**: Only administrators can cancel contests
- **Automatic refunds**: All participants are automatically refunded their entry fees
- **Atomic operations**: Cancellation and refunds are processed atomically
- **Audit logging**: All cancellation actions are logged for audit purposes
- **Status validation**: Prevents cancellation of already cancelled or settled contests

## API Endpoints

### Cancel Contest

**Endpoint**: `POST /api/v1/contest/admin/{contest_id}/cancel`

**Authentication**: Admin required

**Request**: No body required

**Response**:
```json
{
  "success": true,
  "message": "Contest cancelled with 2 successful refunds",
  "participants": 2,
  "successful_refunds": 2,
  "failed_refunds": 0,
  "total_refunded": "20.0",
  "refunds": [
    {
      "user_id": "uuid",
      "entry_id": "uuid", 
      "amount": "10.0",
      "status": "success"
    }
  ],
  "failed_refunds_list": []
}
```

### Alternative Admin Endpoint

**Endpoint**: `POST /api/v1/admin/contest/{contest_id}/cancel`

Same functionality as above, available through the admin API.

## Implementation Details

### Core Functions

#### `refund_contest_entry_atomic()`
- Credits entry fee back to user's deposit balance
- Creates transaction record with type "contest_refund"
- Uses row-level locking to prevent race conditions
- Returns success/failure status

#### `cancel_contest_atomic()`
- Locks contest row to prevent concurrent operations
- Validates contest can be cancelled (not already cancelled/settled)
- Processes refunds for all participants
- Marks contest as cancelled
- Creates audit log entry
- Returns detailed cancellation results

### Database Changes

No schema changes required. The existing `contest_status` enum already includes 'cancelled' status.

### Transaction Types

New transaction type: `contest_refund`
- Records refund transactions for audit purposes
- Links to original contest via `related_entity` and `related_id`
- Includes metadata about cancellation reason

### Audit Logging

All cancellations are logged with:
- Admin who initiated cancellation
- Contest details
- Participant count
- Refund results (successful/failed)
- Total amount refunded

## Business Rules

1. **Cancellation Eligibility**:
   - Contest must be in 'open' or 'closed' status
   - Cannot cancel already cancelled contests
   - Cannot cancel settled contests

2. **Refund Process**:
   - All participants are refunded their full entry fee
   - Refunds are credited to deposit balance (matching original debit priority)
   - Failed refunds are logged but don't prevent contest cancellation

3. **Atomicity**:
   - Contest status change and refunds are processed in single transaction
   - If any refund fails, the operation continues but logs the failure
   - Contest is marked as cancelled regardless of refund success

## Error Handling

- **Contest not found**: Returns 404
- **Already cancelled**: Returns 400 with specific message
- **Settled contest**: Returns 400 with specific message
- **Invalid contest ID**: Returns 400 with format error
- **Database errors**: Returns 500 with error details

## Testing

### Unit Tests
- `test_contest_cancellation.py`: Tests core cancellation logic
- Tests refund functionality with various scenarios
- Tests validation and error conditions

### Integration Tests  
- `test_contest_cancellation_api.py`: Tests API endpoints
- Tests authentication and authorization
- Tests error responses and success scenarios

## Usage Examples

### Cancel Contest with Participants
```bash
curl -X POST "https://api.example.com/api/v1/contest/admin/{contest_id}/cancel" \
  -H "Authorization: Bearer {admin_token}"
```

### Response for Successful Cancellation
```json
{
  "success": true,
  "message": "Contest cancelled with 3 successful refunds",
  "participants": 3,
  "successful_refunds": 3,
  "failed_refunds": 0,
  "total_refunded": "30.0",
  "refunds": [
    {
      "user_id": "user-1-uuid",
      "entry_id": "entry-1-uuid",
      "amount": "10.0",
      "status": "success"
    },
    {
      "user_id": "user-2-uuid", 
      "entry_id": "entry-2-uuid",
      "amount": "10.0",
      "status": "success"
    },
    {
      "user_id": "user-3-uuid",
      "entry_id": "entry-3-uuid", 
      "amount": "10.0",
      "status": "success"
    }
  ],
  "failed_refunds_list": []
}
```

## Security Considerations

- **Admin-only access**: Endpoints require admin authentication
- **Audit trail**: All actions are logged for compliance
- **Atomic operations**: Prevents partial cancellations
- **Input validation**: Contest ID format validation
- **Status checks**: Prevents invalid state transitions

## Monitoring

Key metrics to monitor:
- Cancellation frequency
- Refund success rate
- Failed refunds requiring manual intervention
- Contest status distribution

## Future Enhancements

Potential improvements:
- Bulk cancellation for multiple contests
- Partial refunds for specific participants
- Cancellation reasons and notes
- Email notifications to participants
- Refund processing queue for large contests
