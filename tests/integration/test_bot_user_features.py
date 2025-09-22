"""
Integration tests for bot user features
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from decimal import Decimal

from app.bot.handlers.commands import start_command, balance_command, deposit_command, withdraw_command, contests_command
from app.bot.handlers.callbacks import join_contest_callback, contest_details_callback
from app.repos.invite_code_repo import create_invite_code
from app.repos.deposit_repo import create_deposit_transaction
from app.repos.withdrawal_repo import create_withdrawal
from app.models.enums import UserStatus, ContestStatus


class MockMessage:
    def __init__(self, text, from_user_id, chat_id):
        self.text = text
        self.from_user = MockUser(from_user_id)
        self.chat = MockChat(chat_id)
    
    async def answer(self, text, reply_markup=None, parse_mode=None):
        self.last_answer = text
        self.last_reply_markup = reply_markup
        self.last_parse_mode = parse_mode


class MockUser:
    def __init__(self, user_id):
        self.id = user_id
        self.username = f"user_{user_id}"


class MockChat:
    def __init__(self, chat_id):
        self.id = chat_id


class MockCallbackQuery:
    def __init__(self, data, from_user_id, message):
        self.data = data
        self.from_user = MockUser(from_user_id)
        self.message = message
    
    async def answer(self):
        pass
    
    async def edit_text(self, text, reply_markup=None):
        self.last_edit_text = text
        self.last_reply_markup = reply_markup


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_command_with_invite_code(async_session):
    """Test /start command with valid invite code"""
    # Create invite code
    invite_code = await create_invite_code(
        async_session,
        code="TEST123",
        max_uses=5
    )
    
    # Mock message
    message = MockMessage("/start TEST123", 12345, 67890)
    
    # Mock state
    state = AsyncMock()
    
    with patch('app.bot.handlers.commands.async_session', return_value=async_session):
        await start_command(message)
    
    # Verify response
    assert "Welcome to CricAlgo" in message.last_answer
    assert "bonus" in message.last_answer.lower()
    assert "5.00 USDT" in message.last_answer


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_command_with_invalid_invite_code(async_session):
    """Test /start command with invalid invite code for new user"""
    # Mock message for new user (different telegram_id)
    message = MockMessage("/start INVALID", 99999, 67890)
    
    # Mock state
    state = AsyncMock()
    
    with patch('app.bot.handlers.commands.async_session', return_value=async_session):
        await start_command(message)
    
    # Verify response
    assert "Invalid invite code" in message.last_answer
    assert "try again" in message.last_answer.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deposit_command_shows_user_address(async_session):
    """Test deposit command shows user-specific address and reference"""
    # Mock message
    message = MockMessage("/deposit", 12345, 67890)
    
    # Mock state
    state = AsyncMock()
    
    with patch('app.bot.handlers.commands.async_session', return_value=async_session):
        await deposit_command(message, state)
    
    # Verify response
    assert "Deposit Instructions" in message.last_answer
    assert "Deposit Address:" in message.last_answer
    assert "Deposit Reference" in message.last_answer
    # Check that keyboard was sent (button text is in reply_markup, not message text)
    assert message.last_reply_markup is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_withdraw_command_insufficient_balance(async_session):
    """Test withdraw command with insufficient balance"""
    from app.repos.user_repo import create_user
    from app.repos.wallet_repo import create_wallet_for_user
    from app.models.enums import UserStatus
    
    # Create user with no balance
    user = await create_user(
        session=async_session,
        telegram_id=99998,
        username="test_user_no_balance",
        status=UserStatus.ACTIVE
    )
    await create_wallet_for_user(async_session, user.id)
    
    # Mock message for user with no balance
    message = MockMessage("/withdraw", 99998, 67890)
    
    # Mock state
    state = AsyncMock()
    
    with patch('app.bot.handlers.commands.async_session', return_value=async_session):
        await withdraw_command(message, state)
    
    # Verify response
    assert "Insufficient balance" in message.last_answer
    assert "deposit funds" in message.last_answer.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_contests_command_shows_details(async_session):
    """Test contests command shows detailed information"""
    from app.repos.user_repo import create_user
    from app.repos.contest_repo import create_contest
    from app.models.enums import UserStatus
    from decimal import Decimal
    
    # Create user
    user = await create_user(
        session=async_session,
        telegram_id=12345,
        username="test_user_contests",
        status=UserStatus.ACTIVE
    )
    
    # Create a test contest
    contest = await create_contest(
        session=async_session,
        match_id="test_match_123",
        title="Test Contest",
        entry_fee=Decimal("10.00"),
        max_participants=10,
        prize_structure=[{"1st": "50.00"}, {"2nd": "30.00"}],
        created_by=user.id
    )
    
    # Mock message
    message = MockMessage("/contests", 12345, 67890)
    
    with patch('app.bot.handlers.commands.async_session', return_value=async_session):
        await contests_command(message)
    
    # Verify response
    assert "Available Contests" in message.last_answer
    assert "Test Contest" in message.last_answer
    assert "10.00" in message.last_answer


@pytest.mark.integration
@pytest.mark.asyncio
async def test_join_contest_callback_idempotency(async_session):
    """Test join contest callback is idempotent"""
    # Create test data
    from app.repos.user_repo import create_user
    from app.repos.wallet_repo import create_wallet_for_user
    from app.repos.contest_repo import create_contest
    
    user = await create_user(async_session, 12345, "testuser", UserStatus.ACTIVE)
    await create_wallet_for_user(async_session, user.id)
    
    # Add some balance
    wallet = await async_session.get(app.models.wallet.Wallet, user.id)
    wallet.deposit_balance = Decimal("100.00")
    await async_session.commit()
    
    contest = await create_contest(
        async_session,
        title="Test Contest",
        entry_fee=Decimal("10.00"),
        max_players=10
    )
    
    # Mock callback query
    message = MockMessage("", 12345, 67890)
    callback_query = MockCallbackQuery(f"join_contest:{contest.id}", 12345, message)
    
    with patch('app.bot.handlers.callbacks.async_session', return_value=async_session):
        # First call should succeed
        await join_contest_callback(callback_query)
        first_response = callback_query.last_edit_text
        
        # Second call should be idempotent
        await join_contest_callback(callback_query)
        second_response = callback_query.last_edit_text
        
        # Verify idempotency
        assert "already joined" in second_response or "being processed" in second_response


@pytest.mark.integration
@pytest.mark.asyncio
async def test_contest_details_callback(async_session):
    """Test contest details callback shows comprehensive information"""
    # Create test data
    from app.repos.contest_repo import create_contest
    
    contest = await create_contest(
        async_session,
        title="Test Contest",
        entry_fee=Decimal("10.00"),
        max_players=10,
        description="Test contest description"
    )
    
    # Mock callback query
    message = MockMessage("", 12345, 67890)
    callback_query = MockCallbackQuery(f"contest_details:{contest.id}", 12345, message)
    
    with patch('app.bot.handlers.callbacks.async_session', return_value=async_session):
        await contest_details_callback(callback_query)
    
    # Verify response
    assert "Contest Details" in callback_query.last_edit_text
    assert "Test Contest" in callback_query.last_edit_text
    assert "Entry Fee" in callback_query.last_edit_text
    assert "Players" in callback_query.last_edit_text
    assert "Prize" in callback_query.last_edit_text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deposit_notification_subscription(async_session):
    """Test deposit notification subscription"""
    from app.bot.handlers.commands import subscribe_deposit_notifications_callback
    
    # Mock callback query
    message = MockMessage("", 12345, 67890)
    callback_query = MockCallbackQuery("subscribe_deposit_notifications", 12345, message)
    
    with patch('app.bot.handlers.commands.async_session', return_value=async_session):
        await subscribe_deposit_notifications_callback(callback_query)
    
    # Verify response
    assert "notifications" in callback_query.last_edit_text.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_withdrawal_flow_integration(async_session):
    """Test complete withdrawal flow"""
    # Create user and wallet with balance
    from app.repos.user_repo import create_user
    from app.repos.wallet_repo import create_wallet_for_user
    
    user = await create_user(async_session, 12345, "testuser", UserStatus.ACTIVE)
    wallet = await create_wallet_for_user(async_session, user.id)
    wallet.deposit_balance = Decimal("100.00")
    await async_session.commit()
    
    # Test withdrawal command
    message = MockMessage("/withdraw", 12345, 67890)
    state = AsyncMock()
    
    with patch('app.bot.handlers.commands.async_session', return_value=async_session):
        await withdraw_command(message, state)
    
    # Verify withdrawal options are shown
    assert "Withdrawal Request" in message.last_answer
    assert "Available Balance" in message.last_answer
    assert "Choose withdrawal amount" in message.last_answer


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_mapping_persistence(async_session):
    """Test that chat mapping is saved on user interactions"""
    from app.repos.user_repo import get_user_by_telegram_id, save_chat_id
    
    # Create user
    from app.repos.user_repo import create_user
    user = await create_user(async_session, 12345, "testuser", UserStatus.ACTIVE)
    
    # Save chat ID
    await save_chat_id(async_session, user.id, "67890")
    
    # Verify chat mapping was saved
    from app.models.chat_map import ChatMap
    from sqlalchemy import select
    
    result = await async_session.execute(
        select(ChatMap).where(ChatMap.user_id == str(user.id))
    )
    chat_map = result.scalar_one_or_none()
    
    assert chat_map is not None
    assert chat_map.chat_id == "67890"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_notification_idempotency():
    """Test that notifications use idempotency keys"""
    from app.tasks.notify import send_deposit_confirmation, send_contest_settlement
    import uuid
    
    # Mock Redis client
    with patch('app.tasks.notify.redis_client') as mock_redis:
        mock_redis.exists.return_value = False
        mock_redis.setex.return_value = True
        
        # Test deposit notification with valid UUID
        test_tx_id = str(uuid.uuid4())
        result1 = await send_deposit_confirmation(test_tx_id)
        result2 = await send_deposit_confirmation(test_tx_id)
        
        # Both should succeed (idempotent)
        assert result1 is True
        assert result2 is True
        
        # Verify Redis was called for idempotency
        assert mock_redis.exists.called
        assert mock_redis.setex.called


if __name__ == "__main__":
    pytest.main([__file__])
