"""
Unit tests for bot callbacks
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from uuid import uuid4

from app.bot.handlers.callbacks import (
    join_contest_callback,
    view_my_contests_callback,
    support_callback,
    settings_callback
)
from app.models.user import User
from app.models.wallet import Wallet
from app.models.contest import Contest
from app.models.contest_entry import ContestEntry
from app.models.enums import UserStatus


@pytest.fixture
def mock_callback_query():
    """Mock Telegram callback query"""
    callback = MagicMock()
    callback.from_user.id = 12345
    callback.from_user.username = "testuser"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.data = "join_contest:123e4567-e89b-12d3-a456-426614174000"
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


@pytest.fixture
def mock_contest_entry():
    """Mock contest entry object"""
    entry = ContestEntry(
        id=uuid4(),
        contest_id=uuid4(),
        user_id=uuid4(),
        entry_fee=Decimal('10.00')
    )
    return entry


class TestJoinContestCallback:
    """Test join contest callback functionality"""
    
    @pytest.mark.asyncio
    async def test_join_contest_user_not_found(self, mock_callback_query):
        """Test join contest when user not found"""
        with patch('app.bot.handlers.callbacks.get_async_session') as mock_session, \
             patch('app.bot.handlers.callbacks.get_user_by_telegram_id') as mock_get_user:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = None
            
            await join_contest_callback(mock_callback_query)
            
            mock_callback_query.message.edit_text.assert_called_once_with(
                "❌ User not found. Please use /start first."
            )
    
    @pytest.mark.asyncio
    async def test_join_contest_contest_not_found(self, mock_callback_query, mock_user):
        """Test join contest when contest not found"""
        with patch('app.bot.handlers.callbacks.get_async_session') as mock_session, \
             patch('app.bot.handlers.callbacks.get_user_by_telegram_id') as mock_get_user, \
             patch('app.bot.handlers.callbacks.get_contest_by_id') as mock_get_contest:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = mock_user
            mock_get_contest.return_value = None
            
            await join_contest_callback(mock_callback_query)
            
            mock_callback_query.message.edit_text.assert_called_once_with(
                "❌ Contest not found or no longer available."
            )
    
    @pytest.mark.asyncio
    async def test_join_contest_insufficient_balance(self, mock_callback_query, mock_user, mock_contest):
        """Test join contest with insufficient balance"""
        with patch('app.bot.handlers.callbacks.get_async_session') as mock_session, \
             patch('app.bot.handlers.callbacks.get_user_by_telegram_id') as mock_get_user, \
             patch('app.bot.handlers.callbacks.get_contest_by_id') as mock_get_contest, \
             patch('app.bot.handlers.callbacks.get_wallet_for_user') as mock_get_wallet, \
             patch('app.bot.handlers.callbacks.is_idempotent_operation') as mock_idempotent:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = mock_user
            mock_get_contest.return_value = mock_contest
            mock_idempotent.return_value = False
            
            # Create wallet with insufficient balance
            insufficient_wallet = Wallet(
                id=uuid4(),
                user_id=uuid4(),
                deposit_balance=Decimal('5.00'),  # Less than entry fee
                winning_balance=Decimal('0.00'),
                bonus_balance=Decimal('0.00')
            )
            mock_get_wallet.return_value = insufficient_wallet
            
            await join_contest_callback(mock_callback_query)
            
            mock_callback_query.message.edit_text.assert_called_once()
            
            # Check error message contains expected text
            call_args = mock_callback_query.message.edit_text.call_args[0][0]
            assert "Insufficient balance" in call_args
    
    @pytest.mark.asyncio
    async def test_join_contest_success(self, mock_callback_query, mock_user, mock_contest, mock_wallet):
        """Test join contest success"""
        with patch('app.bot.handlers.callbacks.get_async_session') as mock_session, \
             patch('app.bot.handlers.callbacks.get_user_by_telegram_id') as mock_get_user, \
             patch('app.bot.handlers.callbacks.get_contest_by_id') as mock_get_contest, \
             patch('app.bot.handlers.callbacks.get_wallet_for_user') as mock_get_wallet, \
             patch('app.bot.handlers.callbacks.get_contest_entries') as mock_get_entries, \
             patch('app.bot.handlers.callbacks.debit_for_contest_entry') as mock_debit, \
             patch('app.bot.handlers.callbacks.create_contest_entry') as mock_create_entry, \
             patch('app.bot.handlers.callbacks.is_idempotent_operation') as mock_idempotent:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = mock_user
            mock_get_contest.return_value = mock_contest
            mock_get_wallet.return_value = mock_wallet
            mock_get_entries.return_value = []  # No existing entries
            mock_debit.return_value = (True, None)  # Successful debit
            mock_create_entry.return_value = mock_contest_entry()
            mock_idempotent.return_value = False
            
            await join_contest_callback(mock_callback_query)
            
            mock_callback_query.message.edit_text.assert_called_once()
            
            # Check success message contains expected text
            call_args = mock_callback_query.message.edit_text.call_args[0][0]
            assert "Successfully joined contest!" in call_args
            assert "Test Contest" in call_args


class TestViewMyContestsCallback:
    """Test view my contests callback functionality"""
    
    @pytest.mark.asyncio
    async def test_view_my_contests_user_not_found(self, mock_callback_query):
        """Test view my contests when user not found"""
        with patch('app.bot.handlers.callbacks.get_async_session') as mock_session, \
             patch('app.bot.handlers.callbacks.get_user_by_telegram_id') as mock_get_user:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = None
            
            await view_my_contests_callback(mock_callback_query)
            
            mock_callback_query.message.edit_text.assert_called_once_with(
                "❌ User not found. Please use /start first."
            )
    
    @pytest.mark.asyncio
    async def test_view_my_contests_no_entries(self, mock_callback_query, mock_user):
        """Test view my contests when no entries"""
        with patch('app.bot.handlers.callbacks.get_async_session') as mock_session, \
             patch('app.bot.handlers.callbacks.get_user_by_telegram_id') as mock_get_user, \
             patch('app.bot.handlers.callbacks.get_user_contest_entries') as mock_get_entries:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = mock_user
            mock_get_entries.return_value = []
            
            await view_my_contests_callback(mock_callback_query)
            
            mock_callback_query.message.edit_text.assert_called_once()
            
            # Check message contains expected text
            call_args = mock_callback_query.message.edit_text.call_args[0][0]
            assert "haven't joined any contests yet" in call_args


class TestSupportCallback:
    """Test support callback functionality"""
    
    @pytest.mark.asyncio
    async def test_support_callback(self, mock_callback_query):
        """Test support callback"""
        await support_callback(mock_callback_query)
        
        mock_callback_query.message.edit_text.assert_called_once()
        
        # Check support message contains expected text
        call_args = mock_callback_query.message.edit_text.call_args[0][0]
        assert "Support" in call_args
        assert "support@cricalgo.com" in call_args


class TestSettingsCallback:
    """Test settings callback functionality"""
    
    @pytest.mark.asyncio
    async def test_settings_callback_user_not_found(self, mock_callback_query):
        """Test settings callback when user not found"""
        with patch('app.bot.handlers.callbacks.get_async_session') as mock_session, \
             patch('app.bot.handlers.callbacks.get_user_by_telegram_id') as mock_get_user:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = None
            
            await settings_callback(mock_callback_query)
            
            mock_callback_query.message.edit_text.assert_called_once_with(
                "❌ User not found. Please use /start first."
            )
    
    @pytest.mark.asyncio
    async def test_settings_callback_success(self, mock_callback_query, mock_user):
        """Test settings callback success"""
        with patch('app.bot.handlers.callbacks.get_async_session') as mock_session, \
             patch('app.bot.handlers.callbacks.get_user_by_telegram_id') as mock_get_user:
            
            # Setup mocks
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            mock_get_user.return_value = mock_user
            
            await settings_callback(mock_callback_query)
            
            mock_callback_query.message.edit_text.assert_called_once()
            
            # Check settings message contains expected text
            call_args = mock_callback_query.message.edit_text.call_args[0][0]
            assert "Settings" in call_args
            assert "testuser" in call_args
            assert "12345" in call_args