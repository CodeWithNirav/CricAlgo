"""
Invite code repository with async CRUD operations
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timezone
from app.models.invitation_code import InvitationCode


async def get_invite_code(session: AsyncSession, code: str) -> Optional[InvitationCode]:
    """
    Get invite code by code string.
    
    Args:
        session: Database session
        code: Invite code string
    
    Returns:
        InvitationCode instance or None if not found
    """
    result = await session.execute(
        select(InvitationCode).where(InvitationCode.code == code)
    )
    return result.scalar_one_or_none()


async def validate_invite_code(session: AsyncSession, code: str) -> tuple[bool, str]:
    """
    Validate an invite code without using it.
    
    Args:
        session: Database session
        code: Invite code string
    
    Returns:
        Tuple of (is_valid, message)
    """
    invite_code = await get_invite_code(session, code)
    
    if not invite_code:
        return False, "Invalid invite code"
    
    if not invite_code.enabled:
        return False, "This invite code has been disabled"
    
    # Check if expired
    if invite_code.expires_at and invite_code.expires_at < datetime.now(timezone.utc):
        return False, "This invite code has expired"
    
    # Check if max uses reached
    if invite_code.max_uses and invite_code.uses >= invite_code.max_uses:
        return False, "This invite code has reached its maximum usage limit"
    
    return True, "Invite code is valid"


async def validate_and_use_code(session: AsyncSession, code: str, user_id: str) -> tuple[bool, str]:
    """
    Validate and use an invite code for a user.
    
    Args:
        session: Database session
        code: Invite code string
        user_id: User ID who is using the code
    
    Returns:
        Tuple of (is_valid, message)
    """
    # First validate the code
    is_valid, msg = await validate_invite_code(session, code)
    if not is_valid:
        return False, msg
    
    # If valid, increment usage count
    invite_code = await get_invite_code(session, code)
    invite_code.uses += 1
    await session.commit()
    
    return True, "Invite code applied successfully"


async def create_invite_code(
    session: AsyncSession,
    code: str,
    created_by: Optional[str] = None,
    max_uses: Optional[int] = None,
    expires_at: Optional[datetime] = None
) -> InvitationCode:
    """
    Create a new invite code.
    
    Args:
        session: Database session
        code: Invite code string
        created_by: Admin ID who created the code
        max_uses: Maximum number of uses (None for unlimited)
        expires_at: Expiration datetime (None for no expiration)
    
    Returns:
        Created InvitationCode instance
    """
    invite_code = InvitationCode(
        code=code,
        created_by=created_by,
        max_uses=max_uses,
        expires_at=expires_at,
        enabled=True
    )
    session.add(invite_code)
    await session.commit()
    await session.refresh(invite_code)
    return invite_code


async def get_invite_codes(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    enabled_only: bool = True
) -> list[InvitationCode]:
    """
    Get list of invite codes.
    
    Args:
        session: Database session
        limit: Maximum number of codes to return
        offset: Number of codes to skip
        enabled_only: Only return enabled codes
    
    Returns:
        List of InvitationCode instances
    """
    query = select(InvitationCode)
    
    if enabled_only:
        query = query.where(InvitationCode.enabled == True)
    
    query = query.limit(limit).offset(offset)
    
    result = await session.execute(query)
    return result.scalars().all()


async def disable_invite_code(session: AsyncSession, code: str) -> bool:
    """
    Disable an invite code.
    
    Args:
        session: Database session
        code: Invite code string
    
    Returns:
        True if successful, False if code not found
    """
    result = await session.execute(
        update(InvitationCode)
        .where(InvitationCode.code == code)
        .values(enabled=False)
    )
    
    if result.rowcount > 0:
        await session.commit()
        return True
    return False
