"""
Notification tasks for Telegram bot
"""

import logging
from typing import Optional
from uuid import UUID
from decimal import Decimal
from app.core.redis_client import redis_client
from app.db.session import async_session
from app.repos.deposit_repo import get_user_chat_id
from app.repos.user_repo import get_user_by_id
from app.repos.contest_repo import get_contest_by_id
from app.repos.contest_entry_repo import get_contest_entries_by_contest
from app.models.enums import ContestStatus

logger = logging.getLogger(__name__)


async def send_deposit_confirmation(tx_id: str) -> bool:
    """
    Send deposit confirmation notification to user.
    
    Args:
        tx_id: Transaction ID
    
    Returns:
        True if notification sent successfully
    """
    try:
        async with async_session() as session:
            from app.repos.transaction_repo import get_transaction_by_id
            
            # Get transaction details
            transaction = await get_transaction_by_id(session, UUID(tx_id))
            if not transaction or transaction.tx_type != "deposit":
                logger.error(f"Transaction {tx_id} not found or not a deposit")
                return False
            
            # Get user details
            user = await get_user_by_id(session, transaction.user_id)
            if not user:
                logger.error(f"User {transaction.user_id} not found for transaction {tx_id}")
                return False
            
            # Get user's chat ID
            chat_id = await get_user_chat_id(session, transaction.user_id)
            if not chat_id:
                logger.error(f"Chat ID not found for user {transaction.user_id}")
                return False
            
            # Create idempotency key to prevent duplicate notifications
            idempotency_key = f"deposit_notification:{tx_id}"
            
            # Check if notification already sent
            if await redis_client.exists(idempotency_key):
                logger.info(f"Deposit notification already sent for transaction {tx_id}")
                return True
            
            # Send notification (this would be implemented with actual bot instance)
            # For now, we'll just log it
            notification_text = (
                f"🎉 Deposit Confirmed!\n\n"
                f"Amount: {transaction.amount} {transaction.currency}\n"
                f"Status: Confirmed and credited to your deposit balance\n\n"
                f"Your new balance is available in your wallet."
            )
            
            logger.info(f"Would send deposit notification to chat {chat_id}: {notification_text}")
            
            # Mark notification as sent
            await redis_client.setex(idempotency_key, 86400, "sent")  # 24 hours
            
            return True
            
    except Exception as e:
        logger.error(f"Error sending deposit confirmation for transaction {tx_id}: {e}")
        return False


async def send_contest_settlement(contest_id: str) -> bool:
    """
    Send contest settlement notifications to participants.
    
    Args:
        contest_id: Contest ID
    
    Returns:
        True if notifications sent successfully
    """
    try:
        async with async_session() as session:
            # Get contest details
            contest = await get_contest_by_id(session, UUID(contest_id))
            if not contest:
                logger.error(f"Contest {contest_id} not found")
                return False
            
            # Get contest entries
            entries = await get_contest_entries_by_contest(session, UUID(contest_id))
            if not entries:
                logger.error(f"No entries found for contest {contest_id}")
                return False
            
            # Send notifications to all participants
            for entry in entries:
                user = await get_user_by_id(session, entry.user_id)
                if not user:
                    continue
                
                chat_id = await get_user_chat_id(session, entry.user_id)
                if not chat_id:
                    continue
                
                # Create idempotency key
                idempotency_key = f"contest_settlement:{contest_id}:{entry.user_id}"
                
                # Check if notification already sent
                if await redis_client.exists(idempotency_key):
                    continue
                
                # Determine if user won
                if entry.position == 1:  # Winner
                    notification_text = (
                        f"🏆 Congratulations! You won the contest!\n\n"
                        f"Contest: {contest.title}\n"
                        f"Prize: {entry.prize_amount} {contest.currency}\n"
                        f"Your winnings have been credited to your wallet.\n\n"
                        f"Check your balance to see your new total!"
                    )
                else:  # Non-winner
                    notification_text = (
                        f"📊 Contest Results\n\n"
                        f"Contest: {contest.title}\n"
                        f"Position: #{entry.position}\n"
                        f"Better luck next time!\n\n"
                        f"Check out new contests to try again."
                    )
                
                logger.info(f"Would send contest notification to chat {chat_id}: {notification_text}")
                
                # Mark notification as sent
                await redis_client.setex(idempotency_key, 86400, "sent")  # 24 hours
            
            return True
            
    except Exception as e:
        logger.error(f"Error sending contest settlement notifications for contest {contest_id}: {e}")
        return False


async def send_withdrawal_approval(withdrawal_id: str) -> bool:
    """
    Send withdrawal approval notification to user.
    
    Args:
        withdrawal_id: Withdrawal ID
    
    Returns:
        True if notification sent successfully
    """
    try:
        async with async_session() as session:
            from app.repos.withdrawal_repo import get_withdrawal_by_id
            
            # Get withdrawal details
            withdrawal = await get_withdrawal_by_id(session, UUID(withdrawal_id))
            if not withdrawal:
                logger.error(f"Withdrawal {withdrawal_id} not found")
                return False
            
            # Get user details
            user = await get_user_by_id(session, withdrawal.user_id)
            if not user:
                logger.error(f"User {withdrawal.user_id} not found for withdrawal {withdrawal_id}")
                return False
            
            # Get user's chat ID
            chat_id = await get_user_chat_id(session, withdrawal.user_id)
            if not chat_id:
                logger.error(f"Chat ID not found for user {withdrawal.user_id}")
                return False
            
            # Create idempotency key
            idempotency_key = f"withdrawal_approval:{withdrawal_id}"
            
            # Check if notification already sent
            if await redis_client.exists(idempotency_key):
                logger.info(f"Withdrawal approval notification already sent for {withdrawal_id}")
                return True
            
            # Send notification
            notification_text = (
                f"✅ Withdrawal Approved!\n\n"
                f"Amount: {withdrawal.amount} {withdrawal.currency}\n"
                f"Address: {withdrawal.destination_address}\n"
                f"Status: Approved and being processed\n\n"
                f"Your withdrawal will be processed shortly."
            )
            
            logger.info(f"Would send withdrawal approval notification to chat {chat_id}: {notification_text}")
            
            # Mark notification as sent
            await redis_client.setex(idempotency_key, 86400, "sent")  # 24 hours
            
            return True
            
    except Exception as e:
        logger.error(f"Error sending withdrawal approval notification for {withdrawal_id}: {e}")
        return False
