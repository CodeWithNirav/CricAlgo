"""
Unit tests for contest cancellation functionality
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from app.repos.wallet_repo import refund_contest_entry_atomic
from app.repos.contest_repo import cancel_contest_atomic
from app.models.contest import Contest
from app.models.contest_entry import ContestEntry
from app.models.wallet import Wallet


class TestContestCancellation:
    """Test contest cancellation functionality"""
    
    @pytest.mark.asyncio
    async def test_refund_contest_entry_atomic_success(self):
        """Test successful contest entry refund"""
        # Mock session and wallet
        session = AsyncMock()
        user_id = uuid4()
        contest_id = uuid4()
        amount = Decimal('10.0')
        
        # Mock wallet with sufficient balance
        mock_wallet = Wallet(
            user_id=user_id,
            deposit_balance=Decimal('100.0'),
            winning_balance=Decimal('50.0'),
            bonus_balance=Decimal('25.0')
        )
        
        session.execute.return_value.scalar_one_or_none.return_value = mock_wallet
        
        # Mock transaction creation
        with patch('app.repos.wallet_repo.create_transaction') as mock_create_tx:
            mock_create_tx.return_value = AsyncMock()
            
            success, error = await refund_contest_entry_atomic(
                session, user_id, amount, contest_id
            )
            
            assert success is True
            assert error is None
            assert mock_wallet.deposit_balance == Decimal('110.0')  # 100 + 10
            session.commit.assert_called_once()
            mock_create_tx.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_refund_contest_entry_atomic_wallet_not_found(self):
        """Test refund when wallet not found"""
        session = AsyncMock()
        user_id = uuid4()
        contest_id = uuid4()
        amount = Decimal('10.0')
        
        # Mock wallet not found
        session.execute.return_value.scalar_one_or_none.return_value = None
        
        success, error = await refund_contest_entry_atomic(
            session, user_id, amount, contest_id
        )
        
        assert success is False
        assert error == "Wallet not found"
    
    @pytest.mark.asyncio
    async def test_refund_contest_entry_atomic_invalid_amount(self):
        """Test refund with invalid amount"""
        session = AsyncMock()
        user_id = uuid4()
        contest_id = uuid4()
        amount = Decimal('-10.0')  # Negative amount
        
        success, error = await refund_contest_entry_atomic(
            session, user_id, amount, contest_id
        )
        
        assert success is False
        assert error == "Amount must be positive"
    
    @pytest.mark.asyncio
    async def test_cancel_contest_atomic_no_participants(self):
        """Test contest cancellation with no participants"""
        session = AsyncMock()
        contest_id = uuid4()
        admin_id = uuid4()
        
        # Mock contest
        mock_contest = Contest(
            id=contest_id,
            status='open',
            title="Test Contest",
            entry_fee=Decimal('10.0')
        )
        
        session.execute.return_value.scalar_one_or_none.return_value = mock_contest
        
        # Mock empty entries
        with patch('app.repos.contest_repo.get_contest_entries') as mock_get_entries:
            mock_get_entries.return_value = []
            
            # Mock audit log creation
            with patch('app.repos.contest_repo.AuditLog') as mock_audit_log:
                result = await cancel_contest_atomic(session, contest_id, admin_id)
                
                assert result["success"] is True
                assert result["participants"] == 0
                assert result["total_refunded"] == "0"
                assert mock_contest.status == 'cancelled'
                session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_cancel_contest_atomic_with_participants(self):
        """Test contest cancellation with participants"""
        session = AsyncMock()
        contest_id = uuid4()
        admin_id = uuid4()
        
        # Mock contest
        mock_contest = Contest(
            id=contest_id,
            status='open',
            title="Test Contest",
            entry_fee=Decimal('10.0')
        )
        
        session.execute.return_value.scalar_one_or_none.return_value = mock_contest
        
        # Mock entries
        mock_entries = [
            ContestEntry(
                id=uuid4(),
                contest_id=contest_id,
                user_id=uuid4(),
                amount_debited=Decimal('10.0')
            ),
            ContestEntry(
                id=uuid4(),
                contest_id=contest_id,
                user_id=uuid4(),
                amount_debited=Decimal('10.0')
            )
        ]
        
        with patch('app.repos.contest_repo.get_contest_entries') as mock_get_entries:
            mock_get_entries.return_value = mock_entries
            
            # Mock successful refunds
            with patch('app.repos.contest_repo.refund_contest_entry_atomic') as mock_refund:
                mock_refund.return_value = (True, None)
                
                # Mock audit log creation
                with patch('app.repos.contest_repo.AuditLog'):
                    result = await cancel_contest_atomic(session, contest_id, admin_id)
                    
                    assert result["success"] is True
                    assert result["participants"] == 2
                    assert result["successful_refunds"] == 2
                    assert result["failed_refunds"] == 0
                    assert result["total_refunded"] == "20.0"
                    assert mock_contest.status == 'cancelled'
                    assert len(result["refunds"]) == 2
                    assert len(result["failed_refunds"]) == 0
    
    @pytest.mark.asyncio
    async def test_cancel_contest_atomic_already_cancelled(self):
        """Test cancellation of already cancelled contest"""
        session = AsyncMock()
        contest_id = uuid4()
        admin_id = uuid4()
        
        # Mock already cancelled contest
        mock_contest = Contest(
            id=contest_id,
            status='cancelled',
            title="Test Contest",
            entry_fee=Decimal('10.0')
        )
        
        session.execute.return_value.scalar_one_or_none.return_value = mock_contest
        
        result = await cancel_contest_atomic(session, contest_id, admin_id)
        
        assert result["success"] is False
        assert result["error"] == "Contest already cancelled"
    
    @pytest.mark.asyncio
    async def test_cancel_contest_atomic_settled_contest(self):
        """Test cancellation of settled contest"""
        session = AsyncMock()
        contest_id = uuid4()
        admin_id = uuid4()
        
        # Mock settled contest
        mock_contest = Contest(
            id=contest_id,
            status='settled',
            title="Test Contest",
            entry_fee=Decimal('10.0')
        )
        
        session.execute.return_value.scalar_one_or_none.return_value = mock_contest
        
        result = await cancel_contest_atomic(session, contest_id, admin_id)
        
        assert result["success"] is False
        assert result["error"] == "Cannot cancel settled contest"
    
    @pytest.mark.asyncio
    async def test_cancel_contest_atomic_contest_not_found(self):
        """Test cancellation of non-existent contest"""
        session = AsyncMock()
        contest_id = uuid4()
        admin_id = uuid4()
        
        # Mock contest not found
        session.execute.return_value.scalar_one_or_none.return_value = None
        
        result = await cancel_contest_atomic(session, contest_id, admin_id)
        
        assert result["success"] is False
        assert result["error"] == "Contest not found"
