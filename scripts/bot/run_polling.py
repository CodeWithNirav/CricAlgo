#!/usr/bin/env python3
"""
Run Telegram bot in polling mode
"""

import asyncio
import logging
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.bot.telegram_bot import start_polling
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main function to start the bot"""
    try:
        logger.info("Starting CricAlgo Telegram Bot in polling mode...")
        logger.info(f"Bot token configured: {'Yes' if settings.telegram_bot_token else 'No'}")
        logger.info(f"Redis URL: {settings.redis_url}")
        
        if not settings.telegram_bot_token:
            logger.error("TELEGRAM_BOT_TOKEN is not configured!")
            sys.exit(1)
        
        await start_polling()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
