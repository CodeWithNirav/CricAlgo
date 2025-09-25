"""
Unit tests for invitation code enforcement across all bot features
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.bot.handlers.commands import (
    check_invitation_code_access,
    require_invitation_code,
    balance_command,
    deposit_command,
    contests_command,
    withdraw_command,
    menu_command,
    help_command
)
from app.models.user import User
from app.models.enums import UserStatus


@pytest.fixture
def mock_message():
    """Mock Telegram message"""
    message = MagicMock()
    message.from_user.id = 12345
    message.from_user.username = "testuser"
    message.chat.id = 67890
    message.answer = AsyncMock()
    return message


@pytest.fixture
def mock_user():
    """Mock user object"""
    user = User(
        id=uuid4(),
        telegram_id=12345,
        username="testuser",
        status=UserStatus.ACTIVE
    )
    return user


class TestInvitationCodeEnforcement:
    """Test invitation code enforcement across all bot features"""
    
    @pytest.mark.asyncio
    async def test_check_invitation_code_access_existing_user(self, mock_user):
        """Test access check for existing user"""
        with patch('app.bot.handlers.commands.async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = mock_user
            
            has_access, error_msg = await check_invitation_code_access(12345)
            
            assert has_access is True
            assert error_msg == ""
    
    @pytest.mark.asyncio
    async def test_check_invitation_code_access_no_user(self):
        """Test access check for non-existent user"""
        with patch('app.bot.handlers.commands.async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = None
            
            has_access, error_msg = await check_invitation_code_access(12345)
            
            assert has_access is False
            assert "invitation code" in error_msg
    
    @pytest.mark.asyncio
    async def test_balance_command_blocks_without_invitation(self, mock_message):
        """Test balance command blocks users without invitation code"""
        with patch('app.bot.handlers.commands.check_invitation_code_access') as mock_check, \
             patch('app.bot.handlers.commands.require_invitation_code') as mock_require:
            
            # Mock no access
            mock_check.return_value = (False, "No invitation code")
            
            await balance_command(mock_message)
            
            # Verify invitation code was required
            mock_require.assert_called_once_with(mock_message)
    
    @pytest.mark.asyncio
    async def test_balance_command_allows_with_invitation(self, mock_message, mock_user):
        """Test balance command allows users with invitation code"""
        with patch('app.bot.handlers.commands.check_invitation_code_access') as mock_check, \
             patch('app.bot.handlers.commands.async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user, \
             patch('app.bot.handlers.commands.get_wallet_for_user') as mock_get_wallet:
            
            # Mock access granted
            mock_check.return_value = (True, "")
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = mock_user
            mock_get_wallet.return_value = MagicMock()
            
            await balance_command(mock_message)
            
            # Verify balance was shown (message.answer was called)
            mock_message.answer.assert_called()
    
    @pytest.mark.asyncio
    async def test_deposit_command_blocks_without_invitation(self, mock_message):
        """Test deposit command blocks users without invitation code"""
        with patch('app.bot.handlers.commands.check_invitation_code_access') as mock_check, \
             patch('app.bot.handlers.commands.require_invitation_code') as mock_require:
            
            # Mock no access
            mock_check.return_value = (False, "No invitation code")
            
            await deposit_command(mock_message, None)
            
            # Verify invitation code was required
            mock_require.assert_called_once_with(mock_message)
    
    @pytest.mark.asyncio
    async def test_contests_command_blocks_without_invitation(self, mock_message):
        """Test contests command blocks users without invitation code"""
        with patch('app.bot.handlers.commands.check_invitation_code_access') as mock_check, \
             patch('app.bot.handlers.commands.require_invitation_code') as mock_require:
            
            # Mock no access
            mock_check.return_value = (False, "No invitation code")
            
            await contests_command(mock_message)
            
            # Verify invitation code was required
            mock_require.assert_called_once_with(mock_message)
    
    @pytest.mark.asyncio
    async def test_withdraw_command_blocks_without_invitation(self, mock_message):
        """Test withdraw command blocks users without invitation code"""
        with patch('app.bot.handlers.commands.check_invitation_code_access') as mock_check, \
             patch('app.bot.handlers.commands.require_invitation_code') as mock_require:
            
            # Mock no access
            mock_check.return_value = (False, "No invitation code")
            
            await withdraw_command(mock_message, None)
            
            # Verify invitation code was required
            mock_require.assert_called_once_with(mock_message)
    
    @pytest.mark.asyncio
    async def test_menu_command_blocks_without_invitation(self, mock_message):
        """Test menu command blocks users without invitation code"""
        with patch('app.bot.handlers.commands.check_invitation_code_access') as mock_check, \
             patch('app.bot.handlers.commands.require_invitation_code') as mock_require:
            
            # Mock no access
            mock_check.return_value = (False, "No invitation code")
            
            await menu_command(mock_message)
            
            # Verify invitation code was required
            mock_require.assert_called_once_with(mock_message)
    
    @pytest.mark.asyncio
    async def test_help_command_blocks_without_invitation(self, mock_message):
        """Test help command blocks users without invitation code"""
        with patch('app.bot.handlers.commands.check_invitation_code_access') as mock_check, \
             patch('app.bot.handlers.commands.require_invitation_code') as mock_require:
            
            # Mock no access
            mock_check.return_value = (False, "No invitation code")
            
            await help_command(mock_message)
            
            # Verify invitation code was required
            mock_require.assert_called_once_with(mock_message)
    
    @pytest.mark.asyncio
    async def test_require_invitation_code_message(self, mock_message):
        """Test invitation code requirement message"""
        await require_invitation_code(mock_message)
        
        # Verify message was sent
        mock_message.answer.assert_called_once()
        
        # Check message content
        call_args = mock_message.answer.call_args
        message_text = call_args[0][0]
        assert "Access Restricted" in message_text
        assert "invitation code" in message_text
        assert "YOUR_CODE" in message_text
