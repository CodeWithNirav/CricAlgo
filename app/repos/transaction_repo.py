"""
Transaction repository with CRUD operations
"""

from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.transaction import Transaction


async def create_transaction(
    session: AsyncSession,
    user_id: Optional[UUID],
    tx_type: str,
    amount: Decimal,
    currency: str = 'USDT',
    related_entity: Optional[str] = None,
    related_id: Optional[UUID] = None,
    tx_metadata: Optional[dict] = None
) -> Transaction:
    """
    Create a new transaction record.
    
    Args:
        session: Database session
        user_id: User UUID (optional)
        tx_type: Transaction type (e.g., 'deposit', 'withdrawal', 'contest_entry')
        amount: Transaction amount
        currency: Currency code (default: USDT)
        related_entity: Related entity type (optional)
        related_id: Related entity ID (optional)
        metadata: Additional metadata (optional)
    
    Returns:
        Created Transaction instance
    """
    transaction = Transaction(
        user_id=user_id,
        tx_type=tx_type,
        amount=amount,
        currency=currency,
        related_entity=related_entity,
        related_id=related_id,
        tx_metadata=tx_metadata
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return transaction


async def get_transaction_by_id(session: AsyncSession, transaction_id: UUID) -> Optional[Transaction]:
    """
    Get transaction by ID.
    
    Args:
        session: Database session
        transaction_id: Transaction UUID
    
    Returns:
        Transaction instance or None if not found
    """
    result = await session.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    return result.scalar_one_or_none()


async def get_transactions_by_user(
    session: AsyncSession,
    user_id: UUID,
    limit: int = 100,
    offset: int = 0
) -> List[Transaction]:
    """
    Get transactions for a specific user.
    
    Args:
        session: Database session
        user_id: User UUID
        limit: Maximum number of transactions to return
        offset: Number of transactions to skip
    
    Returns:
        List of Transaction instances
    """
    result = await session.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(desc(Transaction.created_at))
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


async def get_transactions_by_type(
    session: AsyncSession,
    tx_type: str,
    limit: int = 100,
    offset: int = 0
) -> List[Transaction]:
    """
    Get transactions by type.
    
    Args:
        session: Database session
        tx_type: Transaction type
        limit: Maximum number of transactions to return
        offset: Number of transactions to skip
    
    Returns:
        List of Transaction instances
    """
    result = await session.execute(
        select(Transaction)
        .where(Transaction.tx_type == tx_type)
        .order_by(desc(Transaction.created_at))
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


async def update_transaction_metadata(
    session: AsyncSession,
    transaction_id: UUID,
    tx_metadata: dict
) -> Optional[Transaction]:
    """
    Update transaction metadata.
    
    Args:
        session: Database session
        transaction_id: Transaction UUID
        tx_metadata: New metadata dictionary
    
    Returns:
        Updated Transaction instance or None if not found
    """
    transaction = await get_transaction_by_id(session, transaction_id)
    if not transaction:
        return None
    
    transaction.tx_metadata = tx_metadata
    await session.commit()
    await session.refresh(transaction)
    return transaction
