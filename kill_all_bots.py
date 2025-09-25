#!/usr/bin/env python3
"""
Aggressive Bot Cleanup Script
Kills ALL bot processes and cleans up Telegram API state
"""

import asyncio
import sys
import os
import signal
import time
import subprocess

# Add app to path
sys.path.insert(0, 'app')

from app.bot.telegram_bot import get_bot

async def kill_all_bot_processes():
    """Kill all bot processes aggressively"""
    print("🔪 Aggressive Bot Cleanup Starting...")
    
    # Method 1: Use pgrep to find all bot processes
    try:
        result = subprocess.run(['pgrep', '-f', 'start_bot'], capture_output=True, text=True)
        if result.stdout:
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    try:
                        print(f"Killing bot process PID {pid}")
                        os.kill(int(pid), signal.SIGTERM)
                        time.sleep(0.5)
                        # Force kill if still running
                        try:
                            os.kill(int(pid), signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    except (ValueError, ProcessLookupError, PermissionError):
                        continue
    except Exception as e:
        print(f"pgrep failed: {e}")
    
    # Method 2: Check /proc for bot processes
    try:
        for pid in os.listdir('/proc'):
            if pid.isdigit():
                try:
                    with open(f'/proc/{pid}/cmdline', 'r') as f:
                        cmdline = f.read().replace('\x00', ' ').strip()
                        if 'start_bot' in cmdline or 'telegram_bot' in cmdline:
                            print(f"Killing bot process PID {pid}: {cmdline}")
                            os.kill(int(pid), signal.SIGTERM)
                            time.sleep(0.5)
                            try:
                                os.kill(int(pid), signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                except (FileNotFoundError, PermissionError, ValueError):
                    continue
    except Exception as e:
        print(f"proc scan failed: {e}")
    
    print("✅ Bot process cleanup complete")
    time.sleep(2)

async def cleanup_telegram_api():
    """Clean up Telegram API state"""
    print("🧹 Cleaning up Telegram API state...")
    
    try:
        bot = get_bot()
        
        # Delete webhook
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

async def main():
    """Main cleanup function"""
    print("🚨 AGGRESSIVE BOT CLEANUP")
    print("=" * 40)
    
    # Step 1: Kill all bot processes
    await kill_all_bot_processes()
    
    # Step 2: Clean up Telegram API
    await cleanup_telegram_api()
    
    # Step 3: Wait and verify
    print("⏳ Waiting for cleanup to complete...")
    time.sleep(3)
    
    # Step 4: Check if any bot processes remain
    remaining_processes = []
    try:
        for pid in os.listdir('/proc'):
            if pid.isdigit():
                try:
                    with open(f'/proc/{pid}/cmdline', 'r') as f:
                        cmdline = f.read().replace('\x00', ' ').strip()
                        if 'start_bot' in cmdline or 'telegram_bot' in cmdline:
                            remaining_processes.append((pid, cmdline))
                except (FileNotFoundError, PermissionError, ValueError):
                    continue
    except Exception:
        pass
    
    if remaining_processes:
        print(f"⚠️ {len(remaining_processes)} bot processes still running:")
        for pid, cmdline in remaining_processes:
            print(f"  - PID {pid}: {cmdline}")
        return False
    else:
        print("✅ No bot processes found - cleanup successful!")
        return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
