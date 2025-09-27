"""
Match repository for match management
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime

from app.models.match import Match


async def get_matches(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    not_started: bool = False,
    upcoming_only: bool = False
) -> List[Match]:
    """
    Get list of matches.
    
    Args:
        session: Database session
        limit: Maximum number of matches to return
        offset: Number of matches to skip
        status: Filter by match status
        not_started: If True, only return matches that haven't started yet
        upcoming_only: If True, only return matches that are upcoming (not started and not finished)
    
    Returns:
        List of Match instances
    """
    from datetime import datetime
    import pytz
    
    ist_tz = pytz.timezone('Asia/Kolkata')
    
    query = select(Match).order_by(Match.start_time.asc())
    
    if status:
        query = query.where(Match.status == status)
    
    if not_started:
        # Only return matches that haven't started yet (status is 'scheduled')
        query = query.where(Match.status == 'scheduled')
    
    if upcoming_only:
        # Only return matches that are upcoming (not started and not finished)
        # This means: status is 'scheduled' AND start_time is in the future
        now = datetime.now(ist_tz)
        query = query.where(
            Match.status == 'scheduled',
            Match.start_time > now
        )
    
    query = query.limit(limit).offset(offset)
    
    result = await session.execute(query)
    return result.scalars().all()


async def get_match_by_id(session: AsyncSession, match_id: str) -> Optional[Match]:
    """
    Get match by ID.
    
    Args:
        session: Database session
        match_id: Match ID as string
    
    Returns:
        Match instance or None if not found
    """
    from uuid import UUID
    
    try:
        match_uuid = UUID(match_id)
    except ValueError:
        return None
    
    result = await session.execute(
        select(Match).where(Match.id == match_uuid)
    )
    return result.scalar_one_or_none()


async def get_contests_for_match(
    session: AsyncSession,
    match_id: str,
    status: Optional[str] = None,
    user_id: Optional[str] = None
) -> List:
    """
    Get contests for a specific match, filtering out filled contests and contests already joined by user.
    
    Args:
        session: Database session
        match_id: Match ID as string
        status: Filter by contest status
        user_id: Optional user ID to filter out contests already joined by this user
    
    Returns:
        List of Contest instances
    """
    from app.models.contest import Contest
    from app.models.contest_entry import ContestEntry
    from app.models.contest import Contest
    from uuid import UUID
    from sqlalchemy import func
    
    try:
        match_uuid = UUID(match_id)
    except ValueError:
        return []
    
    # Base query for contests
    query = select(Contest).where(Contest.match_id == match_uuid)
    
    if status:
        query = query.where(Contest.status == status)
    
    result = await session.execute(query)
    contests = result.scalars().all()
    
    # Filter out filled contests and user-joined contests
    filtered_contests = []
    
    for contest in contests:
        # Check if contest is filled
        if contest.max_players:
            # Get current participant count
            participant_count_result = await session.execute(
                select(func.count(ContestEntry.id))
                .where(ContestEntry.contest_id == contest.id)
            )
            participant_count = participant_count_result.scalar() or 0
            
            # Skip if contest is filled
            if participant_count >= contest.max_players:
                continue
        
        # Check if user has already joined this contest
        if user_id:
            try:
                user_uuid = UUID(user_id)
                existing_entry_result = await session.execute(
                    select(ContestEntry).where(
                        ContestEntry.contest_id == contest.id,
                        ContestEntry.user_id == user_uuid
                    )
                )
                if existing_entry_result.scalar_one_or_none():
                    continue  # Skip contests already joined by user
            except ValueError:
                # Invalid user_id format, skip user filtering
                pass
        
        filtered_contests.append(contest)
    
    return filtered_contests


async def update_match_status(
    session: AsyncSession,
    match_id: str,
    new_status: str
) -> bool:
    """
    Update match status.
    
    Args:
        session: Database session
        match_id: Match ID as string
        new_status: New status to set
    
    Returns:
        True if updated successfully, False otherwise
    """
    from uuid import UUID
    
    try:
        match_uuid = UUID(match_id)
    except ValueError:
        return False
    
    result = await session.execute(
        select(Match).where(Match.id == match_uuid)
    )
    match = result.scalar_one_or_none()
    
    if not match:
        return False
    
    match.status = new_status
    await session.commit()
    return True


async def get_matches_needing_status_update(session: AsyncSession) -> List[Match]:
    """
    Get matches that need status updates based on their start time.
    
    Args:
        session: Database session
    
    Returns:
        List of Match instances that need status updates
    """
    from datetime import datetime
    import pytz
    
    ist_tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_tz)
    
    # Get matches that should be moved to 'live' status (started but still 'scheduled')
    query = select(Match).where(
        Match.start_time <= now,
        Match.status == 'scheduled'
    )
    
    result = await session.execute(query)
    return result.scalars().all()


async def update_match_statuses_automatically(session: AsyncSession) -> int:
    """
    Automatically update match statuses based on start time.
    
    Args:
        session: Database session
    
    Returns:
        Number of matches updated
    """
    matches_to_update = await get_matches_needing_status_update(session)
    updated_count = 0
    
    for match in matches_to_update:
        # Move from 'scheduled' to 'live' when start time passes
        if match.status == 'scheduled':
            match.status = 'live'
            updated_count += 1
    
    if updated_count > 0:
        await session.commit()
    
    return updated_count
