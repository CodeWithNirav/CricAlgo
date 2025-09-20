"""
Integration test for contest join endpoint
Tests the /api/v1/contest/{contest_id}/join endpoint
"""

import pytest
import httpx
from decimal import Decimal
from uuid import uuid4

from app.db.session import AsyncSessionLocal
from app.repos.user_repo import create_user
from app.repos.contest_repo import create_contest
from app.repos.wallet_repo import update_balances_atomic
from app.repos.contest_entry_repo import get_contest_entries
from app.core.auth import create_access_token
from app.models.enums import ContestStatus, UserStatus


@pytest.mark.asyncio
async def test_contest_join_endpoint_success():
    """Test successful contest join"""
    async with AsyncSessionLocal() as session:
        # Create test user
        user = await create_user(
            session=session,
            username="test_join_user",
            telegram_id=12345,
            status=UserStatus.ACTIVE
        )
        
        # Fund user's wallet
        success, error = await update_balances_atomic(
            session,
            user.id,
            deposit_delta=Decimal("10.0")
        )
        assert success, f"Failed to fund user: {error}"
        
        # Create test contest
        contest = await create_contest(
            session=session,
            match_id="test_match_123",
            title="Test Contest",
            description="Test contest for join testing",
            entry_fee=Decimal("1.0"),
            max_participants=10,
            prize_structure=[{"pos": 1, "pct": 100}],
            status=ContestStatus.OPEN
        )
        
        # Create access token
        token = create_access_token({"sub": str(user.id)})
        
        # Test join endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:8001/api/v1/contest/{contest.id}/join",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert data["message"] == "Successfully joined contest"
            assert "entry_id" in data
            
            # Verify contest entry was created
            entries = await get_contest_entries(session, contest.id, user_id=user.id)
            assert len(entries) == 1
            assert entries[0].user_id == user.id
            assert entries[0].contest_id == contest.id
            assert entries[0].entry_fee == Decimal("1.0")


@pytest.mark.asyncio
async def test_contest_join_endpoint_unauthorized():
    """Test contest join without authentication"""
    async with AsyncSessionLocal() as session:
        # Create test contest
        contest = await create_contest(
            session=session,
            match_id="test_match_456",
            title="Test Contest 2",
            description="Test contest for auth testing",
            entry_fee=Decimal("1.0"),
            max_participants=10,
            prize_structure=[{"pos": 1, "pct": 100}],
            status=ContestStatus.OPEN
        )
        
        # Test join endpoint without auth
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:8001/api/v1/contest/{contest.id}/join"
            )
            
            assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"


@pytest.mark.asyncio
async def test_contest_join_endpoint_insufficient_funds():
    """Test contest join with insufficient funds"""
    async with AsyncSessionLocal() as session:
        # Create test user with no funds
        user = await create_user(
            session=session,
            username="test_join_user_poor",
            telegram_id=12346,
            status=UserStatus.ACTIVE
        )
        
        # Create test contest
        contest = await create_contest(
            session=session,
            match_id="test_match_789",
            title="Test Contest 3",
            description="Test contest for funds testing",
            entry_fee=Decimal("5.0"),
            max_participants=10,
            prize_structure=[{"pos": 1, "pct": 100}],
            status=ContestStatus.OPEN
        )
        
        # Create access token
        token = create_access_token({"sub": str(user.id)})
        
        # Test join endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:8001/api/v1/contest/{contest.id}/join",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
            data = response.json()
            assert "Insufficient balance" in data["detail"]


@pytest.mark.asyncio
async def test_contest_join_endpoint_contest_not_found():
    """Test contest join with non-existent contest"""
    async with AsyncSessionLocal() as session:
        # Create test user
        user = await create_user(
            session=session,
            username="test_join_user_notfound",
            telegram_id=12347,
            status=UserStatus.ACTIVE
        )
        
        # Create access token
        token = create_access_token({"sub": str(user.id)})
        
        # Test join endpoint with fake contest ID
        fake_contest_id = str(uuid4())
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:8001/api/v1/contest/{fake_contest_id}/join",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"


@pytest.mark.asyncio
async def test_contest_join_endpoint_contest_closed():
    """Test contest join with closed contest"""
    async with AsyncSessionLocal() as session:
        # Create test user
        user = await create_user(
            session=session,
            username="test_join_user_closed",
            telegram_id=12348,
            status=UserStatus.ACTIVE
        )
        
        # Fund user's wallet
        success, error = await update_balances_atomic(
            session,
            user.id,
            deposit_delta=Decimal("10.0")
        )
        assert success, f"Failed to fund user: {error}"
        
        # Create closed contest
        contest = await create_contest(
            session=session,
            match_id="test_match_closed",
            title="Closed Contest",
            description="Test contest that's closed",
            entry_fee=Decimal("1.0"),
            max_participants=10,
            prize_structure=[{"pos": 1, "pct": 100}],
            status=ContestStatus.CLOSED
        )
        
        # Create access token
        token = create_access_token({"sub": str(user.id)})
        
        # Test join endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:8001/api/v1/contest/{contest.id}/join",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
            data = response.json()
            assert "not open for joining" in data["detail"]
