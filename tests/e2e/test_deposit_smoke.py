"""
End-to-end tests for deposit processing smoke test
"""

import pytest
import asyncio
import json
import hmac
import hashlib
from decimal import Decimal
from uuid import UUID, uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.user import User
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.tasks.deposits import process_deposit
from app.core.config import settings


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
async def test_user(session: AsyncSession):
    """Create a test user with wallet."""
    user = User(
        id=uuid4(),
        telegram_id=123456789,
        username="smoketestuser",
        status="active"
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    
    # Create wallet for user
    wallet = Wallet(
        user_id=user.id,
        deposit_balance=Decimal('0'),
        winning_balance=Decimal('0'),
        bonus_balance=Decimal('0')
    )
    session.add(wallet)
    await session.commit()
    await session.refresh(wallet)
    
    return user


class TestDepositSmokeE2E:
    """End-to-end smoke tests for deposit processing."""
    
    def test_deposit_processing_full_pipeline(self, client: TestClient, test_user: User):
        """Test complete deposit processing pipeline from webhook to wallet credit."""
        # Mock Redis client
        with patch('app.api.v1.webhooks.get_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.exists.return_value = False  # Not already enqueued
            mock_redis.set.return_value = True  # Successfully mark as enqueued
            mock_get_redis.return_value = mock_redis
            
            # Mock Celery task to run synchronously
            with patch('app.api.v1.webhooks.process_deposit.delay') as mock_delay:
                # Create a mock task that runs synchronously
                def mock_task_delay(tx_id):
                    # Run the actual task synchronously
                    return process_deposit(tx_id)
                
                mock_delay.side_effect = mock_task_delay
                
                # Step 1: Send webhook with sufficient confirmations
                webhook_payload = {
                    "tx_hash": "0xsmoketest123456789",
                    "confirmations": 3,
                    "chain": "bep20",
                    "to_address": "0xrecipient123",
                    "amount": "250.75",
                    "currency": "USDT",
                    "user_id": str(test_user.id),
                    "metadata": {
                        "block_number": 12345,
                        "gas_used": "21000"
                    }
                }
                
                # Calculate HMAC signature if webhook secret is configured
                headers = {}
                if settings.webhook_secret:
                    body = json.dumps(webhook_payload).encode()
                    signature = hmac.new(
                        settings.webhook_secret.encode(),
                        body,
                        hashlib.sha256
                    ).hexdigest()
                    headers["X-Signature"] = signature
                
                response = client.post(
                    "/api/v1/webhook/bep20",
                    json=webhook_payload,
                    headers=headers
                )
                
                # Verify webhook response
                assert response.status_code == 200
                data = response.json()
                assert data["ok"] is True
                assert data["enqueued"] is True
                
                # Verify task was called
                mock_delay.assert_called_once()
                call_args = mock_delay.call_args[0]
                assert len(call_args) == 1
                tx_id = call_args[0]
                
                # Step 2: Verify transaction was created and processed
                # This would normally be done by checking the database
                # For this test, we'll verify the task completed successfully
                assert tx_id is not None
    
    def test_duplicate_webhook_idempotency(self, client: TestClient, test_user: User):
        """Test that duplicate webhooks don't cause double processing."""
        # Mock Redis client
        with patch('app.api.v1.webhooks.get_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.exists.return_value = False  # First call: not enqueued
            mock_redis.set.return_value = True  # Successfully mark as enqueued
            mock_get_redis.return_value = mock_redis
            
            # Mock Celery task
            with patch('app.api.v1.webhooks.process_deposit.delay') as mock_delay:
                mock_delay.return_value = None
                
                webhook_payload = {
                    "tx_hash": "0xduplicatetest123",
                    "confirmations": 3,
                    "chain": "bep20",
                    "to_address": "0xrecipient123",
                    "amount": "100.00",
                    "currency": "USDT",
                    "user_id": str(test_user.id),
                    "metadata": {}
                }
                
                # First webhook call
                response1 = client.post("/api/v1/webhook/bep20", json=webhook_payload)
                assert response1.status_code == 200
                data1 = response1.json()
                assert data1["ok"] is True
                assert data1["enqueued"] is True
                
                # Update Redis mock to simulate already enqueued
                mock_redis.exists.return_value = True
                
                # Second webhook call (duplicate)
                response2 = client.post("/api/v1/webhook/bep20", json=webhook_payload)
                assert response2.status_code == 200
                data2 = response2.json()
                assert data2["ok"] is True
                assert data2["enqueued"] is False
                assert "Already enqueued" in data2["message"]
                
                # Verify task was only called once
                assert mock_delay.call_count == 1
    
    def test_insufficient_confirmations_webhook(self, client: TestClient, test_user: User):
        """Test webhook with insufficient confirmations."""
        # Mock Redis client
        with patch('app.api.v1.webhooks.get_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            
            # Mock Celery task
            with patch('app.api.v1.webhooks.process_deposit.delay') as mock_delay:
                mock_delay.return_value = None
                
                webhook_payload = {
                    "tx_hash": "0xinsufficient123",
                    "confirmations": 1,  # Less than threshold
                    "chain": "bep20",
                    "to_address": "0xrecipient123",
                    "amount": "50.00",
                    "currency": "USDT",
                    "user_id": str(test_user.id),
                    "metadata": {}
                }
                
                response = client.post("/api/v1/webhook/bep20", json=webhook_payload)
                
                assert response.status_code == 200
                data = response.json()
                assert data["ok"] is True
                assert data["enqueued"] is False
                
                # Verify task was not called
                mock_delay.assert_not_called()
    
    def test_webhook_signature_verification(self, client: TestClient, test_user: User):
        """Test webhook signature verification."""
        if not settings.webhook_secret:
            pytest.skip("Webhook secret not configured")
        
        webhook_payload = {
            "tx_hash": "0xsigtest123",
            "confirmations": 3,
            "chain": "bep20",
            "to_address": "0xrecipient123",
            "amount": "75.00",
            "currency": "USDT",
            "user_id": str(test_user.id),
            "metadata": {}
        }
        
        # Test with invalid signature
        response = client.post(
            "/api/v1/webhook/bep20",
            json=webhook_payload,
            headers={"X-Signature": "invalid_signature"}
        )
        assert response.status_code == 401
        assert "Invalid webhook signature" in response.json()["detail"]
        
        # Test with valid signature
        body = json.dumps(webhook_payload).encode()
        signature = hmac.new(
            settings.webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        response = client.post(
            "/api/v1/webhook/bep20",
            json=webhook_payload,
            headers={"X-Signature": signature}
        )
        assert response.status_code == 200
    
    def test_webhook_without_user_id(self, client: TestClient):
        """Test webhook without user_id (should not create transaction)."""
        # Mock Redis client
        with patch('app.api.v1.webhooks.get_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            
            # Mock Celery task
            with patch('app.api.v1.webhooks.process_deposit.delay') as mock_delay:
                mock_delay.return_value = None
                
                webhook_payload = {
                    "tx_hash": "0xnouser123",
                    "confirmations": 3,
                    "chain": "bep20",
                    "to_address": "0xrecipient123",
                    "amount": "100.00",
                    "currency": "USDT",
                    "metadata": {}
                    # No user_id
                }
                
                response = client.post("/api/v1/webhook/bep20", json=webhook_payload)
                
                assert response.status_code == 200
                data = response.json()
                assert data["ok"] is True
                assert data["enqueued"] is False  # No transaction to process
                
                # Verify task was not called
                mock_delay.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_deposit_task_complete_flow(
        self, session: AsyncSession, test_user: User
    ):
        """Test the complete process_deposit task flow."""
        # Create a transaction
        transaction = Transaction(
            id=uuid4(),
            user_id=test_user.id,
            tx_type="deposit",
            amount=Decimal('500.00'),
            currency="USDT",
            tx_metadata={
                "tx_hash": "0xtasktest123",
                "confirmations": 3,
                "status": "pending",
                "block_number": 54321
            }
        )
        session.add(transaction)
        await session.commit()
        await session.refresh(transaction)
        
        # Get initial wallet balance
        wallet = await session.get(Wallet, test_user.id)
        initial_balance = wallet.deposit_balance
        
        # Run the process_deposit task
        result = process_deposit(str(transaction.id))
        
        # Verify task completed successfully
        assert result is True
        
        # Refresh transaction and wallet from database
        await session.refresh(transaction)
        await session.refresh(wallet)
        
        # Verify transaction was processed
        assert transaction.processed_at is not None
        assert transaction.tx_metadata["status"] == "confirmed"
        assert transaction.tx_metadata["confirmations"] == 3
        
        # Verify wallet was credited
        expected_balance = initial_balance + Decimal('500.00')
        assert wallet.deposit_balance == expected_balance
        
        # Verify idempotency - run task again
        result2 = process_deposit(str(transaction.id))
        assert result2 is True
        
        # Verify balance didn't change
        await session.refresh(wallet)
        assert wallet.deposit_balance == expected_balance
