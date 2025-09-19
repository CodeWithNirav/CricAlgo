"""
Integration tests for user repository operations

These tests verify the user repository's CRUD operations,
querying capabilities, and integration with the database layer.
"""

import pytest
from uuid import uuid4

from app.repos.user_repo import (
    create_user,
    get_user_by_id,
    get_user_by_username,
    get_user_by_telegram_id,
    update_user_status
)
from app.models.enums import UserStatus


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_creation_and_retrieval(async_session):
    """Test user creation and retrieval operations."""
    # Create user
    user = await create_user(
        session=async_session,
        telegram_id=12345,
        username="testuser",
        status=UserStatus.ACTIVE
    )
    
    assert user is not None
    assert user.id is not None
    assert user.telegram_id == 12345
    assert user.username == "testuser"
    assert user.status == UserStatus.ACTIVE
    assert user.created_at is not None
    
    # Retrieve user by ID
    retrieved_user = await get_user_by_id(async_session, user.id)
    assert retrieved_user is not None
    assert retrieved_user.id == user.id
    assert retrieved_user.telegram_id == 12345
    assert retrieved_user.username == "testuser"
    assert retrieved_user.status == UserStatus.ACTIVE
    
    # Retrieve user by username
    retrieved_user = await get_user_by_username(async_session, "testuser")
    assert retrieved_user is not None
    assert retrieved_user.id == user.id
    assert retrieved_user.username == "testuser"
    
    # Retrieve user by telegram_id
    retrieved_user = await get_user_by_telegram_id(async_session, 12345)
    assert retrieved_user is not None
    assert retrieved_user.id == user.id
    assert retrieved_user.telegram_id == 12345


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_status_updates(async_session):
    """Test user status update operations."""
    # Create user
    user = await create_user(
        session=async_session,
        telegram_id=67890,
        username="statususer",
        status=UserStatus.ACTIVE
    )
    
    # Update status to suspended
    updated_user = await update_user_status(
        async_session,
        user.id,
        UserStatus.SUSPENDED
    )
    
    assert updated_user is not None
    assert updated_user.id == user.id
    assert updated_user.status == UserStatus.SUSPENDED
    
    # Verify update persisted
    retrieved_user = await get_user_by_id(async_session, user.id)
    assert retrieved_user.status == UserStatus.SUSPENDED
    
    # Update status back to active
    updated_user = await update_user_status(
        async_session,
        user.id,
        UserStatus.ACTIVE
    )
    
    assert updated_user.status == UserStatus.ACTIVE
    
    # Verify final status
    retrieved_user = await get_user_by_id(async_session, user.id)
    assert retrieved_user.status == UserStatus.ACTIVE


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_uniqueness_constraints(async_session):
    """Test user uniqueness constraints."""
    # Create first user
    user1 = await create_user(
        session=async_session,
        telegram_id=11111,
        username="uniqueuser1",
        status=UserStatus.ACTIVE
    )
    
    assert user1 is not None
    
    # Try to create user with same telegram_id (should fail)
    try:
        user2 = await create_user(
            session=async_session,
            telegram_id=11111,  # Same telegram_id
            username="uniqueuser2",
            status=UserStatus.ACTIVE
        )
        pytest.fail("Should have failed due to duplicate telegram_id")
    except Exception as e:
        # Expected to fail due to unique constraint
        assert "duplicate" in str(e).lower() or "unique" in str(e).lower()
    
    # Try to create user with same username (should fail)
    try:
        user3 = await create_user(
            session=async_session,
            telegram_id=22222,
            username="uniqueuser1",  # Same username
            status=UserStatus.ACTIVE
        )
        pytest.fail("Should have failed due to duplicate username")
    except Exception as e:
        # Expected to fail due to unique constraint
        assert "duplicate" in str(e).lower() or "unique" in str(e).lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_query_by_different_criteria(async_session):
    """Test querying users by different criteria."""
    # Create multiple users with different statuses
    active_user = await create_user(
        session=async_session,
        telegram_id=10001,
        username="activeuser",
        status=UserStatus.ACTIVE
    )
    
    suspended_user = await create_user(
        session=async_session,
        telegram_id=10002,
        username="suspendeduser",
        status=UserStatus.SUSPENDED
    )
    
    inactive_user = await create_user(
        session=async_session,
        telegram_id=10003,
        username="inactiveuser",
        status=UserStatus.INACTIVE
    )
    
    # Query by different criteria
    user_by_id = await get_user_by_id(async_session, active_user.id)
    assert user_by_id.username == "activeuser"
    
    user_by_username = await get_user_by_username(async_session, "suspendeduser")
    assert user_by_username.status == UserStatus.SUSPENDED
    
    user_by_telegram = await get_user_by_telegram_id(async_session, 10003)
    assert user_by_telegram.username == "inactiveuser"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_not_found_handling(async_session):
    """Test handling when user doesn't exist."""
    fake_user_id = uuid4()
    
    # Try to get non-existent user by ID
    user = await get_user_by_id(async_session, fake_user_id)
    assert user is None
    
    # Try to get non-existent user by username
    user = await get_user_by_username(async_session, "nonexistentuser")
    assert user is None
    
    # Try to get non-existent user by telegram_id
    user = await get_user_by_telegram_id(async_session, 99999)
    assert user is None
    
    # Try to update non-existent user
    updated_user = await update_user_status(
        async_session,
        fake_user_id,
        UserStatus.ACTIVE
    )
    assert updated_user is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_username_case_sensitivity(async_session):
    """Test username case sensitivity handling."""
    # Create user with lowercase username
    user = await create_user(
        session=async_session,
        telegram_id=20001,
        username="caseuser",
        status=UserStatus.ACTIVE
    )
    
    # Try to query with different case (should not find)
    user_upper = await get_user_by_username(async_session, "CASEUSER")
    # This depends on database collation - PostgreSQL is case-sensitive by default
    # So this should return None
    assert user_upper is None
    
    # Query with correct case
    user_correct = await get_user_by_username(async_session, "caseuser")
    assert user_correct is not None
    assert user_correct.id == user.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_creation_with_different_statuses(async_session):
    """Test user creation with different status values."""
    statuses = [UserStatus.ACTIVE, UserStatus.INACTIVE, UserStatus.SUSPENDED]
    
    for i, status in enumerate(statuses):
        user = await create_user(
            session=async_session,
            telegram_id=30000 + i,
            username=f"statususer{i}",
            status=status
        )
        
        assert user is not None
        assert user.status == status
        
        # Verify status persisted
        retrieved_user = await get_user_by_id(async_session, user.id)
        assert retrieved_user.status == status


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_creation_timestamp(async_session):
    """Test user creation timestamp handling."""
    import time
    from datetime import datetime, timezone
    
    # Create user
    before_creation = datetime.now(timezone.utc)
    
    user = await create_user(
        session=async_session,
        telegram_id=40001,
        username="timestampuser",
        status=UserStatus.ACTIVE
    )
    
    after_creation = datetime.now(timezone.utc)
    
    # Verify created_at is within expected range
    assert user.created_at is not None
    assert before_creation <= user.created_at <= after_creation
    
    # Verify timestamp is timezone-aware
    assert user.created_at.tzinfo is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_large_telegram_id(async_session):
    """Test user creation with large telegram_id values."""
    # Telegram IDs can be very large integers
    large_telegram_id = 9223372036854775807  # Max int64
    
    user = await create_user(
        session=async_session,
        telegram_id=large_telegram_id,
        username="largeiduser",
        status=UserStatus.ACTIVE
    )
    
    assert user is not None
    assert user.telegram_id == large_telegram_id
    
    # Verify retrieval works
    retrieved_user = await get_user_by_telegram_id(async_session, large_telegram_id)
    assert retrieved_user is not None
    assert retrieved_user.id == user.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_username_length_limits(async_session):
    """Test user creation with username length limits."""
    # Test maximum length username (48 characters as per schema)
    max_username = "a" * 48
    
    user = await create_user(
        session=async_session,
        telegram_id=50001,
        username=max_username,
        status=UserStatus.ACTIVE
    )
    
    assert user is not None
    assert user.username == max_username
    assert len(user.username) == 48
    
    # Verify retrieval works
    retrieved_user = await get_user_by_username(async_session, max_username)
    assert retrieved_user is not None
    assert retrieved_user.id == user.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_user_concurrent_creation(async_session):
    """Test concurrent user creation to verify no race conditions."""
    import asyncio
    
    async def create_user_task(telegram_id, username):
        return await create_user(
            session=async_session,
            telegram_id=telegram_id,
            username=username,
            status=UserStatus.ACTIVE
        )
    
    # Create multiple users concurrently
    tasks = []
    for i in range(10):
        task = create_user_task(60000 + i, f"concurrentuser{i}")
        tasks.append(task)
    
    # Execute all tasks concurrently
    users = await asyncio.gather(*tasks)
    
    # Verify all users were created successfully
    assert len(users) == 10
    assert all(user is not None for user in users)
    
    # Verify all usernames are unique
    usernames = [user.username for user in users]
    assert len(set(usernames)) == 10
    
    # Verify all telegram_ids are unique
    telegram_ids = [user.telegram_id for user in users]
    assert len(set(telegram_ids)) == 10
