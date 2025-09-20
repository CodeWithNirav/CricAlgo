"""
Async database session management with connection pooling
"""

import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings

# Pool configuration with environment variable overrides
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", settings.db_pool_size))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", settings.db_max_overflow))

# Create async engine with optimized pooling
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=30,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Export for use in Celery tasks
async_session = AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session for FastAPI dependency injection.
    Provides proper session lifecycle management with connection pooling.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_session() -> AsyncSession:
    """
    Get a database session for dependency injection.
    Use this for FastAPI dependency injection.
    """
    return AsyncSessionLocal()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async database session generator.
    Use this for bot handlers and other async contexts.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()