"""
Integration tests for wallet repository operations

These tests verify the wallet repository's atomic operations, concurrency handling,
and integration with the database layer using real database connections.
"""

import pytest
import asyncio
from decimal import Decimal
from uuid import uuid4

from app.repos.wallet_repo import (
    create_wallet_for_user,
    get_wallet_for_user,
    update_balances_atomic,
    debit_for_contest_entry
)
from app.repos.user_repo import create_user
from app.models.enums import UserStatus
from tests.fixtures.database import (
    create_test_user_with_balance,
    simulate_concurrent_operations,
    assert_wallet_balance,
    DatabaseTestHelper
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_wallet_creation_and_retrieval(async_session):
    """Test wallet creation and retrieval operations."""
    # Create user
    user = await create_user(
        session=async_session,
        telegram_id=12345,
        username="walletuser",
        status=UserStatus.ACTIVE
    )
    
    # Create wallet
    wallet = await create_wallet_for_user(async_session, user.id)
    
    assert wallet is not None
    assert wallet.user_id == user.id
    assert wallet.deposit_balance == Decimal('0')
    assert wallet.winning_balance == Decimal('0')
    assert wallet.bonus_balance == Decimal('0')
    
    # Retrieve wallet
    retrieved_wallet = await get_wallet_for_user(async_session, user.id)
    assert retrieved_wallet is not None
    assert retrieved_wallet.id == wallet.id
    assert retrieved_wallet.user_id == user.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_atomic_balance_updates(async_session):
    """Test atomic balance update operations."""
    # Create user with wallet
    user = await create_test_user_with_balance(
        async_session,
        telegram_id=67890,
        username="balanceuser",
        deposit_balance=Decimal('100.00'),
        bonus_balance=Decimal('50.00'),
        winning_balance=Decimal('25.00')
    )
    
    # Test deposit to deposit balance
    success, error = await update_balances_atomic(
        async_session,
        user.id,
        deposit_delta=Decimal('50.00')
    )
    
    assert success is True
    assert error is None
    
    # Verify balance was updated
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('150.00'),
        expected_bonus=Decimal('50.00'),
        expected_winning=Decimal('25.00')
    )
    
    # Test withdrawal from deposit balance
    success, error = await update_balances_atomic(
        async_session,
        user.id,
        deposit_delta=Decimal('-25.00')
    )
    
    assert success is True
    assert error is None
    
    # Verify balance was updated
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('125.00'),
        expected_bonus=Decimal('50.00'),
        expected_winning=Decimal('25.00')
    )
    
    # Test negative balance (should fail)
    success, error = await update_balances_atomic(
        async_session,
        user.id,
        deposit_delta=Decimal('-200.00')
    )
    
    assert success is False
    assert "Insufficient deposit balance" in error
    
    # Verify balance wasn't changed
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('125.00'),
        expected_bonus=Decimal('50.00'),
        expected_winning=Decimal('25.00')
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_contest_entry_debit_priority(async_session):
    """Test contest entry debit with priority order."""
    # Create user with balances
    user = await create_test_user_with_balance(
        async_session,
        telegram_id=11111,
        username="contestuser",
        deposit_balance=Decimal('100.00'),
        bonus_balance=Decimal('50.00'),
        winning_balance=Decimal('25.00')
    )
    
    # Test small debit (should use deposit only)
    success, error = await debit_for_contest_entry(
        async_session,
        user.id,
        Decimal('30.00')
    )
    
    assert success is True
    assert error is None
    
    # Verify balances
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('70.00'),
        expected_bonus=Decimal('50.00'),
        expected_winning=Decimal('25.00')
    )
    
    # Test larger debit (should use deposit + bonus)
    success, error = await debit_for_contest_entry(
        async_session,
        user.id,
        Decimal('80.00')
    )
    
    assert success is True
    assert error is None
    
    # Verify balances
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('0.00'),
        expected_bonus=Decimal('40.00'),
        expected_winning=Decimal('25.00')
    )
    
    # Test largest debit (should use all remaining)
    success, error = await debit_for_contest_entry(
        async_session,
        user.id,
        Decimal('65.00')
    )
    
    assert success is True
    assert error is None
    
    # Verify balances
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('0.00'),
        expected_bonus=Decimal('0.00'),
        expected_winning=Decimal('0.00')
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_balance_updates(async_session):
    """Test concurrent balance updates to verify no race conditions."""
    # Create user with initial balance
    user = await create_test_user_with_balance(
        async_session,
        telegram_id=22222,
        username="concurrentuser",
        deposit_balance=Decimal('1000.00')
    )
    
    # Define concurrent operations
    async def deposit_operation():
        return await update_balances_atomic(
            async_session,
            user.id,
            deposit_delta=Decimal('10.00')
        )
    
    async def withdrawal_operation():
        return await update_balances_atomic(
            async_session,
            user.id,
            deposit_delta=Decimal('-5.00')
        )
    
    # Create multiple concurrent operations
    operations = []
    for i in range(20):  # 20 operations
        if i % 2 == 0:
            operations.append(deposit_operation)
        else:
            operations.append(withdrawal_operation)
    
    # Execute operations concurrently
    results = await simulate_concurrent_operations(
        async_session,
        operations,
        max_concurrent=10
    )
    
    # Verify all operations succeeded
    successful_operations = [r for r in results if isinstance(r, tuple) and r[0] is True]
    assert len(successful_operations) == 20
    
    # Calculate expected final balance
    # 1000 + (10 * 10) - (5 * 10) = 1000 + 100 - 50 = 1050
    expected_balance = Decimal('1050.00')
    
    # Verify final balance
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=expected_balance
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_insufficient_balance_handling(async_session):
    """Test handling of insufficient balance scenarios."""
    # Create user with small balance
    user = await create_test_user_with_balance(
        async_session,
        telegram_id=33333,
        username="pooruser",
        deposit_balance=Decimal('10.00')
    )
    
    # Try to debit more than available
    success, error = await debit_for_contest_entry(
        async_session,
        user.id,
        Decimal('50.00')
    )
    
    assert success is False
    assert "Insufficient balance" in error
    
    # Verify balance wasn't changed
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('10.00')
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_balance_types_update(async_session):
    """Test updating multiple balance types in one operation."""
    # Create user with balances
    user = await create_test_user_with_balance(
        async_session,
        telegram_id=44444,
        username="multibalanceuser",
        deposit_balance=Decimal('100.00'),
        bonus_balance=Decimal('50.00'),
        winning_balance=Decimal('25.00')
    )
    
    # Update all balance types
    success, error = await update_balances_atomic(
        async_session,
        user.id,
        deposit_delta=Decimal('20.00'),
        bonus_delta=Decimal('-10.00'),
        winning_delta=Decimal('5.00')
    )
    
    assert success is True
    assert error is None
    
    # Verify all balances were updated
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('120.00'),
        expected_bonus=Decimal('40.00'),
        expected_winning=Decimal('30.00')
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_wallet_not_found_handling(async_session):
    """Test handling when wallet doesn't exist."""
    fake_user_id = uuid4()
    
    # Try to update non-existent wallet
    success, error = await update_balances_atomic(
        async_session,
        fake_user_id,
        deposit_delta=Decimal('100.00')
    )
    
    assert success is False
    assert "Wallet not found" in error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_helper_integration(async_session):
    """Test integration with database helper utilities."""
    helper = DatabaseTestHelper(async_session)
    
    # Create user with balance using helper
    user = await helper.create_user_with_balance(
        telegram_id=55555,
        username="helperuser",
        deposit=Decimal('200.00'),
        bonus=Decimal('100.00'),
        winning=Decimal('50.00')
    )
    
    assert user is not None
    assert user.username == "helperuser"
    
    # Verify balances using helper
    balance = await helper.get_wallet_balance(user.id)
    assert balance["deposit"] == Decimal('200.00')
    assert balance["bonus"] == Decimal('100.00')
    assert balance["winning"] == Decimal('50.00')
    
    # Create transactions using helper
    deposit_tx = await helper.create_deposit_transaction(
        user.id,
        Decimal('50.00'),
        "0x1234567890abcdef"
    )
    
    assert deposit_tx is not None
    assert deposit_tx.tx_type == "deposit"
    assert deposit_tx.amount == Decimal('50.00')
    
    withdrawal_tx = await helper.create_withdrawal_transaction(
        user.id,
        Decimal('25.00'),
        "0xfedcba0987654321"
    )
    
    assert withdrawal_tx is not None
    assert withdrawal_tx.tx_type == "withdrawal"
    assert withdrawal_tx.amount == Decimal('25.00')


@pytest.mark.integration
@pytest.mark.asyncio
async def test_balance_precision_handling(async_session):
    """Test handling of decimal precision in balance operations."""
    # Create user with precise balance
    user = await create_test_user_with_balance(
        async_session,
        telegram_id=66666,
        username="precisionuser",
        deposit_balance=Decimal('100.12345678')
    )
    
    # Test precise operations
    success, error = await update_balances_atomic(
        async_session,
        user.id,
        deposit_delta=Decimal('0.87654322')
    )
    
    assert success is True
    assert error is None
    
    # Verify precise balance
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('101.00000000')
    )
    
    # Test precise debit
    success, error = await debit_for_contest_entry(
        async_session,
        user.id,
        Decimal('0.50000000')
    )
    
    assert success is True
    assert error is None
    
    # Verify precise balance after debit
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('100.50000000')
    )
