"""
User repository with async CRUD operations
"""

from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.user import User
from app.models.enums import UserStatus


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str,
    status: UserStatus = UserStatus.ACTIVE.value
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


async def get_users(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None
) -> List[User]:
    """
    Get list of users.
    
    Args:
        session: Database session
        limit: Maximum number of users to return
        offset: Number of users to skip
        status: Filter by user status
    
    Returns:
        List of User instances
    """
    query = select(User).order_by(desc(User.created_at))
    
    if status:
        query = query.where(User.status == UserStatus(status))
    
    query = query.limit(limit).offset(offset)
    
    result = await session.execute(query)
    return result.scalars().all()


async def create_user_if_not_exists(session: AsyncSession, telegram_id: int, username: str, invite_code: str = None):
    """
    Create user if not exists, return existing user if found.
    
    Args:
        session: Database session
        telegram_id: Telegram user ID
        username: Username
        invite_code: Optional invite code
    
    Returns:
        User instance (existing or newly created)
    """
    # Check if user already exists
    existing_user = await get_user_by_telegram_id(session, telegram_id)
    if existing_user:
        return existing_user
    
    # Create new user
    user = await create_user(session, telegram_id, username)
    
    # Create wallet for the user
    from app.repos.wallet_repo import create_wallet_for_user
    await create_wallet_for_user(session, user.id)
    
    return user


async def get_user_by_telegram(session: AsyncSession, telegram_id: int):
    """
    Alias for get_user_by_telegram_id for bot compatibility.
    
    Args:
        session: Database session
        telegram_id: Telegram user ID
    
    Returns:
        User instance or None if not found
    """
    return await get_user_by_telegram_id(session, telegram_id)


async def save_chat_id(session: AsyncSession, user_id: UUID, chat_id: str):
    """
    Save or update chat ID for user notifications.
    
    Args:
        session: Database session
        user_id: User UUID
        chat_id: Telegram chat ID
    
    Returns:
        True if successful
    """
    from app.models.chat_map import ChatMap
    from sqlalchemy import select
    
    # Check if mapping already exists
    result = await session.execute(
        select(ChatMap).where(ChatMap.user_id == str(user_id))
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        # Update existing mapping
        existing.chat_id = chat_id
    else:
        # Create new mapping
        chat_map = ChatMap(user_id=str(user_id), chat_id=chat_id)
        session.add(chat_map)
    
    await session.flush()
    return True
