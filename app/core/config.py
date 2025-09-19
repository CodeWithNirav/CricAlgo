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
