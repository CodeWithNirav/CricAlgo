#!/usr/bin/env python3
"""
Bot Manager - Handles bot conflicts and ensures single instance
"""

import asyncio
import sys
import os
import signal
import time
import subprocess
from typing import Optional

# Add app to path
sys.path.insert(0, 'app')

from app.bot.telegram_bot import get_bot

class BotManager:
    def __init__(self):
        self.bot_process: Optional[subprocess.Popen] = None
        self.lock_file = "/tmp/cricalgo_bot.lock"
        
    def is_bot_running(self) -> bool:
        """Check if bot is already running"""
        try:
            # Check lock file
            if os.path.exists(self.lock_file):
                with open(self.lock_file, 'r') as f:
                    pid = int(f.read().strip())
                try:
                    # Check if process is still running
                    os.kill(pid, 0)
                    return True
                except (OSError, ProcessLookupError):
                    # Process is dead, remove lock file
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
            
            # Delete webhook to ensure polling mode
            webhook_info = await bot.get_webhook_info()
            if webhook_info.url:
                print(f"Deleting webhook: {webhook_info.url}")
                await bot.delete_webhook(drop_pending_updates=True)
                print("✅ Webhook deleted")
            else:
                print("ℹ️ No webhook set")
            
            await bot.session.close()
            
        except Exception as e:
            print(f"❌ Error cleaning up Telegram API: {e}")
    
    async def start_bot(self):
        """Start the bot with conflict resolution"""
        print("🤖 Starting CricAlgo Bot Manager...")
        
        # Check if bot is already running
        if self.is_bot_running():
            print("⚠️ Bot is already running. Stopping existing instance...")
            await self.stop_bot()
            time.sleep(2)
        
        # Clean up Telegram API state
        print("🧹 Cleaning up Telegram API state...")
        await self.cleanup_telegram_api()
        
        # Create lock file
        if not self.create_lock():
            print("❌ Could not create lock file")
            return False
        
        try:
            # Start bot process
            print("🚀 Starting bot process...")
            self.bot_process = subprocess.Popen([
                sys.executable, "/app/start_bot.py"
            ], cwd="/app")
            
            print(f"✅ Bot started with PID: {self.bot_process.pid}")
            
            # Wait for bot to start
            time.sleep(3)
            
            # Check if bot is still running
            if self.bot_process.poll() is None:
                print("🎉 Bot is running successfully!")
                return True
            else:
                print(f"❌ Bot process exited with code: {self.bot_process.returncode}")
                return False
                
        except Exception as e:
            print(f"❌ Error starting bot: {e}")
            self.remove_lock()
            return False
    
    async def stop_bot(self):
        """Stop the bot"""
        try:
            # Read PID from lock file
            if os.path.exists(self.lock_file):
                with open(self.lock_file, 'r') as f:
                    pid = int(f.read().strip())
                
                print(f"🛑 Stopping bot process PID: {pid}")
                
                # Try graceful termination
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(2)
                    
                    # Check if still running
                    try:
                        os.kill(pid, 0)
                        # Still running, force kill
                        os.kill(pid, signal.SIGKILL)
                        print("⚠️ Force killed bot process")
                    except ProcessLookupError:
                        print("✅ Bot process terminated gracefully")
                        
                except ProcessLookupError:
                    print("ℹ️ Bot process not found")
            
            # Clean up
            self.remove_lock()
            
        except Exception as e:
            print(f"❌ Error stopping bot: {e}")
    
    async def restart_bot(self):
        """Restart the bot"""
        print("🔄 Restarting bot...")
        await self.stop_bot()
        time.sleep(2)
        return await self.start_bot()
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received signal {signum}, shutting down...")
        asyncio.create_task(self.stop_bot())
        sys.exit(0)

async def main():
    """Main function"""
    manager = BotManager()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, manager.signal_handler)
    signal.signal(signal.SIGTERM, manager.signal_handler)
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "start":
            success = await manager.start_bot()
            return success
        elif command == "stop":
            await manager.stop_bot()
            return True
        elif command == "restart":
            success = await manager.restart_bot()
            return success
        elif command == "status":
            if manager.is_bot_running():
                print("✅ Bot is running")
                return True
            else:
                print("❌ Bot is not running")
                return False
        else:
            print(f"Unknown command: {command}")
            print("Usage: python bot_manager.py [start|stop|restart|status]")
            return False
    else:
        # Default: start bot
        success = await manager.start_bot()
        return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
