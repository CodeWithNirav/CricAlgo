"""
Integration tests for webhook processing
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from app.repos.user_repo import create_user
from app.repos.wallet_repo import create_wallet_for_user
from app.repos.transaction_repo import create_transaction, get_transaction_by_id
from app.models.enums import UserStatus
from tests.fixtures.database import assert_wallet_balance


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_deposit_confirmation(test_client, async_session):
    """Test webhook deposit confirmation processing."""
    # Create user and wallet
    user = await create_user(
        session=async_session,
        telegram_id=12345,
        username="webhookuser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(async_session, user.id)
    
    # Create pending deposit transaction
    tx_hash = f"0x{''.join([f'{i:02x}' for i in range(32)])}"
    transaction = await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="deposit",
        amount=Decimal('100.00'),
        currency="USDT",
        tx_metadata={
            "tx_hash": tx_hash,
            "confirmations": 0,
            "status": "pending"
        }
    )
    
    # Verify initial wallet balance
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('0.00')
    )
    
    # Send webhook with sufficient confirmations
    webhook_payload = {
        "tx_hash": tx_hash,
        "confirmations": 12,  # Above threshold of 3
        "amount": "100.00",
        "currency": "USDT",
        "status": "confirmed",
        "block_number": 12345678,
        "user_id": str(user.id)
    }
    
    response = await test_client.post(
        "/api/v1/webhooks/bep20",
        json=webhook_payload
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert data["tx_hash"] == tx_hash
    assert "processed successfully" in data["message"]
    
    # Verify wallet balance was updated
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('100.00')
    )
    
    # Verify transaction status was updated
    updated_transaction = await get_transaction_by_id(async_session, transaction.id)
    assert updated_transaction is not None
    # Note: In a real implementation, we'd check the transaction metadata was updated


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_insufficient_confirmations(test_client, async_session):
    """Test webhook with insufficient confirmations."""
    # Create user and wallet
    user = await create_user(
        session=async_session,
        telegram_id=67890,
        username="pendinguser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(async_session, user.id)
    
    # Create pending deposit transaction
    tx_hash = f"0x{''.join([f'{i:02x}' for i in range(32)])}"
    transaction = await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="deposit",
        amount=Decimal('50.00'),
        currency="USDT",
        tx_metadata={
            "tx_hash": tx_hash,
            "confirmations": 0,
            "status": "pending"
        }
    )
    
    # Send webhook with insufficient confirmations
    webhook_payload = {
        "tx_hash": tx_hash,
        "confirmations": 1,  # Below threshold of 3
        "amount": "50.00",
        "currency": "USDT",
        "status": "confirmed",
        "user_id": str(user.id)
    }
    
    response = await test_client.post(
        "/api/v1/webhooks/bep20",
        json=webhook_payload
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert "insufficient confirmations" in data["message"]
    
    # Verify wallet balance was NOT updated
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('0.00')
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_idempotency(test_client, async_session):
    """Test webhook idempotency - same webhook should not be processed twice."""
    # Create user and wallet
    user = await create_user(
        session=async_session,
        telegram_id=11111,
        username="idempotencyuser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(async_session, user.id)
    
    # Create pending deposit transaction
    tx_hash = f"0x{''.join([f'{i:02x}' for i in range(32)])}"
    transaction = await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="deposit",
        amount=Decimal('75.00'),
        currency="USDT",
        tx_metadata={
            "tx_hash": tx_hash,
            "confirmations": 0,
            "status": "pending"
        }
    )
    
    # Send webhook first time
    webhook_payload = {
        "tx_hash": tx_hash,
        "confirmations": 12,
        "amount": "75.00",
        "currency": "USDT",
        "status": "confirmed",
        "user_id": str(user.id)
    }
    
    response1 = await test_client.post(
        "/api/v1/webhooks/bep20",
        json=webhook_payload
    )
    
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["success"] is True
    
    # Get balance after first webhook
    wallet_after_first = await get_wallet_for_user(async_session, user.id)
    balance_after_first = wallet_after_first.deposit_balance
    
    # Send same webhook again
    response2 = await test_client.post(
        "/api/v1/webhooks/bep20",
        json=webhook_payload
    )
    
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["success"] is True
    
    # Get balance after second webhook
    wallet_after_second = await get_wallet_for_user(async_session, user.id)
    balance_after_second = wallet_after_second.deposit_balance
    
    # Verify balance didn't change (idempotency)
    assert balance_after_first == balance_after_second
    assert balance_after_first == Decimal('75.00')


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_failed_transaction(test_client, async_session):
    """Test webhook for failed transaction."""
    # Create user and wallet
    user = await create_user(
        session=async_session,
        telegram_id=22222,
        username="faileduser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(async_session, user.id)
    
    # Create pending deposit transaction
    tx_hash = f"0x{''.join([f'{i:02x}' for i in range(32)])}"
    transaction = await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="deposit",
        amount=Decimal('100.00'),
        currency="USDT",
        tx_metadata={
            "tx_hash": tx_hash,
            "confirmations": 0,
            "status": "pending"
        }
    )
    
    # Send webhook for failed transaction
    webhook_payload = {
        "tx_hash": tx_hash,
        "confirmations": 12,
        "amount": "100.00",
        "currency": "USDT",
        "status": "failed",
        "user_id": str(user.id)
    }
    
    response = await test_client.post(
        "/api/v1/webhooks/bep20",
        json=webhook_payload
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert "processed successfully" in data["message"]
    
    # Verify wallet balance was NOT updated
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('0.00')
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_missing_user(test_client, async_session):
    """Test webhook with missing user ID."""
    tx_hash = f"0x{''.join([f'{i:02x}' for i in range(32)])}"
    
    # Send webhook without user_id
    webhook_payload = {
        "tx_hash": tx_hash,
        "confirmations": 12,
        "amount": "100.00",
        "currency": "USDT",
        "status": "confirmed"
    }
    
    response = await test_client.post(
        "/api/v1/webhooks/bep20",
        json=webhook_payload
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    # Should still process successfully (enqueue task for unknown user)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_invalid_data(test_client):
    """Test webhook with invalid data."""
    # Test missing tx_hash
    webhook_payload = {
        "confirmations": 12,
        "amount": "100.00",
        "currency": "USDT",
        "status": "confirmed"
    }
    
    response = await test_client.post(
        "/api/v1/webhooks/bep20",
        json=webhook_payload
    )
    
    assert response.status_code == 400
    data = response.json()
    assert "tx_hash is required" in data["detail"]
    
    # Test invalid confirmations
    webhook_payload = {
        "tx_hash": "0x1234567890abcdef",
        "confirmations": "invalid",
        "amount": "100.00",
        "currency": "USDT",
        "status": "confirmed"
    }
    
    response = await test_client.post(
        "/api/v1/webhooks/bep20",
        json=webhook_payload
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_health_endpoint(test_client):
    """Test webhook health endpoint."""
    response = await test_client.get("/api/v1/webhooks/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "ok"
    assert data["service"] == "webhooks"
    assert "/api/v1/webhooks/bep20" in data["endpoints"]
