"""
Telegram Bot using aiogram
Minimal skeleton for bot setup and handlers
"""

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from app.core.config import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot and Dispatcher instances
bot: Bot = None
dp: Dispatcher = None


def create_bot() -> Bot:
    """Create bot instance"""
    if not settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")
    
    return Bot(token=settings.telegram_bot_token)


def create_dispatcher() -> Dispatcher:
    """Create dispatcher instance"""
    return Dispatcher()


def register_handlers(dp: Dispatcher) -> None:
    """Register bot handlers"""
    
    @dp.message(Command("start"))
    async def start_handler(message: Message):
        """Handle /start command"""
        await message.answer(
            "Welcome to CricAlgo! 🏏\n\n"
            "This is a cricket algorithm trading bot. "
            "More features coming soon!"
        )
    
    @dp.message(Command("help"))
    async def help_handler(message: Message):
        """Handle /help command"""
        await message.answer(
            "Available commands:\n"
            "/start - Start the bot\n"
            "/help - Show this help message"
        )


def get_bot() -> Bot:
    """Get bot instance (singleton)"""
    global bot
    if bot is None:
        bot = create_bot()
    return bot


def get_dispatcher() -> Dispatcher:
    """Get dispatcher instance (singleton)"""
    global dp
    if dp is None:
        dp = create_dispatcher()
        register_handlers(dp)
    return dp
