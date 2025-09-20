"""
Callback handlers for Telegram bot with idempotency
"""

import logging
from typing import Optional
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.core.config import settings
from app.db.session import get_async_session
from app.repos.user_repo import get_user_by_telegram_id
from app.repos.contest_repo import get_contest_by_id
from app.repos.contest_entry_repo import create_contest_entry, get_contest_entries
from app.repos.wallet_repo import get_wallet_for_user, debit_for_contest_entry
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# Create router for callbacks
callback_router = Router()


async def is_idempotent_operation(operation_key: str, user_id: int) -> bool:
    """
    Check if an operation is idempotent using Redis.
    Returns True if operation was already processed, False otherwise.
    """
    try:
        redis_client = await get_redis_client()
        key = f"bot_operation:{operation_key}:{user_id}"
        
        # Check if key exists (operation already processed)
        exists = await redis_client.exists(key)
        if exists:
            return True
        
        # Set key with expiration (5 minutes)
        await redis_client.setex(key, 300, "processed")
        return False
        
    except Exception as e:
        logger.error(f"Error checking idempotency: {e}")
        # If Redis fails, allow operation to proceed
        return False


@callback_router.callback_query(F.data.startswith("join_contest:"))
async def join_contest_callback(callback_query: CallbackQuery):
    """Handle join contest callback with idempotency"""
    await callback_query.answer()
    
    try:
        # Extract contest ID from callback data
        contest_id_str = callback_query.data.split(":", 1)[1]
        contest_id = contest_id_str
        
        # Create idempotency key
        operation_key = f"join_contest_{contest_id}"
        
        # Check idempotency
        if await is_idempotent_operation(operation_key, callback_query.from_user.id):
            await callback_query.message.edit_text(
                "⚠️ You have already joined this contest or the request is being processed."
            )
            return
        
        async for session in get_async_session():
            # Get user
            user = await get_user_by_telegram_id(session, callback_query.from_user.id)
            if not user:
                await callback_query.message.edit_text(
                    "❌ User not found. Please use /start first."
                )
                return
            
            # Get contest
            from uuid import UUID
            contest = await get_contest_by_id(session, UUID(contest_id))
            if not contest:
                await callback_query.message.edit_text(
                    "❌ Contest not found or no longer available."
                )
                return
            
            # Check if contest is still open
            if contest.status != "open":
                await callback_query.message.edit_text(
                    f"❌ Contest is {contest.status} and cannot be joined."
                )
                return
            
            # Check if user already joined
            existing_entries = await get_contest_entries(
                session, UUID(contest_id), user_id=user.id, limit=1
            )
            if existing_entries:
                await callback_query.message.edit_text(
                    "⚠️ You have already joined this contest."
                )
                return
            
            # Check if contest is full
            if contest.max_players:
                current_entries = await get_contest_entries(session, UUID(contest_id))
                if len(current_entries) >= contest.max_players:
                    await callback_query.message.edit_text(
                        "❌ Contest is full. Cannot join."
                    )
                    return
            
            # Get user's wallet
            wallet = await get_wallet_for_user(session, user.id)
            if not wallet:
                await callback_query.message.edit_text(
                    "❌ Wallet not found. Please contact support."
                )
                return
            
            # Check if user has sufficient balance
            total_balance = wallet.deposit_balance + wallet.winning_balance + wallet.bonus_balance
            if total_balance < contest.entry_fee:
                await callback_query.message.edit_text(
                    f"❌ Insufficient balance. You need {contest.entry_fee} {contest.currency} to join.\n"
                    f"Your current balance: {total_balance} {settings.currency}\n\n"
                    f"Use /deposit to add funds to your wallet."
                )
                return
            
            # Debit wallet for contest entry
            success, error_msg = await debit_for_contest_entry(
                session, user.id, contest.entry_fee
            )
            
            if not success:
                await callback_query.message.edit_text(
                    f"❌ Failed to process payment: {error_msg}"
                )
                return
            
            # Create contest entry
            entry = await create_contest_entry(
                session, UUID(contest_id), user.id, contest.entry_fee
            )
            
            # Success message
            success_text = (
                f"✅ Successfully joined contest!\n\n"
                f"🏏 Contest: {contest.title}\n"
                f"💰 Entry Fee: {contest.entry_fee} {contest.currency}\n"
                f"🆔 Entry ID: {entry.id}\n\n"
                f"Good luck! 🍀"
            )
            
            # Add keyboard with options
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Check Balance", callback_data="balance")],
                [InlineKeyboardButton(text="🏏 View Contests", callback_data="contests")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await callback_query.message.edit_text(success_text, reply_markup=keyboard)
            break
            
    except ValueError as e:
        logger.error(f"Invalid contest ID format: {e}")
        await callback_query.message.edit_text(
            "❌ Invalid contest ID format."
        )
    except Exception as e:
        logger.error(f"Error joining contest: {e}")
        await callback_query.message.edit_text(
            "❌ An error occurred while joining the contest. Please try again later."
        )


@callback_router.callback_query(F.data == "view_my_contests")
async def view_my_contests_callback(callback_query: CallbackQuery):
    """Handle view my contests callback"""
    await callback_query.answer()
    
    try:
        async for session in get_async_session():
            user = await get_user_by_telegram_id(session, callback_query.from_user.id)
            if not user:
                await callback_query.message.edit_text(
                    "❌ User not found. Please use /start first."
                )
                return
            
            # Get user's contest entries
            from app.repos.contest_entry_repo import get_user_contest_entries
            entries = await get_user_contest_entries(session, user.id, limit=10)
            
            if not entries:
                await callback_query.message.edit_text(
                    "📝 You haven't joined any contests yet.\n\n"
                    "Use /contests to see available contests and join them!"
                )
                return
            
            contests_text = "🏏 Your Contest Entries\n\n"
            
            for entry in entries:
                contest = await get_contest_by_id(session, entry.contest_id)
                if contest:
                    contests_text += (
                        f"🎯 {contest.title}\n"
                        f"💰 Entry Fee: {entry.entry_fee} {contest.currency}\n"
                        f"📅 Joined: {entry.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                        f"📊 Status: {contest.status.title()}\n\n"
                    )
            
            # Add back button
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await callback_query.message.edit_text(contests_text, reply_markup=keyboard)
            break
            
    except Exception as e:
        logger.error(f"Error viewing user contests: {e}")
        await callback_query.message.edit_text(
            "❌ An error occurred while retrieving your contests. Please try again later."
        )


@callback_router.callback_query(F.data == "contest_details")
async def contest_details_callback(callback_query: CallbackQuery):
    """Handle contest details callback"""
    await callback_query.answer()
    
    # This would show detailed contest information
    # For now, redirect to contests
    await callback_query.message.edit_text(
        "🏏 Contest Details\n\n"
        "Use /contests to see all available contests with their details."
    )


@callback_router.callback_query(F.data == "support")
async def support_callback(callback_query: CallbackQuery):
    """Handle support callback"""
    await callback_query.answer()
    
    support_text = (
        "🆘 Support\n\n"
        "Need help? Here are your options:\n\n"
        "📧 Email: support@cricalgo.com\n"
        "💬 Telegram: @CricAlgoSupport\n"
        "🌐 Website: https://cricalgo.com/support\n\n"
        "Common issues:\n"
        "• Balance not updating: Wait for blockchain confirmation\n"
        "• Can't join contest: Check your balance and contest status\n"
        "• Withdrawal issues: Contact support with your user ID"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
    ])
    
    await callback_query.message.edit_text(support_text, reply_markup=keyboard)


@callback_router.callback_query(F.data == "settings")
async def settings_callback(callback_query: CallbackQuery):
    """Handle settings callback"""
    await callback_query.answer()
    
    try:
        async for session in get_async_session():
            user = await get_user_by_telegram_id(session, callback_query.from_user.id)
            if not user:
                await callback_query.message.edit_text(
                    "❌ User not found. Please use /start first."
                )
                return
            
            settings_text = (
                f"⚙️ Settings\n\n"
                f"👤 Username: {user.username}\n"
                f"🆔 User ID: {user.id}\n"
                f"📱 Telegram ID: {user.telegram_id}\n"
                f"📊 Status: {user.status.value.title()}\n"
                f"📅 Member since: {user.created_at.strftime('%Y-%m-%d')}\n\n"
                f"💡 Your account information is secure and encrypted."
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await callback_query.message.edit_text(settings_text, reply_markup=keyboard)
            break
            
    except Exception as e:
        logger.error(f"Error showing settings: {e}")
        await callback_query.message.edit_text(
            "❌ An error occurred while retrieving your settings. Please try again later."
        )
