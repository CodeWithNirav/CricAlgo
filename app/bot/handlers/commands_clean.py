"""
User command handlers for Telegram bot
"""

import logging
from typing import Optional
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.core.config import settings
from app.db.session import async_session
from app.repos.user_repo import get_user_by_telegram_id, create_user, save_chat_id
from app.repos.wallet_repo import get_wallet_for_user, create_wallet_for_user
from app.repos.contest_repo import get_contests
from app.repos.contest_entry_repo import get_contest_entries
from app.repos.invite_code_repo import validate_invite_code, validate_and_use_code
from app.repos.deposit_repo import generate_deposit_reference, get_deposit_address_for_user, subscribe_to_deposit_notifications
# Removed old withdrawal_repo imports - now using transaction-based approach
from app.models.enums import UserStatus

logger = logging.getLogger(__name__)

# Create router for user commands
user_router = Router()

# States for user interactions
class UserStates(StatesGroup):
    waiting_for_deposit_amount = State()
    waiting_for_deposit_tx_hash = State()
    waiting_for_withdrawal_amount = State()
    waiting_for_withdrawal_address = State()
    waiting_for_invite_code = State()


async def check_invitation_code_access(telegram_id: int, message: Message = None) -> tuple[bool, str]:
    """
    Check if user has valid invitation code access.
    Returns (has_access, error_message)
    """
    try:
        async with async_session() as session:
            # Check if user exists
            user = await get_user_by_telegram_id(session, telegram_id)
            
            if not user:
                # User doesn't exist - they need invitation code
                return False, "You need a valid invitation code to access CricAlgo. Please use /start with your invitation code."
            
            # User exists - they have access
            return True, ""
            
    except Exception as e:
        logger.error(f"Error checking invitation code access: {e}")
        return False, "Error checking access. Please try again."


async def require_invitation_code(message: Message):
    """
    Show invitation code requirement message
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Enter Invitation Code", callback_data="enter_invite_code")],
        [InlineKeyboardButton(text="🆘 Contact Support", callback_data="support")]
    ])
    
    await message.answer(
        "🔐 *Access Restricted*\n\n"
        "You need a valid invitation code to access CricAlgo features.\n"
        "Please contact an admin or use an invitation link to get started.\n\n"
        "If you have an invitation code, please use:\n"
        "`/start YOUR_CODE`",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def handle_user_start(telegram_id: int, username: str, chat_id: int, invite_code: str = None, message: Message = None):
    """Handle user start logic - can be called from message or callback"""
    try:
        async with async_session() as session:
            # Check if user exists
            user = await get_user_by_telegram_id(session, telegram_id)
            
            # Save chat ID for notifications
            if user:
                await save_chat_id(session, user.id, str(chat_id))
            
            if not user:
                # NEW USERS MUST HAVE INVITATION CODE
                if not invite_code:
                    # This should not happen in the new flow, but handle gracefully
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📝 Enter Invitation Code", callback_data="enter_invite_code")]
                    ])
                    await message.answer(
                        "🔐 *Access Restricted*\n\n"
                        "You need a valid invitation code to access CricAlgo.\n"
                        "Please contact an admin or use an invitation link to get started.",
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                    return
                
                # Validate invitation code before creating user
                is_valid, msg = await validate_invite_code(session, invite_code)
                if not is_valid:
                    # Show error with retry options
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Try Again", callback_data="enter_invite_code")]
                    ])
                    await message.answer(
                        f"❌ *Invalid Invitation Code*\n\n{msg}\n\n"
                        "Please check your invitation code and try again.",
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                    return
                
                # Create new user only after valid invitation code
                user = await create_user(
                    session=session,
                    telegram_id=telegram_id,
                    username=username,
                    status=UserStatus.ACTIVE
                )
                
                # Create wallet for user
                wallet = await create_wallet_for_user(session, user.id)
                
                # Save chat ID for notifications
                await save_chat_id(session, user.id, str(chat_id))
                
                # Apply invitation code bonus and mark code as used
                from decimal import Decimal
                bonus_amount = Decimal("5.00")
                wallet.bonus_balance += bonus_amount
                
                # Mark the invitation code as used
                await validate_and_use_code(session, invite_code, str(user.id))
                await session.commit()
                bonus_text = f"\n🎁 Bonus: You received {bonus_amount} {settings.currency} bonus for using invite code!"
                
                welcome_text = (
                    f"🎉 *Welcome to CricAlgo!* 🏏\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👋 Hello *{user.username}*! Your account has been created successfully.\n\n"
                    f"🚀 *Quick Start:*\n"
                    f"💰 Use /balance to check your wallet\n"
                    f"🏏 Use /contests to see available contests\n"
                    f"❓ Use /help for more commands\n\n"
                    f"{bonus_text}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💡 *Tip:* Use the menu below for easy navigation!"
                )
            else:
                welcome_text = (
                    f"👋 *Welcome back to CricAlgo!* 🏏\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"Hello *{user.username}*!\n\n"
                    f"🚀 *Quick Actions:*\n"
                    f"💰 Use /balance to check your wallet\n"
                    f"🏏 Use /contests to see available contests\n"
                    f"❓ Use /help for more commands\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💡 *Tip:* Use the menu below for easy navigation!"
                )
            
            # Add main menu keyboard
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Balance", callback_data="balance")],
                [InlineKeyboardButton(text="💳 Deposit", callback_data="deposit")],
                [InlineKeyboardButton(text="🏏 Matches", callback_data="matches")],
                [InlineKeyboardButton(text="📊 My Contests", callback_data="my_contests")],
                [InlineKeyboardButton(text="💸 Withdraw", callback_data="withdraw")],
                [InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")],
                [InlineKeyboardButton(text="🆘 Support", callback_data="support")]
            ])
            
            if message:
                await message.answer(welcome_text, reply_markup=keyboard, parse_mode="Markdown")
            return welcome_text, keyboard
            
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        error_text = (
            "❌ Sorry, there was an error starting your account.\n\n"
            "Please try again or contact support if the issue persists."
        )
        error_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Try Again", callback_data="start_without_code")],
            [InlineKeyboardButton(text="🆘 Contact Support", callback_data="support")]
        ])
        if message:
            await message.answer(error_text, reply_markup=error_keyboard)
        return error_text, error_keyboard


@user_router.message(Command("start"))
async def start_command(message: Message):
    """Handle /start command - always ask for invitation code interactively"""
    # Check if user already exists
    try:
        async with async_session() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            
            if user:
                # User exists - show welcome back message
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")],
                    [InlineKeyboardButton(text="💰 Balance", callback_data="balance")],
                    [InlineKeyboardButton(text="🏏 Matches", callback_data="matches")]
                ])
                
                await message.answer(
                    f"🎉 *Welcome back to CricAlgo!* 🏏\n\n"
                    f"Hello *{user.username}*! You're already registered.\n\n"
                    f"Use the menu below to access your account:",
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                return
            
            # User doesn't exist - ask for invitation code
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Enter Invitation Code", callback_data="enter_invite_code")],
                [InlineKeyboardButton(text="🆘 Contact Support", callback_data="support")]
            ])
            
            await message.answer(
                "🔐 *Welcome to CricAlgo!* 🏏\n\n"
                "To get started, you need a valid invitation code.\n"
                "Please contact an admin or use an invitation link.\n\n"
                "If you have an invitation code, click the button below:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await message.answer(
            "❌ Sorry, there was an error. Please try again or contact support.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🆘 Contact Support", callback_data="support")]
            ])
        )


@user_router.message(Command("balance"))
async def balance_command(message: Message):
    """Handle /balance command - show user's wallet balance"""
    # Check invitation code access first
    has_access, error_msg = await check_invitation_code_access(message.from_user.id, message)
    if not has_access:
        await require_invitation_code(message)
        return
    
    try:
        async with async_session() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            
            if not user:
                await message.answer("Please use /start first to register your account.")
                return
            
            # Save chat ID for notifications
            await save_chat_id(session, user.id, str(message.chat.id))
            
            wallet = await get_wallet_for_user(session, user.id)
            
            if not wallet:
                # Create wallet if it doesn't exist
                wallet = await create_wallet_for_user(session, user.id)
            
            total_balance = wallet.deposit_balance + wallet.winning_balance + wallet.bonus_balance
            balance_text = (
                f"💰 *Your Wallet Balance*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💳 *Deposit Balance:* `{wallet.deposit_balance} {settings.currency}`\n"
                f"🏆 *Winning Balance:* `{wallet.winning_balance} {settings.currency}`\n"
                f"🎁 *Bonus Balance:* `{wallet.bonus_balance} {settings.currency}`\n"
                f"🔒 *Held Balance:* `{wallet.held_balance} {settings.currency}`\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 *Total Balance:* `{total_balance} {settings.currency}`\n\n"
                f"💡 *Tip:* Use the buttons below to manage your funds!\n"
                f"🔒 *Held Balance:* Amount pending withdrawal approval"
            )
            
            # Add deposit button
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Deposit", callback_data="deposit")]
            ])
            
            await message.answer(balance_text, reply_markup=keyboard, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Error in balance command: {e}")
        await message.answer(
            "❌ Sorry, there was an error retrieving your balance.\n\n"
            "Please try again or contact support if the issue persists.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Try Again", callback_data="balance")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")],
                [InlineKeyboardButton(text="🆘 Contact Support", callback_data="support")]
            ])
        )


@user_router.message(Command("deposit"))
async def deposit_command(message: Message, state: FSMContext):
    """Handle /deposit command - show deposit instructions and start manual flow"""
    # Check invitation code access first
    has_access, error_msg = await check_invitation_code_access(message.from_user.id, message)
    if not has_access:
        await require_invitation_code(message)
        return
    
    try:
        async with async_session() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            
            if not user:
                await message.answer("Please use /start first to register your account.")
                return
            
            # Get user-specific deposit information
            deposit_address = await get_deposit_address_for_user(session, user.id)
            deposit_reference = await generate_deposit_reference(session, user.id)
            
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
            
            # Add manual deposit flow buttons
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ I Sent USDT", callback_data="submit_deposit_tx")],
                [InlineKeyboardButton(text="💰 Check Balance", callback_data="balance")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await message.answer(deposit_text, reply_markup=keyboard, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Error in deposit command: {e}")
        await message.answer(
            "❌ Sorry, there was an error retrieving deposit information.\n\n"
            "Please try again or contact support if the issue persists.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Try Again", callback_data="deposit")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")],
                [InlineKeyboardButton(text="🆘 Contact Support", callback_data="support")]
            ])
        )


@user_router.message(Command("contests"))
async def contests_command(message: Message):
    """Handle /contests command - show available contests"""
    # Check invitation code access first
    has_access, error_msg = await check_invitation_code_access(message.from_user.id, message)
    if not has_access:
        await require_invitation_code(message)
        return
    
    try:
        async with async_session() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            
            if not user:
                await message.answer("Please use /start first to register your account.")
                return
            
            # Save chat ID for notifications
            await save_chat_id(session, user.id, str(message.chat.id))
            
            # Get open contests, filtering out filled and user-joined contests
            contests = await get_contests(session, limit=10, status="open", user_id=str(user.id))
            
            if not contests:
                await message.answer("No contests available at the moment. Check back later!")
                return
            
            contests_text = "🏏 *Available Contests*\n\n"
            keyboard_buttons = []
            
            for contest in contests:
                # Get current entry count
                from app.repos.contest_entry_repo import get_contest_entries
                current_entries = await get_contest_entries(session, contest.id)
                entry_count = len(current_entries)
                
                contests_text += (
                    f"🎯 *{contest.title}*\n"
                    f"💰 Entry Fee: `{contest.entry_fee} {contest.currency}`\n"
                    f"👥 Players: `{entry_count}/{contest.max_players or '∞'}`\n"
                    f"📅 Status: *{contest.status.title()}*\n\n"
                )
                
                # Add buttons for each contest
                contest_buttons = []
                
                # Join button (only if contest is open and not full)
                if contest.status == "open" and (not contest.max_players or entry_count < contest.max_players):
                    contest_buttons.append(
                        InlineKeyboardButton(
                            text="🎯 Join",
                            callback_data=f"join_contest:{contest.id}"
                        )
                    )
                
                # View details button
                contest_buttons.append(
                    InlineKeyboardButton(
                        text="📊 Details",
                        callback_data=f"contest_details:{contest.id}"
                    )
                )
                
                keyboard_buttons.append(contest_buttons)
            
            # Add main menu button
            keyboard_buttons.append([
                InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await message.answer(contests_text, reply_markup=keyboard, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Error in contests command: {e}")
        await message.answer(
            "❌ Sorry, there was an error retrieving contests.\n\n"
            "Please try again or contact support if the issue persists.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Try Again", callback_data="matches")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")],
                [InlineKeyboardButton(text="🆘 Contact Support", callback_data="support")]
            ])
        )


@user_router.message(Command("withdraw"))
async def withdraw_command(message: Message, state: FSMContext):
    """Handle /withdraw command - start withdrawal process"""
    # Check invitation code access first
    has_access, error_msg = await check_invitation_code_access(message.from_user.id, message)
    if not has_access:
        await require_invitation_code(message)
        return
    
    try:
        async with async_session() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            
            if not user:
                await message.answer("Please use /start first to register your account.")
                return
            
            # Save chat ID for notifications
            await save_chat_id(session, user.id, str(message.chat.id))
            
            # Get user's wallet
            wallet = await get_wallet_for_user(session, user.id)
            if not wallet:
                wallet = await create_wallet_for_user(session, user.id)
            
            # Check if user has sufficient balance
            total_balance = wallet.deposit_balance + wallet.winning_balance + wallet.bonus_balance
            if total_balance <= 0:
                await message.answer(
                    "❌ Insufficient balance for withdrawal.\n\n"
                    "You need to deposit funds first before you can withdraw.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Deposit", callback_data="deposit")],
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            # Show withdrawal amount options
            withdraw_text = (
                f"💸 *Withdrawal Request*\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 *Available Balance:* `{total_balance} {settings.currency}`\n"
                f"💳 *Deposit Balance:* `{wallet.deposit_balance} {settings.currency}`\n"
                f"🏆 *Winning Balance:* `{wallet.winning_balance} {settings.currency}`\n"
                f"🎁 *Bonus Balance:* `{wallet.bonus_balance} {settings.currency}`\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 *Choose withdrawal amount:*"
            )
            
            # Create amount selection keyboard
            keyboard_buttons = []
            
            # Quick amount options
            quick_amounts = [10, 25, 50, 100]
            for amount in quick_amounts:
                if amount <= total_balance:
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            text=f"${amount} {settings.currency}",
                            callback_data=f"withdraw_amount:{amount}"
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
            
            await message.answer(withdraw_text, reply_markup=keyboard, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Error in withdraw command: {e}")
        await message.answer(
            "❌ Sorry, there was an error processing your withdrawal request.\n\n"
            "Please try again or contact support if the issue persists.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Try Again", callback_data="withdraw")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")],
                [InlineKeyboardButton(text="🆘 Contact Support", callback_data="support")]
            ])
        )


@user_router.message(Command("menu"))
async def menu_command(message: Message):
    """Handle /menu command - show main menu"""
    # Check invitation code access first
    has_access, error_msg = await check_invitation_code_access(message.from_user.id, message)
    if not has_access:
        await require_invitation_code(message)
        return
    
    try:
        async with async_session() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            
            if not user:
                await message.answer("Please use /start first to register your account.")
                return
            
            # Show main menu
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Balance", callback_data="balance")],
                [InlineKeyboardButton(text="💳 Deposit", callback_data="deposit")],
                [InlineKeyboardButton(text="🏏 Matches", callback_data="matches")],
                [InlineKeyboardButton(text="📊 My Contests", callback_data="my_contests")],
                [InlineKeyboardButton(text="💸 Withdraw", callback_data="withdraw")],
                [InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")],
                [InlineKeyboardButton(text="🆘 Support", callback_data="support")]
            ])
            
            await message.answer("🏠 *Main Menu*\n\nChoose an option:", reply_markup=keyboard, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Error in menu command: {e}")
        await message.answer(
            "❌ Sorry, there was an error loading the menu.\n\n"
            "Please try again or contact support if the issue persists.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Try Again", callback_data="main_menu")],
                [InlineKeyboardButton(text="🆘 Contact Support", callback_data="support")]
            ])
        )


@user_router.message(Command("help"))
async def help_command(message: Message):
    """Handle /help command - show available commands"""
    # Check invitation code access first
    has_access, error_msg = await check_invitation_code_access(message.from_user.id, message)
    if not has_access:
        await require_invitation_code(message)
        return
    help_text = (
        "🤖 *CricAlgo Bot Commands*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 *Main Commands:*\n"
        "`/start [code]` - Register or login (optional invite code)\n"
        "`/menu` - Show main menu\n"
        "`/balance` - Check your wallet balance\n"
        "`/deposit` - Get deposit instructions\n"
        "`/contests` - View available contests\n"
        "`/withdraw` - Request withdrawal\n"
        "`/help` - Show this help message\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Pro Tips:*\n"
        "• Use inline buttons for quick actions\n"
        "• Check your balance before joining contests\n"
        "• Contact support if you need help\n"
        "• Use /menu for easy navigation\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 *Ready to start?* Use the buttons below!"
    )
    
    # Add help menu keyboard
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")],
        [InlineKeyboardButton(text="💰 Check Balance", callback_data="balance")],
        [InlineKeyboardButton(text="🏏 View Contests", callback_data="matches")]
    ])
    
    await message.answer(help_text, reply_markup=keyboard, parse_mode="Markdown")
