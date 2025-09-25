"""
Unit tests for improved invitation code flow
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.bot.handlers.commands import start_command, enter_invite_code_callback, process_invite_code
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
def mock_callback_query():
    """Mock Telegram callback query"""
    callback = MagicMock()
    callback.from_user.id = 12345
    callback.from_user.username = "testuser"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    return callback


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


class TestImprovedInvitationFlow:
    """Test improved invitation code flow"""
    
    @pytest.mark.asyncio
    async def test_start_command_existing_user(self, mock_message, mock_user):
        """Test /start command for existing user shows welcome back"""
        with patch('app.bot.handlers.commands.async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = mock_user
            
            await start_command(mock_message)
            
            # Verify welcome back message
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "Welcome back to CricAlgo!" in call_args
            assert "already registered" in call_args
    
    @pytest.mark.asyncio
    async def test_start_command_new_user(self, mock_message):
        """Test /start command for new user asks for invitation code"""
        with patch('app.bot.handlers.commands.async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = None
            
            await start_command(mock_message)
            
            # Verify invitation code request
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "Welcome to CricAlgo!" in call_args
            assert "invitation code" in call_args
    
    @pytest.mark.asyncio
    async def test_enter_invite_code_callback(self, mock_callback_query):
        """Test enter invitation code callback"""
        mock_state = MagicMock()
        mock_state.set_state = AsyncMock()
        
        await enter_invite_code_callback(mock_callback_query, mock_state)
        
        # Verify callback was answered
        mock_callback_query.answer.assert_called_once()
        
        # Verify state was set
        mock_state.set_state.assert_called_once()
        
        # Verify message was edited
        mock_callback_query.message.edit_text.assert_called_once()
        call_args = mock_callback_query.message.edit_text.call_args[0][0]
        assert "Enter Your Invitation Code" in call_args
        assert "ABC123" in call_args  # Example code
    
    @pytest.mark.asyncio
    async def test_process_invite_code_valid(self, mock_message, mock_user):
        """Test processing valid invitation code"""
        with patch('app.bot.handlers.commands.handle_user_start') as mock_handle_start:
            mock_message.text = "ABC123"
            mock_state = MagicMock()
            mock_state.clear = AsyncMock()
            
            await process_invite_code(mock_message, mock_state)
            
            # Verify handle_user_start was called with the code
            mock_handle_start.assert_called_once()
            call_args = mock_handle_start.call_args[1]  # keyword arguments
            assert call_args['invite_code'] == "ABC123"
            
            # Verify state was cleared
            mock_state.clear.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_invite_code_empty(self, mock_message):
        """Test processing empty invitation code"""
        mock_message.text = ""
        
        await process_invite_code(mock_message, MagicMock())
        
        # Verify error message
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Please enter a valid invitation code" in call_args
    
    @pytest.mark.asyncio
    async def test_process_invite_code_whitespace(self, mock_message):
        """Test processing whitespace-only invitation code"""
        mock_message.text = "   "
        
        await process_invite_code(mock_message, MagicMock())
        
        # Verify error message
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "Please enter a valid invitation code" in call_args
