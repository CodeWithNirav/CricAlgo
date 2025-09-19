"""
Rate limiting middleware using Redis sliding window
"""

import time
import logging
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from tests.fixtures.redis import RedisTestHelper

# Configure logging
logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis sliding window"""
    
    def __init__(self, app, redis_client=None):
        super().__init__(app)
        self.redis_client = redis_client
        self.redis_helper = RedisTestHelper(redis_client) if redis_client else None
        self.rate_limit_requests = settings.rate_limit_requests
        self.rate_limit_window = settings.rate_limit_window_seconds
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting"""
        
        # Skip rate limiting if Redis is not available
        if not self.redis_helper:
            return await call_next(request)
        
        # Get rate limit key based on endpoint and user
        rate_limit_key = self._get_rate_limit_key(request)
        
        if not rate_limit_key:
            # Skip rate limiting for this request
            return await call_next(request)
        
        # Check rate limit
        is_allowed, retry_after = await self._check_rate_limit(rate_limit_key)
        
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for key: {rate_limit_key}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )
        
        # Process request
        response = await call_next(request)
        
        # Record request
        await self._record_request(rate_limit_key)
        
        return response
    
    def _get_rate_limit_key(self, request: Request) -> Optional[str]:
        """Get rate limit key based on request path and user"""
        path = request.url.path
        
        # Rate limit critical endpoints
        if path.startswith("/api/v1/webhooks/"):
            # Rate limit by IP for webhooks
            client_ip = request.client.host
            return f"rate_limit:webhook:{client_ip}"
        
        elif path.startswith("/api/v1/contest/") and "join" in path:
            # Rate limit contest joins by user
            # This would need to be extracted from JWT token in a real implementation
            # For now, we'll use IP as fallback
            client_ip = request.client.host
            return f"rate_limit:contest_join:{client_ip}"
        
        elif path.startswith("/api/v1/auth/"):
            # Rate limit auth endpoints by IP
            client_ip = request.client.host
            return f"rate_limit:auth:{client_ip}"
        
        elif path.startswith("/api/v1/wallet/withdraw"):
            # Rate limit withdrawals by user
            # This would need to be extracted from JWT token in a real implementation
            # For now, we'll use IP as fallback
            client_ip = request.client.host
            return f"rate_limit:withdraw:{client_ip}"
        
        # No rate limiting for other endpoints
        return None
    
    async def _check_rate_limit(self, key: str) -> tuple[bool, int]:
        """Check if request is within rate limit"""
        try:
            current_time = int(time.time())
            window_start = current_time - self.rate_limit_window
            
            # Get current request count in the window
            request_count = await self.redis_helper.get_counter(key)
            
            if request_count >= self.rate_limit_requests:
                # Calculate retry after time
                retry_after = self.rate_limit_window - (current_time - window_start)
                return False, max(1, retry_after)
            
            return True, 0
            
        except Exception as e:
            logger.error(f"Error checking rate limit for key {key}: {e}")
            # Allow request if rate limiting fails
            return True, 0
    
    async def _record_request(self, key: str):
        """Record a request for rate limiting"""
        try:
            current_time = int(time.time())
            
            # Increment counter with TTL
            await self.redis_helper.increment_counter(key, ttl=self.rate_limit_window)
            
        except Exception as e:
            logger.error(f"Error recording request for key {key}: {e}")


class RateLimitConfig:
    """Rate limiting configuration for different endpoints"""
    
    # Rate limits per endpoint type
    WEBHOOK_LIMITS = {
        "requests": 10,  # 10 requests per window
        "window": 60,    # 60 seconds
    }
    
    CONTEST_JOIN_LIMITS = {
        "requests": 5,   # 5 joins per window
        "window": 300,   # 5 minutes
    }
    
    AUTH_LIMITS = {
        "requests": 10,  # 10 auth attempts per window
        "window": 300,   # 5 minutes
    }
    
    WITHDRAWAL_LIMITS = {
        "requests": 3,   # 3 withdrawals per window
        "window": 3600,  # 1 hour
    }
    
    @classmethod
    def get_limits_for_endpoint(cls, endpoint_type: str) -> Dict[str, int]:
        """Get rate limits for specific endpoint type"""
        limits_map = {
            "webhook": cls.WEBHOOK_LIMITS,
            "contest_join": cls.CONTEST_JOIN_LIMITS,
            "auth": cls.AUTH_LIMITS,
            "withdrawal": cls.WITHDRAWAL_LIMITS,
        }
        return limits_map.get(endpoint_type, {"requests": 30, "window": 60})


def create_rate_limit_middleware(redis_client=None):
    """Create rate limiting middleware instance"""
    return RateLimitMiddleware(None, redis_client)
