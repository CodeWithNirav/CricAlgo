"""
Contest entry repository for contest participation management
"""

from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.contest_entry import ContestEntry


async def create_contest_entry(
    session: AsyncSession,
    contest_id: UUID,
    user_id: UUID,
    entry_fee: Decimal
) -> ContestEntry:
    """
    Create a new contest entry.
    
    Args:
        session: Database session
        contest_id: Contest UUID
        user_id: User UUID
        entry_fee: Entry fee amount
    
    Returns:
        Created ContestEntry instance
    """
    entry = ContestEntry(
        contest_id=contest_id,
        user_id=user_id,
        entry_fee=entry_fee
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def get_contest_entries(
    session: AsyncSession,
    contest_id: UUID,
    user_id: Optional[UUID] = None,
    limit: int = 100,
    offset: int = 0
) -> List[ContestEntry]:
    """
    Get contest entries.
    
    Args:
        session: Database session
        contest_id: Contest UUID
        user_id: Optional user ID to filter by
        limit: Maximum number of entries to return
        offset: Number of entries to skip
    
    Returns:
        List of ContestEntry instances
    """
    query = select(ContestEntry).where(ContestEntry.contest_id == contest_id)
    
    if user_id:
        query = query.where(ContestEntry.user_id == user_id)
    
    query = query.order_by(desc(ContestEntry.created_at)).limit(limit).offset(offset)
    
    result = await session.execute(query)
    return result.scalars().all()


async def get_user_contest_entries(
    session: AsyncSession,
    user_id: UUID,
    limit: int = 50,
    offset: int = 0
) -> List[ContestEntry]:
    """
    Get user's contest entries.
    
    Args:
        session: Database session
        user_id: User UUID
        limit: Maximum number of entries to return
        offset: Number of entries to skip
    
    Returns:
        List of ContestEntry instances
    """
    result = await session.execute(
        select(ContestEntry)
        .where(ContestEntry.user_id == user_id)
        .order_by(desc(ContestEntry.created_at))
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()
