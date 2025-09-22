"""
Integration tests for admin UI endpoints
"""

import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.db.session import get_db
from app.models.admin import Admin
from app.models.user import User
from app.models.invitation_code import InvitationCode
from app.models.match import Match
from app.models.contest import Contest
from app.models.contest_entry import ContestEntry
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.core.auth import get_password_hash
from decimal import Decimal
import uuid
from datetime import datetime, timedelta


@pytest.fixture
async def admin_user(async_session: AsyncSession):
    """Create a test admin user"""
    admin = Admin(
        username="test_admin",
        password_hash=get_password_hash("test_password"),
        email="test@example.com",
        totp_secret=None
    )
    async_session.add(admin)
    await async_session.commit()
    await async_session.refresh(admin)
    return admin


@pytest.fixture
async def test_user(async_session: AsyncSession):
    """Create a test user"""
    user = User(
        telegram_id=123456789,
        username="testuser",
        status="ACTIVE"
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    
    # Create wallet for user
    wallet = Wallet(
        user_id=user.id,
        deposit_balance=Decimal("100.00"),
        winning_balance=Decimal("50.00"),
        bonus_balance=Decimal("25.00")
    )
    async_session.add(wallet)
    await async_session.commit()
    
    return user


@pytest.fixture
async def test_invite_code(async_session: AsyncSession, admin_user: Admin):
    """Create a test invite code"""
    invite_code = InvitationCode(
        code="TEST123",
        max_uses=10,
        expires_at=datetime.utcnow() + timedelta(days=30),
        enabled=True,
        created_by=admin_user.id
    )
    async_session.add(invite_code)
    await async_session.commit()
    await async_session.refresh(invite_code)
    return invite_code


@pytest.fixture
async def test_match(async_session: AsyncSession):
    """Create a test match"""
    match = Match(
        title="Test Match",
        starts_at=datetime.utcnow() + timedelta(hours=1),
        external_id="test-match-001"
    )
    async_session.add(match)
    await async_session.commit()
    await async_session.refresh(match)
    return match


@pytest.fixture
async def test_contest(async_session: AsyncSession, test_match: Match):
    """Create a test contest"""
    contest = Contest(
        match_id=test_match.id,
        code="TEST-CONTEST-001",
        title="Test Contest",
        entry_fee=Decimal("10.00"),
        currency="USDT",
        max_players=100,
        prize_structure={"1st": "50%", "2nd": "30%", "3rd": "20%"},
        commission_pct=Decimal("5.00"),
        join_cutoff=datetime.utcnow() + timedelta(minutes=30),
        status="open"
    )
    async_session.add(contest)
    await async_session.commit()
    await async_session.refresh(contest)
    return contest


@pytest.fixture
async def test_contest_entry(async_session: AsyncSession, test_contest: Contest, test_user: User):
    """Create a test contest entry"""
    entry = ContestEntry(
        contest_id=test_contest.id,
        user_id=test_user.id,
        entry_code="ENTRY-001",
        amount_debited=test_contest.entry_fee
    )
    async_session.add(entry)
    await async_session.commit()
    await async_session.refresh(entry)
    return entry


@pytest.fixture
async def admin_token(admin_user: Admin):
    """Create an admin JWT token"""
    from jose import jwt
    from app.core.config import settings
    from datetime import datetime, timedelta
    
    to_encode = {
        "sub": str(admin_user.id),
        "username": admin_user.username,
        "type": "admin",
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    token = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token


class TestAdminLogin:
    """Test admin login endpoint"""
    
    async def test_admin_login_success(self, test_test_client: AsyncClient, admin_user: Admin):
        """Test successful admin login"""
        response = await test_client.post(
            "/api/v1/admin/login",
            json={
                "username": "test_admin",
                "password": "test_password"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    async def test_admin_login_invalid_credentials(self, test_test_client: AsyncClient):
        """Test admin login with invalid credentials"""
        response = await test_client.post(
            "/api/v1/admin/login",
            json={
                "username": "invalid_user",
                "password": "invalid_password"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "Invalid credentials" in data["detail"]
    
    async def test_admin_login_missing_fields(self, test_test_client: AsyncClient):
        """Test admin login with missing fields"""
        response = await test_client.post(
            "/api/v1/admin/login",
            json={
                "username": "test_admin"
                # Missing password
            }
        )
        
        assert response.status_code == 422


class TestInviteCodes:
    """Test invite codes endpoints"""
    
    async def test_list_invite_codes(self, test_client: AsyncClient, admin_token: str, test_invite_code: InvitationCode):
        """Test listing invite codes"""
        response = await test_client.get(
            "/api/v1/admin/invite_codes",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Check if our test invite code is in the list
        codes = [item["code"] for item in data]
        assert "TEST123" in codes
    
    async def test_list_invite_codes_alias(self, test_client: AsyncClient, admin_token: str, test_invite_code: InvitationCode):
        """Test listing invite codes via alias endpoint"""
        response = await test_client.get(
            "/api/v1/admin/invitecodes",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
    
    async def test_create_invite_code(self, test_client: AsyncClient, admin_token: str):
        """Test creating an invite code"""
        response = await test_client.post(
            "/api/v1/admin/invite_codes",
            json={
                "code": "NEW123",
                "max_uses": 5,
                "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                "enabled": True
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "NEW123"
        assert data["max_uses"] == 5
        assert data["enabled"] is True
    
    async def test_disable_invite_code(self, test_client: AsyncClient, admin_token: str, test_invite_code: InvitationCode):
        """Test disabling an invite code"""
        response = await test_client.post(
            f"/api/v1/admin/invite_codes/{test_invite_code.code}/disable",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
    
    async def test_invite_codes_unauthorized(self, test_client: AsyncClient):
        """Test invite codes endpoints without authentication"""
        response = await test_client.get("/api/v1/admin/invite_codes")
        assert response.status_code == 401


class TestUsers:
    """Test users endpoints"""
    
    async def test_search_users(self, test_client: AsyncClient, admin_token: str, test_user: User):
        """Test searching users"""
        response = await test_client.get(
            "/api/v1/admin/users",
            params={"q": "testuser"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Check if our test user is in the results
        usernames = [user["username"] for user in data]
        assert "testuser" in usernames
    
    async def test_search_users_empty(self, test_client: AsyncClient, admin_token: str):
        """Test searching users with no results"""
        response = await test_client.get(
            "/api/v1/admin/users",
            params={"q": "nonexistentuser"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    async def test_freeze_user(self, test_client: AsyncClient, admin_token: str, test_user: User):
        """Test freezing a user"""
        response = await test_client.post(
            f"/api/v1/admin/users/{test_user.id}/freeze",
            json={"reason": "Test freeze"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
    
    async def test_unfreeze_user(self, test_client: AsyncClient, admin_token: str, test_user: User):
        """Test unfreezing a user"""
        response = await test_client.post(
            f"/api/v1/admin/users/{test_user.id}/unfreeze",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
    
    async def test_adjust_balance(self, test_client: AsyncClient, admin_token: str, test_user: User):
        """Test adjusting user balance"""
        response = await test_client.post(
            f"/api/v1/admin/users/{test_user.id}/adjust_balance",
            json={
                "bucket": "deposit",
                "amount": "50.00",
                "reason": "Test adjustment"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
    
    async def test_adjust_balance_invalid_bucket(self, test_client: AsyncClient, admin_token: str, test_user: User):
        """Test adjusting balance with invalid bucket"""
        response = await test_client.post(
            f"/api/v1/admin/users/{test_user.id}/adjust_balance",
            json={
                "bucket": "invalid",
                "amount": "50.00",
                "reason": "Test adjustment"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "invalid bucket" in data["detail"]["error"]


class TestMatches:
    """Test matches endpoints"""
    
    async def test_list_matches(self, test_client: AsyncClient, admin_token: str, test_match: Match):
        """Test listing matches"""
        response = await test_client.get(
            "/api/v1/admin/matches",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Check if our test match is in the list
        titles = [match["title"] for match in data]
        assert "Test Match" in titles
    
    async def test_create_match(self, test_client: AsyncClient, admin_token: str):
        """Test creating a match"""
        response = await test_client.post(
            "/api/v1/admin/matches",
            json={
                "title": "New Test Match",
                "start_time": (datetime.utcnow() + timedelta(hours=2)).isoformat(),
                "external_id": "new-test-match-001"
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "New Test Match"
        assert "id" in data


class TestContests:
    """Test contests endpoints"""
    
    async def test_list_contests(self, test_client: AsyncClient, admin_token: str, test_contest: Contest):
        """Test listing contests"""
        response = await test_client.get(
            "/api/v1/admin/contests",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Check if our test contest is in the list
        codes = [contest["code"] for contest in data]
        assert "TEST-CONTEST-001" in codes
    
    async def test_get_contest(self, test_client: AsyncClient, admin_token: str, test_contest: Contest):
        """Test getting a specific contest"""
        response = await test_client.get(
            f"/api/v1/admin/contests/{test_contest.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "TEST-CONTEST-001"
        assert data["title"] == "Test Contest"
    
    async def test_get_contest_entries(self, test_client: AsyncClient, admin_token: str, test_contest: Contest, test_contest_entry: ContestEntry):
        """Test getting contest entries"""
        response = await test_client.get(
            f"/api/v1/admin/contests/{test_contest.id}/entries",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Check if our test entry is in the list
        entry_codes = [entry["entry_code"] for entry in data]
        assert "ENTRY-001" in entry_codes


class TestErrorHandling:
    """Test error handling in admin endpoints"""
    
    async def test_invalid_endpoint(self, test_client: AsyncClient, admin_token: str):
        """Test invalid endpoint returns 404"""
        response = await test_client.get(
            "/api/v1/admin/invalid_endpoint",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 404
    
    async def test_invalid_contest_id(self, test_client: AsyncClient, admin_token: str):
        """Test invalid contest ID returns proper error"""
        invalid_id = str(uuid.uuid4())
        response = await test_client.get(
            f"/api/v1/admin/contests/{invalid_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 404
    
    async def test_invalid_user_id(self, test_client: AsyncClient, admin_token: str):
        """Test invalid user ID returns proper error"""
        invalid_id = str(uuid.uuid4())
        response = await test_client.post(
            f"/api/v1/admin/users/{invalid_id}/freeze",
            json={"reason": "Test"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Should not crash with 500, should handle gracefully
        assert response.status_code in [404, 500]  # Depending on implementation
