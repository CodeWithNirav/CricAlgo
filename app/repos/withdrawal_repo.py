"""
Withdrawal repository with CRUD operations
"""

from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update
from datetime import datetime
from app.models.withdrawal import Withdrawal


async def create_withdrawal(
    session: AsyncSession,
    user_id: UUID,
    amount: Decimal,
    address: str,
    currency: str = 'USDT',
    withdrawal_metadata: Optional[dict] = None
) -> Withdrawal:
    """
    Create a new withdrawal record.
    
    Args:
        session: Database session
        user_id: User UUID
        amount: Withdrawal amount
        address: Withdrawal address
        currency: Currency code (default: USDT)
        withdrawal_metadata: Additional metadata (optional)
    
    Returns:
        Created Withdrawal instance
    """
    withdrawal = Withdrawal(
        user_id=user_id,
        amount=amount,
        address=address,
        currency=currency,
        withdrawal_metadata=withdrawal_metadata
    )
    session.add(withdrawal)
    await session.commit()
    await session.refresh(withdrawal)
    return withdrawal


async def get_withdrawal_by_id(session: AsyncSession, withdrawal_id: str) -> Optional[Withdrawal]:
    """
    Get withdrawal by ID.
    
    Args:
        session: Database session
        withdrawal_id: Withdrawal ID (string)
    
    Returns:
        Withdrawal instance or None if not found
    """
    result = await session.execute(
        select(Withdrawal).where(Withdrawal.id == withdrawal_id)
    )
    return result.scalar_one_or_none()


async def get_withdrawals_by_user(
    session: AsyncSession,
    user_id: UUID,
    limit: int = 100,
    offset: int = 0
) -> List[Withdrawal]:
    """
    Get withdrawals for a specific user.
    
    Args:
        session: Database session
        user_id: User UUID
        limit: Maximum number of withdrawals to return
        offset: Number of withdrawals to skip
    
    Returns:
        List of Withdrawal instances
    """
    result = await session.execute(
        select(Withdrawal)
        .where(Withdrawal.user_id == user_id)
        .order_by(desc(Withdrawal.created_at))
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


async def get_withdrawals_by_status(
    session: AsyncSession,
    status: str,
    limit: int = 100,
    offset: int = 0
) -> List[Withdrawal]:
    """
    Get withdrawals by status.
    
    Args:
        session: Database session
        status: Withdrawal status
        limit: Maximum number of withdrawals to return
        offset: Number of withdrawals to skip
    
    Returns:
        List of Withdrawal instances
    """
    result = await session.execute(
        select(Withdrawal)
        .where(Withdrawal.status == status)
        .order_by(desc(Withdrawal.created_at))
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


async def mark_withdrawal_approved(session: AsyncSession, withdrawal_id: str) -> bool:
    """
    Mark a withdrawal as approved.
    
    Args:
        session: Database session
        withdrawal_id: Withdrawal ID (string)
    
    Returns:
        True if successful
    """
    await session.execute(
        update(Withdrawal)
        .where(Withdrawal.id == withdrawal_id)
        .values(status="approved", processed_at=datetime.utcnow())
    )
    await session.commit()
    return True


async def mark_withdrawal_rejected(session: AsyncSession, withdrawal_id: str, reason: str = "") -> bool:
    """
    Mark a withdrawal as rejected.
    
    Args:
        session: Database session
        withdrawal_id: Withdrawal ID (string)
        reason: Rejection reason
    
    Returns:
        True if successful
    """
    await session.execute(
        update(Withdrawal)
        .where(Withdrawal.id == withdrawal_id)
        .values(status="rejected", withdrawal_metadata={"rejection_reason": reason})
    )
    await session.commit()
    return True
