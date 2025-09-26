"""
Contest-specific callback handlers with improved UX
"""

import logging
from typing import Optional
from uuid import UUID
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.core.config import settings
from app.db.session import async_session
from app.repos.user_repo import get_user_by_telegram_id
from app.repos.contest_repo import get_contest_by_id
from app.repos.contest_entry_repo import create_contest_entry, get_contest_entries, get_user_contest_entries
from app.repos.wallet_repo import get_wallet_for_user, debit_for_contest_entry
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# Create router for contest callbacks
contest_callback_router = Router()


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


@contest_callback_router.callback_query(F.data.startswith("join_contest:"))
async def join_contest_callback(callback_query: CallbackQuery):
    """Handle join contest callback with improved UX and idempotency"""
    await callback_query.answer()
    
    try:
        # Extract contest ID from callback data
        contest_id_str = callback_query.data.split(":", 1)[1]
        contest_id = UUID(contest_id_str)
        
        async with async_session() as session:
            # Get user
            user = await get_user_by_telegram_id(session, callback_query.from_user.id)
            if not user:
                await callback_query.message.edit_text(
                    "❌ User not found. Please use /start first.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            # Get contest
            contest = await get_contest_by_id(session, contest_id)
            if not contest:
                await callback_query.message.edit_text(
                    "❌ Contest not found or no longer available.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏏 Back to Contests", callback_data="contests")],
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            # Check if contest is still open
            if contest.status != "open":
                await callback_query.message.edit_text(
                    f"❌ Contest is {contest.status} and cannot be joined.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏏 Back to Contests", callback_data="contests")],
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            # Check if contest is full
            if contest.max_players:
                current_entries = await get_contest_entries(session, contest_id)
                if len(current_entries) >= contest.max_players:
                    await callback_query.message.edit_text(
                        "❌ Contest is full. Cannot join.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🏏 Back to Contests", callback_data="contests")],
                            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                        ])
                    )
                    return
            
            # Get user's wallet
            wallet = await get_wallet_for_user(session, user.id)
            if not wallet:
                await callback_query.message.edit_text(
                    "❌ Wallet not found. Please contact support.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🆘 Contact Support", callback_data="support")],
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            # Check if user has sufficient balance
            total_balance = wallet.deposit_balance + wallet.winning_balance + wallet.bonus_balance
            if total_balance < contest.entry_fee:
                await callback_query.message.edit_text(
                    f"❌ Insufficient balance. You need {contest.entry_fee} {contest.currency} to join.\n"
                    f"Your current balance: {total_balance} {settings.currency}\n\n"
                    f"Use the Deposit button to add funds to your wallet.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Deposit", callback_data="deposit")],
                        [InlineKeyboardButton(text="💰 Check Balance", callback_data="balance")],
                        [InlineKeyboardButton(text="🏏 Back to Contests", callback_data="contests")]
                    ])
                )
                return
            
            # Check if user already joined (database check)
            existing_entries = await get_contest_entries(
                session, contest_id, user_id=user.id, limit=1
            )
            if existing_entries:
                await callback_query.message.edit_text(
                    "⚠️ You have already joined this contest.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📊 View My Contests", callback_data="my_contests")],
                        [InlineKeyboardButton(text="🏏 Back to Contests", callback_data="contests")]
                    ])
                )
                return
            
            # Debit wallet for contest entry
            success, error_msg = await debit_for_contest_entry(
                session, user.id, contest.entry_fee
            )
            
            if not success:
                await callback_query.message.edit_text(
                    f"❌ Failed to process payment: {error_msg}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Try Again", callback_data=f"join_contest:{contest.id}")],
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            # Set idempotency key ONLY after successful wallet debit
            operation_key = f"join_contest_{contest_id}"
            try:
                redis_client = await get_redis_client()
                key = f"bot_operation:{operation_key}:{callback_query.from_user.id}"
                await redis_client.setex(key, 300, "processed")
            except Exception as e:
                logger.error(f"Error setting idempotency key: {e}")
                # Continue even if Redis fails
            
            # Create contest entry
            entry = await create_contest_entry(
                session, contest_id, user.id, contest.entry_fee
            )
            
            # Get match information
            from app.models.match import Match
            from sqlalchemy import select
            
            match = None
            try:
                match_result = await session.execute(
                    select(Match).where(Match.id == contest.match_id)
                )
                match = match_result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Error fetching match info: {e}")
            
            # Success message with improved formatting
            success_text = (
                f"🎉 *Successfully joined contest!*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏏 *Contest:* {contest.title}\n"
                f"💰 *Entry Fee:* `{contest.entry_fee} {contest.currency}`\n"
                f"🆔 *Entry ID:* `{entry.id}`\n"
                f"🔑 *Contest Code:* `{contest.code}`\n"
            )
            
            # Add match information if available
            if match:
                success_text += f"🏆 *Match:* {match.title}\n"
                if match.start_time:
                    from datetime import datetime
                    start_time_str = match.start_time.strftime('%Y-%m-%d %H:%M UTC')
                    success_text += f"⏰ *Match Time:* `{start_time_str}`\n"
            
            # Add user link if provided by admin
            if contest.user_link:
                success_text += f"🔗 *User Link:* {contest.user_link}\n"
            
            success_text += (
                f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🍀 *Good luck!* 🍀"
            )
            
            # Add keyboard with options
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Check Balance", callback_data="balance")],
                [InlineKeyboardButton(text="📊 View My Contests", callback_data="my_contests")],
                [InlineKeyboardButton(text="🏏 View All Contests", callback_data="contests")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await callback_query.message.edit_text(success_text, reply_markup=keyboard, parse_mode="Markdown")
            
    except ValueError as e:
        logger.error(f"Invalid contest ID format: {e}")
        await callback_query.message.edit_text(
            "❌ Invalid contest ID format.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏏 Back to Contests", callback_data="contests")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
        )
    except Exception as e:
        logger.error(f"Error joining contest: {e}")
        await callback_query.message.edit_text(
            "❌ An error occurred while joining the contest.\n\n"
            "Please try again or contact support if the issue persists.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Try Again", callback_data=f"join_contest:{contest_id_str}")],
                [InlineKeyboardButton(text="🏏 Back to Contests", callback_data="contests")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")],
                [InlineKeyboardButton(text="🆘 Contact Support", callback_data="support")]
            ])
        )


@contest_callback_router.callback_query(F.data.startswith("contest_details:"))
async def contest_details_callback(callback_query: CallbackQuery):
    """Handle contest details callback with improved display"""
    await callback_query.answer()
    
    try:
        # Extract contest ID from callback data
        contest_id_str = callback_query.data.split(":", 1)[1]
        contest_id = UUID(contest_id_str)
        
        async with async_session() as session:
            # Get contest details
            contest = await get_contest_by_id(session, contest_id)
            if not contest:
                await callback_query.message.edit_text(
                    "❌ Contest not found or no longer available.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏏 Back to Contests", callback_data="contests")],
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            # Get current entries
            current_entries = await get_contest_entries(session, contest_id)
            entry_count = len(current_entries)
            
            # Get prize structure info with net amounts after commission
            from app.bot.utils.prize_calculator import format_prize_info, get_net_prize_pool_display
            
            # Use max participants for prize calculation (not current count)
            max_participants = contest.max_players or 4  # Default to 4 if no max set
            prize_info = format_prize_info(contest, max_participants)
            
            # Format start time
            start_time = contest.start_time.strftime('%Y-%m-%d %H:%M UTC') if contest.start_time else "TBD"
            
            # Calculate net prize pool after commission using max participants
            net_prize_pool = get_net_prize_pool_display(contest.entry_fee, max_participants)
            
            # Get match information
            from app.models.match import Match
            from sqlalchemy import select
            
            match = None
            try:
                match_result = await session.execute(
                    select(Match).where(Match.id == contest.match_id)
                )
                match = match_result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Error fetching match info: {e}")
            
            # Contest details text with improved formatting
            details_text = (
                f"🏏 *Contest Details*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 *Title:* {contest.title}\n"
                f"💰 *Entry Fee:* `{contest.entry_fee} {contest.currency}`\n"
                f"🏆 *Prize Pool:* `{net_prize_pool} {contest.currency}`\n"
                f"👥 *Players:* `{entry_count}/{contest.max_players or '∞'}`\n"
                f"🔑 *Contest Code:* `{contest.code}`\n"
            )
            
            # Add match information if available
            if match:
                details_text += f"🏆 *Match:* {match.title}\n"
                if match.start_time:
                    from datetime import datetime
                    match_time_str = match.start_time.strftime('%Y-%m-%d %H:%M UTC')
                    details_text += f"⏰ *Match Time:* `{match_time_str}`\n"
            
            # Add user link if provided by admin
            if contest.user_link:
                details_text += f"🔗 *User Link:* {contest.user_link}\n"
            
            details_text += (
                f"📅 *Start Time:* `{start_time}`\n"
                f"📊 *Status:* *{contest.status.title()}*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{prize_info}\n"
                f"📝 *Description:*\n"
                f"{contest.description or 'No description available.'}\n\n"
                f"⚠️ *Rules:*\n"
                f"• Entry fee will be deducted from your wallet\n"
                f"• Prizes are distributed after contest completion\n"
                f"• All decisions are final"
            )
            
            # Create action buttons
            action_buttons = []
            
            # Join button (only if contest is open and not full)
            if contest.status == "open" and (not contest.max_players or entry_count < contest.max_players):
                action_buttons.append([
                    InlineKeyboardButton(
                        text="🎯 Join Contest",
                        callback_data=f"join_contest:{contest.id}"
                    )
                ])
            
            # View entries button (if user is admin or participant)
            user = await get_user_by_telegram_id(session, callback_query.from_user.id)
            if user:
                # Check if user is participant
                user_entries = [e for e in current_entries if e.user_id == user.id]
                if user_entries:
                    action_buttons.append([
                        InlineKeyboardButton(
                            text="📊 View My Entry",
                            callback_data=f"view_my_entry:{contest.id}"
                        )
                    ])
            
            # Back to contests button
            action_buttons.append([
                InlineKeyboardButton(text="🏏 Back to Contests", callback_data="contests"),
                InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=action_buttons)
            
            await callback_query.message.edit_text(details_text, reply_markup=keyboard, parse_mode="Markdown")
            
    except ValueError as e:
        logger.error(f"Invalid contest ID format: {e}")
        await callback_query.message.edit_text(
            "❌ Invalid contest ID format.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏏 Back to Contests", callback_data="contests")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
        )
    except Exception as e:
        logger.error(f"Error showing contest details: {e}")
        await callback_query.message.edit_text(
            "❌ An error occurred while retrieving contest details.\n\n"
            "Please try again or contact support if the issue persists.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Try Again", callback_data="contests")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")],
                [InlineKeyboardButton(text="🆘 Contact Support", callback_data="support")]
            ])
        )


@contest_callback_router.callback_query(F.data.startswith("view_my_entry:"))
async def view_my_entry_callback(callback_query: CallbackQuery):
    """Handle view my entry callback with improved display"""
    await callback_query.answer()
    
    try:
        # Extract contest ID from callback data
        contest_id_str = callback_query.data.split(":", 1)[1]
        contest_id = UUID(contest_id_str)
        
        async with async_session() as session:
            # Get user
            user = await get_user_by_telegram_id(session, callback_query.from_user.id)
            if not user:
                await callback_query.message.edit_text(
                    "❌ User not found. Please use /start first.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            # Get contest
            contest = await get_contest_by_id(session, contest_id)
            if not contest:
                await callback_query.message.edit_text(
                    "❌ Contest not found.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏏 Back to Contests", callback_data="contests")],
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            # Get user's entry
            user_entries = await get_user_contest_entries(session, user.id, contest_id=contest_id, limit=1)
            
            if not user_entries:
                await callback_query.message.edit_text(
                    "❌ You haven't joined this contest yet.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🎯 Join Contest", callback_data=f"join_contest:{contest.id}")],
                        [InlineKeyboardButton(text="🏏 Back to Contests", callback_data="contests")]
                    ])
                )
                return
            
            entry = user_entries[0]
            
            # Get current position (if contest is settled)
            position_text = ""
            if contest.status == "settled" and hasattr(entry, 'position') and entry.position:
                position_text = f"🏆 *Final Position:* #{entry.position}\n"
                if hasattr(entry, 'prize_amount') and entry.prize_amount:
                    position_text += f"💰 *Prize Won:* {entry.prize_amount} {contest.currency}\n"
            
            # Entry details text with improved formatting
            entry_text = (
                f"📊 *Your Contest Entry*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏏 *Contest:* {contest.title}\n"
                f"💰 *Entry Fee:* {entry.entry_fee} {contest.currency}\n"
                f"📅 *Joined:* {entry.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"📊 *Contest Status:* *{contest.status.title()}*\n\n"
                f"{position_text}"
                f"🆔 *Entry ID:* `{entry.id}`\n"
                f"📝 *Notes:* Entry is confirmed and active\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            
            # Action buttons
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏏 Contest Details", callback_data=f"contest_details:{contest.id}")],
                [InlineKeyboardButton(text="🏏 Back to Contests", callback_data="contests")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await callback_query.message.edit_text(entry_text, reply_markup=keyboard, parse_mode="Markdown")
            
    except ValueError as e:
        logger.error(f"Invalid contest ID format: {e}")
        await callback_query.message.edit_text(
            "❌ Invalid contest ID format.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏏 Back to Contests", callback_data="contests")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
        )
    except Exception as e:
        logger.error(f"Error viewing contest entry: {e}")
        await callback_query.message.edit_text(
            "❌ An error occurred while retrieving your entry. Please try again later.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏏 Back to Contests", callback_data="contests")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
        )
