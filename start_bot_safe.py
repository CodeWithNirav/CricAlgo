#!/usr/bin/env python3
"""
Safe Bot Startup Script - Handles conflicts automatically
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

class SafeBotStarter:
    def __init__(self):
        self.bot_process: Optional[subprocess.Popen] = None
        
    def find_and_kill_bot_processes(self):
        """Find and kill all existing bot processes"""
        killed_count = 0
        
        try:
            # Use ps to find bot processes
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            
            for line in lines:
                if 'start_bot.py' in line and 'python' in line:
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            pid = int(parts[1])
                            print(f"Killing bot process PID {pid}")
                            os.kill(pid, signal.SIGTERM)
                            killed_count += 1
                            time.sleep(1)
                        except (ValueError, ProcessLookupError, PermissionError):
                            continue
                            
        except Exception as e:
            print(f"Error finding processes: {e}")
            
        return killed_count
    
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
    
    async def start_bot_safely(self):
        """Start bot with conflict resolution"""
        print("🤖 Starting CricAlgo Bot Safely...")
        
        # Step 1: Kill existing bot processes
        print("1. Cleaning up existing bot processes...")
        killed = self.find_and_kill_bot_processes()
        if killed > 0:
            print(f"   Killed {killed} existing bot processes")
            time.sleep(2)
        else:
            print("   No existing bot processes found")
        
        # Step 2: Clean up Telegram API state
        print("2. Cleaning up Telegram API state...")
        await self.cleanup_telegram_api()
        
        # Step 3: Start bot
        print("3. Starting bot...")
        try:
            self.bot_process = subprocess.Popen([
                sys.executable, "/app/start_bot.py"
            ], cwd="/app")
            
            print(f"✅ Bot started with PID: {self.bot_process.pid}")
            
            # Wait a moment for bot to initialize
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
            return False
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received signal {signum}, shutting down...")
        if self.bot_process:
            self.bot_process.terminate()
        sys.exit(0)

async def main():
    """Main function"""
    starter = SafeBotStarter()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, starter.signal_handler)
    signal.signal(signal.SIGTERM, starter.signal_handler)
    
    # Start bot safely
    success = await starter.start_bot_safely()
    
    if success:
        print("\n✅ Bot started successfully!")
        print("💡 Use Ctrl+C to stop the bot")
        
        # Keep the script running to maintain the bot process
        try:
            while True:
                time.sleep(1)
                if starter.bot_process and starter.bot_process.poll() is not None:
                    print(f"❌ Bot process exited with code: {starter.bot_process.returncode}")
                    break
        except KeyboardInterrupt:
            print("\n🛑 Stopping bot...")
            if starter.bot_process:
                starter.bot_process.terminate()
                starter.bot_process.wait()
            print("✅ Bot stopped")
    else:
        print("\n❌ Failed to start bot")
        return False
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
