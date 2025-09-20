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
from app.db.session import get_async_session
from app.repos.user_repo import get_user_by_telegram_id, create_user
from app.repos.wallet_repo import get_wallet_for_user, create_wallet_for_user
from app.repos.contest_repo import get_contests
from app.models.enums import UserStatus

logger = logging.getLogger(__name__)

# Create router for user commands
user_router = Router()

# States for user interactions
class UserStates(StatesGroup):
    waiting_for_deposit_amount = State()


@user_router.message(Command("start"))
async def start_command(message: Message):
    """Handle /start command - register user if not exists"""
    try:
        async for session in get_async_session():
            # Check if user exists
            user = await get_user_by_telegram_id(session, message.from_user.id)
            
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
                await create_wallet_for_user(session, user.id)
                
                welcome_text = (
                    f"Welcome to CricAlgo! 🏏\n\n"
                    f"Hello {user.username}! Your account has been created successfully.\n"
                    f"Use /balance to check your wallet balance.\n"
                    f"Use /contests to see available contests.\n"
                    f"Use /help for more commands."
                )
            else:
                welcome_text = (
                    f"Welcome back to CricAlgo! 🏏\n\n"
                    f"Hello {user.username}!\n"
                    f"Use /balance to check your wallet balance.\n"
                    f"Use /contests to see available contests.\n"
                    f"Use /help for more commands."
                )
            
            await message.answer(welcome_text)
            break
            
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await message.answer("Sorry, there was an error. Please try again later.")


@user_router.message(Command("balance"))
async def balance_command(message: Message):
    """Handle /balance command - show user's wallet balance"""
    try:
        async for session in get_async_session():
            user = await get_user_by_telegram_id(session, message.from_user.id)
            
            if not user:
                await message.answer("Please use /start first to register your account.")
                return
            
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
            break
            
    except Exception as e:
        logger.error(f"Error in balance command: {e}")
        await message.answer("Sorry, there was an error retrieving your balance. Please try again later.")


@user_router.message(Command("deposit"))
async def deposit_command(message: Message, state: FSMContext):
    """Handle /deposit command - show deposit instructions"""
    try:
        async for session in get_async_session():
            user = await get_user_by_telegram_id(session, message.from_user.id)
            
            if not user:
                await message.answer("Please use /start first to register your account.")
                return
            
            deposit_text = (
                f"💳 Deposit Instructions\n\n"
                f"To deposit funds to your CricAlgo wallet:\n\n"
                f"1. Send USDT to our deposit address\n"
                f"2. Minimum deposit: 10 USDT\n"
                f"3. Network: TRC20 (Tron)\n\n"
                f"⚠️ Important: Only send USDT (TRC20) to this address!\n"
                f"Other tokens will be lost permanently.\n\n"
                f"Your current balance will be updated automatically once the transaction is confirmed."
            )
            
            # Add back to balance button
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Check Balance", callback_data="balance")],
                [InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await message.answer(deposit_text, reply_markup=keyboard)
            break
            
    except Exception as e:
        logger.error(f"Error in deposit command: {e}")
        await message.answer("Sorry, there was an error. Please try again later.")


@user_router.message(Command("contests"))
async def contests_command(message: Message):
    """Handle /contests command - show available contests"""
    try:
        async for session in get_async_session():
            user = await get_user_by_telegram_id(session, message.from_user.id)
            
            if not user:
                await message.answer("Please use /start first to register your account.")
                return
            
            # Get open contests
            contests = await get_contests(session, limit=10, status="open")
            
            if not contests:
                await message.answer("No contests available at the moment. Check back later!")
                return
            
            contests_text = "🏏 Available Contests\n\n"
            keyboard_buttons = []
            
            for contest in contests:
                contests_text += (
                    f"🎯 {contest.title}\n"
                    f"💰 Entry Fee: {contest.entry_fee} {contest.currency}\n"
                    f"👥 Max Players: {contest.max_players or 'Unlimited'}\n"
                    f"📅 Status: {contest.status.title()}\n\n"
                )
                
                # Add join button for each contest
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"Join {contest.title[:20]}...",
                        callback_data=f"join_contest:{contest.id}"
                    )
                ])
            
            # Add main menu button
            keyboard_buttons.append([
                InlineKeyboardButton(text="🏠 Main Menu", callback_data="main_menu")
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            
            await message.answer(contests_text, reply_markup=keyboard)
            break
            
    except Exception as e:
        logger.error(f"Error in contests command: {e}")
        await message.answer("Sorry, there was an error retrieving contests. Please try again later.")


@user_router.message(Command("help"))
async def help_command(message: Message):
    """Handle /help command - show available commands"""
    help_text = (
        "🤖 CricAlgo Bot Commands\n\n"
        "/start - Register or login to your account\n"
        "/balance - Check your wallet balance\n"
        "/deposit - Get deposit instructions\n"
        "/contests - View available contests\n"
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
    # Create a fake message object for the balance command
    fake_message = callback_query.message
    fake_message.from_user = callback_query.from_user
    await balance_command(fake_message)


@user_router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback_query):
    """Handle main menu callback"""
    await callback_query.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Balance", callback_data="balance")],
        [InlineKeyboardButton(text="💳 Deposit", callback_data="deposit")],
        [InlineKeyboardButton(text="🏏 Contests", callback_data="contests")]
    ])
    
    await callback_query.message.edit_text(
        "🏠 Main Menu\n\nChoose an option:",
        reply_markup=keyboard
    )


@user_router.callback_query(F.data == "deposit")
async def deposit_callback(callback_query):
    """Handle deposit callback"""
    await callback_query.answer()
    # Create a fake message object for the deposit command
    fake_message = callback_query.message
    fake_message.from_user = callback_query.from_user
    await deposit_command(fake_message, None)


@user_router.callback_query(F.data == "contests")
async def contests_callback(callback_query):
    """Handle contests callback"""
    await callback_query.answer()
    # Create a fake message object for the contests command
    fake_message = callback_query.message
    fake_message.from_user = callback_query.from_user
    await contests_command(fake_message)
