import os
import redis.asyncio as redis
from app.core.config import settings

REDIS_URL = os.environ.get("REDIS_URL", settings.redis_url)
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

async def get_redis_client():
    """Get Redis client instance"""
    return redis_client