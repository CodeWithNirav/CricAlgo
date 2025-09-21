"""
Wallet repository with atomic balance operations
"""

from typing import Optional, Tuple
from uuid import UUID
from decimal import Decimal
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from app.models.wallet import Wallet
from app.models.user import User

# Configure logging
logger = logging.getLogger(__name__)


async def get_wallet_for_user(session: AsyncSession, user_id: UUID) -> Optional[Wallet]:
    """
    Get wallet for a specific user.
    
    Args:
        session: Database session
        user_id: User UUID
    
    Returns:
        Wallet instance or None if not found
    """
    result = await session.execute(
        select(Wallet).where(Wallet.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_wallet_for_user(session: AsyncSession, user_id: UUID) -> Wallet:
    """
    Create a new wallet for a user.
    
    Args:
        session: Database session
        user_id: User UUID
    
    Returns:
        Created Wallet instance or existing wallet if one already exists
    """
    # Check if wallet already exists
    existing_wallet = await get_wallet_for_user(session, user_id)
    if existing_wallet:
        return existing_wallet
    
    wallet = Wallet(
        user_id=user_id,
        deposit_balance=Decimal('0'),
        winning_balance=Decimal('0'),
        bonus_balance=Decimal('0')
    )
    session.add(wallet)
    await session.commit()
    await session.refresh(wallet)
    return wallet


async def update_balances_atomic(
    session: AsyncSession,
    user_id: UUID,
    deposit_delta: Decimal = Decimal('0'),
    winning_delta: Decimal = Decimal('0'),
    bonus_delta: Decimal = Decimal('0')
) -> Tuple[bool, Optional[str]]:
    """
    Atomically update wallet balances with row-level locking.
    
    This function uses SELECT FOR UPDATE to prevent race conditions
    and ensures atomic balance updates within a single transaction.
    
    Args:
        session: Database session
        user_id: User UUID
        deposit_delta: Change to deposit balance (can be negative)
        winning_delta: Change to winning balance (can be negative)
        bonus_delta: Change to bonus balance (can be negative)
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        # Lock the wallet row for update to prevent race conditions
        result = await session.execute(
            select(Wallet)
            .where(Wallet.user_id == user_id)
            .with_for_update()
        )
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            return False, "Wallet not found"
        
        # Calculate new balances
        new_deposit = wallet.deposit_balance + deposit_delta
        new_winning = wallet.winning_balance + winning_delta
        new_bonus = wallet.bonus_balance + bonus_delta
        
        # Check for negative balances
        if new_deposit < 0:
            return False, "Insufficient deposit balance"
        if new_winning < 0:
            return False, "Insufficient winning balance"
        if new_bonus < 0:
            return False, "Insufficient bonus balance"
        
        # Update balances
        wallet.deposit_balance = new_deposit
        wallet.winning_balance = new_winning
        wallet.bonus_balance = new_bonus
        
        await session.commit()
        return True, None
        
    except Exception as e:
        await session.rollback()
        return False, f"Database error: {str(e)}"


async def credit_deposit_atomic(
    session: AsyncSession,
    user_id: UUID,
    amount: Decimal,
    tx_id: Optional[UUID] = None,
    tx_hash: Optional[str] = None
) -> Tuple[bool, Optional[str], Optional[Decimal]]:
    """
    Atomically credit user's deposit balance with row-level locking.
    
    This function uses SELECT FOR UPDATE to prevent race conditions
    and ensures atomic balance updates within a single transaction.
    
    Args:
        session: Database session
        user_id: User UUID
        amount: Amount to credit (must be positive)
        tx_id: Transaction ID for logging (optional)
        tx_hash: Transaction hash for logging (optional)
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str], new_balance: Optional[Decimal])
    """
    try:
        if amount <= 0:
            return False, "Amount must be positive", None
        
        # Lock the wallet row for update to prevent race conditions
        result = await session.execute(
            select(Wallet)
            .where(Wallet.user_id == user_id)
            .with_for_update()
        )
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            return False, "Wallet not found", None
        
        # Calculate new deposit balance
        new_deposit_balance = wallet.deposit_balance + amount
        
        # Update deposit balance
        wallet.deposit_balance = new_deposit_balance
        
        await session.commit()
        
        logger.info(f"Credited {amount} to user {user_id} deposit balance. New balance: {new_deposit_balance}")
        return True, None, new_deposit_balance
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error crediting deposit for user {user_id}: {str(e)}")
        return False, f"Database error: {str(e)}", None


async def credit_winning_atomic(
    session: AsyncSession,
    user_id: UUID,
    amount: Decimal,
    reason: str,
    meta: Optional[dict] = None
) -> Tuple[bool, Optional[str], Optional[Decimal]]:
    """
    Atomically credit user's winning balance with row-level locking.
    
    This function uses SELECT FOR UPDATE to prevent race conditions
    and ensures atomic balance updates within a single transaction.
    Includes idempotency check via meta["idempotency_key"].
    
    Args:
        session: Database session
        user_id: User UUID
        amount: Amount to credit (must be positive)
        reason: Reason for the credit (e.g., "contest_payout")
        meta: Optional metadata dict with idempotency_key
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str], new_balance: Optional[Decimal])
    """
    try:
        if amount <= 0:
            return False, "Amount must be positive", None
        
        # Check for idempotency if idempotency_key provided
        if meta and meta.get("idempotency_key"):
            from app.repos.transaction_repo import get_transaction_by_metadata
            existing_tx = await get_transaction_by_metadata(
                session, 
                {"idempotency_key": meta["idempotency_key"]}
            )
            if existing_tx:
                logger.info(f"Idempotent credit skipped for user {user_id} with key {meta['idempotency_key']}")
                # Return existing balance
                wallet = await get_wallet_for_user(session, user_id)
                return True, None, wallet.winning_balance if wallet else Decimal('0')
        
        # Lock the wallet row for update to prevent race conditions
        result = await session.execute(
            select(Wallet)
            .where(Wallet.user_id == user_id)
            .with_for_update()
        )
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            return False, "Wallet not found", None
        
        # Calculate new winning balance
        new_winning_balance = wallet.winning_balance + amount
        
        # Update winning balance
        wallet.winning_balance = new_winning_balance
        
        logger.info(f"Credited {amount} to user {user_id} winning balance. New balance: {new_winning_balance}")
        return True, None, new_winning_balance
        
    except Exception as e:
        logger.error(f"Error crediting winning balance for user {user_id}: {str(e)}")
        return False, f"Database error: {str(e)}", None


async def get_wallet_by_user(session: AsyncSession, user_id: UUID):
    """
    Alias for get_wallet_for_user for bot compatibility.
    
    Args:
        session: Database session
        user_id: User UUID
    
    Returns:
        Wallet instance or None if not found
    """
    return await get_wallet_for_user(session, user_id)


async def debit_for_contest_entry(
    session: AsyncSession,
    user_id: UUID,
    amount: Decimal
) -> Tuple[bool, Optional[str]]:
    """
    Debit wallet for contest entry using priority order:
    deposit_balance -> bonus_balance -> winning_balance
    
    Args:
        session: Database session
        user_id: User UUID
        amount: Amount to debit
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        # Lock the wallet row for update
        result = await session.execute(
            select(Wallet)
            .where(Wallet.user_id == user_id)
            .with_for_update()
        )
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            return False, "Wallet not found"
        
        remaining = amount
        deposit_debit = Decimal('0')
        bonus_debit = Decimal('0')
        winning_debit = Decimal('0')
        
        # Try deposit balance first
        if remaining > 0 and wallet.deposit_balance > 0:
            deposit_debit = min(remaining, wallet.deposit_balance)
            remaining -= deposit_debit
        
        # Try bonus balance second
        if remaining > 0 and wallet.bonus_balance > 0:
            bonus_debit = min(remaining, wallet.bonus_balance)
            remaining -= bonus_debit
        
        # Try winning balance last
        if remaining > 0 and wallet.winning_balance > 0:
            winning_debit = min(remaining, wallet.winning_balance)
            remaining -= winning_debit
        
        # Check if we have enough balance
        if remaining > 0:
            return False, "Insufficient balance for contest entry"
        
        # Update balances
        wallet.deposit_balance -= deposit_debit
        wallet.bonus_balance -= bonus_debit
        wallet.winning_balance -= winning_debit
        
        await session.commit()
        return True, None
        
    except Exception as e:
        await session.rollback()
        return False, f"Database error: {str(e)}"


async def credit_deposit_atomic(
    session: AsyncSession,
    user_id: UUID,
    amount: Decimal,
    tx_id: Optional[UUID] = None,
    tx_hash: Optional[str] = None
) -> Tuple[bool, Optional[str], Optional[Decimal]]:
    """
    Atomically credit user's deposit balance with row-level locking.
    
    This function uses SELECT FOR UPDATE to prevent race conditions
    and ensures atomic balance updates within a single transaction.
    
    Args:
        session: Database session
        user_id: User UUID
        amount: Amount to credit (must be positive)
        tx_id: Transaction ID for logging (optional)
        tx_hash: Transaction hash for logging (optional)
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str], new_balance: Optional[Decimal])
    """
    try:
        if amount <= 0:
            return False, "Amount must be positive", None
        
        # Lock the wallet row for update to prevent race conditions
        result = await session.execute(
            select(Wallet)
            .where(Wallet.user_id == user_id)
            .with_for_update()
        )
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            return False, "Wallet not found", None
        
        # Calculate new deposit balance
        new_deposit_balance = wallet.deposit_balance + amount
        
        # Update deposit balance
        wallet.deposit_balance = new_deposit_balance
        
        await session.commit()
        
        logger.info(f"Credited {amount} to user {user_id} deposit balance. New balance: {new_deposit_balance}")
        return True, None, new_deposit_balance
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error crediting deposit for user {user_id}: {str(e)}")
        return False, f"Database error: {str(e)}", None


async def credit_winning_atomic(
    session: AsyncSession,
    user_id: UUID,
    amount: Decimal,
    reason: str,
    meta: Optional[dict] = None
) -> Tuple[bool, Optional[str], Optional[Decimal]]:
    """
    Atomically credit user's winning balance with row-level locking.
    
    This function uses SELECT FOR UPDATE to prevent race conditions
    and ensures atomic balance updates within a single transaction.
    Includes idempotency check via meta["idempotency_key"].
    
    Args:
        session: Database session
        user_id: User UUID
        amount: Amount to credit (must be positive)
        reason: Reason for the credit (e.g., "contest_payout")
        meta: Optional metadata dict with idempotency_key
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str], new_balance: Optional[Decimal])
    """
    try:
        if amount <= 0:
            return False, "Amount must be positive", None
        
        # Check for idempotency if idempotency_key provided
        if meta and meta.get("idempotency_key"):
            from app.repos.transaction_repo import get_transaction_by_metadata
            existing_tx = await get_transaction_by_metadata(
                session, 
                {"idempotency_key": meta["idempotency_key"]}
            )
            if existing_tx:
                logger.info(f"Idempotent credit skipped for user {user_id} with key {meta['idempotency_key']}")
                # Return existing balance
                wallet = await get_wallet_for_user(session, user_id)
                return True, None, wallet.winning_balance if wallet else Decimal('0')
        
        # Lock the wallet row for update to prevent race conditions
        result = await session.execute(
            select(Wallet)
            .where(Wallet.user_id == user_id)
            .with_for_update()
        )
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            return False, "Wallet not found", None
        
        # Calculate new winning balance
        new_winning_balance = wallet.winning_balance + amount
        
        # Update winning balance
        wallet.winning_balance = new_winning_balance
        
        logger.info(f"Credited {amount} to user {user_id} winning balance. New balance: {new_winning_balance}")
        return True, None, new_winning_balance
        
    except Exception as e:
        logger.error(f"Error crediting winning balance for user {user_id}: {str(e)}")
        return False, f"Database error: {str(e)}", None


async def get_wallet_by_user(session: AsyncSession, user_id: UUID):
    """
    Alias for get_wallet_for_user for bot compatibility.
    
    Args:
        session: Database session
        user_id: User UUID
    
    Returns:
        Wallet instance or None if not found
    """
    return await get_wallet_for_user(session, user_id)
