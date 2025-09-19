"""
Contest repository for contest management
"""

from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.contest import Contest
from app.models.enums import ContestStatus


async def create_contest(
    session: AsyncSession,
    match_id: str,
    title: str,
    description: Optional[str],
    entry_fee: Decimal,
    max_participants: int,
    prize_structure: dict,
    created_by: UUID
) -> Contest:
    """
    Create a new contest.
    
    Args:
        session: Database session
        match_id: Cricket match ID
        title: Contest title
        description: Contest description
        entry_fee: Entry fee amount
        max_participants: Maximum number of participants
        prize_structure: Prize structure as JSON
        created_by: Admin user ID who created the contest
    
    Returns:
        Created Contest instance
    """
    contest = Contest(
        match_id=match_id,
        title=title,
        description=description,
        entry_fee=entry_fee,
        max_participants=max_participants,
        prize_structure=prize_structure,
        status=ContestStatus.OPEN,
        created_by=created_by
    )
    session.add(contest)
    await session.commit()
    await session.refresh(contest)
    return contest


async def get_contest_by_id(session: AsyncSession, contest_id: UUID) -> Optional[Contest]:
    """
    Get contest by ID.
    
    Args:
        session: Database session
        contest_id: Contest UUID
    
    Returns:
        Contest instance or None if not found
    """
    result = await session.execute(
        select(Contest).where(Contest.id == contest_id)
    )
    return result.scalar_one_or_none()


async def get_contests(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None
) -> List[Contest]:
    """
    Get list of contests.
    
    Args:
        session: Database session
        limit: Maximum number of contests to return
        offset: Number of contests to skip
        status: Filter by contest status
    
    Returns:
        List of Contest instances
    """
    query = select(Contest).order_by(desc(Contest.created_at))
    
    if status:
        query = query.where(Contest.status == ContestStatus(status))
    
    query = query.limit(limit).offset(offset)
    
    result = await session.execute(query)
    return result.scalars().all()


async def join_contest(
    session: AsyncSession,
    contest_id: UUID,
    user_id: UUID,
    entry_fee: Decimal
) -> bool:
    """
    Join a contest (creates contest entry).
    
    Args:
        session: Database session
        contest_id: Contest UUID
        user_id: User UUID
        entry_fee: Entry fee amount
    
    Returns:
        True if joined successfully, False otherwise
    """
    # This function is a placeholder - actual implementation would be in contest_entry_repo
    # For now, we'll just return True
    return True


async def settle_contest(
    session: AsyncSession,
    contest_id: UUID
) -> bool:
    """
    Settle a contest (mark as settled).
    
    Args:
        session: Database session
        contest_id: Contest UUID
    
    Returns:
        True if settled successfully, False otherwise
    """
    contest = await get_contest_by_id(session, contest_id)
    if not contest:
        return False
    
    contest.status = ContestStatus.SETTLED
    await session.commit()
    return True
