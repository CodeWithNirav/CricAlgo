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
        
        # Check if user has sufficient balance (held balance is not available for contest entry)
        total_balance = wallet.deposit_balance + wallet.bonus_balance + wallet.winning_balance
        if total_balance < amount:
            return False, "Insufficient balance"
        
        # Debit in priority order: deposit -> bonus -> winning
        remaining = amount
        
        # First, debit from deposit balance
        if remaining > 0 and wallet.deposit_balance > 0:
            debit_from_deposit = min(remaining, wallet.deposit_balance)
            wallet.deposit_balance -= debit_from_deposit
            remaining -= debit_from_deposit
        
        # Then, debit from bonus balance
        if remaining > 0 and wallet.bonus_balance > 0:
            debit_from_bonus = min(remaining, wallet.bonus_balance)
            wallet.bonus_balance -= debit_from_bonus
            remaining -= debit_from_bonus
        
        # Finally, debit from winning balance
        if remaining > 0 and wallet.winning_balance > 0:
            debit_from_winning = min(remaining, wallet.winning_balance)
            wallet.winning_balance -= debit_from_winning
            remaining -= debit_from_winning
        
        if remaining > 0:
            return False, "Insufficient balance after priority deduction"
        
        await session.commit()
        logger.info(f"Debited {amount} from user {user_id} for contest entry")
        return True, None
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error debiting for contest entry for user {user_id}: {str(e)}")
        return False, f"Database error: {str(e)}"


async def process_withdrawal_atomic(
    session: AsyncSession,
    user_id: UUID,
    amount: Decimal
) -> Tuple[bool, Optional[str], Optional[dict]]:
    """
    Process withdrawal with atomic balance deduction using priority order.
    
    Args:
        session: Database session
        user_id: User UUID
        amount: Amount to withdraw (must be positive)
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str], deduction_breakdown: Optional[dict])
    """
    try:
        if amount <= 0:
            return False, "Amount must be positive", None
        
        # Lock the wallet row for update
        result = await session.execute(
            select(Wallet)
            .where(Wallet.user_id == user_id)
            .with_for_update()
        )
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            return False, "Wallet not found", None
        
        # Check if user has sufficient balance
        total_balance = wallet.deposit_balance + wallet.bonus_balance + wallet.winning_balance
        if total_balance < amount:
            return False, "Insufficient balance", None
        
        # Calculate deduction breakdown with priority: deposit -> winning -> bonus
        deposit_delta = Decimal('0')
        winning_delta = Decimal('0')
        bonus_delta = Decimal('0')
        
        remaining_amount = amount
        
        # First, deduct from deposit balance
        if remaining_amount > 0 and wallet.deposit_balance > 0:
            deduct_from_deposit = min(remaining_amount, wallet.deposit_balance)
            deposit_delta = -deduct_from_deposit
            remaining_amount -= deduct_from_deposit
        
        # Then, deduct from winning balance
        if remaining_amount > 0 and wallet.winning_balance > 0:
            deduct_from_winning = min(remaining_amount, wallet.winning_balance)
            winning_delta = -deduct_from_winning
            remaining_amount -= deduct_from_winning
        
        # Finally, deduct from bonus balance
        if remaining_amount > 0 and wallet.bonus_balance > 0:
            deduct_from_bonus = min(remaining_amount, wallet.bonus_balance)
            bonus_delta = -deduct_from_bonus
            remaining_amount -= deduct_from_bonus
        
        if remaining_amount > 0:
            return False, "Insufficient balance after priority deduction", None
        
        # Update balances
        wallet.deposit_balance += deposit_delta
        wallet.winning_balance += winning_delta
        wallet.bonus_balance += bonus_delta
        
        await session.commit()
        
        deduction_breakdown = {
            "deposit_delta": str(deposit_delta),
            "winning_delta": str(winning_delta),
            "bonus_delta": str(bonus_delta)
        }
        
        logger.info(f"Processed withdrawal for user {user_id}: {amount}")
        return True, None, deduction_breakdown
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error processing withdrawal for user {user_id}: {str(e)}")
        return False, f"Database error: {str(e)}", None


async def refund_contest_entry_atomic(
    session: AsyncSession,
    user_id: UUID,
    amount: Decimal,
    contest_id: UUID
) -> Tuple[bool, Optional[str]]:
    """
    Refund a contest entry by crediting the amount back to user's wallet.
    Credits are added to deposit_balance to match the original debit priority.
    
    Args:
        session: Database session
        user_id: User UUID
        amount: Amount to refund (must be positive)
        contest_id: Contest UUID for transaction tracking
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        if amount <= 0:
            return False, "Amount must be positive"
        
        # Lock the wallet row for update
        result = await session.execute(
            select(Wallet)
            .where(Wallet.user_id == user_id)
            .with_for_update()
        )
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            return False, "Wallet not found"
        
        # Credit the amount to deposit balance (matching original debit priority)
        wallet.deposit_balance += amount
        
        # Create transaction record for the refund
        from app.repos.transaction_repo import create_transaction
        await create_transaction(
            session=session,
            user_id=user_id,
            tx_type="contest_refund",
            amount=amount,
            currency="USDT",
            related_entity="contest",
            related_id=contest_id,
            tx_metadata={
                "contest_id": str(contest_id),
                "refund_reason": "contest_cancelled",
                "status": "processed"
            }
        )
        
        await session.commit()
        
        logger.info(f"Refunded {amount} to user {user_id} for contest {contest_id}")
        return True, None
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error refunding contest entry for user {user_id}: {str(e)}")
        return False, f"Database error: {str(e)}"


async def process_withdrawal_hold_atomic(
    session: AsyncSession,
    user_id: UUID,
    amount: Decimal
) -> Tuple[bool, Optional[str]]:
    """
    Process withdrawal by moving amount from winning balance to held balance.
    Only winning balance can be withdrawn.
    
    Args:
        session: Database session
        user_id: User UUID
        amount: Amount to withdraw (must be positive)
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        if amount <= 0:
            return False, "Amount must be positive"
        
        # Lock the wallet row for update
        result = await session.execute(
            select(Wallet)
            .where(Wallet.user_id == user_id)
            .with_for_update()
        )
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            return False, "Wallet not found"
        
        # Check if user has sufficient winning balance
        if wallet.winning_balance < amount:
            return False, "Insufficient winning balance for withdrawal"
        
        # Move amount from winning balance to held balance
        wallet.winning_balance -= amount
        wallet.held_balance += amount
        
        await session.commit()
        
        logger.info(f"Withdrawal hold processed for user {user_id}: {amount} moved to held balance")
        return True, None
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error processing withdrawal hold for user {user_id}: {str(e)}")
        return False, f"Database error: {str(e)}"


async def release_withdrawal_hold_atomic(
    session: AsyncSession,
    user_id: UUID,
    amount: Decimal
) -> Tuple[bool, Optional[str]]:
    """
    Release withdrawal hold by moving amount from held balance back to winning balance.
    Used when withdrawal is rejected.
    
    Args:
        session: Database session
        user_id: User UUID
        amount: Amount to release (must be positive)
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        if amount <= 0:
            return False, "Amount must be positive"
        
        # Lock the wallet row for update
        result = await session.execute(
            select(Wallet)
            .where(Wallet.user_id == user_id)
            .with_for_update()
        )
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            return False, "Wallet not found"
        
        # Check if user has sufficient held balance
        if wallet.held_balance < amount:
            return False, "Insufficient held balance to release"
        
        # Move amount from held balance back to winning balance
        wallet.held_balance -= amount
        wallet.winning_balance += amount
        
        await session.commit()
        
        logger.info(f"Withdrawal hold released for user {user_id}: {amount} moved back to winning balance")
        return True, None
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error releasing withdrawal hold for user {user_id}: {str(e)}")
        return False, f"Database error: {str(e)}"


async def complete_withdrawal_atomic(
    session: AsyncSession,
    user_id: UUID,
    amount: Decimal
) -> Tuple[bool, Optional[str]]:
    """
    Complete withdrawal by removing amount from held balance.
    Used when withdrawal is approved and processed.
    
    Args:
        session: Database session
        user_id: User UUID
        amount: Amount to complete (must be positive)
    
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        if amount <= 0:
            return False, "Amount must be positive"
        
        # Lock the wallet row for update
        result = await session.execute(
            select(Wallet)
            .where(Wallet.user_id == user_id)
            .with_for_update()
        )
        wallet = result.scalar_one_or_none()
        
        if not wallet:
            return False, "Wallet not found"
        
        # Check if user has sufficient held balance
        if wallet.held_balance < amount:
            return False, "Insufficient held balance to complete withdrawal"
        
        # Remove amount from held balance (withdrawal completed)
        wallet.held_balance -= amount
        
        await session.commit()
        
        logger.info(f"Withdrawal completed for user {user_id}: {amount} removed from held balance")
        return True, None
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error completing withdrawal for user {user_id}: {str(e)}")
        return False, f"Database error: {str(e)}"