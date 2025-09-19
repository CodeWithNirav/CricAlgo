"""
Unit tests to detect improper async session usage
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db


def test_get_db_is_async_generator():
    """Test that get_db() returns an async generator context manager"""
    # get_db should be an async context manager, not a direct session
    db_context = get_db()
    
    # It should be an async generator context manager
    assert hasattr(db_context, '__aenter__')
    assert hasattr(db_context, '__aexit__')
    assert hasattr(db_context, '__anext__')
    
    # It should not be an AsyncSession directly
    assert not isinstance(db_context, AsyncSession)


@pytest.mark.asyncio
async def test_get_db_yields_async_session():
    """Test that get_db() yields an AsyncSession when used as context manager"""
    async with get_db() as session:
        assert isinstance(session, AsyncSession)
        assert hasattr(session, 'execute')
        assert hasattr(session, 'commit')
        assert hasattr(session, 'rollback')
        assert hasattr(session, 'close')


def test_get_db_usage_pattern():
    """Test that get_db() follows the correct usage pattern"""
    # This test documents the correct usage pattern
    # get_db() should be used as: async with get_db() as session:
    # NOT as: session = get_db()
    
    db_context = get_db()
    
    # The context manager should not be used directly as a session
    with pytest.raises(AttributeError):
        # This should fail because db_context is not an AsyncSession
        db_context.execute("SELECT 1")
