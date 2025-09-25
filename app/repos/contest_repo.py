"""
Contest repository for contest management
"""

import time
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
    entry_fee: Decimal,
    max_participants: int,
    prize_structure: list,
    created_by: Optional[UUID] = None
) -> Contest:
    """
    Create a new contest.
    
    Args:
        session: Database session
        match_id: Cricket match ID
        title: Contest title
        entry_fee: Entry fee amount
        max_participants: Maximum number of participants
        prize_structure: Prize structure as list of position/percentage objects
        created_by: Admin user ID who created the contest (optional)
    
    Returns:
        Created Contest instance
    """
    import uuid
    from uuid import UUID as UUIDType
    from datetime import datetime, timezone
    from sqlalchemy import text
    
    # Generate unique contest code
    contest_code = f"CONTEST_{int(time.time())}{uuid.uuid4().hex[:6].upper()}"
    
    # Convert match_id to UUID if it's a string
    if isinstance(match_id, str):
        try:
            match_uuid = UUIDType(match_id)
        except ValueError:
            # If not a valid UUID, generate one from the string
            match_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, match_id)
    else:
        match_uuid = match_id
    
    from app.core.config import settings
    
    # Ensure default prize structure (100% to 1st rank only)
    if not prize_structure:
        prize_structure = [{"pos": 1, "pct": 100}]
    
    contest = Contest(
        match_id=match_uuid,
        code=contest_code,
        title=title,
        entry_fee=entry_fee,
        max_players=max_participants,
        prize_structure=prize_structure,
        commission_pct=settings.platform_commission_pct,
        status="open"
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
        # Handle both string and enum status values
        if isinstance(status, str):
            query = query.where(Contest.status == status)
        else:
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
    
    contest.status = 'settled'
    await session.commit()
    return True


async def list_active_contests(session: AsyncSession):
    """
    List all active contests for bot display.
    
    Args:
        session: Database session
    
    Returns:
        List of active contest dictionaries
    """
    result = await session.execute(
        select(Contest).where(Contest.status == ContestStatus.OPEN.value).order_by(Contest.created_at)
    )
    contests = result.scalars().all()
    return [contest for contest in contests]


async def get_contest_detail(session: AsyncSession, contest_id: str):
    """
    Get contest details by ID.
    
    Args:
        session: Database session
        contest_id: Contest ID as string
    
    Returns:
        Contest instance or None if not found
    """
    try:
        contest_uuid = UUID(contest_id)
    except ValueError:
        return None
    
    result = await session.execute(
        select(Contest).where(Contest.id == contest_uuid)
    )
    return result.scalar_one_or_none()


async def join_contest_atomic(session: AsyncSession, contest_id: str, telegram_id: int):
    """
    Atomically join a contest with wallet debit.
    
    Args:
        session: Database session
        contest_id: Contest ID as string
        telegram_id: Telegram user ID
    
    Returns:
        Dictionary with success status and details
    """
    from app.repos.user_repo import get_user_by_telegram_id
    from app.repos.wallet_repo import get_wallet_for_user, debit_for_contest_entry
    from app.models.contest_entry import ContestEntry
    from decimal import Decimal
    import uuid
    
    try:
        # Get user by telegram ID
        user = await get_user_by_telegram_id(session, telegram_id)
        if not user:
            return {"ok": False, "error": "User not registered"}
        
        # Get contest
        contest = await get_contest_detail(session, contest_id)
        if not contest:
            return {"ok": False, "error": "Contest not found"}
        
        # Check if contest is still open
        if contest.status != ContestStatus.OPEN.value:
            return {"ok": False, "error": "Contest is not open"}
        
        # Get user's wallet
        wallet = await get_wallet_for_user(session, user.id)
        if not wallet:
            return {"ok": False, "error": "No wallet found"}
        
        # Check if user already joined this contest
        from sqlalchemy import select
        existing_entry = await session.execute(
            select(ContestEntry).where(
                ContestEntry.contest_id == contest.id,
                ContestEntry.user_id == user.id
            )
        )
        if existing_entry.scalar_one_or_none():
            return {"ok": False, "error": "Already joined this contest"}
        
        # Debit wallet for contest entry
        entry_fee = Decimal(str(contest.entry_fee))
        success, error = await debit_for_contest_entry(session, user.id, entry_fee)
        if not success:
            return {"ok": False, "error": error}
        
        # Create contest entry
        entry_code = f"ENTRY_{int(time.time())}{uuid.uuid4().hex[:6].upper()}"
        contest_entry = ContestEntry(
            contest_id=contest.id,
            user_id=user.id,
            entry_code=entry_code,
            amount_debited=entry_fee
        )
        session.add(contest_entry)
        await session.commit()
        
        return {
            "ok": True,
            "contest_title": contest.title,
            "entry_fee": str(entry_fee)
        }
        
    except Exception as e:
        await session.rollback()
        return {"ok": False, "error": f"Database error: {str(e)}"}
