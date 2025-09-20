"""
Admin repository for admin user management
"""

from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.admin import Admin
from app.models.user import User


async def is_admin_user(session: AsyncSession, user_id: UUID) -> bool:
    """
    Check if a user is an admin.
    
    Args:
        session: Database session
        user_id: User UUID
    
    Returns:
        True if user is admin, False otherwise
    """
    # Since Admin and User are separate models, we need to check by username
    # First get the user, then check if there's an admin with the same username
    from app.repos.user_repo import get_user_by_id
    
    user = await get_user_by_id(session, user_id)
    if not user:
        return False
    
    # Check if there's an admin with the same username
    # Since we now use the same username for both User and Admin tables
    result = await session.execute(
        select(Admin).where(Admin.username == user.username)
    )
    admin = result.scalar_one_or_none()
    return admin is not None


async def create_admin_user(
    session: AsyncSession,
    user_id: UUID,
    totp_secret: str,
    is_super_admin: bool = False
) -> Admin:
    """
    Create an admin user.
    
    Args:
        session: Database session
        user_id: User UUID
        totp_secret: TOTP secret for 2FA
        is_super_admin: Whether this is a super admin
    
    Returns:
        Created Admin instance
    """
    admin = Admin(
        user_id=user_id,
        totp_secret=totp_secret,
        is_super_admin=is_super_admin
    )
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin


async def get_admin_by_username(session: AsyncSession, username: str) -> Optional[Admin]:
    """
    Get admin by username.
    
    Args:
        session: Database session
        username: Admin username
    
    Returns:
        Admin instance or None if not found
    """
    result = await session.execute(
        select(Admin).where(Admin.username == username)
    )
    return result.scalar_one_or_none()


async def get_admin_by_user_id(session: AsyncSession, user_id: UUID) -> Optional[Admin]:
    """
    Get admin by user ID.
    
    Args:
        session: Database session
        user_id: User UUID
    
    Returns:
        Admin instance or None if not found
    """
    # Since Admin and User are separate models, we need to check by username
    from app.repos.user_repo import get_user_by_id
    
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    
    # Check if there's an admin with the same username
    # Since we now use the same username for both User and Admin tables
    result = await session.execute(
        select(Admin).where(Admin.username == user.username)
    )
    return result.scalar_one_or_none()


async def get_admin_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[Admin]:
    """
    Get admin by Telegram ID.
    
    Args:
        session: Database session
        telegram_id: Telegram user ID
    
    Returns:
        Admin instance or None if not found
    """
    # First get the user by telegram_id
    from app.repos.user_repo import get_user_by_telegram_id
    
    user = await get_user_by_telegram_id(session, telegram_id)
    if not user:
        return None
    
    # Check if there's an admin with the same username
    result = await session.execute(
        select(Admin).where(Admin.username == user.username)
    )
    return result.scalar_one_or_none()


async def get_all_admins(session: AsyncSession) -> list[Admin]:
    """
    Get all admin users.
    
    Args:
        session: Database session
    
    Returns:
        List of Admin instances
    """
    result = await session.execute(
        select(Admin).join(User).order_by(User.created_at.desc())
    )
    return result.scalars().all()
