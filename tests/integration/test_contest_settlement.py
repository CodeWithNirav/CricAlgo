"""
Integration tests for contest settlement functionality
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from app.services.settlement import settle_contest
from app.models.contest import Contest
from app.models.contest_entry import ContestEntry
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.models.audit_log import AuditLog
from app.models.enums import ContestStatus
from app.repos.wallet_repo import get_wallet_for_user, create_wallet_for_user


class TestContestSettlementIntegration:
    """Integration tests for contest settlement"""
    
    @pytest.mark.asyncio
    async def test_settlement_winner_takes_all(self, db_session):
        """Test complete settlement flow with winner-takes-all"""
        # Create users and wallets
        user1_id = uuid4()
        user2_id = uuid4()
        
        wallet1 = await create_wallet_for_user(db_session, user1_id)
        wallet2 = await create_wallet_for_user(db_session, user2_id)
        
        # Give users some deposit balance
        wallet1.deposit_balance = Decimal("10.0")
        wallet2.deposit_balance = Decimal("10.0")
        await db_session.commit()
        
        # Create contest
        contest = Contest(
            id=uuid4(),
            match_id=uuid4(),
            code="INTEG001",
            title="Integration Test Contest",
            entry_fee=Decimal("1.0"),
            currency="USDT",
            max_players=2,
            prize_structure=[{"pos": 1, "pct": 100}],
            commission_pct=Decimal("5.0"),
            status=ContestStatus.OPEN
        )
        db_session.add(contest)
        await db_session.commit()
        
        # Create entries
        entry1 = ContestEntry(
            id=uuid4(),
            contest_id=contest.id,
            user_id=user1_id,
            entry_code="ENTRY001",
            amount_debited=Decimal("1.0")
        )
        entry2 = ContestEntry(
            id=uuid4(),
            contest_id=contest.id,
            user_id=user2_id,
            entry_code="ENTRY002",
            amount_debited=Decimal("1.0")
        )
        db_session.add_all([entry1, entry2])
        await db_session.commit()
        
        # Record initial winning balances
        initial_winning1 = wallet1.winning_balance
        initial_winning2 = wallet2.winning_balance
        
        # Settle contest
        result = await settle_contest(db_session, contest.id)
        
        # Verify settlement result
        assert result["success"] is True
        assert result["num_players"] == 2
        assert result["total_prize_pool"] == "2.00000000"
        assert result["commission_amount"] == "0.10000000"
        assert result["distributable_pool"] == "1.90000000"
        assert len(result["payouts"]) == 1
        
        # Verify contest status
        await db_session.refresh(contest)
        assert contest.status == ContestStatus.SETTLED
        assert contest.settled_at is not None
        
        # Verify wallet balances
        await db_session.refresh(wallet1)
        await db_session.refresh(wallet2)
        
        # Winner (first entry) should get the payout
        expected_winning1 = initial_winning1 + Decimal("1.90000000")
        assert wallet1.winning_balance == expected_winning1
        assert wallet2.winning_balance == initial_winning2  # No change
        
        # Verify transaction records
        from sqlalchemy import select
        transactions = await db_session.execute(
            select(Transaction)
            .where(Transaction.related_entity == "contest")
            .where(Transaction.related_id == contest.id)
        )
        tx_list = transactions.scalars().all()
        assert len(tx_list) == 1
        assert tx_list[0].user_id == user1_id
        assert tx_list[0].amount == Decimal("1.90000000")
        assert tx_list[0].tx_type == "internal"
        
        # Verify audit log
        audit_logs = await db_session.execute(
            select(AuditLog)
            .where(AuditLog.action == "contest_settlement")
        )
        audit_list = audit_logs.scalars().all()
        assert len(audit_list) == 1
        assert audit_list[0].details["contest_id"] == str(contest.id)
    
    @pytest.mark.asyncio
    async def test_settlement_idempotency(self, db_session):
        """Test that settlement is idempotent - can be called multiple times safely"""
        # Create users and wallets
        user1_id = uuid4()
        user2_id = uuid4()
        
        wallet1 = await create_wallet_for_user(db_session, user1_id)
        wallet2 = await create_wallet_for_user(db_session, user2_id)
        
        # Create contest
        contest = Contest(
            id=uuid4(),
            match_id=uuid4(),
            code="IDEMP001",
            title="Idempotency Test Contest",
            entry_fee=Decimal("1.0"),
            currency="USDT",
            max_players=2,
            prize_structure=[{"pos": 1, "pct": 100}],
            commission_pct=Decimal("5.0"),
            status=ContestStatus.OPEN
        )
        db_session.add(contest)
        await db_session.commit()
        
        # Create entries
        entry1 = ContestEntry(
            id=uuid4(),
            contest_id=contest.id,
            user_id=user1_id,
            entry_code="ENTRY001",
            amount_debited=Decimal("1.0")
        )
        entry2 = ContestEntry(
            id=uuid4(),
            contest_id=contest.id,
            user_id=user2_id,
            entry_code="ENTRY002",
            amount_debited=Decimal("1.0")
        )
        db_session.add_all([entry1, entry2])
        await db_session.commit()
        
        # First settlement
        result1 = await settle_contest(db_session, contest.id)
        assert result1["success"] is True
        
        # Record balances after first settlement
        await db_session.refresh(wallet1)
        await db_session.refresh(wallet2)
        balance_after_first = wallet1.winning_balance
        
        # Second settlement (should be idempotent)
        result2 = await settle_contest(db_session, contest.id)
        assert result2["success"] is True
        assert result2["status"] == "already_settled"
        
        # Verify balances didn't change
        await db_session.refresh(wallet1)
        await db_session.refresh(wallet2)
        assert wallet1.winning_balance == balance_after_first
        
        # Verify only one transaction was created
        from sqlalchemy import select
        transactions = await db_session.execute(
            select(Transaction)
            .where(Transaction.related_entity == "contest")
            .where(Transaction.related_id == contest.id)
        )
        tx_list = transactions.scalars().all()
        assert len(tx_list) == 1  # Only one transaction, not two
    
    @pytest.mark.asyncio
    async def test_settlement_split_payouts(self, db_session):
        """Test settlement with multiple winners and split payouts"""
        # Create users and wallets
        user_ids = [uuid4() for _ in range(3)]
        wallets = []
        for user_id in user_ids:
            wallet = await create_wallet_for_user(db_session, user_id)
            wallets.append(wallet)
        
        # Create contest
        contest = Contest(
            id=uuid4(),
            match_id=uuid4(),
            code="SPLIT001",
            title="Split Payout Test Contest",
            entry_fee=Decimal("1.0"),
            currency="USDT",
            max_players=3,
            prize_structure=[
                {"pos": 1, "pct": 50},
                {"pos": 2, "pct": 30},
                {"pos": 3, "pct": 20}
            ],
            commission_pct=Decimal("5.0"),
            status=ContestStatus.OPEN
        )
        db_session.add(contest)
        await db_session.commit()
        
        # Create entries
        entries = []
        for i, user_id in enumerate(user_ids):
            entry = ContestEntry(
                id=uuid4(),
                contest_id=contest.id,
                user_id=user_id,
                entry_code=f"ENTRY{i+1:03d}",
                amount_debited=Decimal("1.0")
            )
            entries.append(entry)
        db_session.add_all(entries)
        await db_session.commit()
        
        # Record initial balances
        initial_balances = [wallet.winning_balance for wallet in wallets]
        
        # Settle contest
        result = await settle_contest(db_session, contest.id)
        
        # Verify settlement result
        assert result["success"] is True
        assert result["num_players"] == 3
        assert len(result["payouts"]) == 3
        
        # Verify contest status
        await db_session.refresh(contest)
        assert contest.status == ContestStatus.SETTLED
        
        # Verify wallet balances
        for i, wallet in enumerate(wallets):
            await db_session.refresh(wallet)
            expected_payout = Decimal(result["payouts"][i]["amount"])
            expected_balance = initial_balances[i] + expected_payout
            assert wallet.winning_balance == expected_balance
        
        # Verify transaction records
        from sqlalchemy import select
        transactions = await db_session.execute(
            select(Transaction)
            .where(Transaction.related_entity == "contest")
            .where(Transaction.related_id == contest.id)
        )
        tx_list = transactions.scalars().all()
        assert len(tx_list) == 3  # One transaction per winner
        
        # Verify total payout amount
        total_payouts = sum(Decimal(tx.amount) for tx in tx_list)
        assert total_payouts == Decimal("2.85000000")  # 95% of 3.0
    
    @pytest.mark.asyncio
    async def test_settlement_already_cancelled(self, db_session):
        """Test settlement of already cancelled contest"""
        # Create contest
        contest = Contest(
            id=uuid4(),
            match_id=uuid4(),
            code="CANCEL001",
            title="Cancelled Contest",
            entry_fee=Decimal("1.0"),
            currency="USDT",
            max_players=2,
            prize_structure=[{"pos": 1, "pct": 100}],
            commission_pct=Decimal("5.0"),
            status=ContestStatus.CANCELLED  # Already cancelled
        )
        db_session.add(contest)
        await db_session.commit()
        
        # Try to settle cancelled contest
        result = await settle_contest(db_session, contest.id)
        
        # Should return existing result without error
        assert result["success"] is True
        assert result["status"] == "already_settled"
    
    @pytest.mark.asyncio
    async def test_settlement_no_entries(self, db_session):
        """Test settlement of contest with no entries"""
        # Create contest
        contest = Contest(
            id=uuid4(),
            match_id=uuid4(),
            code="NOENTRY001",
            title="No Entries Contest",
            entry_fee=Decimal("1.0"),
            currency="USDT",
            max_players=2,
            prize_structure=[{"pos": 1, "pct": 100}],
            commission_pct=Decimal("5.0"),
            status=ContestStatus.OPEN
        )
        db_session.add(contest)
        await db_session.commit()
        
        # Try to settle contest with no entries
        with pytest.raises(ValueError, match="No entries found"):
            await settle_contest(db_session, contest.id)
    
    @pytest.mark.asyncio
    async def test_settlement_nonexistent_contest(self, db_session):
        """Test settlement of non-existent contest"""
        fake_contest_id = uuid4()
        
        # Try to settle non-existent contest
        with pytest.raises(ValueError, match="not found"):
            await settle_contest(db_session, fake_contest_id)
