"""
Database-specific test fixtures and utilities
"""

import asyncio
from typing import AsyncGenerator, List
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.models.enums import UserStatus
from app.repos.user_repo import create_user
from app.repos.wallet_repo import create_wallet_for_user, update_balances_atomic
from app.repos.transaction_repo import create_transaction


async def create_test_user_with_wallet(
    session: AsyncSession,
    telegram_id: int,
    username: str,
    status: UserStatus = UserStatus.ACTIVE
) -> User:
    """Create a test user with associated wallet."""
    user = await create_user(
        session=session,
        telegram_id=telegram_id,
        username=username,
        status=status
    )
    
    # Create wallet for user
    await create_wallet_for_user(session, user.id)
    
    return user


async def create_test_user_with_balance(
    session: AsyncSession,
    telegram_id: int,
    username: str,
    deposit_balance: Decimal = Decimal('0'),
    bonus_balance: Decimal = Decimal('0'),
    winning_balance: Decimal = Decimal('0'),
    status: UserStatus = UserStatus.ACTIVE
) -> User:
    """Create a test user with wallet and specified balances."""
    user = await create_test_user_with_wallet(session, telegram_id, username, status)
    
    if deposit_balance > 0 or bonus_balance > 0 or winning_balance > 0:
        await update_balances_atomic(
            session,
            user.id,
            deposit_delta=deposit_balance,
            bonus_delta=bonus_balance,
            winning_delta=winning_balance
        )
    
    return user


async def create_test_transaction(
    session: AsyncSession,
    user_id: UUID,
    tx_type: str = "deposit",
    amount: Decimal = Decimal('100.00'),
    currency: str = "USDT",
    tx_hash: str = None,
    confirmations: int = 0,
    **kwargs
) -> Transaction:
    """Create a test transaction with common defaults."""
    if tx_hash is None:
        tx_hash = f"0x{''.join([f'{i:02x}' for i in range(32)])}"
    
    metadata = {
        "tx_hash": tx_hash,
        "confirmations": confirmations,
        **kwargs.get("tx_metadata", {})
    }
    
    return await create_transaction(
        session=session,
        user_id=user_id,
        tx_type=tx_type,
        amount=amount,
        currency=currency,
        tx_metadata=metadata,
        **{k: v for k, v in kwargs.items() if k != "tx_metadata"}
    )


async def create_multiple_test_users(
    session: AsyncSession,
    count: int,
    base_telegram_id: int = 10000
) -> List[User]:
    """Create multiple test users with wallets."""
    users = []
    
    for i in range(count):
        user = await create_test_user_with_wallet(
            session,
            telegram_id=base_telegram_id + i,
            username=f"testuser{i}"
        )
        users.append(user)
    
    return users


async def get_wallet_balance(session: AsyncSession, user_id: UUID) -> dict:
    """Get current wallet balance for a user."""
    from app.repos.wallet_repo import get_wallet_for_user
    
    wallet = await get_wallet_for_user(session, user_id)
    if not wallet:
        return {"deposit": Decimal('0'), "bonus": Decimal('0'), "winning": Decimal('0')}
    
    return {
        "deposit": wallet.deposit_balance,
        "bonus": wallet.bonus_balance,
        "winning": wallet.winning_balance
    }


async def assert_wallet_balance(
    session: AsyncSession,
    user_id: UUID,
    expected_deposit: Decimal,
    expected_bonus: Decimal = None,
    expected_winning: Decimal = None
):
    """Assert wallet balance matches expected values."""
    balance = await get_wallet_balance(session, user_id)
    
    assert balance["deposit"] == expected_deposit
    if expected_bonus is not None:
        assert balance["bonus"] == expected_bonus
    if expected_winning is not None:
        assert balance["winning"] == expected_winning


async def simulate_concurrent_operations(
    session: AsyncSession,
    operations: List[callable],
    max_concurrent: int = 5
) -> List:
    """
    Simulate concurrent operations using asyncio.gather.
    
    Args:
        session: Database session
        operations: List of async functions to execute concurrently
        max_concurrent: Maximum number of concurrent operations
    
    Returns:
        List of results from all operations
    """
    # Split operations into batches to avoid overwhelming the database
    results = []
    
    for i in range(0, len(operations), max_concurrent):
        batch = operations[i:i + max_concurrent]
        batch_results = await asyncio.gather(*[op() for op in batch], return_exceptions=True)
        results.extend(batch_results)
    
    return results


class DatabaseTestHelper:
    """Helper class for common database test operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_user_with_balance(
        self,
        telegram_id: int,
        username: str,
        deposit: Decimal = Decimal('0'),
        bonus: Decimal = Decimal('0'),
        winning: Decimal = Decimal('0')
    ) -> User:
        """Create user with specified balances."""
        return await create_test_user_with_balance(
            self.session, telegram_id, username, deposit, bonus, winning
        )
    
    async def create_deposit_transaction(
        self,
        user_id: UUID,
        amount: Decimal,
        tx_hash: str = None
    ) -> Transaction:
        """Create a deposit transaction."""
        return await create_test_transaction(
            self.session,
            user_id=user_id,
            tx_type="deposit",
            amount=amount,
            tx_hash=tx_hash
        )
    
    async def create_withdrawal_transaction(
        self,
        user_id: UUID,
        amount: Decimal,
        tx_hash: str = None
    ) -> Transaction:
        """Create a withdrawal transaction."""
        return await create_test_transaction(
            self.session,
            user_id=user_id,
            tx_type="withdrawal",
            amount=amount,
            tx_hash=tx_hash
        )
    
    async def get_user_by_username(self, username: str) -> User:
        """Get user by username."""
        from app.repos.user_repo import get_user_by_username
        return await get_user_by_username(self.session, username)
    
    async def get_wallet_balance(self, user_id: UUID) -> dict:
        """Get wallet balance for user."""
        return await get_wallet_balance(self.session, user_id)
