"""
Unit tests for user deletion functionality
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.api.admin_manage import delete_user
from app.models.user import User
from app.models.wallet import Wallet
from app.models.enums import UserStatus


@pytest.fixture
def mock_admin():
    """Mock admin user"""
    admin = MagicMock()
    admin.username = "test_admin"
    admin.id = uuid4()
    return admin


@pytest.fixture
def mock_user():
    """Mock user to be deleted"""
    user = User(
        id=uuid4(),
        telegram_id=12345,
        username="testuser",
        status=UserStatus.ACTIVE
    )
    return user


class TestUserDeletion:
    """Test user deletion functionality"""
    
    @pytest.mark.asyncio
    async def test_delete_user_success(self, mock_admin, mock_user):
        """Test successful user deletion"""
        # Create mock database session
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.add = AsyncMock()
        
        # Mock user exists - need to mock the result object properly
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        result = await delete_user(
            user_id=str(mock_user.id),
            current_admin=mock_admin,
            db=mock_db
        )
        
        # Verify success response
        assert result["ok"] is True
        assert "deleted successfully" in result["message"]
        assert mock_user.username in result["message"]
    
    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, mock_admin):
        """Test deletion of non-existent user"""
        # Create mock database session
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        
        # Mock user not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        
        # Should raise HTTPException
        with pytest.raises(Exception):  # HTTPException
            await delete_user(
                user_id="non-existent-id",
                current_admin=mock_admin,
                db=mock_db
            )
    
    @pytest.mark.asyncio
    async def test_delete_user_audit_log_created(self, mock_admin, mock_user):
        """Test that audit log is created for user deletion"""
        # Create mock database session
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.add = AsyncMock()
        
        # Mock user exists
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result
        
        await delete_user(
            user_id=str(mock_user.id),
            current_admin=mock_admin,
            db=mock_db
        )
        
        # Verify audit log was added
        mock_db.add.assert_called()
        # Check that the last call was an AuditLog
        audit_log_call = mock_db.add.call_args[0][0]
        assert hasattr(audit_log_call, 'action')
        assert audit_log_call.action == "delete_user"
