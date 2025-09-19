"""
Integration tests for deposit processing pipeline
"""

import pytest
import asyncio
from decimal import Decimal
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.user import User
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.tasks.deposits import process_deposit
from app.core.config import settings


# Use existing fixtures from conftest.py

@pytest.fixture
async def deposit_transaction(async_session: AsyncSession, test_user: User) -> Transaction:
    """Create a test deposit transaction."""
    transaction = Transaction(
        id=uuid4(),
        user_id=test_user.id,
        tx_type="deposit",
        amount=Decimal('100.50'),
        currency="USDT",
        tx_metadata={
            "tx_hash": "0x1234567890abcdef",
            "confirmations": 0,
            "status": "pending"
        }
    )
    async_session.add(transaction)
    await async_session.commit()
    await async_session.refresh(transaction)
    
    return transaction


class TestDepositProcessing:
    """Test deposit processing pipeline."""
    
    @pytest.mark.asyncio
    async def test_webhook_receives_confirmation_and_enqueues_processing(
        self, test_client: AsyncClient, test_user: User, deposit_transaction: Transaction
    ):
        """Test that webhook receives confirmation and enqueues processing."""
        # Mock Redis client
        with patch('app.api.v1.webhooks.get_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.exists.return_value = False  # Not already enqueued
            mock_redis.set.return_value = True  # Successfully mark as enqueued
            mock_get_redis.return_value = mock_redis
            
            # Mock Celery task
            with patch('app.api.v1.webhooks.process_deposit.delay') as mock_delay:
                mock_delay.return_value = None
                
                # Send webhook with sufficient confirmations
                webhook_payload = {
                    "tx_hash": "0x1234567890abcdef",
                    "confirmations": 3,
                    "chain": "bep20",
                    "to_address": "0xrecipient",
                    "amount": "100.50",
                    "currency": "USDT",
                    "user_id": str(test_user.id),
                    "metadata": {}
                }
                
                response = await test_client.post("/api/v1/webhooks/bep20", json=webhook_payload)
                
                assert response.status_code == 200
                data = response.json()
                assert data["ok"] is True
                assert data["enqueued"] is True
                
                # Verify task was enqueued
                mock_delay.assert_called_once_with(str(deposit_transaction.id))
    
    @pytest.mark.asyncio
    async def test_webhook_idempotency_prevents_double_processing(
        self, test_client: AsyncClient, test_user: User, deposit_transaction: Transaction
    ):
        """Test that duplicate webhooks don't enqueue processing twice."""
        # Mock Redis client
        with patch('app.api.v1.webhooks.get_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.exists.return_value = True  # Already enqueued
            mock_get_redis.return_value = mock_redis
            
            # Mock Celery task
            with patch('app.api.v1.webhooks.process_deposit.delay') as mock_delay:
                mock_delay.return_value = None
                
                # Send webhook with sufficient confirmations
                webhook_payload = {
                    "tx_hash": "0x1234567890abcdef",
                    "confirmations": 3,
                    "chain": "bep20",
                    "to_address": "0xrecipient",
                    "amount": "100.50",
                    "currency": "USDT",
                    "user_id": str(test_user.id),
                    "metadata": {}
                }
                
                response = await test_client.post("/api/v1/webhooks/bep20", json=webhook_payload)
                
                assert response.status_code == 200
                data = response.json()
                assert data["ok"] is True
                assert data["enqueued"] is False
                assert "Already enqueued" in data["message"]
                
                # Verify task was NOT enqueued
                mock_delay.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_webhook_insufficient_confirmations_does_not_enqueue(
        self, test_client: AsyncClient, test_user: User, deposit_transaction: Transaction
    ):
        """Test that insufficient confirmations don't enqueue processing."""
        # Mock Redis client
        with patch('app.api.v1.webhooks.get_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            
            # Mock Celery task
            with patch('app.api.v1.webhooks.process_deposit.delay') as mock_delay:
                mock_delay.return_value = None
                
                # Send webhook with insufficient confirmations
                webhook_payload = {
                    "tx_hash": "0x1234567890abcdef",
                    "confirmations": 1,  # Less than threshold
                    "chain": "bep20",
                    "to_address": "0xrecipient",
                    "amount": "100.50",
                    "currency": "USDT",
                    "user_id": str(test_user.id),
                    "metadata": {}
                }
                
                response = await test_client.post("/api/v1/webhooks/bep20", json=webhook_payload)
                
                assert response.status_code == 200
                data = response.json()
                assert data["ok"] is True
                assert data["enqueued"] is False
                
                # Verify task was NOT enqueued
                mock_delay.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_deposit_task_credits_wallet_atomically(
        self, async_session: AsyncSession, test_user: User, deposit_transaction: Transaction
    ):
        """Test that process_deposit task credits wallet atomically."""
        # Update transaction metadata with sufficient confirmations
        deposit_transaction.tx_metadata.update({
            "confirmations": 3,
            "status": "pending"
        })
        await async_session.commit()
        
        # Run the task
        result = process_deposit(str(deposit_transaction.id))
        
        # Verify task completed successfully
        assert result is True
        
        # Refresh transaction from database
        await async_session.refresh(deposit_transaction)
        
        # Verify transaction was marked as processed
        assert deposit_transaction.processed_at is not None
        assert deposit_transaction.tx_metadata["status"] == "confirmed"
        
        # Verify wallet was credited
        wallet = await async_session.get(Wallet, test_user.id)
        assert wallet.deposit_balance == Decimal('100.50')
    
    @pytest.mark.asyncio
    async def test_process_deposit_task_idempotency(
        self, async_session: AsyncSession, test_user: User, deposit_transaction: Transaction
    ):
        """Test that process_deposit task is idempotent."""
        # Update transaction metadata with sufficient confirmations
        deposit_transaction.tx_metadata.update({
            "confirmations": 3,
            "status": "pending"
        })
        await async_session.commit()
        
        # Run the task first time
        result1 = process_deposit(str(test_transaction.id))
        assert result1 is True
        
        # Get wallet balance after first run
        wallet = await async_session.get(Wallet, test_user.id)
        balance_after_first = wallet.deposit_balance
        
        # Run the task second time
        result2 = process_deposit(str(test_transaction.id))
        assert result2 is True
        
        # Verify balance didn't change
        await async_session.refresh(wallet)
        assert wallet.deposit_balance == balance_after_first
    
    @pytest.mark.asyncio
    async def test_process_deposit_task_insufficient_confirmations_retries(
        self, async_session: AsyncSession, test_user: User, deposit_transaction: Transaction
    ):
        """Test that process_deposit task retries when confirmations are insufficient."""
        # Update transaction metadata with insufficient confirmations
        deposit_transaction.tx_metadata.update({
            "confirmations": 1,  # Less than threshold
            "status": "pending"
        })
        await async_session.commit()
        
        # Mock the retry mechanism
        with patch('app.tasks.deposits.process_deposit.retry') as mock_retry:
            mock_retry.side_effect = Exception("Retry called")
            
            # Run the task
            with pytest.raises(Exception, match="Retry called"):
                process_deposit(str(deposit_transaction.id))
            
            # Verify retry was called
            mock_retry.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_webhook_creates_transaction_if_not_exists(
        self, test_client: AsyncClient, test_user: User
    ):
        """Test that webhook creates transaction if it doesn't exist."""
        # Mock Redis client
        with patch('app.api.v1.webhooks.get_redis') as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.exists.return_value = False  # Not already enqueued
            mock_redis.set.return_value = True  # Successfully mark as enqueued
            mock_get_redis.return_value = mock_redis
            
            # Mock Celery task
            with patch('app.api.v1.webhooks.process_deposit.delay') as mock_delay:
                mock_delay.return_value = None
                
                # Send webhook with user_id but no existing transaction
                webhook_payload = {
                    "tx_hash": "0xnewtransaction",
                    "confirmations": 3,
                    "chain": "bep20",
                    "to_address": "0xrecipient",
                    "amount": "50.25",
                    "currency": "USDT",
                    "user_id": str(test_user.id),
                    "metadata": {}
                }
                
                response = await test_client.post("/api/v1/webhooks/bep20", json=webhook_payload)
                
                assert response.status_code == 200
                data = response.json()
                assert data["ok"] is True
                assert data["enqueued"] is True
                
                # Verify task was enqueued (with new transaction ID)
                mock_delay.assert_called_once()
                call_args = mock_delay.call_args[0]
                assert len(call_args) == 1
                assert isinstance(call_args[0], str)  # Transaction ID as string
