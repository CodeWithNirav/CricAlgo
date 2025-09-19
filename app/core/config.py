"""
Application configuration using Pydantic BaseSettings
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application settings
    app_name: str = "CricAlgo"
    app_env: str = "development"
    debug: bool = False
    
    # Database settings
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/cricalgo"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    
    # Redis settings
    redis_url: str = "redis://localhost:6379/0"
    
    # Celery settings
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    
    # JWT settings
    jwt_secret_key: str = "your-jwt-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    
    # Rate limiting settings
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60
    
    # Business settings
    platform_commission_pct: float = 5.0
    confirmation_threshold: int = 3
    currency: str = "USDT"
    
    # Webhook settings
    webhook_secret: Optional[str] = None
    
    # Telegram Bot settings
    telegram_bot_token: Optional[str] = None
    telegram_webhook_url: Optional[str] = None
    
    # Security settings
    secret_key: str = "your-secret-key-change-in-production"
    
    # API settings
    api_v1_prefix: str = "/api/v1"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
