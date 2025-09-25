#!/usr/bin/env python3
"""
Bot Conflict Resolution Script
Permanently fixes bot conflict issues by implementing proper process management
"""

import asyncio
import sys
import os
import signal
import psutil
import time
from typing import List

# Add app to path
sys.path.insert(0, 'app')

from app.bot.telegram_bot import get_bot

class BotConflictResolver:
    def __init__(self):
        self.bot_token = "8257937151:AAGyRy10haSpTNYG-kOQ3wU2emBnybx3qAs"
        
    def find_bot_processes(self) -> List[psutil.Process]:
        """Find all processes that might be running the bot"""
        bot_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                
                # Check for bot-related processes
                if any(keyword in cmdline.lower() for keyword in [
                    'start_bot.py', 'telegram_bot', 'bot.py', 
                    'python.*bot', 'python.*telegram'
                ]):
                    bot_processes.append(proc)
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
        return bot_processes
    
    def kill_bot_processes(self) -> int:
        """Kill all bot processes"""
        processes = self.find_bot_processes()
        killed_count = 0
        
        print(f"Found {len(processes)} bot processes to kill:")
        
        for proc in processes:
            try:
                print(f"  Killing PID {proc.pid}: {' '.join(proc.cmdline())}")
                proc.terminate()
                
                # Wait for process to terminate
                try:
                    proc.wait(timeout=5)
                    killed_count += 1
                    print(f"    ✅ Process {proc.pid} terminated")
                except psutil.TimeoutExpired:
                    # Force kill if it doesn't terminate
                    proc.kill()
                    killed_count += 1
                    print(f"    ⚠️ Process {proc.pid} force killed")
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                print(f"    ❌ Could not kill process {proc.pid}")
                
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
            
            # Get bot info to verify connection
            me = await bot.get_me()
            print(f"✅ Bot verified: {me.first_name} (@{me.username})")
            
            await bot.session.close()
            
        except Exception as e:
            print(f"❌ Error cleaning up Telegram API: {e}")
    
    async def resolve_conflicts(self):
        """Main conflict resolution process"""
        print("🔧 Bot Conflict Resolution Starting...")
        print("=" * 50)
        
        # Step 1: Kill existing bot processes
        print("1. Killing existing bot processes...")
        killed = self.kill_bot_processes()
        print(f"   Killed {killed} processes")
        
        # Step 2: Wait for processes to fully terminate
        print("2. Waiting for processes to terminate...")
        time.sleep(2)
        
        # Step 3: Clean up Telegram API state
        print("3. Cleaning up Telegram API state...")
        await self.cleanup_telegram_api()
        
        # Step 4: Verify no conflicts remain
        print("4. Verifying no conflicts remain...")
        remaining = self.find_bot_processes()
        if remaining:
            print(f"   ⚠️ {len(remaining)} processes still running:")
            for proc in remaining:
                print(f"     - PID {proc.pid}: {' '.join(proc.cmdline())}")
        else:
            print("   ✅ No bot processes running")
        
        print("\n🎉 Bot conflict resolution complete!")
        return len(remaining) == 0

async def main():
    """Main function"""
    resolver = BotConflictResolver()
    success = await resolver.resolve_conflicts()
    
    if success:
        print("\n✅ Ready to start bot without conflicts!")
        return True
    else:
        print("\n❌ Some conflicts remain. Manual intervention may be required.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
