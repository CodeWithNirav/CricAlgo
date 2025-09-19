"""
Redis client wrapper for CricAlgo

This module provides a centralized Redis client configuration and connection management.
It uses redis.asyncio for async Redis operations.
"""

import redis.asyncio as redis
from typing import Optional
from app.core.config import settings


# Global Redis client instance
_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """
    Get Redis client instance.
    
    Returns:
        Redis client instance
    """
    global _redis_client
    
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            encoding="utf-8"
        )
    
    return _redis_client


async def close_redis():
    """Close Redis client connection."""
    global _redis_client
    
    if _redis_client:
        await _redis_client.close()
        _redis_client = None


async def get_redis_helper():
    """
    Get Redis test helper for compatibility with existing code.
    
    Returns:
        RedisTestHelper instance
    """
    from tests.fixtures.redis import RedisTestHelper
    
    redis_client = await get_redis()
    return RedisTestHelper(redis_client)
