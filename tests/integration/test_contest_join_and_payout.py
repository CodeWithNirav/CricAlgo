"""
Integration tests for contest join and payout functionality
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from app.repos.user_repo import create_user
from app.repos.wallet_repo import create_wallet_for_user, get_wallet_for_user
from app.repos.contest_repo import create_contest, get_contest_by_id
from app.repos.contest_entry_repo import get_contest_entries
from app.models.enums import UserStatus, ContestStatus
from tests.fixtures.database import assert_wallet_balance


@pytest.mark.integration
@pytest.mark.asyncio
async def test_contest_creation_and_join(test_client, async_session):
    """Test contest creation and user joining."""
    # Create admin user
    admin_user = await create_user(
        session=async_session,
        telegram_id=99999,
        username="admin",
        status=UserStatus.ACTIVE
    )
    
    # Create regular user
    user = await create_user(
        session=async_session,
        telegram_id=12345,
        username="contestuser",
        status=UserStatus.ACTIVE
    )
    
    # Create wallets
    await create_wallet_for_user(async_session, admin_user.id)
    await create_wallet_for_user(async_session, user.id)
    
    # Add balance to user
    from app.repos.wallet_repo import update_balances_atomic
    await update_balances_atomic(
        async_session,
        user.id,
        deposit_delta=Decimal('100.00')
    )
    
    # Create JWT tokens
    from app.core.auth import create_access_token
    admin_token = create_access_token(data={"sub": str(admin_user.id)})
    user_token = create_access_token(data={"sub": str(user.id)})
    
    # Create contest (admin)
    contest_data = {
        "match_id": "match_123",
        "title": "Test Contest",
        "description": "A test contest",
        "entry_fee": "10.00",
        "max_participants": 5,
        "prize_structure": {
            "1": "50%",
            "2": "30%",
            "3": "20%"
        }
    }
    
    response = await test_client.post(
        "/api/v1/contest/admin/contest",
        json=contest_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    contest_data_response = response.json()
    contest_id = contest_data_response["id"]
    
    assert contest_data_response["title"] == "Test Contest"
    assert contest_data_response["entry_fee"] == "10.00"
    assert contest_data_response["max_participants"] == 5
    assert contest_data_response["current_participants"] == 0
    
    # Join contest (user)
    response = await test_client.post(
        f"/api/v1/contest/{contest_id}/join",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    
    assert response.status_code == 200
    join_data = response.json()
    
    assert join_data["success"] is True
    assert "Successfully joined contest" in join_data["message"]
    assert "entry_id" in join_data
    
    # Verify wallet was debited
    await assert_wallet_balance(
        async_session,
        user.id,
        expected_deposit=Decimal('90.00')  # 100 - 10
    )
    
    # Verify contest entry was created
    contest_entries = await get_contest_entries(async_session, uuid4(contest_id))
    assert len(contest_entries) == 1
    assert contest_entries[0].user_id == user.id
    assert contest_entries[0].entry_fee == Decimal('10.00')


@pytest.mark.integration
@pytest.mark.asyncio
async def test_contest_join_insufficient_balance(test_client, async_session):
    """Test contest join with insufficient balance."""
    # Create user
    user = await create_user(
        session=async_session,
        telegram_id=67890,
        username="pooruser",
        status=UserStatus.ACTIVE
    )
    
    # Create wallet (no balance added)
    await create_wallet_for_user(async_session, user.id)
    
    # Create contest
    admin_user = await create_user(
        session=async_session,
        telegram_id=99998,
        username="admin2",
        status=UserStatus.ACTIVE
    )
    
    await create_wallet_for_user(async_session, admin_user.id)
    
    contest = await create_contest(
        session=async_session,
        match_id="match_456",
        title="Test Contest 2",
        description="Another test contest",
        entry_fee=Decimal('50.00'),
        max_participants=3,
        prize_structure={"1": "100%"},
        created_by=admin_user.id
    )
    
    # Create JWT token
    from app.core.auth import create_access_token
    user_token = create_access_token(data={"sub": str(user.id)})
    
    # Try to join contest
    response = await test_client.post(
        f"/api/v1/contest/{contest.id}/join",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert "Insufficient balance" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_contest_join_already_joined(test_client, async_session):
    """Test contest join when user already joined."""
    # Create user
    user = await create_user(
        session=async_session,
        telegram_id=11111,
        username="repeatuser",
        status=UserStatus.ACTIVE
    )
    
    # Create wallet with balance
    await create_wallet_for_user(async_session, user.id)
    from app.repos.wallet_repo import update_balances_atomic
    await update_balances_atomic(
        async_session,
        user.id,
        deposit_delta=Decimal('100.00')
    )
    
    # Create contest
    admin_user = await create_user(
        session=async_session,
        telegram_id=99997,
        username="admin3",
        status=UserStatus.ACTIVE
    )
    
    await create_wallet_for_user(async_session, admin_user.id)
    
    contest = await create_contest(
        session=async_session,
        match_id="match_789",
        title="Test Contest 3",
        description="Another test contest",
        entry_fee=Decimal('20.00'),
        max_participants=5,
        prize_structure={"1": "100%"},
        created_by=admin_user.id
    )
    
    # Create JWT token
    from app.core.auth import create_access_token
    user_token = create_access_token(data={"sub": str(user.id)})
    
    # Join contest first time
    response = await test_client.post(
        f"/api/v1/contest/{contest.id}/join",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    
    assert response.status_code == 200
    
    # Try to join again
    response = await test_client.post(
        f"/api/v1/contest/{contest.id}/join",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert "already joined" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_contest_join_full_contest(test_client, async_session):
    """Test contest join when contest is full."""
    # Create users
    users = []
    for i in range(3):
        user = await create_user(
            session=async_session,
            telegram_id=20000 + i,
            username=f"user{i}",
            status=UserStatus.ACTIVE
        )
        await create_wallet_for_user(async_session, user.id)
        from app.repos.wallet_repo import update_balances_atomic
        await update_balances_atomic(
            async_session,
            user.id,
            deposit_delta=Decimal('100.00')
        )
        users.append(user)
    
    # Create contest with max 2 participants
    admin_user = await create_user(
        session=async_session,
        telegram_id=99996,
        username="admin4",
        status=UserStatus.ACTIVE
    )
    
    await create_wallet_for_user(async_session, admin_user.id)
    
    contest = await create_contest(
        session=async_session,
        match_id="match_full",
        title="Full Contest",
        description="A contest that will be full",
        entry_fee=Decimal('10.00'),
        max_participants=2,  # Only 2 participants allowed
        prize_structure={"1": "100%"},
        created_by=admin_user.id
    )
    
    # Create JWT tokens
    from app.core.auth import create_access_token
    user_tokens = [create_access_token(data={"sub": str(user.id)}) for user in users]
    
    # First two users join successfully
    for i in range(2):
        response = await test_client.post(
            f"/api/v1/contest/{contest.id}/join",
            headers={"Authorization": f"Bearer {user_tokens[i]}"}
        )
        assert response.status_code == 200
    
    # Third user tries to join (should fail - contest is full)
    response = await test_client.post(
        f"/api/v1/contest/{contest.id}/join",
        headers={"Authorization": f"Bearer {user_tokens[2]}"}
    )
    
    assert response.status_code == 400
    data = response.json()
    assert "full" in data["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_contest_settlement(test_client, async_session):
    """Test contest settlement and payout distribution."""
    # Create admin user
    admin_user = await create_user(
        session=async_session,
        telegram_id=99995,
        username="admin5",
        status=UserStatus.ACTIVE
    )
    
    await create_wallet_for_user(async_session, admin_user.id)
    
    # Create contest
    contest = await create_contest(
        session=async_session,
        match_id="match_settle",
        title="Settlement Contest",
        description="A contest for testing settlement",
        entry_fee=Decimal('20.00'),
        max_participants=3,
        prize_structure={
            "1": "50%",
            "2": "30%",
            "3": "20%"
        },
        created_by=admin_user.id
    )
    
    # Create users and join contest
    users = []
    for i in range(3):
        user = await create_user(
            session=async_session,
            telegram_id=30000 + i,
            username=f"settleuser{i}",
            status=UserStatus.ACTIVE
        )
        await create_wallet_for_user(async_session, user.id)
        from app.repos.wallet_repo import update_balances_atomic
        await update_balances_atomic(
            async_session,
            user.id,
            deposit_delta=Decimal('100.00')
        )
        users.append(user)
        
        # Join contest
        from app.repos.contest_entry_repo import create_contest_entry
        await create_contest_entry(
            session=async_session,
            contest_id=contest.id,
            user_id=user.id,
            entry_fee=Decimal('20.00')
        )
    
    # Create admin JWT token
    from app.core.auth import create_access_token
    admin_token = create_access_token(data={"sub": str(admin_user.id)})
    
    # Settle contest
    response = await test_client.post(
        f"/api/v1/contest/admin/{contest.id}/settle",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    settle_data = response.json()
    
    assert settle_data["success"] is True
    assert settle_data["total_payouts"] == 3
    assert "total_commission" in settle_data
    
    # Verify contest was marked as settled
    updated_contest = await get_contest_by_id(async_session, contest.id)
    assert updated_contest.status == ContestStatus.SETTLED


@pytest.mark.integration
@pytest.mark.asyncio
async def test_contest_list_endpoint(test_client, async_session):
    """Test contest list endpoint."""
    # Create admin user
    admin_user = await create_user(
        session=async_session,
        telegram_id=99994,
        username="admin6",
        status=UserStatus.ACTIVE
    )
    
    await create_wallet_for_user(async_session, admin_user.id)
    
    # Create multiple contests
    for i in range(3):
        await create_contest(
            session=async_session,
            match_id=f"match_list_{i}",
            title=f"Contest {i}",
            description=f"Description for contest {i}",
            entry_fee=Decimal('10.00'),
            max_participants=5,
            prize_structure={"1": "100%"},
            created_by=admin_user.id
        )
    
    # Test contest list endpoint
    response = await test_client.get("/api/v1/contest/")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "contests" in data
    assert len(data["contests"]) == 3
    assert data["limit"] == 50
    assert data["offset"] == 0
    
    # Check contest details
    contests = data["contests"]
    for i, contest in enumerate(contests):
        assert contest["title"] == f"Contest {2-i}"  # Should be in reverse order
        assert contest["entry_fee"] == "10.00"
        assert contest["max_participants"] == 5
        assert contest["current_participants"] == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_contest_detail_endpoint(test_client, async_session):
    """Test contest detail endpoint."""
    # Create admin user
    admin_user = await create_user(
        session=async_session,
        telegram_id=99993,
        username="admin7",
        status=UserStatus.ACTIVE
    )
    
    await create_wallet_for_user(async_session, admin_user.id)
    
    # Create contest
    contest = await create_contest(
        session=async_session,
        match_id="match_detail",
        title="Detail Contest",
        description="A contest for testing detail endpoint",
        entry_fee=Decimal('15.00'),
        max_participants=4,
        prize_structure={"1": "60%", "2": "40%"},
        created_by=admin_user.id
    )
    
    # Test contest detail endpoint
    response = await test_client.get(f"/api/v1/contest/{contest.id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == str(contest.id)
    assert data["title"] == "Detail Contest"
    assert data["description"] == "A contest for testing detail endpoint"
    assert data["entry_fee"] == "15.00"
    assert data["max_participants"] == 4
    assert data["current_participants"] == 0
    assert data["prize_structure"] == {"1": "60%", "2": "40%"}
    assert "participants" in data
    assert len(data["participants"]) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unauthorized_contest_access(test_client):
    """Test contest endpoints without authentication."""
    # Test contest list without auth (should work)
    response = await test_client.get("/api/v1/contest/")
    assert response.status_code == 200
    
    # Test contest detail without auth (should work)
    fake_contest_id = str(uuid4())
    response = await test_client.get(f"/api/v1/contest/{fake_contest_id}")
    assert response.status_code == 404  # Contest not found, but endpoint accessible
    
    # Test contest join without auth
    response = await test_client.post(f"/api/v1/contest/{fake_contest_id}/join")
    assert response.status_code == 401
    
    # Test contest creation without auth
    contest_data = {
        "match_id": "test",
        "title": "Test",
        "entry_fee": "10.00",
        "max_participants": 5,
        "prize_structure": {"1": "100%"}
    }
    
    response = await test_client.post("/api/v1/contest/admin/contest", json=contest_data)
    assert response.status_code == 401
    
    # Test contest settlement without auth
    response = await test_client.post(f"/api/v1/contest/admin/{fake_contest_id}/settle")
    assert response.status_code == 401
