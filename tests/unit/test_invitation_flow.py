"""
Unit tests for invitation code flow
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from uuid import uuid4

from app.bot.handlers.commands import handle_user_start
from app.models.user import User
from app.models.wallet import Wallet
from app.models.invitation_code import InvitationCode
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
def mock_invitation_code():
    """Mock invitation code object"""
    code = InvitationCode(
        code="TEST123",
        max_uses=10,
        uses=0,
        enabled=True
    )
    return code


class TestInvitationFlow:
    """Test invitation code flow functionality"""
    
    @pytest.mark.asyncio
    async def test_new_user_without_invite_code(self, mock_message):
        """Test new user without invitation code is blocked"""
        with patch('app.bot.handlers.commands.async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = None
            
            await handle_user_start(
                telegram_id=12345,
                username="testuser",
                chat_id=67890,
                invite_code=None,
                message=mock_message
            )
            
            # Verify access is blocked
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "Access Restricted" in call_args
            assert "invitation code" in call_args
    
    @pytest.mark.asyncio
    async def test_new_user_with_invalid_invite_code(self, mock_message):
        """Test new user with invalid invitation code is blocked"""
        with patch('app.bot.handlers.commands.async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user, \
             patch('app.bot.handlers.commands.validate_invite_code') as mock_validate:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = None
            mock_validate.return_value = (False, "Invalid invite code")
            
            await handle_user_start(
                telegram_id=12345,
                username="testuser",
                chat_id=67890,
                invite_code="INVALID123",
                message=mock_message
            )
            
            # Verify access is blocked
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "Invalid Invitation Code" in call_args
            assert "Invalid invite code" in call_args
    
    @pytest.mark.asyncio
    async def test_new_user_with_valid_invite_code(self, mock_message, mock_invitation_code):
        """Test new user with valid invitation code is allowed"""
        with patch('app.bot.handlers.commands.async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user, \
             patch('app.bot.handlers.commands.validate_invite_code') as mock_validate, \
             patch('app.bot.handlers.commands.create_user') as mock_create_user, \
             patch('app.bot.handlers.commands.create_wallet_for_user') as mock_create_wallet, \
             patch('app.bot.handlers.commands.save_chat_id') as mock_save_chat, \
             patch('app.bot.handlers.commands.validate_and_use_code') as mock_use_code:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = None
            mock_validate.return_value = (True, "Invite code is valid")
            mock_use_code.return_value = (True, "Invite code applied successfully")
            
            # Mock user and wallet creation
            mock_user = User(
                id=uuid4(),
                telegram_id=12345,
                username="testuser",
                status=UserStatus.ACTIVE
            )
            mock_wallet = Wallet(
                id=uuid4(),
                user_id=mock_user.id,
                deposit_balance=Decimal('0.00'),
                winning_balance=Decimal('0.00'),
                bonus_balance=Decimal('5.00')
            )
            
            mock_create_user.return_value = mock_user
            mock_create_wallet.return_value = mock_wallet
            
            await handle_user_start(
                telegram_id=12345,
                username="testuser",
                chat_id=67890,
                invite_code="TEST123",
                message=mock_message
            )
            
            # Verify user creation and invitation code usage
            mock_create_user.assert_called_once()
            mock_create_wallet.assert_called_once()
            mock_save_chat.assert_called_once()
            mock_use_code.assert_called_once()
            
            # Verify welcome message
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "Welcome to CricAlgo!" in call_args
            assert "Bonus" in call_args
    
    @pytest.mark.asyncio
    async def test_existing_user_bypasses_invitation_requirement(self, mock_message):
        """Test existing user can access bot without invitation code"""
        with patch('app.bot.handlers.commands.async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user, \
             patch('app.bot.handlers.commands.save_chat_id') as mock_save_chat:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_user = User(
                id=uuid4(),
                telegram_id=12345,
                username="testuser",
                status=UserStatus.ACTIVE
            )
            mock_get_user.return_value = mock_user
            
            await handle_user_start(
                telegram_id=12345,
                username="testuser",
                chat_id=67890,
                invite_code=None,
                message=mock_message
            )
            
            # Verify existing user can access
            mock_save_chat.assert_called_once()
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "Welcome back to CricAlgo!" in call_args
