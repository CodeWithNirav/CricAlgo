"""
Redis-specific test fixtures and utilities
"""

import json
import asyncio
from typing import Any, Dict, Optional
import redis.asyncio as redis


class RedisTestHelper:
    """Helper class for Redis test operations."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def set_json(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set a JSON value in Redis."""
        json_str = json.dumps(value)
        return await self.redis.set(key, json_str, ex=ttl)
    
    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a JSON value from Redis."""
        value = await self.redis.get(key)
        if value is None:
            return None
        return json.loads(value)
    
    async def set_idempotency_key(self, tx_hash: str, ttl: int = 3600) -> bool:
        """Set an idempotency key for transaction processing."""
        key = f"processed:tx_hash:{tx_hash}"
        return await self.redis.set(key, "1", ex=ttl)
    
    async def check_idempotency_key(self, tx_hash: str) -> bool:
        """Check if an idempotency key exists."""
        key = f"processed:tx_hash:{tx_hash}"
        return await self.redis.exists(key) > 0
    
    async def set_webhook_data(self, tx_hash: str, data: Dict[str, Any], ttl: int = 3600) -> bool:
        """Store webhook data for a transaction."""
        key = f"webhook:data:{tx_hash}"
        return await self.set_json(key, data, ttl)
    
    async def get_webhook_data(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Get webhook data for a transaction."""
        key = f"webhook:data:{tx_hash}"
        return await self.get_json(key)
    
    async def increment_counter(self, key: str, ttl: Optional[int] = None) -> int:
        """Increment a counter in Redis."""
        count = await self.redis.incr(key)
        if ttl:
            await self.redis.expire(key, ttl)
        return count
    
    async def get_counter(self, key: str) -> int:
        """Get counter value."""
        value = await self.redis.get(key)
        return int(value) if value else 0
    
    async def clear_all(self):
        """Clear all keys in the current database."""
        await self.redis.flushdb()
    
    async def get_all_keys(self, pattern: str = "*") -> list:
        """Get all keys matching pattern."""
        return await self.redis.keys(pattern)


async def create_redis_test_helper(redis_client: redis.Redis) -> RedisTestHelper:
    """Create a Redis test helper instance."""
    return RedisTestHelper(redis_client)


class MockRedisClient:
    """Mock Redis client for testing without actual Redis."""
    
    def __init__(self):
        self._data = {}
        self._ttl = {}
    
    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set a key-value pair."""
        self._data[key] = value
        if ex:
            self._ttl[key] = asyncio.get_event_loop().time() + ex
        return True
    
    async def get(self, key: str) -> Optional[str]:
        """Get a value by key."""
        if key in self._ttl and asyncio.get_event_loop().time() > self._ttl[key]:
            del self._data[key]
            del self._ttl[key]
            return None
        return self._data.get(key)
    
    async def exists(self, key: str) -> int:
        """Check if key exists."""
        return 1 if await self.get(key) is not None else 0
    
    async def incr(self, key: str) -> int:
        """Increment a counter."""
        current = int(await self.get(key) or "0")
        new_value = current + 1
        await self.set(key, str(new_value))
        return new_value
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for a key."""
        if key in self._data:
            self._ttl[key] = asyncio.get_event_loop().time() + ttl
            return True
        return False
    
    async def keys(self, pattern: str = "*") -> list:
        """Get all keys matching pattern."""
        if pattern == "*":
            return list(self._data.keys())
        # Simple pattern matching (not regex)
        return [k for k in self._data.keys() if pattern.replace("*", "") in k]
    
    async def flushdb(self):
        """Clear all data."""
        self._data.clear()
        self._ttl.clear()
    
    async def close(self):
        """Close the mock client."""
        pass
