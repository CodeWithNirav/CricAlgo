#!/usr/bin/env python3
"""
Run Telegram bot in webhook mode
"""

import asyncio
import logging
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.bot.telegram_bot import start_webhook
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main function to start the bot in webhook mode"""
    try:
        logger.info("Starting CricAlgo Telegram Bot in webhook mode...")
        logger.info(f"Bot token configured: {'Yes' if settings.telegram_bot_token else 'No'}")
        logger.info(f"Webhook URL: {settings.telegram_webhook_url}")
        logger.info(f"Redis URL: {settings.redis_url}")
        
        if not settings.telegram_bot_token:
            logger.error("TELEGRAM_BOT_TOKEN is not configured!")
            sys.exit(1)
        
        if not settings.telegram_webhook_url:
            logger.error("TELEGRAM_WEBHOOK_URL is not configured!")
            sys.exit(1)
        
        await start_webhook(settings.telegram_webhook_url)
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
