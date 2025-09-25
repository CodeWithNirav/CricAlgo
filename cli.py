#!/usr/bin/env python3
"""
CricAlgo Unified CLI
Consolidated entry point for all CricAlgo operations
"""

import asyncio
import sys
import os
import signal
import time
import subprocess
import logging
from typing import Optional
from pathlib import Path

# Add app to path
sys.path.insert(0, 'app')

from app.bot.telegram_bot import get_bot, start_polling, start_webhook
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CricAlgoCLI:
    def __init__(self):
        self.bot_process: Optional[subprocess.Popen] = None
        self.lock_file = "/tmp/cricalgo_bot.lock"
        
    def is_bot_running(self) -> bool:
        """Check if bot is already running"""
        try:
            if os.path.exists(self.lock_file):
                with open(self.lock_file, 'r') as f:
                    pid = int(f.read().strip())
                try:
                    os.kill(pid, 0)
                    return True
                except (OSError, ProcessLookupError):
                    os.remove(self.lock_file)
                    return False
            return False
        except Exception:
            return False
    
    def create_lock(self) -> bool:
        """Create lock file"""
        try:
            with open(self.lock_file, 'w') as f:
                f.write(str(os.getpid()))
            return True
        except Exception:
            return False
    
    def remove_lock(self):
        """Remove lock file"""
        try:
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except Exception:
            pass
    
    async def cleanup_telegram_api(self):
        """Clean up Telegram API state"""
        try:
            bot = get_bot()
            
            webhook_info = await bot.get_webhook_info()
            if webhook_info.url:
                logger.info(f"Deleting webhook: {webhook_info.url}")
                await bot.delete_webhook(drop_pending_updates=True)
                logger.info("✅ Webhook deleted")
            else:
                logger.info("ℹ️ No webhook set")
            
            await bot.session.close()
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up Telegram API: {e}")
    
    async def start_bot_polling(self):
        """Start bot in polling mode"""
        logger.info("🤖 Starting CricAlgo Telegram Bot in polling mode...")
        logger.info(f"📱 Bot Token: {settings.telegram_bot_token[:10]}...")
        logger.info(f"🔧 Environment: {settings.app_env}")
        
        if not settings.telegram_bot_token:
            logger.error("TELEGRAM_BOT_TOKEN is not configured!")
            return False
        
        try:
            await start_polling()
            return True
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
            return True
        except Exception as e:
            logger.error(f"❌ Error starting bot: {e}")
            return False
    
    async def start_bot_webhook(self):
        """Start bot in webhook mode"""
        logger.info("🤖 Starting CricAlgo Telegram Bot in webhook mode...")
        logger.info(f"📱 Bot Token: {settings.telegram_bot_token[:10]}...")
        logger.info(f"🔗 Webhook URL: {settings.telegram_webhook_url}")
        
        if not settings.telegram_bot_token:
            logger.error("TELEGRAM_BOT_TOKEN is not configured!")
            return False
        
        if not settings.telegram_webhook_url:
            logger.error("TELEGRAM_WEBHOOK_URL is not configured!")
            return False
        
        try:
            await start_webhook(settings.telegram_webhook_url)
            return True
        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user")
            return True
        except Exception as e:
            logger.error(f"❌ Error starting bot: {e}")
            return False
    
    async def start_bot_managed(self):
        """Start bot with process management"""
        logger.info("🤖 Starting CricAlgo Bot Manager...")
        
        if self.is_bot_running():
            logger.warning("⚠️ Bot is already running. Stopping existing instance...")
            await self.stop_bot()
            time.sleep(2)
        
        logger.info("🧹 Cleaning up Telegram API state...")
        await self.cleanup_telegram_api()
        
        if not self.create_lock():
            logger.error("❌ Could not create lock file")
            return False
        
        try:
            logger.info("🚀 Starting bot process...")
            self.bot_process = subprocess.Popen([
                sys.executable, "cli.py", "bot", "polling"
            ], cwd=os.getcwd())
            
            logger.info(f"✅ Bot started with PID: {self.bot_process.pid}")
            
            time.sleep(3)
            
            if self.bot_process.poll() is None:
                logger.info("🎉 Bot is running successfully!")
                return True
            else:
                logger.error(f"❌ Bot process exited with code: {self.bot_process.returncode}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error starting bot: {e}")
            self.remove_lock()
            return False
    
    async def stop_bot(self):
        """Stop the bot"""
        try:
            if os.path.exists(self.lock_file):
                with open(self.lock_file, 'r') as f:
                    pid = int(f.read().strip())
                
                logger.info(f"🛑 Stopping bot process PID: {pid}")
                
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(2)
                    
                    try:
                        os.kill(pid, 0)
                        os.kill(pid, signal.SIGKILL)
                        logger.warning("⚠️ Force killed bot process")
                    except ProcessLookupError:
                        logger.info("✅ Bot process terminated gracefully")
                        
                except ProcessLookupError:
                    logger.info("ℹ️ Bot process not found")
            
            self.remove_lock()
            
        except Exception as e:
            logger.error(f"❌ Error stopping bot: {e}")
    
    async def restart_bot(self):
        """Restart the bot"""
        logger.info("🔄 Restarting bot...")
        await self.stop_bot()
        time.sleep(2)
        return await self.start_bot_managed()
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"\n🛑 Received signal {signum}, shutting down...")
        asyncio.create_task(self.stop_bot())
        sys.exit(0)

def print_help():
    """Print help information"""
    print("""
CricAlgo Unified CLI

Usage:
  python cli.py <command> [options]

Commands:
  bot polling          Start bot in polling mode
  bot webhook          Start bot in webhook mode  
  bot managed          Start bot with process management
  bot stop             Stop running bot
  bot restart          Restart bot
  bot status           Check bot status
  bot cleanup          Clean up Telegram API state
  
  app start            Start FastAPI application
  app dev              Start FastAPI in development mode
  
  db migrate           Run database migrations
  db upgrade           Upgrade database
  db downgrade         Downgrade database
  
  test                 Run tests
  test smoke           Run smoke tests
  test load            Run load tests
  
  help                 Show this help message

Examples:
  python cli.py bot polling
  python cli.py app start
  python cli.py db migrate
  python cli.py test smoke
""")

async def main():
    """Main CLI function"""
    if len(sys.argv) < 2:
        print_help()
        return False
    
    command = sys.argv[1].lower()
    cli = CricAlgoCLI()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, cli.signal_handler)
    signal.signal(signal.SIGTERM, cli.signal_handler)
    
    if command == "bot":
        if len(sys.argv) < 3:
            print("Bot subcommand required. Use: polling, webhook, managed, stop, restart, status, cleanup")
            return False
        
        subcommand = sys.argv[2].lower()
        
        if subcommand == "polling":
            return await cli.start_bot_polling()
        elif subcommand == "webhook":
            return await cli.start_bot_webhook()
        elif subcommand == "managed":
            return await cli.start_bot_managed()
        elif subcommand == "stop":
            await cli.stop_bot()
            return True
        elif subcommand == "restart":
            return await cli.restart_bot()
        elif subcommand == "status":
            if cli.is_bot_running():
                print("✅ Bot is running")
                return True
            else:
                print("❌ Bot is not running")
                return False
        elif subcommand == "cleanup":
            await cli.cleanup_telegram_api()
            return True
        else:
            print(f"Unknown bot subcommand: {subcommand}")
            return False
    
    elif command == "app":
        if len(sys.argv) < 3:
            print("App subcommand required. Use: start, dev")
            return False
        
        subcommand = sys.argv[2].lower()
        
        if subcommand == "start":
            logger.info("🚀 Starting FastAPI application...")
            os.system("uvicorn app.main:app --host 0.0.0.0 --port 8000")
            return True
        elif subcommand == "dev":
            logger.info("🚀 Starting FastAPI in development mode...")
            os.system("uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
            return True
        else:
            print(f"Unknown app subcommand: {subcommand}")
            return False
    
    elif command == "db":
        if len(sys.argv) < 3:
            print("Database subcommand required. Use: migrate, upgrade, downgrade")
            return False
        
        subcommand = sys.argv[2].lower()
        
        if subcommand == "migrate":
            logger.info("🔄 Running database migrations...")
            os.system("alembic upgrade head")
            return True
        elif subcommand == "upgrade":
            logger.info("⬆️ Upgrading database...")
            os.system("alembic upgrade head")
            return True
        elif subcommand == "downgrade":
            logger.info("⬇️ Downgrading database...")
            os.system("alembic downgrade -1")
            return True
        else:
            print(f"Unknown database subcommand: {subcommand}")
            return False
    
    elif command == "test":
        if len(sys.argv) < 3:
            print("Test subcommand required. Use: smoke, load, or run without subcommand for unit tests")
            return False
        
        subcommand = sys.argv[2].lower()
        
        if subcommand == "smoke":
            logger.info("🧪 Running smoke tests...")
            os.system("python scripts/smoke_test.py")
            return True
        elif subcommand == "load":
            logger.info("⚡ Running load tests...")
            os.system("k6 run --vus 100 --duration 5m load/k6/webhook_test.js")
            return True
        else:
            print(f"Unknown test subcommand: {subcommand}")
            return False
    
    elif command == "help":
        print_help()
        return True
    
    else:
        print(f"Unknown command: {command}")
        print_help()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
