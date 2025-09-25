"""
Deposit repository for handling deposit references and notifications
"""

from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.transaction import Transaction
from app.models.chat_map import ChatMap
import hashlib
import secrets
import logging

logger = logging.getLogger(__name__)


async def generate_deposit_reference(session: AsyncSession, user_id: UUID) -> str:
    """
    Generate a unique deposit reference for a user.
    This creates a deterministic reference that can be used as a memo.
    
    Args:
        session: Database session
        user_id: User UUID
    
    Returns:
        Unique deposit reference string
    """
    # Create a deterministic reference based on user ID
    user_str = str(user_id)
    timestamp = str(int(__import__('time').time()))
    random_suffix = secrets.token_hex(4)
    
    # Combine and hash to create a unique reference
    combined = f"{user_str}_{timestamp}_{random_suffix}"
    reference = hashlib.sha256(combined.encode()).hexdigest()[:16].upper()
    
    return f"CRIC_{reference}"


async def get_deposit_address_for_user(session: AsyncSession, user_id: UUID) -> str:
    """
    Get deposit address for a user. For now, returns a fixed address.
    In production, this could be per-user addresses or a single address with memo.
    
    Args:
        session: Database session
        user_id: User UUID
    
    Returns:
        Deposit address string
    """
    # BEP20 (BSC) deposit address for all users
    return "0x509b2589086060a4bcd61fc8db7e4b862f3bcf57"


async def create_deposit_transaction(
    session: AsyncSession,
    user_id: UUID,
    amount: float,
    tx_hash: str,
    deposit_reference: str,
    confirmations: int = 0
) -> Transaction:
    """
    Create a deposit transaction record.
    
    Args:
        session: Database session
        user_id: User UUID
        amount: Deposit amount
        tx_hash: Transaction hash
        deposit_reference: Deposit reference/memo
        confirmations: Number of confirmations
    
    Returns:
        Created Transaction instance
    """
    from decimal import Decimal
    
    transaction = Transaction(
        user_id=user_id,
        tx_type="deposit",
        amount=Decimal(str(amount)),
        currency="USDT",
        tx_metadata={
            "deposit_reference": deposit_reference,
            "network": "BEP20",
            "tx_hash": tx_hash,
            "confirmations": confirmations
        }
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return transaction


async def get_user_chat_id(session: AsyncSession, user_id: UUID) -> Optional[str]:
    """
    Get user's chat ID for notifications.
    
    Args:
        session: Database session
        user_id: User UUID
    
    Returns:
        Chat ID string or None if not found
    """
    try:
        result = await session.execute(
            select(ChatMap).where(ChatMap.user_id == str(user_id))
        )
        chat_map = result.scalar_one_or_none()
        return chat_map.chat_id if chat_map else None
    except Exception as e:
        # Handle case where chat_map table doesn't exist
        logger.warning(f"Failed to get chat ID for user {user_id}: {e}")
        return None


async def subscribe_to_deposit_notifications(session: AsyncSession, user_id: UUID, chat_id: str) -> bool:
    """
    Subscribe user to deposit notifications.
    
    Args:
        session: Database session
        user_id: User UUID
        chat_id: Telegram chat ID
    
    Returns:
        True if successful
    """
    from app.repos.user_repo import save_chat_id
    return await save_chat_id(session, user_id, chat_id)


async def get_pending_deposits(session: AsyncSession, user_id: UUID) -> list[Transaction]:
    """
    Get pending deposits for a user.
    
    Args:
        session: Database session
        user_id: User UUID
    
    Returns:
        List of pending deposit transactions
    """
    result = await session.execute(
        select(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.tx_type == "deposit",
            Transaction.status.in_(["pending", "confirmed"])
        )
        .order_by(Transaction.created_at.desc())
    )
    return result.scalars().all()
