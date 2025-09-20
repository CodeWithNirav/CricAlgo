"""
Telegram Bot using aiogram with comprehensive handlers and rate limiting
"""

import asyncio
import logging
from typing import Optional
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import Message, Update, TelegramObject
from aiogram.filters import Command
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage

from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.bot.handlers.commands import user_router
from app.bot.handlers.admin_commands import admin_router
from app.bot.handlers.callbacks import callback_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot and Dispatcher instances
bot: Bot = None
dp: Dispatcher = None


class RateLimitMiddleware(BaseMiddleware):
    """Rate limiting middleware for bot commands"""
    
    def __init__(self, rate_limit: int = 10, window: int = 60):
        self.rate_limit = rate_limit
        self.window = window
    
    async def __call__(self, handler, event: TelegramObject, data: dict):
        if isinstance(event, Update) and event.message:
            user_id = event.message.from_user.id
            
            try:
                redis_client = await get_redis_client()
                key = f"bot_rate_limit:{user_id}"
                
                # Get current count
                current_count = await redis_client.get(key)
                if current_count is None:
                    current_count = 0
                else:
                    current_count = int(current_count)
                
                # Check rate limit
                if current_count >= self.rate_limit:
                    await event.message.answer(
                        "⚠️ Rate limit exceeded. Please wait before sending more commands."
                    )
                    return
                
                # Increment counter
                await redis_client.incr(key)
                await redis_client.expire(key, self.window)
                
            except Exception as e:
                logger.error(f"Rate limiting error: {e}")
                # If Redis fails, allow the request to proceed
        
        return await handler(event, data)


def create_bot() -> Bot:
    """Create bot instance"""
    if not settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required")
    
    return Bot(token=settings.telegram_bot_token)


def create_dispatcher() -> Dispatcher:
    """Create dispatcher instance with Redis storage"""
    try:
        # Try to use Redis storage for FSM
        storage = RedisStorage.from_url(settings.redis_url)
    except Exception as e:
        logger.warning(f"Failed to connect to Redis, using memory storage: {e}")
        storage = MemoryStorage()
    
    dp = Dispatcher(storage=storage)
    
    # Add rate limiting middleware
    dp.message.middleware(RateLimitMiddleware(
        rate_limit=settings.rate_limit_requests,
        window=settings.rate_limit_window_seconds
    ))
    
    # Register routers
    dp.include_router(user_router)
    dp.include_router(admin_router)
    dp.include_router(callback_router)
    
    return dp


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
    return dp


async def start_polling():
    """Start bot in polling mode"""
    bot = get_bot()
    dp = get_dispatcher()
    
    try:
        logger.info("Starting bot in polling mode...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Error in polling: {e}")
        raise
    finally:
        await bot.session.close()


async def start_webhook(webhook_url: str, webhook_path: str = "/webhook"):
    """Start bot in webhook mode"""
    bot = get_bot()
    dp = get_dispatcher()
    
    try:
        # Set webhook
        await bot.set_webhook(
            url=f"{webhook_url}{webhook_path}",
            secret_token=settings.webhook_secret
        )
        logger.info(f"Webhook set to {webhook_url}{webhook_path}")
        
        # Start webhook
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Error in webhook mode: {e}")
        raise
    finally:
        await bot.session.close()


async def process_webhook_update(update_data: dict):
    """Process webhook update"""
    bot = get_bot()
    dp = get_dispatcher()
    
    try:
        from aiogram.types import Update
        update = Update.model_validate(update_data, from_attributes=True)
        await dp.feed_update(bot, update)
    except Exception as e:
        logger.error(f"Error processing webhook update: {e}")
        raise
