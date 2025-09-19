"""
Unit tests for contest settlement math calculations
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from app.services.settlement import settle_contest
from app.models.contest import Contest
from app.models.contest_entry import ContestEntry
from app.models.enums import ContestStatus


class TestSettlementMath:
    """Test settlement math calculations with various scenarios"""
    
    @pytest.mark.asyncio
    async def test_winner_takes_all_2_players(self, db_session):
        """Test winner-takes-all with 2 players"""
        # Create contest
        contest = Contest(
            id=uuid4(),
            match_id=uuid4(),
            code="TEST001",
            title="Test Contest",
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
            user_id=uuid4(),
            entry_code="ENTRY001",
            amount_debited=Decimal("1.0")
        )
        entry2 = ContestEntry(
            id=uuid4(),
            contest_id=contest.id,
            user_id=uuid4(),
            entry_code="ENTRY002",
            amount_debited=Decimal("1.0")
        )
        db_session.add_all([entry1, entry2])
        await db_session.commit()
        
        # Settle contest
        result = await settle_contest(db_session, contest.id)
        
        # Verify calculations
        assert result["success"] is True
        assert result["num_players"] == 2
        assert result["total_prize_pool"] == "2.00000000"
        assert result["commission_pct"] == 5.0
        assert result["commission_amount"] == "0.10000000"
        assert result["distributable_pool"] == "1.90000000"
        assert result["total_payouts"] == "1.90000000"
        assert len(result["payouts"]) == 1
        assert result["payouts"][0]["amount"] == "1.90000000"
        assert result["payouts"][0]["position"] == 1
    
    @pytest.mark.asyncio
    async def test_split_payout_3_players(self, db_session):
        """Test split payout with 3 players"""
        # Create contest
        contest = Contest(
            id=uuid4(),
            match_id=uuid4(),
            code="TEST002",
            title="Test Contest",
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
        for i in range(3):
            entry = ContestEntry(
                id=uuid4(),
                contest_id=contest.id,
                user_id=uuid4(),
                entry_code=f"ENTRY{i+1:03d}",
                amount_debited=Decimal("1.0")
            )
            entries.append(entry)
        db_session.add_all(entries)
        await db_session.commit()
        
        # Settle contest
        result = await settle_contest(db_session, contest.id)
        
        # Verify calculations
        assert result["success"] is True
        assert result["num_players"] == 3
        assert result["total_prize_pool"] == "3.00000000"
        assert result["commission_amount"] == "0.15000000"
        assert result["distributable_pool"] == "2.85000000"
        assert result["total_payouts"] == "2.85000000"
        assert len(result["payouts"]) == 3
        
        # Check individual payouts
        payouts = {p["position"]: Decimal(p["amount"]) for p in result["payouts"]}
        assert payouts[1] == Decimal("1.42500000")  # 50% of 2.85
        assert payouts[2] == Decimal("0.85500000")  # 30% of 2.85
        assert payouts[3] == Decimal("0.57000000")  # 20% of 2.85
        
        # Verify total matches distributable pool
        total_payouts = sum(payouts.values())
        assert total_payouts == Decimal("2.85000000")
    
    @pytest.mark.asyncio
    async def test_high_precision_calculations(self, db_session):
        """Test calculations with high precision amounts"""
        # Create contest with odd amounts
        contest = Contest(
            id=uuid4(),
            match_id=uuid4(),
            code="TEST003",
            title="Test Contest",
            entry_fee=Decimal("1.23456789"),
            currency="USDT",
            max_players=2,
            prize_structure=[{"pos": 1, "pct": 100}],
            commission_pct=Decimal("3.33"),
            status=ContestStatus.OPEN
        )
        db_session.add(contest)
        await db_session.commit()
        
        # Create entries
        entry1 = ContestEntry(
            id=uuid4(),
            contest_id=contest.id,
            user_id=uuid4(),
            entry_code="ENTRY001",
            amount_debited=Decimal("1.23456789")
        )
        entry2 = ContestEntry(
            id=uuid4(),
            contest_id=contest.id,
            user_id=uuid4(),
            entry_code="ENTRY002",
            amount_debited=Decimal("1.23456789")
        )
        db_session.add_all([entry1, entry2])
        await db_session.commit()
        
        # Settle contest
        result = await settle_contest(db_session, contest.id)
        
        # Verify calculations maintain precision
        assert result["success"] is True
        assert result["total_prize_pool"] == "2.46913578"
        assert result["commission_amount"] == "0.08222222"  # 3.33% of 2.46913578
        assert result["distributable_pool"] == "2.38691356"
        assert result["total_payouts"] == "2.38691356"
    
    @pytest.mark.asyncio
    async def test_no_commission(self, db_session):
        """Test settlement with no commission"""
        # Create contest
        contest = Contest(
            id=uuid4(),
            match_id=uuid4(),
            code="TEST004",
            title="Test Contest",
            entry_fee=Decimal("1.0"),
            currency="USDT",
            max_players=2,
            prize_structure=[{"pos": 1, "pct": 100}],
            commission_pct=Decimal("0.0"),
            status=ContestStatus.OPEN
        )
        db_session.add(contest)
        await db_session.commit()
        
        # Create entries
        entry1 = ContestEntry(
            id=uuid4(),
            contest_id=contest.id,
            user_id=uuid4(),
            entry_code="ENTRY001",
            amount_debited=Decimal("1.0")
        )
        entry2 = ContestEntry(
            id=uuid4(),
            contest_id=contest.id,
            user_id=uuid4(),
            entry_code="ENTRY002",
            amount_debited=Decimal("1.0")
        )
        db_session.add_all([entry1, entry2])
        await db_session.commit()
        
        # Settle contest
        result = await settle_contest(db_session, contest.id)
        
        # Verify no commission
        assert result["success"] is True
        assert result["commission_pct"] == 0.0
        assert result["commission_amount"] == "0.00000000"
        assert result["total_prize_pool"] == "2.00000000"
        assert result["distributable_pool"] == "2.00000000"
        assert result["total_payouts"] == "2.00000000"
    
    @pytest.mark.asyncio
    async def test_position_beyond_players(self, db_session):
        """Test prize structure with positions beyond number of players"""
        # Create contest
        contest = Contest(
            id=uuid4(),
            match_id=uuid4(),
            code="TEST005",
            title="Test Contest",
            entry_fee=Decimal("1.0"),
            currency="USDT",
            max_players=2,
            prize_structure=[
                {"pos": 1, "pct": 60},
                {"pos": 2, "pct": 30},
                {"pos": 3, "pct": 10}  # This should be skipped
            ],
            commission_pct=Decimal("5.0"),
            status=ContestStatus.OPEN
        )
        db_session.add(contest)
        await db_session.commit()
        
        # Create entries
        entry1 = ContestEntry(
            id=uuid4(),
            contest_id=contest.id,
            user_id=uuid4(),
            entry_code="ENTRY001",
            amount_debited=Decimal("1.0")
        )
        entry2 = ContestEntry(
            id=uuid4(),
            contest_id=contest.id,
            user_id=uuid4(),
            entry_code="ENTRY002",
            amount_debited=Decimal("1.0")
        )
        db_session.add_all([entry1, entry2])
        await db_session.commit()
        
        # Settle contest
        result = await settle_contest(db_session, contest.id)
        
        # Verify only 2 payouts (position 3 skipped)
        assert result["success"] is True
        assert len(result["payouts"]) == 2
        assert result["payouts"][0]["position"] == 1
        assert result["payouts"][1]["position"] == 2
        
        # Verify total percentage is 90% (60% + 30%)
        payouts = {p["position"]: Decimal(p["amount"]) for p in result["payouts"]}
        total_payouts = sum(payouts.values())
        expected_total = Decimal("1.90000000") * Decimal("0.90")  # 90% of distributable pool
        assert total_payouts == expected_total
    
    @pytest.mark.asyncio
    async def test_default_winner_takes_all(self, db_session):
        """Test default winner-takes-all when no prize structure provided"""
        # Create contest with no prize structure
        contest = Contest(
            id=uuid4(),
            match_id=uuid4(),
            code="TEST006",
            title="Test Contest",
            entry_fee=Decimal("1.0"),
            currency="USDT",
            max_players=2,
            prize_structure=None,  # No prize structure
            commission_pct=Decimal("5.0"),
            status=ContestStatus.OPEN
        )
        db_session.add(contest)
        await db_session.commit()
        
        # Create entries
        entry1 = ContestEntry(
            id=uuid4(),
            contest_id=contest.id,
            user_id=uuid4(),
            entry_code="ENTRY001",
            amount_debited=Decimal("1.0")
        )
        entry2 = ContestEntry(
            id=uuid4(),
            contest_id=contest.id,
            user_id=uuid4(),
            entry_code="ENTRY002",
            amount_debited=Decimal("1.0")
        )
        db_session.add_all([entry1, entry2])
        await db_session.commit()
        
        # Settle contest
        result = await settle_contest(db_session, contest.id)
        
        # Verify default winner-takes-all
        assert result["success"] is True
        assert result["prize_structure"] == [{"pos": 1, "pct": 100}]
        assert len(result["payouts"]) == 1
        assert result["payouts"][0]["position"] == 1
        assert result["payouts"][0]["amount"] == "1.90000000"
