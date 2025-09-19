"""
Test configuration and fixtures for CricAlgo

This module provides shared fixtures for database, Redis, and application testing.
It supports both SQLite (fast) and PostgreSQL (realistic) testing modes.

Usage:
    # Run with SQLite (fast, in-memory)
    pytest tests/

    # Run with PostgreSQL (realistic, requires running postgres)
    DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/cricalgo_test pytest tests/

    # Run with custom database URL
    pytest --db-url=postgresql+asyncpg://user:pass@host:port/db tests/
"""

import os
import asyncio
import pytest
from typing import AsyncGenerator, Generator
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import text
import redis.asyncio as redis
from httpx import AsyncClient
from fastapi import FastAPI

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.models.enums import UserStatus
from app.repos.user_repo import create_user
from app.repos.wallet_repo import create_wallet_for_user


def pytest_addoption(parser):
    """Add custom command line options for pytest."""
    parser.addoption(
        "--db-url",
        action="store",
        default=os.getenv("DATABASE_URL"),
        help="Database URL for testing (defaults to DATABASE_URL env var)"
    )
    parser.addoption(
        "--redis-url", 
        action="store",
        default=os.getenv("REDIS_URL", "redis://localhost:6379/1"),
        help="Redis URL for testing"
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def db_url(request):
    """Get database URL from command line or environment."""
    url = request.config.getoption("--db-url")
    if not url:
        # Default to SQLite for fast tests
        url = "sqlite+aiosqlite:///:memory:"
    return url


@pytest.fixture(scope="session")
def redis_url(request):
    """Get Redis URL from command line or environment."""
    return request.config.getoption("--redis-url")


@pytest.fixture(scope="session")
async def db_engine(db_url):
    """
    Create database engine and run migrations.
    
    This fixture:
    1. Creates a test database engine
    2. Creates all tables using Alembic migrations
    3. Yields the engine for use in tests
    4. Cleans up after all tests complete
    """
    # Determine if we're using PostgreSQL or SQLite
    is_postgres = "postgresql" in db_url
    is_sqlite = "sqlite" in db_url
    
    if is_sqlite:
        # Use in-memory SQLite for fast tests
        engine = create_async_engine(
            db_url,
            echo=False,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False}
        )
    else:
        # Use PostgreSQL with connection pooling
        engine = create_async_engine(
            db_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True
        )
    
    # Create all tables
    async with engine.begin() as conn:
        if is_postgres:
            # For PostgreSQL, create a test schema
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS test_schema"))
            await conn.execute(text("SET search_path TO test_schema, public"))
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    if is_postgres:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA IF EXISTS test_schema CASCADE"))
    
    await engine.dispose()


@pytest.fixture
async def async_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create an async database session with transaction rollback.
    
    This fixture:
    1. Creates a new session
    2. Begins a savepoint (nested transaction)
    3. Yields the session for test use
    4. Rolls back to savepoint after test (ensuring test isolation)
    """
    async_session_factory = async_sessionmaker(
        db_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    async with async_session_factory() as session:
        # Begin a savepoint for rollback
        await session.begin_nested()
        
        try:
            yield session
        finally:
            # Rollback to savepoint to ensure test isolation
            await session.rollback()


@pytest.fixture
async def redis_client(redis_url):
    """
    Create Redis client with test database isolation.
    
    This fixture:
    1. Connects to Redis
    2. Flushes the test database before each test
    3. Yields the client for test use
    4. Flushes the test database after each test
    """
    # Use a separate Redis database for tests
    test_redis_url = redis_url.replace("/0", "/1")  # Use DB 1 for tests
    
    redis_client = redis.from_url(test_redis_url, decode_responses=True)
    
    # Flush test database before test
    await redis_client.flushdb()
    
    yield redis_client
    
    # Flush test database after test
    await redis_client.flushdb()
    await redis_client.close()


@pytest.fixture
async def test_app(db_engine, redis_client) -> FastAPI:
    """
    Create test FastAPI app with overridden dependencies.
    
    This fixture:
    1. Creates a test app instance
    2. Overrides database dependency to use test session
    3. Overrides Redis dependency to use test client
    4. Returns the configured app
    """
    # Create async session factory for dependency injection
    async_session_factory = async_sessionmaker(
        db_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    async def get_test_db():
        """Test database dependency."""
        async with async_session_factory() as session:
            yield session
    
    async def get_test_redis():
        """Test Redis dependency."""
        return redis_client
    
    # Override dependencies
    app.dependency_overrides[get_db] = get_test_db
    # Note: Add Redis dependency override when implemented
    
    return app


@pytest.fixture
async def test_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """
    Create HTTP test client for API testing.
    
    This fixture:
    1. Creates an AsyncClient with the test app
    2. Yields the client for test use
    3. Properly closes the client after test
    """
    async with AsyncClient(app=test_app, base_url="http://test") as client:
        yield client


# Test data fixtures
@pytest.fixture
async def test_user(async_session: AsyncSession) -> User:
    """Create a test user with wallet."""
    import time
    unique_telegram_id = int(time.time() * 1000) % 1000000  # Use timestamp for uniqueness
    user = await create_user(
        session=async_session,
        telegram_id=unique_telegram_id,
        username="testuser",
        status=UserStatus.ACTIVE.value
    )
    
    # Create wallet for user
    await create_wallet_for_user(async_session, user.id)
    
    return user


@pytest.fixture
async def test_user_with_balance(async_session: AsyncSession) -> User:
    """Create a test user with wallet and initial balance."""
    from app.repos.wallet_repo import update_balances_atomic
    
    user = await create_user(
        session=async_session,
        telegram_id=67890,
        username="richuser",
        status=UserStatus.ACTIVE.value
    )
    
    # Create wallet for user
    await create_wallet_for_user(async_session, user.id)
    
    # Add some balance
    await update_balances_atomic(
        async_session,
        user.id,
        deposit_delta=Decimal('100.00'),
        bonus_delta=Decimal('50.00'),
        winning_delta=Decimal('25.00')
    )
    
    return user


@pytest.fixture
async def test_transaction(async_session: AsyncSession, test_user: User) -> Transaction:
    """Create a test transaction."""
    from app.repos.transaction_repo import create_transaction
    
    transaction = await create_transaction(
        session=async_session,
        user_id=test_user.id,
        tx_type="deposit",
        amount=Decimal('100.00'),
        currency="USDT",
        related_entity="deposit_request",
        related_id=uuid4(),
        tx_metadata={"tx_hash": "0x1234567890abcdef", "confirmations": 0}
    )
    
    return transaction


# Utility fixtures for common test patterns
@pytest.fixture
def sample_tx_hash():
    """Generate a sample transaction hash for testing."""
    return f"0x{''.join([f'{i:02x}' for i in range(32)])}"


@pytest.fixture
def sample_webhook_payload(sample_tx_hash):
    """Generate a sample webhook payload for testing."""
    return {
        "tx_hash": sample_tx_hash,
        "confirmations": 12,
        "block_number": 12345678,
        "status": "confirmed"
    }


# Markers for different test types
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_docker: mark test as requiring Docker"
    )


# Skip E2E tests by default unless RUN_E2E=1
def pytest_collection_modifyitems(config, items):
    """Modify test collection to skip E2E tests by default."""
    if not os.getenv("RUN_E2E"):
        skip_e2e = pytest.mark.skip(reason="requires RUN_E2E=1 environment variable")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)
