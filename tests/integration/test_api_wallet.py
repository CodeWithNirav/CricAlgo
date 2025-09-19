"""
Integration tests for wallet API endpoints
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from app.repos.user_repo import create_user
from app.repos.wallet_repo import create_wallet_for_user, get_wallet_for_user
from app.models.enums import UserStatus
from tests.fixtures.database import assert_wallet_balance


@pytest.mark.integration
@pytest.mark.asyncio
async def test_wallet_balance_endpoint(test_client, async_session):
    """Test GET /api/v1/wallet endpoint."""
    # Create user and wallet
    user = await create_user(
        session=async_session,
        telegram_id=12345,
        username="walletuser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(async_session, user.id)
    
    # Add some balance
    from app.repos.wallet_repo import update_balances_atomic
    await update_balances_atomic(
        async_session,
        user.id,
        deposit_delta=Decimal('100.00'),
        bonus_delta=Decimal('50.00'),
        winning_delta=Decimal('25.00')
    )
    
    # Create JWT token for authentication
    from app.core.auth import create_access_token
    token = create_access_token(data={"sub": str(user.id)})
    
    # Test wallet balance endpoint
    response = await test_client.get(
        "/api/v1/wallet/",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["deposit_balance"] == "100.00"
    assert data["bonus_balance"] == "50.00"
    assert data["winning_balance"] == "25.00"
    assert data["total_balance"] == "175.00"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_withdrawal_request_endpoint(test_client, async_session):
    """Test POST /api/v1/wallet/withdraw endpoint."""
    # Create user and wallet
    user = await create_user(
        session=async_session,
        telegram_id=67890,
        username="withdrawuser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(async_session, user.id)
    
    # Add balance
    from app.repos.wallet_repo import update_balances_atomic
    await update_balances_atomic(
        async_session,
        user.id,
        deposit_delta=Decimal('200.00')
    )
    
    # Create JWT token
    from app.core.auth import create_access_token
    token = create_access_token(data={"sub": str(user.id)})
    
    # Test withdrawal request
    withdrawal_data = {
        "amount": "50.00",
        "currency": "USDT",
        "withdrawal_address": "0x1234567890abcdef",
        "notes": "Test withdrawal"
    }
    
    response = await test_client.post(
        "/api/v1/wallet/withdraw",
        json=withdrawal_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert data["status"] == "pending"
    assert "transaction_id" in data
    assert "message" in data
    
    # Verify wallet balance was debited
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('150.00')  # 200 - 50
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_withdrawal_insufficient_balance(test_client, async_session):
    """Test withdrawal with insufficient balance."""
    # Create user and wallet
    user = await create_user(
        session=async_session,
        telegram_id=11111,
        username="pooruser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(async_session, user.id)
    
    # Create JWT token
    from app.core.auth import create_access_token
    token = create_access_token(data={"sub": str(user.id)})
    
    # Test withdrawal with insufficient balance
    withdrawal_data = {
        "amount": "100.00",
        "currency": "USDT",
        "withdrawal_address": "0x1234567890abcdef"
    }
    
    response = await test_client.post(
        "/api/v1/wallet/withdraw",
        json=withdrawal_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert "Insufficient balance" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_wallet_transactions_endpoint(test_client, async_session):
    """Test GET /api/v1/wallet/transactions endpoint."""
    # Create user and wallet
    user = await create_user(
        session=async_session,
        telegram_id=22222,
        username="txuser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(async_session, user.id)
    
    # Create some transactions
    from app.repos.transaction_repo import create_transaction
    await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="deposit",
        amount=Decimal('100.00'),
        currency="USDT",
        tx_metadata={"status": "confirmed"}
    )
    
    await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="withdrawal",
        amount=Decimal('25.00'),
        currency="USDT",
        tx_metadata={"status": "pending"}
    )
    
    # Create JWT token
    from app.core.auth import create_access_token
    token = create_access_token(data={"sub": str(user.id)})
    
    # Test transactions endpoint
    response = await test_client.get(
        "/api/v1/wallet/transactions",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "transactions" in data
    assert len(data["transactions"]) == 2
    assert data["limit"] == 50
    assert data["offset"] == 0
    
    # Check transaction details
    transactions = data["transactions"]
    deposit_tx = next(tx for tx in transactions if tx["type"] == "deposit")
    withdrawal_tx = next(tx for tx in transactions if tx["type"] == "withdrawal")
    
    assert deposit_tx["amount"] == "100.00"
    assert deposit_tx["currency"] == "USDT"
    assert deposit_tx["status"] == "confirmed"
    
    assert withdrawal_tx["amount"] == "25.00"
    assert withdrawal_tx["currency"] == "USDT"
    assert withdrawal_tx["status"] == "pending"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unauthorized_wallet_access(test_client):
    """Test wallet endpoints without authentication."""
    # Test wallet balance without token
    response = await test_client.get("/api/v1/wallet/")
    assert response.status_code == 401
    
    # Test withdrawal without token
    withdrawal_data = {
        "amount": "50.00",
        "currency": "USDT",
        "withdrawal_address": "0x1234567890abcdef"
    }
    
    response = await test_client.post("/api/v1/wallet/withdraw", json=withdrawal_data)
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_withdrawal_data(test_client, async_session):
    """Test withdrawal with invalid data."""
    # Create user and wallet
    user = await create_user(
        session=async_session,
        telegram_id=33333,
        username="invaliduser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(async_session, user.id)
    
    # Create JWT token
    from app.core.auth import create_access_token
    token = create_access_token(data={"sub": str(user.id)})
    
    # Test with negative amount
    withdrawal_data = {
        "amount": "-50.00",
        "currency": "USDT",
        "withdrawal_address": "0x1234567890abcdef"
    }
    
    response = await test_client.post(
        "/api/v1/wallet/withdraw",
        json=withdrawal_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert "positive" in data["detail"]
    
    # Test with zero amount
    withdrawal_data["amount"] = "0.00"
    
    response = await test_client.post(
        "/api/v1/wallet/withdraw",
        json=withdrawal_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert "positive" in data["detail"]
    
    # Test with invalid amount format
    withdrawal_data["amount"] = "invalid"
    
    response = await test_client.post(
        "/api/v1/wallet/withdraw",
        json=withdrawal_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert "Invalid amount format" in data["detail"]
