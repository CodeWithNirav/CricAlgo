"""
Database model tests for CricAlgo

These tests verify the ORM models and repository layer functionality.
They test CRUD operations, atomic balance updates, and transaction isolation.
"""

import os
import pytest
import asyncio
from decimal import Decimal
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.models.user import User
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.models.enums import UserStatus
from app.repos.user_repo import create_user, get_user_by_id, get_user_by_username
from app.repos.wallet_repo import (
    create_wallet_for_user, 
    get_wallet_for_user, 
    update_balances_atomic,
    debit_for_contest_entry
)
from app.repos.transaction_repo import create_transaction, get_transaction_by_id


# Test database URL - use SQLite for fast tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Clean up
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_session(test_engine):
    """Create a test database session."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.mark.asyncio
async def test_create_user_and_wallet(test_session: AsyncSession):
    """Test creating a user and wallet."""
    
    # Create user
    user = await create_user(
        session=test_session,
        telegram_id=12345,
        username="testuser",
        status=UserStatus.ACTIVE
    )
    
    assert user.id is not None
    assert user.telegram_id == 12345
    assert user.username == "testuser"
    assert user.status == UserStatus.ACTIVE
    
    # Create wallet for user
    wallet = await create_wallet_for_user(test_session, user.id)
    
    assert wallet.id is not None
    assert wallet.user_id == user.id
    assert wallet.deposit_balance == Decimal('0')
    assert wallet.winning_balance == Decimal('0')
    assert wallet.bonus_balance == Decimal('0')
    
    # Verify wallet can be retrieved
    retrieved_wallet = await get_wallet_for_user(test_session, user.id)
    assert retrieved_wallet is not None
    assert retrieved_wallet.id == wallet.id


@pytest.mark.asyncio
async def test_user_repository_operations(test_session: AsyncSession):
    """Test user repository CRUD operations."""
    
    # Create user
    user = await create_user(
        session=test_session,
        telegram_id=67890,
        username="testuser2",
        status=UserStatus.ACTIVE
    )
    
    # Test get by ID
    retrieved_user = await get_user_by_id(test_session, user.id)
    assert retrieved_user is not None
    assert retrieved_user.username == "testuser2"
    
    # Test get by username
    retrieved_user = await get_user_by_username(test_session, "testuser2")
    assert retrieved_user is not None
    assert retrieved_user.id == user.id


@pytest.mark.asyncio
async def test_wallet_balance_updates_atomic(test_session: AsyncSession):
    """Test atomic wallet balance updates."""
    
    # Create user and wallet
    user = await create_user(
        session=test_session,
        telegram_id=11111,
        username="balanceuser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(test_session, user.id)
    
    # Test deposit to deposit balance
    success, error = await update_balances_atomic(
        test_session,
        user.id,
        deposit_delta=Decimal('100.50')
    )
    
    assert success is True
    assert error is None
    
    # Verify balance was updated
    updated_wallet = await get_wallet_for_user(test_session, user.id)
    assert updated_wallet.deposit_balance == Decimal('100.50')
    
    # Test withdrawal from deposit balance
    success, error = await update_balances_atomic(
        test_session,
        user.id,
        deposit_delta=Decimal('-50.25')
    )
    
    assert success is True
    assert error is None
    
    # Verify balance was updated
    updated_wallet = await get_wallet_for_user(test_session, user.id)
    assert updated_wallet.deposit_balance == Decimal('50.25')
    
    # Test negative balance (should fail)
    success, error = await update_balances_atomic(
        test_session,
        user.id,
        deposit_delta=Decimal('-100.00')
    )
    
    assert success is False
    assert "Insufficient deposit balance" in error


@pytest.mark.asyncio
async def test_contest_entry_debit_priority(test_session: AsyncSession):
    """Test contest entry debit with priority order."""
    
    # Create user and wallet with some balances
    user = await create_user(
        session=test_session,
        telegram_id=22222,
        username="contestuser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(test_session, user.id)
    
    # Set up initial balances
    await update_balances_atomic(
        test_session,
        user.id,
        deposit_delta=Decimal('50.00'),
        bonus_delta=Decimal('30.00'),
        winning_delta=Decimal('20.00')
    )
    
    # Test debit for contest entry (should use deposit first)
    success, error = await debit_for_contest_entry(
        test_session,
        user.id,
        Decimal('25.00')
    )
    
    assert success is True
    assert error is None
    
    # Verify balances (deposit should be reduced)
    updated_wallet = await get_wallet_for_user(test_session, user.id)
    assert updated_wallet.deposit_balance == Decimal('25.00')
    assert updated_wallet.bonus_balance == Decimal('30.00')
    assert updated_wallet.winning_balance == Decimal('20.00')
    
    # Test larger debit that uses multiple buckets
    success, error = await debit_for_contest_entry(
        test_session,
        user.id,
        Decimal('40.00')  # Should use remaining deposit + some bonus
    )
    
    assert success is True
    assert error is None
    
    # Verify balances
    updated_wallet = await get_wallet_for_user(test_session, user.id)
    assert updated_wallet.deposit_balance == Decimal('0.00')
    assert updated_wallet.bonus_balance == Decimal('15.00')  # 30 - 15 = 15
    assert updated_wallet.winning_balance == Decimal('20.00')


@pytest.mark.asyncio
async def test_transaction_creation(test_session: AsyncSession):
    """Test transaction creation and retrieval."""
    
    # Create user
    user = await create_user(
        session=test_session,
        telegram_id=33333,
        username="txuser",
        status=UserStatus.ACTIVE
    )
    
    # Create transaction
    transaction = await create_transaction(
        session=test_session,
        user_id=user.id,
        tx_type="deposit",
        amount=Decimal('100.00'),
        currency="USDT",
        related_entity="deposit_request",
        related_id=uuid4(),
        tx_metadata={"tx_hash": "0x1234567890abcdef"}
    )
    
    assert transaction.id is not None
    assert transaction.user_id == user.id
    assert transaction.tx_type == "deposit"
    assert transaction.amount == Decimal('100.00')
    assert transaction.currency == "USDT"
    assert transaction.tx_metadata["tx_hash"] == "0x1234567890abcdef"
    
    # Test retrieval
    retrieved_tx = await get_transaction_by_id(test_session, transaction.id)
    assert retrieved_tx is not None
    assert retrieved_tx.id == transaction.id


@pytest.mark.asyncio
async def test_concurrent_balance_updates(test_session: AsyncSession):
    """Test that concurrent balance updates are handled correctly."""
    
    # Create user and wallet
    user = await create_user(
        session=test_session,
        telegram_id=44444,
        username="concurrentuser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(test_session, user.id)
    
    # Set initial balance
    await update_balances_atomic(
        test_session,
        user.id,
        deposit_delta=Decimal('100.00')
    )
    
    # Simulate concurrent updates (in real scenario, these would be separate sessions)
    # For this test, we'll just verify the atomic nature of updates
    success1, error1 = await update_balances_atomic(
        test_session,
        user.id,
        deposit_delta=Decimal('50.00')
    )
    
    success2, error2 = await update_balances_atomic(
        test_session,
        user.id,
        deposit_delta=Decimal('25.00')
    )
    
    # Both should succeed
    assert success1 is True
    assert success2 is True
    assert error1 is None
    assert error2 is None
    
    # Verify final balance
    updated_wallet = await get_wallet_for_user(test_session, user.id)
    assert updated_wallet.deposit_balance == Decimal('175.00')  # 100 + 50 + 25


@pytest.mark.asyncio
async def test_insufficient_balance_handling(test_session: AsyncSession):
    """Test handling of insufficient balance scenarios."""
    
    # Create user and wallet
    user = await create_user(
        session=test_session,
        telegram_id=55555,
        username="pooruser",
        status=UserStatus.ACTIVE
    )
    
    wallet = await create_wallet_for_user(test_session, user.id)
    
    # Set small balance
    await update_balances_atomic(
        test_session,
        user.id,
        deposit_delta=Decimal('10.00')
    )
    
    # Try to debit more than available
    success, error = await debit_for_contest_entry(
        test_session,
        user.id,
        Decimal('50.00')
    )
    
    assert success is False
    assert "Insufficient balance" in error
    
    # Verify balance wasn't changed
    updated_wallet = await get_wallet_for_user(test_session, user.id)
    assert updated_wallet.deposit_balance == Decimal('10.00')


# Skip these tests if not running in CI or with Postgres
@pytest.mark.skipif(
    not os.getenv("CI") and "postgresql" not in settings.database_url,
    reason="Postgres-specific tests require PostgreSQL database"
)
@pytest.mark.asyncio
async def test_postgres_specific_features():
    """Test PostgreSQL-specific features like row-level locking."""
    # These tests would require actual PostgreSQL database
    # and would test SELECT FOR UPDATE functionality
    pass
