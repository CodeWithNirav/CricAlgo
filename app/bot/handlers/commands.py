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
from app.repos.invite_code_repo import validate_and_use_code
from app.repos.deposit_repo import generate_deposit_reference, get_deposit_address_for_user, subscribe_to_deposit_notifications
from app.repos.withdrawal_repo import create_withdrawal, get_withdrawal
from app.models.enums import UserStatus

logger = logging.getLogger(__name__)

# Create router for user commands
user_router = Router()

# States for user interactions
class UserStates(StatesGroup):
    waiting_for_deposit_amount = State()
    waiting_for_withdrawal_amount = State()
    waiting_for_withdrawal_address = State()


@user_router.message(Command("start"))
async def start_command(message: Message):
    """Handle /start command - register user if not exists, optionally with invite code"""
    try:
        # Extract invite code from command if present
        invite_code = None
        if len(message.text.split()) > 1:
            invite_code = message.text.split()[1]
        
        async with async_session() as session:
            # Check if user exists
            user = await get_user_by_telegram_id(session, message.from_user.id)
            
            # Save chat ID for notifications
            if user:
                await save_chat_id(session, user.id, str(message.chat.id))
            
            if not user:
                # Create new user
                username = message.from_user.username or f"user_{message.from_user.id}"
                user = await create_user(
                    session=session,
                    telegram_id=message.from_user.id,
                    username=username,
                    status=UserStatus.ACTIVE
                )
                
                # Create wallet for user
                wallet = await create_wallet_for_user(session, user.id)
                
                # Save chat ID for notifications
                await save_chat_id(session, user.id, str(message.chat.id))
                
                # Handle invite code if provided
                bonus_text = ""
                if invite_code:
                    is_valid, msg = await validate_and_use_code(session, invite_code, str(user.id))
                    if is_valid:
                        # Credit bonus to user (e.g., 5 USDT bonus)
                        from decimal import Decimal
                        bonus_amount = Decimal("5.00")
                        wallet.bonus_balance += bonus_amount
                        await session.commit()
                        bonus_text = f"\n🎁 Bonus: You received {bonus_amount} {settings.currency} bonus for using invite code!"
                    else:
                        # Show error with retry options
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🔄 Try Again", callback_data=f"start_with_code:{invite_code}")],
                            [InlineKeyboardButton(text="➡️ Continue Without Code", callback_data="start_without_code")]
                        ])
                        await message.answer(
                            f"❌ {msg}\n\nWould you like to try again or continue without an invite code?",
                            reply_markup=keyboard
                        )
                        return
                
                welcome_text = (
                    f"Welcome to CricAlgo! 🏏\n\n"
                    f"Hello {user.username}! Your account has been created successfully.\n"
                    f"Use /balance to check your wallet balance.\n"
                    f"Use /contests to see available contests.\n"
                    f"Use /help for more commands.{bonus_text}"
                )
            else:
                welcome_text = (
                    f"Welcome back to CricAlgo! 🏏\n\n"
                    f"Hello {user.username}!\n"
                    f"Use /balance to check your wallet balance.\n"
                    f"Use /contests to see available contests.\n"
                    f"Use /help for more commands."
                )
            
            # Add main menu keyboard
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Balance", callback_data="balance")],
                [InlineKeyboardButton(text="💳 Deposit", callback_data="deposit")],
                [InlineKeyboardButton(text="🏏 Contests", callback_data="contests")],
                [InlineKeyboardButton(text="💸 Withdraw", callback_data="withdraw")],
                [InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")]
            ])
            
            await message.answer(welcome_text, reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await message.answer("Sorry, there was an error. Please try again later.")


@user_router.message(Command("balance"))
async def balance_command(message: Message):
    """Handle /balance command - show user's wallet balance"""
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
            
            balance_text = (
                f"💰 Your Wallet Balance\n\n"
                f"💳 Deposit Balance: {wallet.deposit_balance} {settings.currency}\n"
                f"🏆 Winning Balance: {wallet.winning_balance} {settings.currency}\n"
                f"🎁 Bonus Balance: {wallet.bonus_balance} {settings.currency}\n\n"
                f"💵 Total Balance: {wallet.deposit_balance + wallet.winning_balance + wallet.bonus_balance} {settings.currency}"
            )
            
            # Add deposit button
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Deposit", callback_data="deposit")]
            ])
            
            await message.answer(balance_text, reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"Error in balance command: {e}")
        await message.answer("Sorry, there was an error retrieving your balance. Please try again later.")


@user_router.message(Command("deposit"))
async def deposit_command(message: Message, state: FSMContext):
    """Handle /deposit command - show deposit instructions with per-user address"""
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
                f"💳 Deposit Instructions\n\n"
                f"To deposit funds to your CricAlgo wallet:\n\n"
                f"📍 Deposit Address:\n"
                f"`{deposit_address}`\n\n"
                f"🏷️ Deposit Reference (Memo):\n"
                f"`{deposit_reference}`\n\n"
                f"📋 Instructions:\n"
                f"1. Send USDT to the address above\n"
                f"2. Use the deposit reference as memo\n"
                f"3. Minimum deposit: 10 USDT\n"
                f"4. Network: TRC20 (Tron)\n\n"
                f"⚠️ Important: Only send USDT (TRC20) to this address!\n"
                f"Other tokens will be lost permanently.\n\n"
                f"Your balance will be updated automatically once confirmed."
            )
            
            # Add notification subscription and other buttons
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔔 Notify me when confirmed", callback_data="subscribe_deposit_notifications")],
                [InlineKeyboardButton(text="💰 Check Balance", callback_data="balance")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await message.answer(deposit_text, reply_markup=keyboard, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"Error in deposit command: {e}")
        await message.answer("Sorry, there was an error. Please try again later.")


@user_router.message(Command("contests"))
async def contests_command(message: Message):
    """Handle /contests command - show available contests"""
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
            
            contests_text = "🏏 Available Contests\n\n"
            keyboard_buttons = []
            
            for contest in contests:
                # Get current entry count
                from app.repos.contest_entry_repo import get_contest_entries
                current_entries = await get_contest_entries(session, contest.id)
                entry_count = len(current_entries)
                
                contests_text += (
                    f"🎯 {contest.title}\n"
                    f"💰 Entry Fee: {contest.entry_fee} {contest.currency}\n"
                    f"👥 Players: {entry_count}/{contest.max_players or '∞'}\n"
                    f"📅 Status: {contest.status.title()}\n\n"
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
            
            await message.answer(contests_text, reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"Error in contests command: {e}")
        await message.answer("Sorry, there was an error retrieving contests. Please try again later.")


@user_router.message(Command("withdraw"))
async def withdraw_command(message: Message, state: FSMContext):
    """Handle /withdraw command - start withdrawal process"""
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
                f"💸 Withdrawal Request\n\n"
                f"💰 Available Balance: {total_balance} {settings.currency}\n"
                f"💳 Deposit Balance: {wallet.deposit_balance} {settings.currency}\n"
                f"🏆 Winning Balance: {wallet.winning_balance} {settings.currency}\n"
                f"🎁 Bonus Balance: {wallet.bonus_balance} {settings.currency}\n\n"
                f"Choose withdrawal amount:"
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
            
            await message.answer(withdraw_text, reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"Error in withdraw command: {e}")
        await message.answer("Sorry, there was an error. Please try again later.")


@user_router.message(Command("menu"))
async def menu_command(message: Message):
    """Handle /menu command - show main menu"""
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
                [InlineKeyboardButton(text="💸 Withdraw", callback_data="withdraw")],
                [InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")]
            ])
            
            await message.answer("🏠 Main Menu\n\nChoose an option:", reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"Error in menu command: {e}")
        await message.answer("Sorry, there was an error. Please try again later.")


@user_router.message(Command("help"))
async def help_command(message: Message):
    """Handle /help command - show available commands"""
    help_text = (
        "🤖 CricAlgo Bot Commands\n\n"
        "/start [code] - Register or login to your account (optional invite code)\n"
        "/menu - Show main menu\n"
        "/balance - Check your wallet balance\n"
        "/deposit - Get deposit instructions\n"
        "/contests - View available contests\n"
        "/withdraw - Request withdrawal\n"
        "/help - Show this help message\n\n"
        "💡 Tips:\n"
        "• Use inline buttons for quick actions\n"
        "• Check your balance before joining contests\n"
        "• Contact support if you need help"
    )
    
    await message.answer(help_text)


@user_router.callback_query(F.data == "balance")
async def balance_callback(callback_query):
    """Handle balance callback"""
    await callback_query.answer()
    # Create a new message object to avoid frozen instance error
    from aiogram.types import Message
    fake_message = Message(
        message_id=callback_query.message.message_id,
        from_user=callback_query.from_user,
        chat=callback_query.message.chat,
        date=callback_query.message.date,
        content_type=callback_query.message.content_type,
        text="",
        reply_markup=callback_query.message.reply_markup
    )
    await balance_command(fake_message)


@user_router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback_query):
    """Handle main menu callback"""
    await callback_query.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Balance", callback_data="balance")],
        [InlineKeyboardButton(text="💳 Deposit", callback_data="deposit")],
        [InlineKeyboardButton(text="🏏 Contests", callback_data="contests")],
        [InlineKeyboardButton(text="💸 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton(text="⚙️ Settings", callback_data="settings")]
    ])
    
    await callback_query.message.edit_text(
        "🏠 Main Menu\n\nChoose an option:",
        reply_markup=keyboard
    )


@user_router.callback_query(F.data == "deposit")
async def deposit_callback(callback_query):
    """Handle deposit callback"""
    await callback_query.answer()
    # Create a new message object to avoid frozen instance error
    from aiogram.types import Message
    fake_message = Message(
        message_id=callback_query.message.message_id,
        from_user=callback_query.from_user,
        chat=callback_query.message.chat,
        date=callback_query.message.date,
        content_type=callback_query.message.content_type,
        text="",
        reply_markup=callback_query.message.reply_markup
    )
    await deposit_command(fake_message, None)


@user_router.callback_query(F.data == "contests")
async def contests_callback(callback_query):
    """Handle contests callback"""
    await callback_query.answer()
    # Create a new message object to avoid frozen instance error
    from aiogram.types import Message
    fake_message = Message(
        message_id=callback_query.message.message_id,
        from_user=callback_query.from_user,
        chat=callback_query.message.chat,
        date=callback_query.message.date,
        content_type=callback_query.message.content_type,
        text="",
        reply_markup=callback_query.message.reply_markup
    )
    await contests_command(fake_message)


@user_router.callback_query(F.data.startswith("start_with_code:"))
async def start_with_code_callback(callback_query):
    """Handle start with invite code retry"""
    await callback_query.answer()
    invite_code = callback_query.data.split(":", 1)[1]
    
    # Create a fake message with the invite code
    from aiogram.types import Message
    fake_message = Message(
        message_id=callback_query.message.message_id,
        from_user=callback_query.from_user,
        chat=callback_query.message.chat,
        date=callback_query.message.date,
        content_type=callback_query.message.content_type,
        text=f"/start {invite_code}",
        reply_markup=callback_query.message.reply_markup
    )
    await start_command(fake_message)


@user_router.callback_query(F.data == "start_without_code")
async def start_without_code_callback(callback_query):
    """Handle start without invite code"""
    await callback_query.answer()
    
    # Create a fake message without invite code
    from aiogram.types import Message
    fake_message = Message(
        message_id=callback_query.message.message_id,
        from_user=callback_query.from_user,
        chat=callback_query.message.chat,
        date=callback_query.message.date,
        content_type=callback_query.message.content_type,
        text="/start",
        reply_markup=callback_query.message.reply_markup
    )
    await start_command(fake_message)


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
        
        # Store amount in state
        await state.update_data(withdrawal_amount=amount)
        await state.set_state(UserStates.waiting_for_withdrawal_address)
        
        await message.answer(
            f"💸 Withdrawal Amount: {amount} {settings.currency}\n\n"
            f"Please enter the destination address where you want to receive the funds:\n\n"
            f"⚠️ Make sure the address is correct - withdrawals cannot be reversed!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Cancel", callback_data="withdraw_cancel")]
            ])
        )
        
    except ValueError:
        await message.answer("❌ Invalid amount. Please enter a valid number:")
    except Exception as e:
        logger.error(f"Error processing withdrawal amount: {e}")
        await message.answer("Sorry, there was an error. Please try again.")


@user_router.message(UserStates.waiting_for_withdrawal_address)
async def process_withdrawal_address(message: Message, state: FSMContext):
    """Process withdrawal address input"""
    try:
        address = message.text.strip()
        
        if len(address) < 10:  # Basic validation
            await message.answer("❌ Address seems too short. Please enter a valid address:")
            return
        
        # Get amount from state
        data = await state.get_data()
        amount = data.get("withdrawal_amount")
        
        if not amount:
            await message.answer("❌ Error: Amount not found. Please start over.")
            await state.clear()
            return
        
        # Create withdrawal request
        async with async_session() as session:
            user = await get_user_by_telegram_id(session, message.from_user.id)
            
            if not user:
                await message.answer("❌ User not found. Please use /start first.")
                await state.clear()
                return
            
            # Check balance again
            wallet = await get_wallet_for_user(session, user.id)
            total_balance = wallet.deposit_balance + wallet.winning_balance + wallet.bonus_balance
            
            if amount > total_balance:
                await message.answer(
                    f"❌ Insufficient balance. You have {total_balance} {settings.currency} available.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Try Again", callback_data="withdraw")],
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                await state.clear()
                return
            
            # Create withdrawal request
            withdrawal = await create_withdrawal(
                session,
                user.telegram_id,
                amount,
                address
            )
            
            await state.clear()
            
            # Show confirmation
            await message.answer(
                f"✅ Withdrawal Request Created!\n\n"
                f"💰 Amount: {amount} {settings.currency}\n"
                f"📍 Address: {address}\n"
                f"📋 ID: {withdrawal['id']}\n"
                f"📊 Status: Pending\n\n"
                f"Your withdrawal request has been submitted for approval. "
                f"You will be notified when it's processed.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 View Status", callback_data=f"withdrawal_status:{withdrawal['id']}")],
                    [InlineKeyboardButton(text="❌ Cancel Request", callback_data=f"withdrawal_cancel:{withdrawal['id']}")],
                    [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                ])
            )
            
    except Exception as e:
        logger.error(f"Error processing withdrawal address: {e}")
        await message.answer("Sorry, there was an error. Please try again.")
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
        withdrawal_id = callback_query.data.split(":", 1)[1]
        
        async with async_session() as session:
            withdrawal = await get_withdrawal(session, withdrawal_id)
            
            if not withdrawal:
                await callback_query.message.edit_text(
                    "❌ Withdrawal not found.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            status_emoji = {
                "pending": "⏳",
                "approved": "✅",
                "rejected": "❌",
                "completed": "🎉"
            }.get(withdrawal.status, "❓")
            
            await callback_query.message.edit_text(
                f"📊 Withdrawal Status\n\n"
                f"💰 Amount: {withdrawal.amount} {settings.currency}\n"
                f"📍 Address: {withdrawal.address}\n"
                f"📋 ID: {withdrawal.id}\n"
                f"📊 Status: {status_emoji} {withdrawal.status.title()}\n\n"
                f"Status updates will be sent to you automatically.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Refresh", callback_data=f"withdrawal_status:{withdrawal_id}")],
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
        withdrawal_id = callback_query.data.split(":", 1)[1]
        
        async with async_session() as session:
            withdrawal = await get_withdrawal(session, withdrawal_id)
            
            if not withdrawal:
                await callback_query.message.edit_text("❌ Withdrawal not found.")
                return
            
            if withdrawal.status != "pending":
                await callback_query.message.edit_text(
                    f"❌ Cannot cancel withdrawal. Status: {withdrawal.status.title()}"
                )
                return
            
            # Update withdrawal status to cancelled
            withdrawal.status = "cancelled"
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
    
    # Create a fake message object
    from aiogram.types import Message
    fake_message = Message(
        message_id=callback_query.message.message_id,
        from_user=callback_query.from_user,
        chat=callback_query.message.chat,
        date=callback_query.message.date,
        content_type=callback_query.message.content_type,
        text="/withdraw",
        reply_markup=callback_query.message.reply_markup
    )
    await withdraw_command(fake_message, state)


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
                f"📊 Status: {user.status.title()}\n"
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
