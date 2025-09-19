"""
User repository with async CRUD operations
"""

from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.models.enums import UserStatus


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str,
    status: UserStatus = UserStatus.ACTIVE
) -> User:
    """
    Create a new user.
    
    Args:
        session: Database session
        telegram_id: Telegram user ID
        username: Username (must be unique)
        status: User status (default: ACTIVE)
    
    Returns:
        Created User instance
    """
    user = User(
        telegram_id=telegram_id,
        username=username,
        status=status
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> Optional[User]:
    """
    Get user by ID.
    
    Args:
        session: Database session
        user_id: User UUID
    
    Returns:
        User instance or None if not found
    """
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
    """
    Get user by username.
    
    Args:
        session: Database session
        username: Username
    
    Returns:
        User instance or None if not found
    """
    result = await session.execute(
        select(User).where(User.username == username)
    )
    return result.scalar_one_or_none()


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    """
    Get user by Telegram ID.
    
    Args:
        session: Database session
        telegram_id: Telegram user ID
    
    Returns:
        User instance or None if not found
    """
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def update_user(
    session: AsyncSession,
    user_id: UUID,
    username: Optional[str] = None,
    status: Optional[UserStatus] = None
) -> Optional[User]:
    """
    Update user information.
    
    Args:
        session: Database session
        user_id: User UUID
        username: New username (optional)
        status: New status (optional)
    
    Returns:
        Updated User instance or None if not found
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        return None
    
    if username is not None:
        user.username = username
    if status is not None:
        user.status = status
    
    await session.commit()
    await session.refresh(user)
    return user
