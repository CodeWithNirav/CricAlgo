#!/usr/bin/env python3
"""
Clear all idempotency keys from Redis
Use this when users get stuck with "already joined" errors
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.redis import get_redis_client

async def clear_idempotency_keys():
    """Clear all bot operation idempotency keys"""
    try:
        redis_client = await get_redis_client()
        
        # Get all bot operation keys
        keys = await redis_client.keys("bot_operation:*")
        
        if keys:
            # Delete all keys
            deleted_count = await redis_client.delete(*keys)
            print(f"✅ Cleared {deleted_count} idempotency keys")
            
            # List the keys that were cleared
            for key in keys:
                print(f"   - {key.decode()}")
        else:
            print("ℹ️ No idempotency keys found")
            
    except Exception as e:
        print(f"❌ Error clearing keys: {e}")

if __name__ == "__main__":
    asyncio.run(clear_idempotency_keys())
