"""
Chat mapping repository for storing user chat IDs
"""

import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.chat_map import ChatMap

logger = logging.getLogger(__name__)

async def save_chat_id(session: AsyncSession, user_id: str, chat_id: str) -> bool:
    """
    Save or update chat ID for a user
    """
    try:
        # Check if mapping already exists
        stmt = select(ChatMap).where(ChatMap.user_id == user_id)
        result = await session.execute(stmt)
        existing_mapping = result.scalar_one_or_none()
        
        if existing_mapping:
            # Update existing mapping
            existing_mapping.chat_id = chat_id
            logger.info(f"Updated chat mapping for user {user_id}: {chat_id}")
        else:
            # Create new mapping
            new_mapping = ChatMap(
                user_id=user_id,
                chat_id=chat_id
            )
            session.add(new_mapping)
            logger.info(f"Created new chat mapping for user {user_id}: {chat_id}")
        
        await session.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error saving chat ID for user {user_id}: {e}")
        await session.rollback()
        return False

async def get_chat_id(session: AsyncSession, user_id: str) -> Optional[str]:
    """
    Get chat ID for a user
    """
    try:
        stmt = select(ChatMap).where(ChatMap.user_id == user_id)
        result = await session.execute(stmt)
        mapping = result.scalar_one_or_none()
        
        if mapping:
            return mapping.chat_id
        return None
        
    except Exception as e:
        logger.error(f"Error getting chat ID for user {user_id}: {e}")
        return None

async def delete_chat_mapping(session: AsyncSession, user_id: str) -> bool:
    """
    Delete chat mapping for a user
    """
    try:
        stmt = select(ChatMap).where(ChatMap.user_id == user_id)
        result = await session.execute(stmt)
        mapping = result.scalar_one_or_none()
        
        if mapping:
            await session.delete(mapping)
            await session.commit()
            logger.info(f"Deleted chat mapping for user {user_id}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error deleting chat mapping for user {user_id}: {e}")
        await session.rollback()
        return False
