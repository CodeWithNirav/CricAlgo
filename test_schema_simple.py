#!/usr/bin/env python3
"""
Simple test to verify contest schema changes work correctly
"""

import asyncio
import sys
from decimal import Decimal
from uuid import uuid4

# Add the app directory to the path
sys.path.insert(0, '.')

from app.db.session import AsyncSessionLocal
from app.models.contest import Contest
from app.models.contest_entry import ContestEntry
from app.models.user import User
from app.models.wallet import Wallet
from app.models.enums import ContestStatus, UserStatus
from app.repos.contest_repo import create_contest
from app.repos.contest_entry_repo import create_contest_entry
from app.repos.user_repo import create_user
from app.repos.wallet_repo import debit_for_contest_entry, credit_deposit_atomic


async def test_schema_fields():
    """Test that the new schema fields are working correctly"""
    print("🧪 Testing contest schema fields...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Create a test user
            print("1. Creating test user...")
            user = await create_user(
                session=session,
                telegram_id=66666,
                username="test_schema_user_66666",
                status=UserStatus.ACTIVE
            )
            print(f"   ✅ User created: {user.id}")
            
            # Fund the user's wallet
            print("2. Funding user wallet...")
            success, error, new_balance = await credit_deposit_atomic(
                session=session,
                user_id=user.id,
                amount=Decimal("10.0")
            )
            assert success, f"Failed to fund user: {error}"
            print(f"   ✅ User wallet funded with balance: {new_balance}")
            
            # Create a match first
            print("3. Creating test match...")
            from app.models.match import Match
            match = Match(
                id=uuid4(),
                external_id="test_match_123",
                title="Test Match",
                start_time="2025-09-20T20:00:00Z"
            )
            session.add(match)
            await session.commit()
            print(f"   ✅ Match created: {match.id}")
            
            # Create a contest
            print("4. Creating contest...")
            contest = await create_contest(
                session=session,
                match_id=str(match.id),
                title="Schema Test Contest",
                entry_fee=Decimal("1.0"),
                max_participants=5,
                prize_structure=[{"pos": 1, "pct": 100}]
            )
            print(f"   ✅ Contest created: {contest.id}")
            print(f"   - Title: {contest.title}")
            print(f"   - Entry fee: {contest.entry_fee}")
            print(f"   - Max players: {contest.max_players}")
            print(f"   - Prize structure: {contest.prize_structure}")
            print(f"   - Status: {contest.status}")
            print(f"   - Settled at: {contest.settled_at}")
            print(f"   - Updated at: {contest.updated_at}")
            
            # Test updating settled_at
            print("5. Testing settled_at field...")
            from datetime import datetime, timezone
            contest.settled_at = datetime.now(timezone.utc)
            contest.status = ContestStatus.SETTLED
            await session.commit()
            print(f"   ✅ Contest settled at: {contest.settled_at}")
            print(f"   ✅ Contest status: {contest.status}")
            
            # Join the contest
            print("6. Joining contest...")
            entry = await create_contest_entry(
                session=session,
                contest_id=contest.id,
                user_id=user.id,
                entry_fee=Decimal("1.0")
            )
            print(f"   ✅ Contest entry created: {entry.id}")
            print(f"   - Contest ID: {entry.contest_id}")
            print(f"   - User ID: {entry.user_id}")
            print(f"   - Amount debited: {entry.amount_debited}")
            print(f"   - Payout TX ID: {entry.payout_tx_id}")
            
            # Test updating payout_tx_id
            print("7. Testing payout_tx_id field...")
            entry.payout_tx_id = uuid4()
            await session.commit()
            print(f"   ✅ Payout TX ID set: {entry.payout_tx_id}")
            
            print("\n🎉 All schema tests passed! The new fields are working correctly.")
            return True
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = asyncio.run(test_schema_fields())
    sys.exit(0 if success else 1)
