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
                [InlineKeyboardButton(text="🏏 Contests", callback_data="contests")],
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
                    [InlineKeyboardButton(text="🏏 Contests", callback_data="contests")]
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
            
            # Get open contests
            contests = await get_contests(session, limit=10, status="open")
            
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
                [InlineKeyboardButton(text="🔄 Try Again", callback_data="contests")],
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
                [InlineKeyboardButton(text="🏏 Contests", callback_data="contests")],
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
        [InlineKeyboardButton(text="🏏 View Contests", callback_data="contests")]
    ])
    
    await message.answer(help_text, reply_markup=keyboard, parse_mode="Markdown")


@user_router.callback_query(F.data == "balance")
async def balance_callback(callback_query):
    """Handle balance callback"""
    await callback_query.answer()
    
    # Check invitation code access first
    has_access, error_msg = await check_invitation_code_access(callback_query.from_user.id)
    if not has_access:
        await require_invitation_code(callback_query.message)
        return
    
    # Get balance directly without creating fake message
    try:
        async with async_session() as session:
            # Get user
            user = await get_user_by_telegram_id(session, callback_query.from_user.id)
            if not user:
                await callback_query.message.answer("❌ User not found. Please use /start first.")
                return
            
            # Get wallet
            wallet = await get_wallet_for_user(session, user.id)
            if not wallet:
                await callback_query.message.answer("❌ Wallet not found. Please contact support.")
                return
            
            # Format balance text
            balance_text = f"💰 **Your Wallet Balance**\n\n"
            balance_text += f"💳 **Deposit Balance:** {wallet.deposit_balance} USDT\n"
            balance_text += f"🏆 **Winning Balance:** {wallet.winning_balance} USDT\n"
            balance_text += f"🎁 **Bonus Balance:** {wallet.bonus_balance} USDT\n\n"
            balance_text += f"💎 **Total Balance:** {wallet.deposit_balance + wallet.winning_balance + wallet.bonus_balance} USDT"
            
            # Create keyboard
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Deposit", callback_data="deposit")],
                [InlineKeyboardButton(text="💸 Withdraw", callback_data="withdraw")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await callback_query.message.edit_text(
                balance_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Error in balance callback: {e}")
        await callback_query.message.answer("❌ Error loading balance. Please try again.")


@user_router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback_query):
    """Handle main menu callback"""
    await callback_query.answer()
    
    # Check invitation code access first
    has_access, error_msg = await check_invitation_code_access(callback_query.from_user.id)
    if not has_access:
        await require_invitation_code(callback_query.message)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Balance", callback_data="balance")],
        [InlineKeyboardButton(text="💳 Deposit", callback_data="deposit")],
        [InlineKeyboardButton(text="🏏 Contests", callback_data="contests")],
        [InlineKeyboardButton(text="📊 My Contests", callback_data="my_contests")],
        [InlineKeyboardButton(text="💸 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton(text="🆘 Support", callback_data="support")]
    ])
    
    await callback_query.message.edit_text(
        "🏠 *Main Menu*\n\nChoose an option:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


@user_router.callback_query(F.data == "deposit")
async def deposit_callback(callback_query):
    """Handle deposit callback"""
    await callback_query.answer()
    
    # Check invitation code access first
    has_access, error_msg = await check_invitation_code_access(callback_query.from_user.id)
    if not has_access:
        await require_invitation_code(callback_query.message)
        return
    
    # Handle deposit directly without creating fake message
    try:
        async with async_session() as session:
            # Get user
            user = await get_user_by_telegram_id(session, callback_query.from_user.id)
            if not user:
                await callback_query.message.answer("❌ User not found. Please use /start first.")
                return
            
            # Get or create wallet
            wallet = await get_wallet_for_user(session, user.id)
            if not wallet:
                wallet = await create_wallet_for_user(session, user.id)
            
            # Get deposit address
            deposit_address = await get_deposit_address_for_user(session, user.id)
            if not deposit_address:
                await callback_query.message.answer("❌ Error generating deposit address. Please try again.")
                return
            
            # Format deposit text
            deposit_text = f"💳 **Deposit USDT**\n\n"
            deposit_text += f"📝 **Your Deposit Address:**\n`{deposit_address}`\n\n"
            deposit_text += f"⚠️ **Important:**\n"
            deposit_text += f"• Send only USDT to this address\n"
            deposit_text += f"• Minimum deposit: No minimum\n"
            deposit_text += f"• Network: BEP20 (BSC)\n"
            deposit_text += f"• Deposits are processed automatically\n\n"
            deposit_text += f"💡 **Tip:** Copy the address above and send USDT from your wallet."
            
            # Create keyboard
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Refresh Balance", callback_data="balance")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await callback_query.message.edit_text(
                deposit_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Error in deposit callback: {e}")
        await callback_query.message.answer("❌ Error loading deposit info. Please try again.")


@user_router.callback_query(F.data == "contests")
async def contests_callback(callback_query):
    """Handle contests callback"""
    await callback_query.answer()
    
    # Check invitation code access first
    has_access, error_msg = await check_invitation_code_access(callback_query.from_user.id)
    if not has_access:
        await require_invitation_code(callback_query.message)
        return
    
    # Get contests directly without creating fake message
    try:
        async with async_session() as session:
            # Get user
            user = await get_user_by_telegram_id(session, callback_query.from_user.id)
            if not user:
                await callback_query.message.answer("❌ User not found. Please use /start first.")
                return
            
            # Get open contests
            contests = await get_contests(session, limit=10, status='open')
            
            if not contests:
                contests_text = "🎯 **No contests available at the moment.**\n\nCheck back later for new contests!"
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                ])
            else:
                contests_text = "🎯 **Available Contests:**\n\n"
                keyboard_buttons = []
                
                for contest in contests:
                    # Get current entries count
                    entries = await get_contest_entries(session, contest.id, limit=100)
                    current_entries = len(entries)
                    
                    contests_text += f"🏆 **{contest.title}**\n"
                    contests_text += f"💰 Entry Fee: {contest.entry_fee} {contest.currency}\n"
                    contests_text += f"👥 Players: {current_entries}/{contest.max_players}\n"
                    contests_text += f"🎁 Prize: {contest.prize_structure}\n\n"
                    
                    # Add join button if not at capacity
                    if current_entries < contest.max_players:
                        keyboard_buttons.append([
                            InlineKeyboardButton(
                                text=f"Join {contest.title}",
                                callback_data=f"join_contest:{contest.id}"
                            )
                        ])
                
                # Add main menu button
                keyboard_buttons.append([
                    InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")
                ])
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await callback_query.message.edit_text(
                contests_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Error in contests callback: {e}")
        await callback_query.message.answer("❌ Error loading contests. Please try again.")


@user_router.callback_query(F.data == "enter_invite_code")
async def enter_invite_code_callback(callback_query, state: FSMContext):
    """Handle enter invitation code callback"""
    await callback_query.answer()
    
    await state.set_state(UserStates.waiting_for_invite_code)
    await callback_query.message.edit_text(
        "📝 *Enter Your Invitation Code*\n\n"
        "Please send me your invitation code by typing it directly.\n"
        "Example: `ABC123` or `MYCODE456`\n\n"
        "⚠️ Make sure to type the code exactly as provided.",
        parse_mode="Markdown"
    )


@user_router.callback_query(F.data == "submit_deposit_tx")
async def submit_deposit_tx_callback(callback_query, state: FSMContext):
    """Handle deposit transaction hash submission"""
    logger.info(f"User clicked submit_deposit_tx: {callback_query.from_user.id}")
    await callback_query.answer()
    
    try:
        async with async_session() as session:
            user = await get_user_by_telegram_id(session, callback_query.from_user.id)
            
            if not user:
                await callback_query.message.edit_text("Please use /start first to register your account.")
                return
            
            # Set state to wait for transaction hash
            await state.set_state(UserStates.waiting_for_deposit_tx_hash)
            
            await callback_query.message.edit_text(
                "📝 **Submit Your Transaction Hash**\n\n"
                "Please send your transaction hash (TX ID) from your wallet.\n\n"
                "**Example:** `0x1234567890abcdef1234567890abcdef12345678`\n\n"
                "⚠️ **Important:**\n"
                "• Make sure you sent USDT to the correct address\n"
                "• Use the exact transaction hash from your wallet\n"
                "• Your deposit will be manually verified by our team\n\n"
                "Type your transaction hash now:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Cancel", callback_data="main_menu")]
                ]),
                parse_mode="Markdown"
            )
                
    except Exception as e:
        logger.error(f"Error in deposit transaction submission: {e}")
        await callback_query.message.edit_text("Sorry, there was an error. Please try again later.")


@user_router.callback_query(F.data == "subscribe_deposit_notifications")
async def subscribe_deposit_notifications_callback(callback_query):
    """Handle deposit notification subscription"""
    await callback_query.answer()
    
    try:
        async with async_session() as session:
            user = await get_user_by_telegram_id(session, callback_query.from_user.id)
            
            if not user:
                await callback_query.message.edit_text("Please use /start first to register your account.")
                return
            
            # Subscribe to deposit notifications
            success = await subscribe_to_deposit_notifications(
                session, 
                user.id, 
                str(callback_query.message.chat.id)
            )
            
            if success:
                await callback_query.message.edit_text(
                    "✅ You will now receive notifications when your deposits are confirmed!\n\n"
                    "You can check your balance anytime using /balance or the menu below.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💰 Check Balance", callback_data="balance")],
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
            else:
                await callback_query.message.edit_text(
                    "❌ Failed to subscribe to notifications. Please try again later.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Try Again", callback_data="subscribe_deposit_notifications")],
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                
    except Exception as e:
        logger.error(f"Error in deposit notification subscription: {e}")
        await callback_query.message.edit_text("Sorry, there was an error. Please try again later.")


@user_router.callback_query(F.data.startswith("withdraw_amount:"))
async def withdraw_amount_callback(callback_query, state: FSMContext):
    """Handle withdrawal amount selection"""
    await callback_query.answer()
    
    try:
        amount = float(callback_query.data.split(":", 1)[1])
        
        # Store amount in state
        await state.update_data(withdrawal_amount=amount)
        await state.set_state(UserStates.waiting_for_withdrawal_address)
        
        await callback_query.message.edit_text(
            f"💸 Withdrawal Amount: {amount} {settings.currency}\n\n"
            f"Please enter the destination address where you want to receive the funds:\n\n"
            f"⚠️ Make sure the address is correct - withdrawals cannot be reversed!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Cancel", callback_data="withdraw_cancel")]
            ])
        )
        
    except Exception as e:
        logger.error(f"Error in withdraw amount callback: {e}")
        await callback_query.message.edit_text("Sorry, there was an error. Please try again.")


@user_router.callback_query(F.data == "withdraw_custom_amount")
async def withdraw_custom_amount_callback(callback_query, state: FSMContext):
    """Handle custom withdrawal amount"""
    await callback_query.answer()
    
    await state.set_state(UserStates.waiting_for_withdrawal_amount)
    
    await callback_query.message.edit_text(
        f"💰 Custom Withdrawal Amount\n\n"
        f"Please enter the amount you want to withdraw (in {settings.currency}):\n\n"
        f"Example: 25.50",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="withdraw_cancel")]
        ])
    )


@user_router.message(UserStates.waiting_for_withdrawal_amount)
async def process_withdrawal_amount(message: Message, state: FSMContext):
    """Process custom withdrawal amount input"""
    try:
        amount = float(message.text)
        
        if amount <= 0:
            await message.answer("❌ Amount must be greater than 0. Please try again:")
            return
        
        # Convert to Decimal and store in state
        from decimal import Decimal
        amount_decimal = Decimal(str(amount))
        await state.update_data(withdrawal_amount=str(amount_decimal))
        await state.set_state(UserStates.waiting_for_withdrawal_address)
        
        await message.answer(
            f"💸 Withdrawal Amount: {amount_decimal} {settings.currency}\n\n"
            f"Please enter the destination address where you want to receive the funds:\n\n"
            f"⚠️ Make sure the address is correct - withdrawals cannot be reversed!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Cancel", callback_data="withdraw_cancel")]
            ])
        )
        
    except ValueError:
        await message.answer("❌ Invalid amount. Please enter a valid number:")
    except Exception as e:
        logger.error(f"Error processing withdrawal amount: {str(e)}")
        await message.answer("Sorry, there was an error. Please try again.")


@user_router.message(UserStates.waiting_for_deposit_tx_hash)
async def process_deposit_tx_hash(message: Message, state: FSMContext):
    """Process deposit transaction hash input"""
    logger.info(f"Processing deposit tx hash: {message.text}")
    try:
        tx_hash = message.text.strip()
        
        # Basic validation for transaction hash
        if not tx_hash.startswith("0x") or len(tx_hash) < 10:
            await message.answer("❌ Invalid transaction hash format. Please enter a valid BSC transaction hash (starts with 0x):")
            return
        
        # Create deposit request for manual approval
        async with async_session() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            
            if not user:
                await message.answer("❌ User not found. Please use /start first.")
                await state.clear()
                return
            
            # Create manual deposit transaction
            from app.repos.deposit_repo import create_deposit_transaction
            from decimal import Decimal
            
            # For manual deposits, we'll set amount to 0 initially and let admin set the actual amount
            transaction = await create_deposit_transaction(
                session=session,
                user_id=user.id,
                amount=0.0,  # Will be updated by admin
                tx_hash=tx_hash,
                deposit_reference=f"MANUAL_{user.telegram_id}",
                confirmations=0
            )
            
            # Update transaction metadata to mark as manual approval needed
            from sqlalchemy import text
            
            # Use direct SQL update to ensure metadata is properly saved
            import json
            new_metadata = {
                "status": "pending_approval",
                "manual_approval": True,
                "telegram_id": str(user.telegram_id),
                "username": user.username or "Unknown"
            }
            
            # Get current metadata and merge with new metadata
            current_metadata = transaction.tx_metadata or {}
            current_metadata.update(new_metadata)
            
            # Update the transaction directly
            transaction.tx_metadata = current_metadata
            await session.commit()
            
            await message.answer(
                f"✅ **Deposit Request Submitted!**\n\n"
                f"📝 **Transaction Hash:** `{tx_hash}`\n"
                f"👤 **User:** @{user.username or 'Unknown'}\n"
                f"🆔 **User ID:** {user.telegram_id}\n\n"
                f"⏳ **Status:** Pending Manual Approval\n\n"
                f"Our team will verify your transaction and approve your deposit.\n"
                f"You'll receive a notification once it's approved!\n\n"
                f"💡 **Tip:** You can check your balance anytime with /balance",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💰 Check Balance", callback_data="balance")],
                    [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                ]),
                parse_mode="Markdown"
            )
            
            await state.clear()
            
    except Exception as e:
        logger.error(f"Error processing deposit transaction hash: {e}")
        await message.answer(
            "❌ Sorry, there was an error processing your transaction hash.\n\n"
            "Please try again or contact support if the issue persists.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Try Again", callback_data="submit_deposit_tx")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
        )
        await state.clear()


@user_router.message(UserStates.waiting_for_withdrawal_address)
async def process_withdrawal_address(message: Message, state: FSMContext):
    """Process withdrawal address input"""
    logger.info(f"Processing withdrawal address: {message.text}")
    logger.info(f"Function process_withdrawal_address started")
    try:
        address = message.text.strip()
        logger.info(f"Address after strip: {address}")
        
        if len(address) < 10:  # Basic validation
            logger.info(f"Address too short: {len(address)}")
            await message.answer("❌ Address seems too short. Please enter a valid address:")
            return
        
        # Get amount from state
        logger.info(f"Getting amount from state")
        data = await state.get_data()
        amount_str = data.get("withdrawal_amount")
        logger.info(f"Amount from state: {amount_str}")
        
        if not amount_str:
            logger.error("No withdrawal amount found in state")
            await message.answer("❌ Error: Amount not found. Please start over.")
            await state.clear()
            return
        
        # Convert string back to Decimal
        logger.info(f"Converting amount to Decimal")
        from decimal import Decimal
        amount = Decimal(amount_str)
        logger.info(f"Amount converted to Decimal: {amount}")
        logger.info(f"About to start withdrawal processing")
        
        # Create withdrawal request with simplified approach
        try:
            async with async_session() as session:
                user = await get_user_by_telegram_id(session, message.from_user.id)
                
                if not user:
                    await message.answer("❌ User not found. Please use /start first.")
                    await state.clear()
                    return
                
                # Check winning balance (only winning balance can be withdrawn)
                logger.info(f"Getting wallet for user {user.id}")
                wallet = await get_wallet_for_user(session, user.id)
                logger.info(f"Wallet retrieved: winning_balance={wallet.winning_balance}, amount={amount}")
                
                if amount > wallet.winning_balance:
                    await message.answer(
                        f"❌ Insufficient winning balance. You have {wallet.winning_balance} {settings.currency} winning balance available for withdrawal.\n\n"
                        f"💡 Only winning balance can be withdrawn, not deposit or bonus balance.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔄 Try Again", callback_data="withdraw")],
                            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                        ])
                    )
                    await state.clear()
                    return
                
                logger.info(f"Balance check passed: amount {amount} <= winning_balance {wallet.winning_balance}")
                # Process withdrawal hold (move from winning to held balance)
                logger.info(f"About to call process_withdrawal_hold_atomic for user {user.id} with amount {amount}")
                from app.repos.wallet_repo import process_withdrawal_hold_atomic
                logger.info(f"Calling process_withdrawal_hold_atomic for user {user.id} with amount {amount}")
                success, error = await process_withdrawal_hold_atomic(
                    session=session,
                    user_id=user.id,
                    amount=amount
                )
                logger.info(f"process_withdrawal_hold_atomic result: success={success}, error={error}")
                
                if not success:
                    await message.answer(
                        f"❌ Failed to process withdrawal hold: {error}\n\nPlease try again or contact support.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔄 Try Again", callback_data="withdraw")],
                            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                        ])
                    )
                    await state.clear()
                    return
                
                # Create withdrawal transaction
                from app.repos.transaction_repo import create_transaction
                transaction = await create_transaction(
                    session=session,
                    user_id=user.id,
                    tx_type="withdrawal",
                    amount=amount,
                    currency="USDT",
                    related_entity="withdrawal_request",
                    related_id=user.id,
                    tx_metadata={
                        "withdrawal_address": address,
                        "notes": f"Withdrawal request from Telegram bot",
                        "status": "pending",
                        "amount_held": str(amount)
                    }
                )
                
                # Commit the transaction
                await session.commit()
                logger.info(f"Withdrawal transaction created successfully: {transaction.id}")
                
        except Exception as error:
            logger.error(f"Error processing withdrawal: {str(error)}")
            await message.answer(
                f"❌ Failed to process withdrawal: {str(error)}\n\nPlease try again or contact support.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Try Again", callback_data="withdraw")],
                    [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                ])
            )
            await state.clear()
            
            # Show confirmation
            await message.answer(
                f"✅ Withdrawal Request Created!\n\n"
                f"💰 Amount: {amount} {settings.currency}\n"
                f"📍 Address: {address}\n"
                f"📋 ID: {transaction.id}\n"
                f"📊 Status: Pending\n\n"
                f"Your withdrawal request has been submitted for approval. "
                f"You will be notified when it's processed.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 View Status", callback_data=f"withdrawal_status:{transaction.id}")],
                    [InlineKeyboardButton(text="❌ Cancel Request", callback_data=f"withdrawal_cancel:{transaction.id}")],
                    [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                ])
            )
            
    except Exception as e:
        logger.error(f"Error processing withdrawal address: {e}")
        await message.answer("Sorry, there was an error. Please try again.")
        await state.clear()


@user_router.message(UserStates.waiting_for_invite_code)
async def process_invite_code(message: Message, state: FSMContext):
    """Process invitation code input"""
    try:
        invite_code = message.text.strip()
        
        if not invite_code:
            await message.answer("❌ Please enter a valid invitation code.")
            return
        
        # Process the invitation code using the start handler
        await handle_user_start(
            telegram_id=message.from_user.id,
            username=message.from_user.username or f"user_{message.from_user.id}",
            chat_id=message.chat.id,
            invite_code=invite_code,
            message=message
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error processing invitation code: {e}")
        await message.answer("❌ Error processing invitation code. Please try again.")
        await state.clear()


@user_router.callback_query(F.data == "withdraw_cancel")
async def withdraw_cancel_callback(callback_query, state: FSMContext):
    """Handle withdrawal cancellation"""
    await callback_query.answer()
    
    await state.clear()
    
    await callback_query.message.edit_text(
        "❌ Withdrawal cancelled.\n\n"
        "You can start a new withdrawal anytime using /withdraw",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 New Withdrawal", callback_data="withdraw")],
            [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
        ])
    )


@user_router.callback_query(F.data.startswith("withdrawal_status:"))
async def withdrawal_status_callback(callback_query):
    """Handle withdrawal status check"""
    await callback_query.answer()
    
    try:
        transaction_id = callback_query.data.split(":", 1)[1]
        
        async with async_session() as session:
            from app.repos.transaction_repo import get_transaction_by_id
            transaction = await get_transaction_by_id(session, transaction_id)
            
            if not transaction or transaction.tx_type != "withdrawal":
                await callback_query.message.edit_text(
                    "❌ Withdrawal not found.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            # Get status from metadata
            status = transaction.tx_metadata.get("status", "pending") if transaction.tx_metadata else "pending"
            withdrawal_address = transaction.tx_metadata.get("withdrawal_address", "N/A") if transaction.tx_metadata else "N/A"
            
            status_emoji = {
                "pending": "⏳",
                "approved": "✅",
                "rejected": "❌",
                "completed": "🎉"
            }.get(status, "❓")
            
            await callback_query.message.edit_text(
                f"📊 Withdrawal Status\n\n"
                f"💰 Amount: {transaction.amount} {transaction.currency}\n"
                f"📍 Address: {withdrawal_address}\n"
                f"📋 ID: {transaction.id}\n"
                f"📊 Status: {status_emoji} {status.title()}\n\n"
                f"Status updates will be sent to you automatically.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Refresh", callback_data=f"withdrawal_status:{transaction_id}")],
                    [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                ])
            )
            
    except Exception as e:
        logger.error(f"Error checking withdrawal status: {e}")
        await callback_query.message.edit_text("Sorry, there was an error. Please try again.")


@user_router.callback_query(F.data.startswith("withdrawal_cancel:"))
async def withdrawal_cancel_request_callback(callback_query):
    """Handle withdrawal request cancellation"""
    await callback_query.answer()
    
    try:
        transaction_id = callback_query.data.split(":", 1)[1]
        
        async with async_session() as session:
            from app.repos.transaction_repo import get_transaction_by_id, update_transaction_metadata
            transaction = await get_transaction_by_id(session, transaction_id)
            
            if not transaction or transaction.tx_type != "withdrawal":
                await callback_query.message.edit_text("❌ Withdrawal not found.")
                return
            
            # Check current status
            current_status = transaction.tx_metadata.get("status", "pending") if transaction.tx_metadata else "pending"
            if current_status != "pending":
                await callback_query.message.edit_text(
                    f"❌ Cannot cancel withdrawal. Status: {current_status.title()}"
                )
                return
            
            # Update transaction metadata to cancelled
            updated_metadata = transaction.metadata.copy() if transaction.metadata else {}
            updated_metadata["status"] = "cancelled"
            await update_transaction_metadata(session, transaction_id, updated_metadata)
            await session.commit()
            
            await callback_query.message.edit_text(
                f"✅ Withdrawal Cancelled\n\n"
                f"Your withdrawal request has been cancelled successfully.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💸 New Withdrawal", callback_data="withdraw")],
                    [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                ])
            )
            
    except Exception as e:
        logger.error(f"Error cancelling withdrawal: {e}")
        await callback_query.message.edit_text("Sorry, there was an error. Please try again.")


@user_router.callback_query(F.data == "withdraw")
async def withdraw_callback(callback_query, state: FSMContext):
    """Handle withdraw callback from menu"""
    await callback_query.answer()
    
    # Check invitation code access first
    has_access, error_msg = await check_invitation_code_access(callback_query.from_user.id)
    if not has_access:
        await require_invitation_code(callback_query.message)
        return
    
    # Handle withdraw directly without creating fake message
    try:
        async with async_session() as session:
            # Get user
            user = await get_user_by_telegram_id(session, callback_query.from_user.id)
            if not user:
                await callback_query.message.answer("❌ User not found. Please use /start first.")
                return
            
            # Get wallet
            wallet = await get_wallet_for_user(session, user.id)
            if not wallet:
                await callback_query.message.answer("❌ Wallet not found. Please contact support.")
                return
            
            # Check if user has sufficient balance
            total_balance = wallet.deposit_balance + wallet.winning_balance + wallet.bonus_balance
            if total_balance <= 0:
                withdraw_text = "💸 **Withdraw Funds**\n\n"
                withdraw_text += "❌ **Insufficient Balance**\n\n"
                withdraw_text += f"💰 **Your Balance:** {total_balance} USDT\n"
                withdraw_text += f"💳 **Deposit Balance:** {wallet.deposit_balance} USDT\n"
                withdraw_text += f"🏆 **Winning Balance:** {wallet.winning_balance} USDT\n"
                withdraw_text += f"🎁 **Bonus Balance:** {wallet.bonus_balance} USDT\n\n"
                withdraw_text += "💡 **Tip:** You need to deposit funds first before you can withdraw."
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Deposit Funds", callback_data="deposit")],
                    [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                ])
            else:
                withdraw_text = "💸 **Withdraw Funds**\n\n"
                withdraw_text += f"💰 **Available Balance:** {total_balance} USDT\n"
                withdraw_text += f"💳 **Deposit Balance:** {wallet.deposit_balance} USDT\n"
                withdraw_text += f"🏆 **Winning Balance:** {wallet.winning_balance} USDT\n"
                withdraw_text += f"🎁 **Bonus Balance:** {wallet.bonus_balance} USDT\n\n"
                withdraw_text += "⚠️ **Important:**\n"
                withdraw_text += "• Minimum withdrawal: 10 USDT\n"
                withdraw_text += "• Withdrawal fee: 1 USDT\n"
                withdraw_text += "• Processing time: 1-24 hours\n\n"
                withdraw_text += "Please enter the amount you want to withdraw:"
                
                # Set state to wait for withdrawal amount
                await state.set_state(UserStates.waiting_for_withdrawal_amount)
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                ])
            
            await callback_query.message.edit_text(
                withdraw_text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Error in withdraw callback: {e}")
        await callback_query.message.answer("❌ Error loading withdraw info. Please try again.")


@user_router.callback_query(F.data == "my_contests")
async def my_contests_callback(callback_query):
    """Handle my contests callback"""
    await callback_query.answer()
    
    # Check invitation code access first
    has_access, error_msg = await check_invitation_code_access(callback_query.from_user.id)
    if not has_access:
        await require_invitation_code(callback_query.message)
        return
    
    try:
        async with async_session() as session:
            user = await get_user_by_telegram_id(session, callback_query.from_user.id)
            
            if not user:
                await callback_query.message.edit_text("Please use /start first to register your account.")
                return
            
            # Get user's contest entries
            from app.repos.contest_entry_repo import get_user_contest_entries
            entries = await get_user_contest_entries(session, user.id, limit=10)
            
            if not entries:
                await callback_query.message.edit_text(
                    "📝 You haven't joined any contests yet.\n\n"
                    "Use the Contests button to see available contests and join them!",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏏 View Contests", callback_data="contests")],
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            contests_text = "🏏 Your Contest Entries\n\n"
            
            for entry in entries:
                from app.repos.contest_repo import get_contest_by_id
                contest = await get_contest_by_id(session, entry.contest_id)
                if contest:
                    status_emoji = {
                        "open": "🟢",
                        "closed": "🔴", 
                        "settled": "🏆",
                        "cancelled": "❌"
                    }.get(contest.status, "❓")
                    
                    contests_text += (
                        f"{status_emoji} {contest.title}\n"
                        f"💰 Entry Fee: {entry.entry_fee} {contest.currency}\n"
                        f"📅 Joined: {entry.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                        f"📊 Status: {contest.status.title()}\n\n"
                    )
            
            # Add back button
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏏 View All Contests", callback_data="contests")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await callback_query.message.edit_text(contests_text, reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"Error in my contests callback: {e}")
        await callback_query.message.edit_text("Sorry, there was an error. Please try again later.")


@user_router.callback_query(F.data == "settings")
async def settings_callback(callback_query):
    """Handle settings callback"""
    await callback_query.answer()
    
    try:
        async with async_session() as session:
            user = await get_user_by_telegram_id(session, callback_query.from_user.id)
            
            if not user:
                await callback_query.message.edit_text("Please use /start first to register your account.")
                return
            
            settings_text = (
                f"⚙️ Settings\n\n"
                f"👤 Username: {user.username}\n"
                f"🆔 User ID: {user.id}\n"
                f"📊 Status: {user.status.value.title()}\n"
                f"📅 Member since: {user.created_at.strftime('%Y-%m-%d')}\n\n"
                f"🔔 Notifications: Enabled\n"
                f"💬 Language: English\n\n"
                f"Use the buttons below to manage your account:"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔔 Notification Settings", callback_data="notification_settings")],
                [InlineKeyboardButton(text="📊 View Profile", callback_data="view_profile")],
                [InlineKeyboardButton(text="❓ Help & Support", callback_data="help_support")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await callback_query.message.edit_text(settings_text, reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"Error in settings callback: {e}")
        await callback_query.message.edit_text("Sorry, there was an error. Please try again later.")
