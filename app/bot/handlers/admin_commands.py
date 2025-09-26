"""
Admin command handlers for Telegram bot
"""

import os
import logging
from typing import Optional
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Check if admin commands are disabled via environment variable
if os.environ.get("DISABLE_TELEGRAM_ADMIN_CMDS","false").lower() in ("1","true","yes"):
    # admin commands disabled in production, exit early
    def _disabled_stub(*args, **kwargs):
        return None
    # override handlers with stub to avoid accidental admin actions
    create_contest_command = _disabled_stub
    process_contest_title = _disabled_stub
    process_contest_entry_fee = _disabled_stub
    process_contest_max_players = _disabled_stub
    process_contest_prize_structure = _disabled_stub
    settle_contest_command = _disabled_stub
    process_settlement_contest_id = _disabled_stub
    approve_withdraw_command = _disabled_stub
    process_withdrawal_user_id = _disabled_stub
    process_withdrawal_amount = _disabled_stub
    admin_help_command = _disabled_stub

from app.core.config import settings
from app.db.session import get_async_session
from app.repos.user_repo import get_user_by_telegram_id
from app.repos.admin_repo import get_admin_by_telegram_id
from app.repos.contest_repo import create_contest, get_contests, settle_contest
from app.repos.contest_entry_repo import get_contest_entries
from app.repos.wallet_repo import get_wallet_for_user

logger = logging.getLogger(__name__)

# Create router for admin commands
admin_router = Router()

# States for admin interactions
class AdminStates(StatesGroup):
    waiting_for_contest_title = State()
    waiting_for_contest_code = State()
    waiting_for_contest_entry_fee = State()
    waiting_for_contest_max_players = State()
    waiting_for_contest_user_link = State()
    waiting_for_contest_prize_structure = State()
    waiting_for_settlement_contest_id = State()
    waiting_for_withdrawal_user_id = State()
    waiting_for_withdrawal_amount = State()


async def is_admin(telegram_id: int) -> bool:
    """Check if user is an admin"""
    try:
        async for session in get_async_session():
            admin = await get_admin_by_telegram_id(session, telegram_id)
            return admin is not None
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False


@admin_router.message(Command("create_contest"))
async def create_contest_command(message: Message, state: FSMContext):
    """Handle /create_contest command - admin only"""
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Access denied. Admin privileges required.")
        return
    
    await state.set_state(AdminStates.waiting_for_contest_title)
    await message.answer(
        "🏏 Create New Contest\n\n"
        "Please enter the contest title:"
    )


@admin_router.message(AdminStates.waiting_for_contest_title)
async def process_contest_title(message: Message, state: FSMContext):
    """Process contest title input"""
    await state.update_data(title=message.text)
    await state.set_state(AdminStates.waiting_for_contest_entry_fee)
    await message.answer(
        "💰 Entry Fee\n\n"
        "Please enter the entry fee amount (in USDT):"
    )


@admin_router.message(AdminStates.waiting_for_contest_entry_fee)
async def process_contest_entry_fee(message: Message, state: FSMContext):
    """Process contest entry fee input"""
    try:
        entry_fee = Decimal(message.text)
        if entry_fee <= 0:
            await message.answer("❌ Entry fee must be greater than 0. Please try again:")
            return
        
        await state.update_data(entry_fee=entry_fee)
        await state.set_state(AdminStates.waiting_for_contest_max_players)
        await message.answer(
            "👥 Maximum Players\n\n"
            "Please enter the maximum number of players (or 0 for unlimited):"
        )
    except (ValueError, TypeError):
        await message.answer("❌ Invalid amount. Please enter a valid number:")
        return


@admin_router.message(AdminStates.waiting_for_contest_max_players)
async def process_contest_max_players(message: Message, state: FSMContext):
    """Process contest max players input"""
    try:
        max_players = int(message.text)
        if max_players < 0:
            await message.answer("❌ Maximum players must be 0 or greater. Please try again:")
            return
        
        await state.update_data(max_players=max_players if max_players > 0 else None)
        await state.set_state(AdminStates.waiting_for_contest_prize_structure)
        await message.answer(
            "🏆 Prize Structure\n\n"
            "Please enter the prize structure as JSON:\n"
            "Example: [{\"position\": 1, \"percentage\": 50}, {\"position\": 2, \"percentage\": 30}, {\"position\": 3, \"percentage\": 20}]"
        )
    except (ValueError, TypeError):
        await message.answer("❌ Invalid number. Please enter a valid integer:")
        return


@admin_router.message(AdminStates.waiting_for_contest_prize_structure)
async def process_contest_prize_structure(message: Message, state: FSMContext):
    """Process contest prize structure input"""
    try:
        import json
        prize_structure = json.loads(message.text)
        
        # Validate prize structure
        if not isinstance(prize_structure, list):
            raise ValueError("Prize structure must be a list")
        
        total_percentage = sum(item.get("percentage", 0) for item in prize_structure)
        if abs(total_percentage - 100) > 0.01:  # Allow small floating point errors
            await message.answer("❌ Total percentage must equal 100%. Please try again:")
            return
        
        data = await state.get_data()
        
        # Create contest
        async for session in get_async_session():
            user = await get_user_by_telegram_id(session, message.from_user.id)
            
            contest = await create_contest(
                session=session,
                match_id="default_match",  # You might want to implement match selection
                title=data["title"],
                description=None,
                entry_fee=data["entry_fee"],
                max_participants=data["max_players"],
                prize_structure=prize_structure,
                created_by=user.id if user else None
            )
            
            success_text = (
                f"✅ Contest Created Successfully!\n\n"
                f"🏏 Title: {contest.title}\n"
                f"💰 Entry Fee: {contest.entry_fee} {contest.currency}\n"
                f"👥 Max Players: {contest.max_players or 'Unlimited'}\n"
                f"🏆 Prize Structure: {len(prize_structure)} positions\n"
                f"🆔 Contest ID: {contest.id}\n"
                f"📝 Contest Code: {contest.code}"
            )
            
            await message.answer(success_text)
            break
        
        await state.clear()
        
    except json.JSONDecodeError:
        await message.answer("❌ Invalid JSON format. Please try again:")
        return
    except Exception as e:
        logger.error(f"Error creating contest: {e}")
        await message.answer("❌ Error creating contest. Please try again.")
        await state.clear()


@admin_router.message(Command("settle"))
async def settle_contest_command(message: Message, state: FSMContext):
    """Handle /settle command - admin only"""
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Access denied. Admin privileges required.")
        return
    
    await state.set_state(AdminStates.waiting_for_settlement_contest_id)
    await message.answer(
        "🏆 Settle Contest\n\n"
        "Please enter the contest ID to settle:"
    )


@admin_router.message(AdminStates.waiting_for_settlement_contest_id)
async def process_settlement_contest_id(message: Message, state: FSMContext):
    """Process settlement contest ID input"""
    try:
        from uuid import UUID
        contest_id = UUID(message.text)
        
        async for session in get_async_session():
            success = await settle_contest(session, contest_id)
            
            if success:
                await message.answer("✅ Contest settled successfully!")
            else:
                await message.answer("❌ Contest not found or already settled.")
            break
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Invalid contest ID format. Please enter a valid UUID:")
        return
    except Exception as e:
        logger.error(f"Error settling contest: {e}")
        await message.answer("❌ Error settling contest. Please try again.")
        await state.clear()


@admin_router.message(Command("approve_withdraw"))
async def approve_withdraw_command(message: Message, state: FSMContext):
    """Handle /approve_withdraw command - admin only"""
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Access denied. Admin privileges required.")
        return
    
    await state.set_state(AdminStates.waiting_for_withdrawal_user_id)
    await message.answer(
        "💸 Approve Withdrawal\n\n"
        "Please enter the user ID for withdrawal approval:"
    )


@admin_router.message(AdminStates.waiting_for_withdrawal_user_id)
async def process_withdrawal_user_id(message: Message, state: FSMContext):
    """Process withdrawal user ID input"""
    try:
        from uuid import UUID
        user_id = UUID(message.text)
        
        # Check if user exists and get their wallet
        async for session in get_async_session():
            user = await get_user_by_telegram_id(session, message.from_user.id)
            if not user:
                await message.answer("❌ User not found.")
                await state.clear()
                return
            
            wallet = await get_wallet_for_user(session, user_id)
            if not wallet:
                await message.answer("❌ User wallet not found.")
                await state.clear()
                return
            
            await state.update_data(user_id=user_id)
            await state.set_state(AdminStates.waiting_for_withdrawal_amount)
            
            await message.answer(
                f"💰 Withdrawal Amount\n\n"
                f"User's current balance:\n"
                f"💳 Deposit: {wallet.deposit_balance} {settings.currency}\n"
                f"🏆 Winning: {wallet.winning_balance} {settings.currency}\n"
                f"🎁 Bonus: {wallet.bonus_balance} {settings.currency}\n\n"
                f"Please enter the withdrawal amount:"
            )
            break
        
    except ValueError:
        await message.answer("❌ Invalid user ID format. Please enter a valid UUID:")
        return


@admin_router.message(AdminStates.waiting_for_withdrawal_amount)
async def process_withdrawal_amount(message: Message, state: FSMContext):
    """Process withdrawal amount input"""
    try:
        amount = Decimal(message.text)
        if amount <= 0:
            await message.answer("❌ Withdrawal amount must be greater than 0. Please try again:")
            return
        
        data = await state.get_data()
        user_id = data["user_id"]
        
        # Here you would implement the actual withdrawal logic
        # For now, we'll just show a confirmation
        await message.answer(
            f"✅ Withdrawal Approved!\n\n"
            f"👤 User ID: {user_id}\n"
            f"💰 Amount: {amount} {settings.currency}\n\n"
            f"Note: This is a placeholder. Implement actual withdrawal processing."
        )
        
        await state.clear()
        
    except (ValueError, TypeError):
        await message.answer("❌ Invalid amount. Please enter a valid number:")
        return
    except Exception as e:
        logger.error(f"Error processing withdrawal: {e}")
        await message.answer("❌ Error processing withdrawal. Please try again.")
        await state.clear()


@admin_router.message(Command("admin_help"))
async def admin_help_command(message: Message):
    """Handle /admin_help command - show admin commands"""
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Access denied. Admin privileges required.")
        return
    
    help_text = (
        "🔧 Admin Commands\n\n"
        "/create_contest - Create a new contest\n"
        "/settle - Settle a contest\n"
        "/approve_withdraw - Approve user withdrawal\n"
        "/admin_help - Show this help message\n\n"
        "⚠️ These commands are restricted to admin users only."
    )
    
    await message.answer(help_text)
