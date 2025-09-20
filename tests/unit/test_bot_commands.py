"""
Unit tests for bot commands
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from uuid import uuid4

from app.bot.handlers.commands import (
    start_command,
    balance_command,
    deposit_command,
    contests_command,
    help_command
)
from app.models.user import User
from app.models.wallet import Wallet
from app.models.contest import Contest
from app.models.enums import UserStatus


@pytest.fixture
def mock_message():
    """Mock Telegram message"""
    message = MagicMock()
    message.from_user.id = 12345
    message.from_user.username = "testuser"
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


@pytest.fixture
def mock_wallet():
    """Mock wallet object"""
    wallet = Wallet(
        id=uuid4(),
        user_id=uuid4(),
        deposit_balance=Decimal('100.00'),
        winning_balance=Decimal('50.00'),
        bonus_balance=Decimal('25.00')
    )
    return wallet


@pytest.fixture
def mock_contest():
    """Mock contest object"""
    contest = Contest(
        id=uuid4(),
        match_id=uuid4(),
        code="CONTEST_123",
        title="Test Contest",
        entry_fee=Decimal('10.00'),
        currency="USDT",
        max_players=100,
        prize_structure=[{"position": 1, "percentage": 50}],
        status="open"
    )
    return contest


class TestStartCommand:
    """Test start command functionality"""
    
    @pytest.mark.asyncio
    async def test_start_command_new_user(self, mock_message):
        """Test start command for new user"""
        with patch('app.bot.handlers.commands.get_async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user, \
             patch('app.bot.handlers.commands.create_user') as mock_create_user, \
             patch('app.bot.handlers.commands.create_wallet_for_user') as mock_create_wallet:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = None
            mock_create_user.return_value = mock_user()
            mock_create_wallet.return_value = mock_wallet()
            
            await start_command(mock_message)
            
            # Verify user creation
            mock_create_user.assert_called_once()
            mock_create_wallet.assert_called_once()
            mock_message.answer.assert_called_once()
            
            # Check welcome message contains expected text
            call_args = mock_message.answer.call_args[0][0]
            assert "Welcome to CricAlgo!" in call_args
            assert "account has been created" in call_args
    
    @pytest.mark.asyncio
    async def test_start_command_existing_user(self, mock_message, mock_user):
        """Test start command for existing user"""
        with patch('app.bot.handlers.commands.get_async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = mock_user
            
            await start_command(mock_message)
            
            # Verify no user creation
            mock_message.answer.assert_called_once()
            
            # Check welcome message contains expected text
            call_args = mock_message.answer.call_args[0][0]
            assert "Welcome back to CricAlgo!" in call_args


class TestBalanceCommand:
    """Test balance command functionality"""
    
    @pytest.mark.asyncio
    async def test_balance_command_user_not_found(self, mock_message):
        """Test balance command when user not found"""
        with patch('app.bot.handlers.commands.get_async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = None
            
            await balance_command(mock_message)
            
            mock_message.answer.assert_called_once_with(
                "Please use /start first to register your account."
            )
    
    @pytest.mark.asyncio
    async def test_balance_command_success(self, mock_message, mock_user, mock_wallet):
        """Test balance command success"""
        with patch('app.bot.handlers.commands.get_async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user, \
             patch('app.bot.handlers.commands.get_wallet_for_user') as mock_get_wallet:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = mock_user
            mock_get_wallet.return_value = mock_wallet
            
            await balance_command(mock_message)
            
            mock_message.answer.assert_called_once()
            
            # Check balance message contains expected text
            call_args = mock_message.answer.call_args[0][0]
            assert "Your Wallet Balance" in call_args
            assert "100.00" in call_args  # deposit balance
            assert "50.00" in call_args   # winning balance
            assert "25.00" in call_args   # bonus balance


class TestDepositCommand:
    """Test deposit command functionality"""
    
    @pytest.mark.asyncio
    async def test_deposit_command_user_not_found(self, mock_message):
        """Test deposit command when user not found"""
        with patch('app.bot.handlers.commands.get_async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = None
            
            await deposit_command(mock_message, None)
            
            mock_message.answer.assert_called_once_with(
                "Please use /start first to register your account."
            )
    
    @pytest.mark.asyncio
    async def test_deposit_command_success(self, mock_message, mock_user):
        """Test deposit command success"""
        with patch('app.bot.handlers.commands.get_async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = mock_user
            
            await deposit_command(mock_message, None)
            
            mock_message.answer.assert_called_once()
            
            # Check deposit message contains expected text
            call_args = mock_message.answer.call_args[0][0]
            assert "Deposit Instructions" in call_args
            assert "USDT" in call_args


class TestContestsCommand:
    """Test contests command functionality"""
    
    @pytest.mark.asyncio
    async def test_contests_command_user_not_found(self, mock_message):
        """Test contests command when user not found"""
        with patch('app.bot.handlers.commands.get_async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = None
            
            await contests_command(mock_message)
            
            mock_message.answer.assert_called_once_with(
                "Please use /start first to register your account."
            )
    
    @pytest.mark.asyncio
    async def test_contests_command_no_contests(self, mock_message, mock_user):
        """Test contests command when no contests available"""
        with patch('app.bot.handlers.commands.get_async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user, \
             patch('app.bot.handlers.commands.get_contests') as mock_get_contests:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = mock_user
            mock_get_contests.return_value = []
            
            await contests_command(mock_message)
            
            mock_message.answer.assert_called_once_with(
                "No contests available at the moment. Check back later!"
            )
    
    @pytest.mark.asyncio
    async def test_contests_command_success(self, mock_message, mock_user, mock_contest):
        """Test contests command success"""
        with patch('app.bot.handlers.commands.get_async_session') as mock_session, \
             patch('app.bot.handlers.commands.get_user_by_telegram_id') as mock_get_user, \
             patch('app.bot.handlers.commands.get_contests') as mock_get_contests:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = mock_user
            mock_get_contests.return_value = [mock_contest]
            
            await contests_command(mock_message)
            
            mock_message.answer.assert_called_once()
            
            # Check contests message contains expected text
            call_args = mock_message.answer.call_args[0][0]
            assert "Available Contests" in call_args
            assert "Test Contest" in call_args
            assert "10.00" in call_args  # entry fee


class TestHelpCommand:
    """Test help command functionality"""
    
    @pytest.mark.asyncio
    async def test_help_command(self, mock_message):
        """Test help command"""
        await help_command(mock_message)
        
        mock_message.answer.assert_called_once()
        
        # Check help message contains expected text
        call_args = mock_message.answer.call_args[0][0]
        assert "CricAlgo Bot Commands" in call_args
        assert "/start" in call_args
        assert "/balance" in call_args
        assert "/deposit" in call_args
        assert "/contests" in call_args
        assert "/help" in call_args
