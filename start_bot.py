#!/usr/bin/env python3
"""
CricAlgo Telegram Bot Startup Script
"""

import asyncio
import logging
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

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
        logger.info("🤖 Starting CricAlgo Telegram Bot...")
        logger.info(f"📱 Bot Token: {settings.telegram_bot_token[:10]}...")
        logger.info(f"🔧 Environment: {settings.app_env}")
        logger.info(f"💾 Database: {settings.database_url}")
        logger.info(f"🔴 Redis: {settings.redis_url}")
        
        # Start the bot in polling mode
        await start_polling()
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Error starting bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
