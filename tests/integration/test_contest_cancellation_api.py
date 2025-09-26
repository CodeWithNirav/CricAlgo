"""
Integration tests for contest cancellation API endpoints
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.models.contest import Contest
from app.models.contest_entry import ContestEntry
from app.models.wallet import Wallet
from app.models.user import User
from app.models.admin import Admin


class TestContestCancellationAPI:
    """Test contest cancellation API endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_admin(self):
        """Mock admin user"""
        return Admin(
            id=uuid4(),
            username="test_admin",
            email="admin@test.com"
        )
    
    @pytest.fixture
    def mock_contest(self):
        """Mock contest"""
        return Contest(
            id=uuid4(),
            match_id=uuid4(),
            code="TEST123",
            title="Test Contest",
            entry_fee=Decimal('10.0'),
            status='open',
            max_players=10
        )
    
    @pytest.fixture
    def mock_entries(self, mock_contest):
        """Mock contest entries"""
        return [
            ContestEntry(
                id=uuid4(),
                contest_id=mock_contest.id,
                user_id=uuid4(),
                amount_debited=Decimal('10.0')
            ),
            ContestEntry(
                id=uuid4(),
                contest_id=mock_contest.id,
                user_id=uuid4(),
                amount_debited=Decimal('10.0')
            )
        ]
    
    def test_cancel_contest_success(self, client, mock_admin, mock_contest, mock_entries):
        """Test successful contest cancellation"""
        contest_id = str(mock_contest.id)
        
        with patch('app.core.auth.get_current_admin') as mock_auth, \
             patch('app.db.session.get_db') as mock_db, \
             patch('app.repos.contest_repo.get_contest_by_id') as mock_get_contest, \
             patch('app.repos.contest_repo.cancel_contest_atomic') as mock_cancel:
            
            # Mock authentication
            mock_auth.return_value = mock_admin
            
            # Mock database session
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock contest retrieval
            mock_get_contest.return_value = mock_contest
            
            # Mock successful cancellation
            mock_cancel.return_value = {
                "success": True,
                "message": "Contest cancelled with 2 successful refunds",
                "participants": 2,
                "successful_refunds": 2,
                "failed_refunds": 0,
                "total_refunded": "20.0",
                "refunds": [
                    {"user_id": str(uuid4()), "amount": "10.0", "status": "success"},
                    {"user_id": str(uuid4()), "amount": "10.0", "status": "success"}
                ],
                "failed_refunds": []
            }
            
            response = client.post(f"/api/v1/contest/admin/{contest_id}/cancel")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["participants"] == 2
            assert data["successful_refunds"] == 2
            assert data["failed_refunds"] == 0
            assert data["total_refunded"] == "20.0"
    
    def test_cancel_contest_not_found(self, client, mock_admin):
        """Test cancellation of non-existent contest"""
        contest_id = str(uuid4())
        
        with patch('app.core.auth.get_current_admin') as mock_auth, \
             patch('app.db.session.get_db') as mock_db, \
             patch('app.repos.contest_repo.get_contest_by_id') as mock_get_contest:
            
            # Mock authentication
            mock_auth.return_value = mock_admin
            
            # Mock database session
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock contest not found
            mock_get_contest.return_value = None
            
            response = client.post(f"/api/v1/contest/admin/{contest_id}/cancel")
            
            assert response.status_code == 404
            data = response.json()
            assert "Contest not found" in data["detail"]
    
    def test_cancel_contest_already_cancelled(self, client, mock_admin, mock_contest):
        """Test cancellation of already cancelled contest"""
        contest_id = str(mock_contest.id)
        mock_contest.status = 'cancelled'
        
        with patch('app.core.auth.get_current_admin') as mock_auth, \
             patch('app.db.session.get_db') as mock_db, \
             patch('app.repos.contest_repo.get_contest_by_id') as mock_get_contest:
            
            # Mock authentication
            mock_auth.return_value = mock_admin
            
            # Mock database session
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock already cancelled contest
            mock_get_contest.return_value = mock_contest
            
            response = client.post(f"/api/v1/contest/admin/{contest_id}/cancel")
            
            assert response.status_code == 400
            data = response.json()
            assert "Contest already cancelled" in data["detail"]
    
    def test_cancel_contest_settled(self, client, mock_admin, mock_contest):
        """Test cancellation of settled contest"""
        contest_id = str(mock_contest.id)
        mock_contest.status = 'settled'
        
        with patch('app.core.auth.get_current_admin') as mock_auth, \
             patch('app.db.session.get_db') as mock_db, \
             patch('app.repos.contest_repo.get_contest_by_id') as mock_get_contest:
            
            # Mock authentication
            mock_auth.return_value = mock_admin
            
            # Mock database session
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session
            
            # Mock settled contest
            mock_get_contest.return_value = mock_contest
            
            response = client.post(f"/api/v1/contest/admin/{contest_id}/cancel")
            
            assert response.status_code == 400
            data = response.json()
            assert "Cannot cancel settled contest" in data["detail"]
    
    def test_cancel_contest_invalid_id(self, client, mock_admin):
        """Test cancellation with invalid contest ID"""
        invalid_id = "invalid-uuid"
        
        with patch('app.core.auth.get_current_admin') as mock_auth:
            # Mock authentication
            mock_auth.return_value = mock_admin
            
            response = client.post(f"/api/v1/contest/admin/{invalid_id}/cancel")
            
            assert response.status_code == 400
            data = response.json()
            assert "Invalid contest ID format" in data["detail"]
    
    def test_cancel_contest_unauthorized(self, client):
        """Test cancellation without admin authentication"""
        contest_id = str(uuid4())
        
        response = client.post(f"/api/v1/contest/admin/{contest_id}/cancel")
        
        assert response.status_code == 401  # Unauthorized
