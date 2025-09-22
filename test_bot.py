#!/usr/bin/env python3
"""
Test script to verify bot functionality
"""

import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.bot.telegram_bot import get_bot, get_dispatcher
from app.core.config import settings

async def test_bot():
    """Test bot functionality"""
    try:
        print("🤖 Testing CricAlgo Telegram Bot...")
        
        # Get bot instance
        bot = get_bot()
        print(f"✅ Bot created successfully")
        print(f"📱 Bot Token: {bot.token[:10]}...")
        
        # Get bot info
        bot_info = await bot.get_me()
        print(f"👤 Bot Username: @{bot_info.username}")
        print(f"📛 Bot Name: {bot_info.first_name}")
        
        # Get dispatcher
        dp = get_dispatcher()
        print(f"✅ Dispatcher created successfully")
        
        print("\n🎉 Bot is ready to use!")
        print("\n📋 Available Commands:")
        print("  /start - Start the bot and register")
        print("  /start INVITE123 - Start with invite code")
        print("  /menu - Show main menu")
        print("  /balance - Check wallet balance")
        print("  /deposit - Get deposit instructions")
        print("  /withdraw - Start withdrawal process")
        print("  /contests - View available contests")
        print("  /help - Show help information")
        
        print(f"\n🔗 To test the bot, send a message to @{bot_info.username} on Telegram")
        print("   or use the bot token to interact via Telegram API")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing bot: {e}")
        return False
    finally:
        await bot.session.close()

if __name__ == "__main__":
    success = asyncio.run(test_bot())
    sys.exit(0 if success else 1)
