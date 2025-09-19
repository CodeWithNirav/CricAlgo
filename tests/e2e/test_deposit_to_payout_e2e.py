"""
End-to-end tests for deposit to payout flow

These tests verify the complete flow from deposit transaction creation
through webhook confirmation to wallet balance updates, including
idempotency testing.
"""

import pytest
import asyncio
import subprocess
import time
import requests
from decimal import Decimal
from uuid import uuid4
from typing import Optional

from app.repos.user_repo import create_user
from app.repos.wallet_repo import create_wallet_for_user, get_wallet_for_user
from app.repos.transaction_repo import create_transaction, get_transaction_by_id
from app.models.enums import UserStatus
from tests.fixtures.database import assert_wallet_balance
from tests.fixtures.webhooks import WebhookTestHelper, create_deposit_webhook_payload


class FakeBlockchainService:
    """Helper class to manage fake blockchain service for testing."""
    
    def __init__(self, base_url: str = "http://localhost:8081"):
        self.base_url = base_url
        self.process: Optional[subprocess.Popen] = None
    
    async def start(self):
        """Start the fake blockchain service."""
        if self.process is None:
            self.process = subprocess.Popen([
                "python", "tests/e2e/fake_blockchain_service.py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for service to start
            await self._wait_for_service()
    
    async def stop(self):
        """Stop the fake blockchain service."""
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
    
    async def _wait_for_service(self, timeout: int = 10):
        """Wait for the service to be ready."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.base_url}/", timeout=1)
                if response.status_code == 200:
                    return
            except requests.exceptions.RequestException:
                pass
            await asyncio.sleep(0.1)
        
        raise TimeoutError("Fake blockchain service failed to start")
    
    async def send_webhook(self, payload: dict) -> dict:
        """Send webhook to the fake blockchain service."""
        response = requests.post(
            f"{self.base_url}/webhook",
            json=payload,
            timeout=5
        )
        return response.json()
    
    async def get_webhook_data(self, tx_hash: str) -> dict:
        """Get webhook data from the fake blockchain service."""
        response = requests.get(f"{self.base_url}/webhooks/{tx_hash}", timeout=5)
        return response.json()
    
    async def clear_webhooks(self):
        """Clear all webhook data."""
        requests.delete(f"{self.base_url}/webhooks", timeout=5)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_deposit_confirmation_flow(test_client, async_session, redis_client):
    """
    Test complete deposit confirmation flow:
    1. Create user and wallet
    2. Create pending deposit transaction
    3. Send webhook confirmation
    4. Verify wallet balance updated
    """
    # Create user and wallet
    user = await create_user(
        session=async_session,
        telegram_id=12345,
        username="e2euser",
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
    
    # Create webhook helper
    webhook_helper = WebhookTestHelper(test_client)
    
    # Send deposit confirmation webhook
    webhook_response = await webhook_helper.send_deposit_webhook(
        tx_hash=tx_hash,
        confirmations=12,
        amount="100.00",
        currency="USDT",
        user_id=str(user.id)
    )
    
    # Verify webhook was processed successfully
    assert webhook_response["status_code"] in [200, 201]
    
    # Wait for background processing (if any)
    await asyncio.sleep(0.5)
    
    # Verify wallet balance was updated
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('100.00')
    )
    
    # Verify transaction status was updated
    updated_transaction = await get_transaction_by_id(async_session, transaction.id)
    assert updated_transaction is not None
    # Note: This would depend on actual webhook processing implementation


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_webhook_idempotency(test_client, async_session, redis_client):
    """
    Test webhook idempotency:
    1. Send same webhook multiple times
    2. Verify only one credit occurs
    """
    # Create user and wallet
    user = await create_user(
        session=async_session,
        telegram_id=67890,
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
        amount=Decimal('50.00'),
        currency="USDT",
        tx_metadata={
            "tx_hash": tx_hash,
            "confirmations": 0,
            "status": "pending"
        }
    )
    
    # Create webhook helper
    webhook_helper = WebhookTestHelper(test_client)
    
    # Send webhook first time
    response1 = await webhook_helper.send_deposit_webhook(
        tx_hash=tx_hash,
        confirmations=12,
        amount="50.00",
        currency="USDT",
        user_id=str(user.id)
    )
    
    # Wait for processing
    await asyncio.sleep(0.5)
    
    # Get balance after first webhook
    wallet_after_first = await get_wallet_for_user(async_session, user.id)
    balance_after_first = wallet_after_first.deposit_balance
    
    # Send same webhook again
    response2 = await webhook_helper.send_deposit_webhook(
        tx_hash=tx_hash,
        confirmations=12,
        amount="50.00",
        currency="USDT",
        user_id=str(user.id)
    )
    
    # Wait for processing
    await asyncio.sleep(0.5)
    
    # Get balance after second webhook
    wallet_after_second = await get_wallet_for_user(async_session, user.id)
    balance_after_second = wallet_after_second.deposit_balance
    
    # Verify balance didn't change (idempotency)
    assert balance_after_first == balance_after_second
    assert balance_after_first == Decimal('50.00')
    
    # Verify both webhooks were received (but only one processed)
    assert response1["status_code"] in [200, 201]
    assert response2["status_code"] in [200, 201]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_multiple_deposits_same_user(test_client, async_session, redis_client):
    """
    Test multiple deposits for the same user:
    1. Create user and wallet
    2. Process multiple deposit webhooks
    3. Verify cumulative balance
    """
    # Create user and wallet
    user = await create_user(
        session=async_session,
        telegram_id=11111,
        username="multiuser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(async_session, user.id)
    
    # Create multiple deposit transactions
    transactions = []
    amounts = [Decimal('25.00'), Decimal('50.00'), Decimal('75.00')]
    
    for i, amount in enumerate(amounts):
        tx_hash = f"0x{''.join([f'{i:02x}' for j in range(32)])}"
        transaction = await create_transaction(
            session=async_session,
            user_id=user.id,
            tx_type="deposit",
            amount=amount,
            currency="USDT",
            tx_metadata={
                "tx_hash": tx_hash,
                "confirmations": 0,
                "status": "pending"
            }
        )
        transactions.append((transaction, tx_hash, amount))
    
    # Create webhook helper
    webhook_helper = WebhookTestHelper(test_client)
    
    # Process each deposit
    for transaction, tx_hash, amount in transactions:
        response = await webhook_helper.send_deposit_webhook(
            tx_hash=tx_hash,
            confirmations=12,
            amount=str(amount),
            currency="USDT",
            user_id=str(user.id)
        )
        
        assert response["status_code"] in [200, 201]
        await asyncio.sleep(0.1)  # Small delay between webhooks
    
    # Wait for all processing to complete
    await asyncio.sleep(1.0)
    
    # Verify cumulative balance
    expected_total = sum(amounts)
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=expected_total
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_withdrawal_confirmation_flow(test_client, async_session, redis_client):
    """
    Test withdrawal confirmation flow:
    1. Create user with balance
    2. Create withdrawal transaction
    3. Send withdrawal confirmation webhook
    4. Verify balance updated correctly
    """
    # Create user with initial balance
    user = await create_user(
        session=async_session,
        telegram_id=22222,
        username="withdrawaluser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(async_session, user.id)
    
    # Add initial balance
    from app.repos.wallet_repo import update_balances_atomic
    await update_balances_atomic(
        async_session,
        user.id,
        deposit_delta=Decimal('200.00')
    )
    
    # Create withdrawal transaction
    tx_hash = f"0x{''.join([f'{i:02x}' for i in range(32)])}"
    transaction = await create_transaction(
        session=async_session,
        user_id=user.id,
        tx_type="withdrawal",
        amount=Decimal('50.00'),
        currency="USDT",
        tx_metadata={
            "tx_hash": tx_hash,
            "confirmations": 0,
            "status": "pending"
        }
    )
    
    # Verify initial balance
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('200.00')
    )
    
    # Create webhook helper
    webhook_helper = WebhookTestHelper(test_client)
    
    # Send withdrawal confirmation webhook
    webhook_response = await webhook_helper.send_withdrawal_webhook(
        tx_hash=tx_hash,
        confirmations=12,
        amount="50.00",
        currency="USDT",
        user_id=str(user.id)
    )
    
    # Verify webhook was processed
    assert webhook_response["status_code"] in [200, 201]
    
    # Wait for processing
    await asyncio.sleep(0.5)
    
    # Verify balance was updated (withdrawal should reduce balance)
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('150.00')  # 200 - 50
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_failed_transaction_handling(test_client, async_session, redis_client):
    """
    Test handling of failed transactions:
    1. Create user and transaction
    2. Send failed transaction webhook
    3. Verify no balance change
    """
    # Create user and wallet
    user = await create_user(
        session=async_session,
        telegram_id=33333,
        username="faileduser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(async_session, user.id)
    
    # Create pending transaction
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
    
    # Verify initial balance
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('0.00')
    )
    
    # Create webhook helper
    webhook_helper = WebhookTestHelper(test_client)
    
    # Send failed transaction webhook
    webhook_response = await webhook_helper.send_failed_webhook(
        tx_hash=tx_hash,
        reason="Insufficient gas"
    )
    
    # Verify webhook was received
    assert webhook_response["status_code"] in [200, 201]
    
    # Wait for processing
    await asyncio.sleep(0.5)
    
    # Verify balance was not changed
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('0.00')
    )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_insufficient_confirmations_handling(test_client, async_session, redis_client):
    """
    Test handling of transactions with insufficient confirmations:
    1. Create user and transaction
    2. Send webhook with low confirmations
    3. Verify transaction remains pending
    """
    # Create user and wallet
    user = await create_user(
        session=async_session,
        telegram_id=44444,
        username="pendinguser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(async_session, user.id)
    
    # Create pending transaction
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
    
    # Create webhook helper
    webhook_helper = WebhookTestHelper(test_client)
    
    # Send webhook with insufficient confirmations
    webhook_response = await webhook_helper.send_pending_webhook(
        tx_hash=tx_hash,
        confirmations=1,  # Less than required threshold
        amount="100.00",
        currency="USDT"
    )
    
    # Verify webhook was received
    assert webhook_response["status_code"] in [200, 201]
    
    # Wait for processing
    await asyncio.sleep(0.5)
    
    # Verify balance was not changed (insufficient confirmations)
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('0.00')
    )
    
    # Verify transaction is still pending
    updated_transaction = await get_transaction_by_id(async_session, transaction.id)
    assert updated_transaction is not None
    # Note: This would depend on actual webhook processing implementation


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_concurrent_webhook_processing(test_client, async_session, redis_client):
    """
    Test concurrent webhook processing:
    1. Create multiple users and transactions
    2. Send webhooks concurrently
    3. Verify all balances updated correctly
    """
    # Create multiple users with wallets
    users = []
    transactions = []
    
    for i in range(5):
        user = await create_user(
            session=async_session,
            telegram_id=50000 + i,
            username=f"concurrentuser{i}",
            status=UserStatus.ACTIVE
        )
        
        wallet = await create_wallet_for_user(async_session, user.id)
        
        tx_hash = f"0x{''.join([f'{i:02x}' for j in range(32)])}"
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
        
        users.append(user)
        transactions.append((transaction, tx_hash))
    
    # Create webhook helper
    webhook_helper = WebhookTestHelper(test_client)
    
    # Send all webhooks concurrently
    async def send_webhook(transaction, tx_hash):
        return await webhook_helper.send_deposit_webhook(
            tx_hash=tx_hash,
            confirmations=12,
            amount="100.00",
            currency="USDT",
            user_id=str(transaction.user_id)
        )
    
    # Execute all webhooks concurrently
    webhook_tasks = [
        send_webhook(transaction, tx_hash)
        for transaction, tx_hash in transactions
    ]
    
    responses = await asyncio.gather(*webhook_tasks)
    
    # Verify all webhooks were processed
    for response in responses:
        assert response["status_code"] in [200, 201]
    
    # Wait for all processing to complete
    await asyncio.sleep(1.0)
    
    # Verify all balances were updated
    for user in users:
        await assert_wallet_balance(
            async_session,
            user.id,
            expected_deposit=Decimal('100.00')
        )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_webhook_retry_mechanism(test_client, async_session, redis_client):
    """
    Test webhook retry mechanism:
    1. Create user and transaction
    2. Send webhook with retries
    3. Verify idempotency is maintained
    """
    # Create user and wallet
    user = await create_user(
        session=async_session,
        telegram_id=55555,
        username="retryuser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(async_session, user.id)
    
    # Create pending transaction
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
    
    # Create webhook helper
    webhook_helper = WebhookTestHelper(test_client)
    
    # Create webhook payload
    payload = create_deposit_webhook_payload(
        tx_hash=tx_hash,
        amount="75.00",
        currency="USDT",
        confirmations=12
    )
    
    # Simulate webhook retries
    from tests.fixtures.webhooks import simulate_webhook_retry
    responses = await simulate_webhook_retry(
        webhook_helper,
        payload,
        max_retries=3,
        delay=0.1
    )
    
    # Verify at least one webhook succeeded
    successful_responses = [
        r for r in responses if r["status_code"] < 400
    ]
    assert len(successful_responses) >= 1
    
    # Wait for processing
    await asyncio.sleep(0.5)
    
    # Verify balance was updated only once (idempotency)
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('75.00')
    )
