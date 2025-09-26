"""
Unified callback handlers for Telegram bot with consistent UI/UX
"""

import logging
from typing import Optional, List, Dict, Any
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.core.config import settings
from app.db.session import async_session
from app.repos.user_repo import get_user_by_telegram_id
from app.repos.contest_repo import get_contest_by_id, get_contests, get_contest_participants_count
from app.repos.contest_entry_repo import create_contest_entry, get_contest_entries, get_user_contest_entries
from app.repos.wallet_repo import get_wallet_for_user, debit_for_contest_entry, create_wallet_for_user
from app.repos.deposit_repo import get_deposit_address_for_user
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# Create router for unified callbacks
unified_callback_router = Router()


class BotUIComponents:
    """Reusable UI components for consistent bot interface"""
    
    @staticmethod
    def get_main_menu_keyboard() -> InlineKeyboardMarkup:
        """Standard main menu keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Balance", callback_data="balance")],
            [InlineKeyboardButton(text="💳 Deposit", callback_data="deposit")],
            [InlineKeyboardButton(text="🏏 Contests", callback_data="contests")],
            [InlineKeyboardButton(text="📊 My Contests", callback_data="my_contests")],
            [InlineKeyboardButton(text="💸 Withdraw", callback_data="withdraw")],
            [InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton(text="🆘 Support", callback_data="support")]
        ])
    
    @staticmethod
    def get_back_to_main_keyboard() -> InlineKeyboardMarkup:
        """Standard back to main menu keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
        ])
    
    @staticmethod
    def get_navigation_keyboard(back_to: str = "main_menu", additional_buttons: List[List[InlineKeyboardButton]] = None) -> InlineKeyboardMarkup:
        """Flexible navigation keyboard"""
        buttons = []
        if additional_buttons:
            buttons.extend(additional_buttons)
        buttons.append([InlineKeyboardButton(text="🏠 Main Menu", callback_data=back_to)])
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def get_error_keyboard(operation: str = "main_menu") -> InlineKeyboardMarkup:
        """Standard error recovery keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Try Again", callback_data=operation)],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")],
            [InlineKeyboardButton(text="🆘 Support", callback_data="support")]
        ])


class BotResponseHandler:
    """Centralized response handling for consistent user experience"""
    
    @staticmethod
    async def handle_callback_response(callback_query: CallbackQuery, text: str, keyboard: InlineKeyboardMarkup = None, parse_mode: str = "Markdown"):
        """Consistent callback response handling"""
        try:
            await callback_query.answer()
            if keyboard:
                await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode=parse_mode)
            else:
                await callback_query.message.edit_text(text, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"Error handling callback response: {e}")
            # Fallback to sending new message
            try:
                await callback_query.message.answer(text, reply_markup=keyboard, parse_mode=parse_mode)
            except Exception as fallback_error:
                logger.error(f"Fallback response also failed: {fallback_error}")
                await callback_query.message.answer("❌ An error occurred. Please try again.")
    
    @staticmethod
    async def handle_error(callback_query: CallbackQuery, error_msg: str, operation: str = "main_menu"):
        """Consistent error handling"""
        logger.error(f"Bot error for user {callback_query.from_user.id}: {error_msg}")
        keyboard = BotUIComponents.get_error_keyboard(operation)
        await BotResponseHandler.handle_callback_response(
            callback_query,
            f"❌ {error_msg}\n\nPlease try again or contact support if the issue persists.",
            keyboard
        )


async def check_user_access(callback_query: CallbackQuery) -> tuple[bool, Optional[Any]]:
    """Check if user has access and return user object if valid"""
    try:
        async with async_session() as session:
            user = await get_user_by_telegram_id(session, callback_query.from_user.id)
            if not user:
                await BotResponseHandler.handle_callback_response(
                    callback_query,
                    "❌ User not found. Please use /start first to register your account.",
                    BotUIComponents.get_back_to_main_keyboard()
                )
                return False, None
            return True, user
    except Exception as e:
        logger.error(f"Error checking user access: {e}")
        await BotResponseHandler.handle_error(callback_query, "Failed to verify user access")
        return False, None


# Main Menu Handler
@unified_callback_router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback_query: CallbackQuery):
    """Handle main menu callback with consistent UI"""
    await BotResponseHandler.handle_callback_response(
        callback_query,
        "🏠 *Main Menu*\n\nChoose an option:",
        BotUIComponents.get_main_menu_keyboard()
    )


# Balance Handler
@unified_callback_router.callback_query(F.data == "balance")
async def balance_callback(callback_query: CallbackQuery):
    """Handle balance callback with consistent formatting"""
    has_access, user = await check_user_access(callback_query)
    if not has_access:
        return
    
    try:
        async with async_session() as session:
            wallet = await get_wallet_for_user(session, user.id)
            if not wallet:
                await BotResponseHandler.handle_callback_response(
                    callback_query,
                    "❌ Wallet not found. Please contact support.",
                    BotUIComponents.get_back_to_main_keyboard()
                )
                return
            
            # Format balance with consistent styling
            total_balance = wallet.deposit_balance + wallet.winning_balance + wallet.bonus_balance
            
            balance_text = (
                "💰 *Your Wallet Balance*\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💳 *Deposit Balance:* `{wallet.deposit_balance} USDT`\n"
                f"🏆 *Winning Balance:* `{wallet.winning_balance} USDT`\n"
                f"🎁 *Bonus Balance:* `{wallet.bonus_balance} USDT`\n\n"
                f"💎 *Total Balance:* `{total_balance} USDT`\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
            
            # Navigation buttons
            keyboard = BotUIComponents.get_navigation_keyboard(
                additional_buttons=[
                    [InlineKeyboardButton(text="💳 Deposit", callback_data="deposit")],
                    [InlineKeyboardButton(text="💸 Withdraw", callback_data="withdraw")]
                ]
            )
            
            await BotResponseHandler.handle_callback_response(callback_query, balance_text, keyboard)
            
    except Exception as e:
        await BotResponseHandler.handle_error(callback_query, "Failed to load balance information")


# Deposit Handler
@unified_callback_router.callback_query(F.data == "deposit")
async def deposit_callback(callback_query: CallbackQuery):
    """Handle deposit callback - same as /deposit command"""
    has_access, user = await check_user_access(callback_query)
    if not has_access:
        return
    
    try:
        async with async_session() as session:
            # Get user-specific deposit information (same as /deposit command)
            from app.repos.deposit_repo import generate_deposit_reference
            deposit_address = await get_deposit_address_for_user(session, user.id)
            deposit_reference = await generate_deposit_reference(session, user.id)
            
            # Format deposit text (same as /deposit command)
            deposit_text = (
                f"💳 *Manual Deposit Process*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📍 *Deposit Address:*\n"
                f"`{deposit_address}`\n\n"
                f"🏷️ *Deposit Reference (Memo):*\n"
                f"`{deposit_reference}`\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📋 *Step-by-Step Instructions:*\n"
                f"1️⃣ Send USDT to the address above\n"
                f"2️⃣ Use the deposit reference as memo\n"
                f"3️⃣ Minimum deposit: *No minimum*\n"
                f"4️⃣ Network: *BEP20 (BSC)*\n\n"
                f"⚠️ *Important:* Only send USDT (BEP20) to this address!\n"
                f"Other tokens will be lost permanently.\n\n"
                f"✅ After sending, click 'I Sent USDT' to submit your transaction hash for manual approval."
            )
            
            # Add manual deposit flow buttons (same as /deposit command)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ I Sent USDT", callback_data="submit_deposit_tx")],
                [InlineKeyboardButton(text="💰 Check Balance", callback_data="balance")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await BotResponseHandler.handle_callback_response(callback_query, deposit_text, keyboard)
            
    except Exception as e:
        await BotResponseHandler.handle_error(callback_query, "Failed to load deposit information")


# Contests Handler
@unified_callback_router.callback_query(F.data == "contests")
async def contests_callback(callback_query: CallbackQuery):
    """Handle contests callback with improved display"""
    has_access, user = await check_user_access(callback_query)
    if not has_access:
        return
    
    try:
        async with async_session() as session:
            # Get open contests
            contests = await get_contests(session, limit=10, status='open')
            
            if not contests:
                contests_text = (
                    "🎯 *No Contests Available*\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "There are no open contests at the moment.\n"
                    "Check back later for new contests!\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                )
                keyboard = BotUIComponents.get_back_to_main_keyboard()
            else:
                contests_text = "🎯 *Available Contests*\n\n"
                keyboard_buttons = []
                
                for contest in contests:
                    # Get current entries count
                    entries = await get_contest_entries(session, contest.id, limit=100)
                    current_entries = len(entries)
                    
                    # Calculate net prize pool after commission using max participants
                    from app.bot.utils.prize_calculator import get_net_prize_pool_display
                    max_participants = contest.max_players or 4  # Default to 4 if no max set
                    net_prize_pool = get_net_prize_pool_display(contest.entry_fee, max_participants)
                    
                    # Format contest display
                    contests_text += (
                        f"🏆 *{contest.title}*\n"
                        f"💰 Entry Fee: `{contest.entry_fee} {contest.currency}`\n"
                        f"👥 Players: `{current_entries}/{contest.max_players or '∞'}`\n"
                        f"🎁 Prize: `{net_prize_pool} {contest.currency}`\n\n"
                    )
                    
                    # Add join button if not at capacity
                    if not contest.max_players or current_entries < contest.max_players:
                        keyboard_buttons.append([
                            InlineKeyboardButton(
                                text=f"🎯 Join {contest.title}",
                                callback_data=f"join_contest:{contest.id}"
                            )
                        ])
                
                # Add navigation
                keyboard = BotUIComponents.get_navigation_keyboard(
                    additional_buttons=keyboard_buttons
                )
            
            await BotResponseHandler.handle_callback_response(callback_query, contests_text, keyboard)
            
    except Exception as e:
        await BotResponseHandler.handle_error(callback_query, "Failed to load contests")


# My Contests Handler
@unified_callback_router.callback_query(F.data == "my_contests")
async def my_contests_callback(callback_query: CallbackQuery):
    """Handle my contests callback - shows active contests by default"""
    has_access, user = await check_user_access(callback_query)
    if not has_access:
        return
    
    try:
        async with async_session() as session:
            # Get user's active contest entries (open contests only)
            logger.info(f"Getting active contest entries for user {user.id}")
            entries = await get_user_contest_entries(session, user.id, limit=5, contest_status="open")
            logger.info(f"Found {len(entries)} active contest entries")
            logger.info(f"DEBUG: Active contests callback triggered for user {user.id}")
            
            if not entries:
                contests_text = (
                    "🏏 *Your Active Contests*\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "You don't have any active contests at the moment.\n"
                    "Use the Contests button to see available contests and join them!\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                )
                keyboard = BotUIComponents.get_navigation_keyboard(
                    additional_buttons=[
                        [InlineKeyboardButton(text="🏏 View Contests", callback_data="contests")],
                        [InlineKeyboardButton(text="📋 Closed Contests", callback_data="my_contests_closed")]
                    ]
                )
            else:
                contests_text = "🏏 *Your Active Contests*\n\n"
                
                for entry in entries:
                    logger.info(f"Getting contest {entry.contest_id} for entry {entry.id}")
                    try:
                        contest = await get_contest_by_id(session, entry.contest_id)
                        if contest:
                            logger.info(f"Found contest: {contest.title}")
                            
                            # Get match information
                            from app.models.match import Match
                            from sqlalchemy import select
                            match_result = await session.execute(
                                select(Match).where(Match.id == contest.match_id)
                            )
                            match = match_result.scalar_one_or_none()
                            
                            # Format match time
                            match_time = ""
                            if match and match.start_time:
                                match_time = match.start_time.strftime('%Y-%m-%d %H:%M UTC')
                            
                            # Create detailed contest display like after joining
                            contests_text += (
                                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"🏏 *Contest: {contest.title}*\n"
                                f"💰 *Entry Fee:* `{entry.amount_debited} {contest.currency}`\n"
                                f"🆔 *Entry ID:* `{entry.id}`\n"
                                f"🔑 *Contest Code:* `{contest.code}`\n"
                                f"🏆 *Match:* {match.title if match else 'TBD'}\n"
                                f"⏰ *Match Time:* {match_time if match_time else 'TBD'}\n"
                                f"🔗 *User Link:* {contest.user_link if contest.user_link else 'N/A'}\n"
                                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"🍀 *Good luck!* 🍀\n\n"
                            )
                        else:
                            logger.warning(f"Contest {entry.contest_id} not found for entry {entry.id}")
                            contests_text += (
                                f"❓ *Contest Entry*\n"
                                f"💰 Entry Fee: `{entry.amount_debited} USDT`\n"
                                f"📅 Joined: `{entry.created_at.strftime('%Y-%m-%d %H:%M')}`\n"
                                f"📊 Status: *Unknown*\n\n"
                            )
                    except Exception as e:
                        logger.error(f"Error getting contest {entry.contest_id}: {e}")
                        contests_text += (
                            f"❓ *Contest Entry*\n"
                            f"💰 Entry Fee: `{entry.amount_debited} USDT`\n"
                            f"📅 Joined: `{entry.created_at.strftime('%Y-%m-%d %H:%M')}`\n"
                            f"📊 Status: *Error loading contest*\n\n"
                        )
                
                # Navigation buttons
                keyboard = BotUIComponents.get_navigation_keyboard(
                    additional_buttons=[
                        [InlineKeyboardButton(text="🏏 View All Contests", callback_data="contests")],
                        [InlineKeyboardButton(text="📋 Closed Contests", callback_data="my_contests_closed")]
                    ]
                )
            
            await BotResponseHandler.handle_callback_response(callback_query, contests_text, keyboard)
            
    except Exception as e:
        await BotResponseHandler.handle_error(callback_query, "Failed to load your contests")


# Closed Contests Handler
@unified_callback_router.callback_query(F.data == "my_contests_closed")
async def my_contests_closed_callback(callback_query: CallbackQuery):
    """Handle closed contests callback - shows closed/settled contests"""
    has_access, user = await check_user_access(callback_query)
    if not has_access:
        return
    
    try:
        async with async_session() as session:
            # Get user's closed contest entries (closed, settled, cancelled)
            logger.info(f"Getting closed contest entries for user {user.id}")
            logger.info(f"DEBUG: Closed contests callback triggered for user {user.id}")
            
            # Get entries for closed/settled/cancelled contests
            closed_entries = []
            try:
                # First try to get all user entries and filter manually
                logger.info("Getting all user entries for closed contests filtering")
                all_entries = await get_user_contest_entries(session, user.id, limit=20)
                logger.info(f"Found {len(all_entries)} total entries")
                
                for entry in all_entries:
                    try:
                        contest = await get_contest_by_id(session, entry.contest_id)
                        if contest and contest.status in ["closed", "settled", "cancelled"]:
                            closed_entries.append(entry)
                            logger.info(f"Added closed contest: {contest.title} (status: {contest.status})")
                    except Exception as contest_error:
                        logger.error(f"Error getting contest {entry.contest_id}: {contest_error}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error getting entries for closed contests: {e}")
                # If all fails, return empty list
                closed_entries = []
            
            # Sort by created_at descending and limit to 5
            closed_entries.sort(key=lambda x: x.created_at, reverse=True)
            closed_entries = closed_entries[:5]
            
            logger.info(f"Found {len(closed_entries)} closed contest entries")
            
            if not closed_entries:
                contests_text = (
                    "📋 *Your Closed Contests*\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "You don't have any closed contests yet.\n"
                    "Contests will appear here once they are closed or settled.\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                )
                keyboard = BotUIComponents.get_navigation_keyboard(
                    additional_buttons=[
                        [InlineKeyboardButton(text="🏏 Active Contests", callback_data="my_contests")],
                        [InlineKeyboardButton(text="🏏 View All Contests", callback_data="contests")]
                    ]
                )
            else:
                contests_text = "📋 *Your Closed Contests*\n\n"
                
                for entry in closed_entries:
                    logger.info(f"Getting contest {entry.contest_id} for entry {entry.id}")
                    try:
                        contest = await get_contest_by_id(session, entry.contest_id)
                        if contest:
                            logger.info(f"Found contest: {contest.title}")
                            
                            # Get detailed contest information with net prize after commission
                            from app.bot.utils.prize_calculator import get_net_prize_pool_display
                            participants_count = await get_contest_participants_count(session, contest.id)
                            # Use max participants for prize calculation (not current count)
                            max_participants = contest.max_players or 4  # Default to 4 if no max set
                            net_prize_pool = get_net_prize_pool_display(contest.entry_fee, max_participants)
                            
                            # Status emoji and additional info
                            status_emoji = {
                                "closed": "🔴",
                                "settled": "🏆", 
                                "cancelled": "❌"
                            }.get(contest.status, "❓")
                            
                            # Add position/prize info if settled
                            position_info = ""
                            if contest.status == "settled" and hasattr(entry, 'winner_rank') and entry.winner_rank:
                                position_info = f"🏆 Position: #{entry.winner_rank}\n"
                                if hasattr(entry, 'payout_amount') and entry.payout_amount:
                                    position_info += f"💰 Prize: {entry.payout_amount} {contest.currency}\n"
                            
                            contests_text += (
                                f"{status_emoji} *{contest.title}*\n"
                                f"💰 Entry Fee: `{entry.amount_debited} {contest.currency}`\n"
                                f"🏆 Prize Pool: `{net_prize_pool} {contest.currency}`\n"
                                f"👥 Participants: `{participants_count}/{contest.max_players or '∞'}`\n"
                                f"📅 Joined: `{entry.created_at.strftime('%Y-%m-%d %H:%M')}`\n"
                                f"📊 Status: *{contest.status.title()}*\n"
                                f"{position_info}\n"
                            )
                        else:
                            logger.warning(f"Contest {entry.contest_id} not found for entry {entry.id}")
                            contests_text += (
                                f"❓ *Contest Entry*\n"
                                f"💰 Entry Fee: `{entry.amount_debited} USDT`\n"
                                f"📅 Joined: `{entry.created_at.strftime('%Y-%m-%d %H:%M')}`\n"
                                f"📊 Status: *Unknown*\n\n"
                            )
                    except Exception as e:
                        logger.error(f"Error getting contest {entry.contest_id}: {e}")
                        contests_text += (
                            f"❓ *Contest Entry*\n"
                            f"💰 Entry Fee: `{entry.amount_debited} USDT`\n"
                            f"📅 Joined: `{entry.created_at.strftime('%Y-%m-%d %H:%M')}`\n"
                            f"📊 Status: *Error loading contest*\n\n"
                        )
                
                # Navigation buttons
                keyboard = BotUIComponents.get_navigation_keyboard(
                    additional_buttons=[
                        [InlineKeyboardButton(text="🏏 Active Contests", callback_data="my_contests")],
                        [InlineKeyboardButton(text="🏏 View All Contests", callback_data="contests")]
                    ]
                )
            
            await BotResponseHandler.handle_callback_response(callback_query, contests_text, keyboard)
            
    except Exception as e:
        logger.error(f"Error in closed contests callback: {e}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await BotResponseHandler.handle_error(callback_query, f"Failed to load your closed contests: {str(e)}")


# Settings Handler
@unified_callback_router.callback_query(F.data == "settings")
async def settings_callback(callback_query: CallbackQuery):
    """Handle settings callback with user information"""
    has_access, user = await check_user_access(callback_query)
    if not has_access:
        return
    
    try:
        settings_text = (
            "⚙️ *Settings*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Username:* {user.username}\n"
            f"🆔 *User ID:* `{user.id}`\n"
            f"📱 *Telegram ID:* `{user.telegram_id}`\n"
            f"📊 *Status:* *{user.status.value.title()}*\n"
            f"📅 *Member since:* `{user.created_at.strftime('%Y-%m-%d')}`\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔒 *Your account information is secure and encrypted.*\n\n"
            "💡 *Tip:* Use the menu below for quick navigation!"
        )
        
        await BotResponseHandler.handle_callback_response(
            callback_query, 
            settings_text, 
            BotUIComponents.get_back_to_main_keyboard()
        )
        
    except Exception as e:
        await BotResponseHandler.handle_error(callback_query, "Failed to load settings"        )


# Withdraw Amount Handlers
@unified_callback_router.callback_query(F.data.startswith("withdraw_amount:"))
async def withdraw_amount_callback(callback_query: CallbackQuery, state: FSMContext):
    """Handle specific withdraw amount selection"""
    has_access, user = await check_user_access(callback_query)
    if not has_access:
        return
    
    try:
        # Extract amount from callback data
        amount_str = callback_query.data.split(":")[1]
        amount = float(amount_str)
        
        async with async_session() as session:
            wallet = await get_wallet_for_user(session, user.id)
            winning_balance = wallet.winning_balance
            
            if amount > winning_balance:
                await BotResponseHandler.handle_callback_response(
                    callback_query,
                    f"❌ Insufficient winning balance!\n\n"
                    f"Requested: ${amount} {settings.currency}\n"
                    f"Available winning balance: ${winning_balance} {settings.currency}\n\n"
                    "You can only withdraw from your winning balance.\n"
                    "Win contests to earn withdrawable funds!",
                    InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Try Again", callback_data="withdraw")],
                        [InlineKeyboardButton(text="🏏 Join Contests", callback_data="contests")],
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            # Ask for withdrawal address
            await BotResponseHandler.handle_callback_response(
                callback_query,
                f"💸 *Withdrawal Request*\n\n"
                f"Amount: ${amount} {settings.currency}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Please provide your BEP20 wallet address where you want to receive the funds.\n\n"
                f"⚠️ *Important:*\n"
                f"• Only send to BEP20 (BSC) addresses\n"
                f"• Double-check the address before submitting\n"
                f"• Wrong addresses will result in lost funds\n\n"
                f"Enter your BEP20 address:",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Cancel", callback_data="withdraw_cancel")]
                ])
            )
            
            # Set state to wait for withdrawal address
            from app.bot.handlers.commands import UserStates
            await state.set_state(UserStates.waiting_for_withdrawal_address)
            await state.update_data(withdrawal_amount=amount)
            
            
    except Exception as e:
        logger.error(f"Error in withdraw amount callback: {e}")
        await BotResponseHandler.handle_callback_response(
            callback_query,
            "❌ Error processing withdrawal request. Please try again.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Try Again", callback_data="withdraw")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
        )


@unified_callback_router.callback_query(F.data == "withdraw_custom_amount")
async def withdraw_custom_amount_callback(callback_query: CallbackQuery, state: FSMContext):
    """Handle custom withdraw amount input"""
    has_access, user = await check_user_access(callback_query)
    if not has_access:
        return
    
    await callback_query.answer()
    
    # Set state for custom amount input
    from app.bot.handlers.commands import UserStates
    await state.set_state(UserStates.waiting_for_withdrawal_amount)
    
    await callback_query.message.edit_text(
        "💰 *Custom Withdrawal Amount*\n\n"
        "Please enter the amount you want to withdraw.\n"
        "Example: `25.50` or `100`\n\n"
        "⚠️ Make sure you have sufficient balance.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="withdraw_cancel")]
        ])
    )


@unified_callback_router.callback_query(F.data == "withdraw_insufficient")
async def withdraw_insufficient_callback(callback_query: CallbackQuery):
    """Handle insufficient balance button clicks"""
    await callback_query.answer("❌ Insufficient balance for this amount", show_alert=True)


@unified_callback_router.callback_query(F.data == "withdraw_cancel")
async def withdraw_cancel_callback(callback_query: CallbackQuery, state: FSMContext):
    """Handle withdraw cancellation"""
    has_access, user = await check_user_access(callback_query)
    if not has_access:
        return
    
    await state.clear()
    await BotResponseHandler.handle_callback_response(
        callback_query,
        "❌ Withdrawal cancelled.\n\n"
        "You can start a new withdrawal request anytime.",
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 New Withdrawal", callback_data="withdraw")],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
        ])
        )


# Submit Deposit Transaction Handler
@unified_callback_router.callback_query(F.data == "submit_deposit_tx")
async def submit_deposit_tx_callback(callback_query: CallbackQuery, state: FSMContext):
    """Handle submit deposit transaction hash callback"""
    has_access, user = await check_user_access(callback_query)
    if not has_access:
        return
    
    await callback_query.answer()
    
    # Set state for transaction hash input
    from app.bot.handlers.commands import UserStates
    await state.set_state(UserStates.waiting_for_deposit_tx_hash)
    
    await callback_query.message.edit_text(
        "📝 *Submit Transaction Hash*\n\n"
        "Please send me your transaction hash (TXID) from your wallet.\n\n"
        "Example: `0x1234567890abcdef...`\n\n"
        "⚠️ Make sure to copy the complete transaction hash.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="deposit")]
        ])
    )


# Withdrawal Status Handler
@unified_callback_router.callback_query(F.data == "withdrawal_status")
async def withdrawal_status_callback(callback_query: CallbackQuery):
    """Handle withdrawal status check callback"""
    has_access, user = await check_user_access(callback_query)
    if not has_access:
        return
    
    try:
        async with async_session() as session:
            # Get user's withdrawal requests from Transaction table
            from app.models.transaction import Transaction
            from sqlalchemy import select, and_
            
            # Query for user's withdrawal transactions
            stmt = select(Transaction).where(
                and_(
                    Transaction.user_id == user.id,
                    Transaction.tx_type == "withdrawal"
                )
            ).order_by(Transaction.created_at.desc())
            
            result = await session.execute(stmt)
            withdrawals = result.scalars().all()
            
            if not withdrawals:
                status_text = (
                    "📊 *Withdrawal Status*\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "Your withdrawal requests:\n\n"
                    "🔄 No pending withdrawals found.\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "All withdrawals are processed within 24 hours.\n"
                    "Contact support if you have any questions."
                )
            else:
                status_text = "📊 *Withdrawal Status*\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nYour withdrawal requests:\n\n"
                
                for withdrawal in withdrawals[:5]:  # Show last 5 withdrawals
                    status = "Pending"
                    if withdrawal.tx_metadata and withdrawal.tx_metadata.get("status"):
                        status = withdrawal.tx_metadata.get("status", "Pending").title()
                    
                    status_icon = "🔄" if status == "Pending" else "✅" if status == "Confirmed" else "❌"
                    
                    status_text += f"{status_icon} *{withdrawal.amount} USDT*\n"
                    status_text += f"   Status: {status}\n"
                    status_text += f"   Date: {withdrawal.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                    status_text += f"   ID: `{str(withdrawal.id)[:8]}...`\n\n"
                
                status_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                status_text += "All withdrawals are processed within 24 hours.\n"
                status_text += "Contact support if you have any questions."
            
            await BotResponseHandler.handle_callback_response(
                callback_query,
                status_text,
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💰 New Withdrawal", callback_data="withdraw")],
                    [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                ])
            )
            
    except Exception as e:
        logger.error(f"Error checking withdrawal status: {e}")
        await BotResponseHandler.handle_callback_response(
            callback_query,
            "❌ Error checking withdrawal status. Please try again.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Try Again", callback_data="withdrawal_status")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
        )


# Join Contest Handler
@unified_callback_router.callback_query(F.data.startswith("join_contest:"))
async def join_contest_callback(callback_query: CallbackQuery):
    """Handle join contest callback"""
    has_access, user = await check_user_access(callback_query)
    if not has_access:
        return
    
    try:
        # Extract contest ID from callback data
        contest_id = callback_query.data.split(":")[1]
        
        async with async_session() as session:
            # Get contest details
            contest = await get_contest_by_id(session, contest_id)
            if not contest:
                await BotResponseHandler.handle_callback_response(
                    callback_query,
                    "❌ Contest not found!",
                    BotUIComponents.get_back_to_main_keyboard()
                )
                return
            
            # Check user's wallet
            wallet = await get_wallet_for_user(session, user.id)
            total_balance = wallet.deposit_balance + wallet.winning_balance + wallet.bonus_balance
            
            if total_balance < contest.entry_fee:
                await BotResponseHandler.handle_callback_response(
                    callback_query,
                    f"❌ Insufficient balance!\n\n"
                    f"Entry fee: {contest.entry_fee} {contest.currency}\n"
                    f"Your balance: {total_balance} USDT\n\n"
                    "Please deposit more funds to join this contest.",
                    InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Deposit", callback_data="deposit")],
                        [InlineKeyboardButton(text="🏏 Contests", callback_data="contests")],
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            # Create contest entry
            from decimal import Decimal
            entry = await create_contest_entry(session, contest.id, user.id, Decimal(str(contest.entry_fee)))
            success, error = await debit_for_contest_entry(session, user.id, Decimal(str(contest.entry_fee)))
            if not success:
                await BotResponseHandler.handle_callback_response(
                    callback_query,
                    f"❌ Error joining contest: {error}",
                    InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏏 Contests", callback_data="contests")],
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
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
            
            await BotResponseHandler.handle_callback_response(
                callback_query,
                success_text,
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💰 Check Balance", callback_data="balance")],
                    [InlineKeyboardButton(text="📊 View My Contests", callback_data="my_contests")],
                    [InlineKeyboardButton(text="🏏 View All Contests", callback_data="contests")],
                    [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                ])
            )
            
    except Exception as e:
        logger.error(f"Error joining contest: {e}")
        await BotResponseHandler.handle_callback_response(
            callback_query,
            "❌ Error joining contest. Please try again.",
            BotUIComponents.get_back_to_main_keyboard()
        )


# Support Handler
@unified_callback_router.callback_query(F.data == "support")
async def support_callback(callback_query: CallbackQuery):
    """Handle support callback with comprehensive help information"""
    support_text = (
        "🆘 *Support*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Need help? Here are your options:\n\n"
        "📧 *Email:* support@cricalgo.com\n"
        "💬 *Telegram:* @CricAlgoSupport\n"
        "🌐 *Website:* https://cricalgo.com/support\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔧 *Common Issues:*\n"
        "• Balance not updating: Wait for blockchain confirmation\n"
        "• Can't join contest: Check your balance and contest status\n"
        "• Withdrawal issues: Contact support with your user ID\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Tip:* Use /menu for quick access to all features!"
    )
    
    await BotResponseHandler.handle_callback_response(
        callback_query, 
        support_text, 
        BotUIComponents.get_back_to_main_keyboard()
    )


# Main Menu Handler
@unified_callback_router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback_query: CallbackQuery):
    """Handle main menu callback - show main menu"""
    has_access, user = await check_user_access(callback_query)
    if not has_access:
        return
    
    menu_text = (
        f"🏠 *Main Menu*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Welcome back, {user.username}!\n\n"
        f"Choose an option below:\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    await BotResponseHandler.handle_callback_response(
        callback_query,
        menu_text,
        BotUIComponents.get_main_menu_keyboard()
    )


# Enter Invite Code Handler
@unified_callback_router.callback_query(F.data == "enter_invite_code")
async def enter_invite_code_callback(callback_query: CallbackQuery, state: FSMContext):
    """Handle enter invitation code callback"""
    await callback_query.answer()
    
    # Import UserStates from commands
    from app.bot.handlers.commands import UserStates
    
    await state.set_state(UserStates.waiting_for_invite_code)
    await callback_query.message.edit_text(
        "📝 *Enter Your Invitation Code*\n\n"
        "Please send me your invitation code by typing it directly.\n"
        "Example: `ABC123` or `MYCODE456`\n\n"
        "⚠️ Make sure to type the code exactly as provided.",
        parse_mode="Markdown"
    )


# Withdraw Handler (placeholder - needs implementation)
@unified_callback_router.callback_query(F.data == "withdraw")
async def withdraw_callback(callback_query: CallbackQuery):
    """Handle withdraw callback - same as /withdraw command"""
    has_access, user = await check_user_access(callback_query)
    if not has_access:
        return
    
    try:
        async with async_session() as session:
            # Get user's wallet
            wallet = await get_wallet_for_user(session, user.id)
            if not wallet:
                wallet = await create_wallet_for_user(session, user.id)
            
            # Check if user has sufficient WINNING balance (only winning balance can be withdrawn)
            winning_balance = wallet.winning_balance
            if winning_balance <= 0:
                await BotResponseHandler.handle_callback_response(
                    callback_query,
                    "❌ Insufficient winning balance for withdrawal.\n\n"
                    "You can only withdraw from your winning balance.\n"
                    "Win contests to earn withdrawable funds!",
                    InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏏 Join Contests", callback_data="contests")],
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            # Show withdrawal amount options (only from winning balance)
            withdraw_text = (
                f"💸 *Withdrawal Request*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏆 *Winning Balance (Withdrawable):* `{winning_balance} {settings.currency}`\n"
                f"💳 *Deposit Balance:* `{wallet.deposit_balance} {settings.currency}` (Not withdrawable)\n"
                f"🎁 *Bonus Balance:* `{wallet.bonus_balance} {settings.currency}` (Not withdrawable)\n\n"
                f"ℹ️ *Note:* Only winning balance can be withdrawn.\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 *Choose withdrawal amount:*"
            )
            
            # Create amount selection keyboard (same as /withdraw command)
            keyboard_buttons = []
            
            # Quick amount options - show all buttons, disable if insufficient winning balance
            quick_amounts = [10, 25, 50, 100]
            for amount in quick_amounts:
                if amount <= winning_balance:
                    # Show as clickable button
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            text=f"${amount} {settings.currency}",
                            callback_data=f"withdraw_amount:{amount}"
                        )
                    ])
                else:
                    # Show as disabled button (grayed out)
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            text=f"${amount} {settings.currency} (Insufficient)",
                            callback_data="withdraw_insufficient"
                        )
                    ])
            
            # Custom amount option
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="💰 Custom Amount",
                    callback_data="withdraw_custom_amount"
                )
            ])
            
            # Back to menu
            keyboard_buttons.append([
                InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await BotResponseHandler.handle_callback_response(callback_query, withdraw_text, keyboard)
            
    except Exception as e:
        logger.error(f"Error in withdraw callback: {e}")
        await BotResponseHandler.handle_callback_response(
            callback_query,
            "❌ Sorry, there was an error processing your withdrawal request.\n\n"
            "Please try again or contact support if the issue persists.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Try Again", callback_data="withdraw")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")],
                [InlineKeyboardButton(text="🆘 Contact Support", callback_data="support")]
            ])
        )
