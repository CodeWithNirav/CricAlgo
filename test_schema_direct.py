#!/usr/bin/env python3
"""
Direct test to verify contest schema changes work correctly
"""

import asyncio
import sys
from decimal import Decimal
from uuid import uuid4
from datetime import datetime, timezone

# Add the app directory to the path
sys.path.insert(0, '.')

from app.db.session import AsyncSessionLocal
from app.models.contest import Contest
from app.models.contest_entry import ContestEntry
from app.models.user import User
from app.models.wallet import Wallet
from app.models.enums import ContestStatus, UserStatus
from app.repos.user_repo import create_user
from app.repos.wallet_repo import credit_deposit_atomic
from sqlalchemy import text


async def test_schema_direct():
    """Test that the new schema fields are working correctly"""
    print("🧪 Testing contest schema fields directly...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Create a test user
            print("1. Creating test user...")
            user = await create_user(
                session=session,
                telegram_id=44444,
                username="test_schema_user_44444",
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
            
            # Create a match directly in the database
            print("3. Creating test match...")
            match_id = uuid4()
            await session.execute(text("""
                INSERT INTO matches (id, external_id, title, start_time, status)
                VALUES (:id, :external_id, :title, :start_time, :status)
            """), {
                "id": match_id,
                "external_id": "test_match_123",
                "title": "Test Match",
                "start_time": datetime.now(timezone.utc),
                "status": "scheduled"
            })
            await session.commit()
            print(f"   ✅ Match created: {match_id}")
            
            # Create a contest
            print("4. Creating contest...")
            contest = Contest(
                id=uuid4(),
                match_id=match_id,
                code="TEST_SCHEMA_001",
                title="Schema Test Contest",
                entry_fee=Decimal("1.0"),
                currency="USDT",
                max_players=5,
                prize_structure=[{"pos": 1, "pct": 100}],
                commission_pct=Decimal("5.0"),
                status="open",
                settled_at=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            session.add(contest)
            await session.commit()
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
            contest.settled_at = datetime.now(timezone.utc)
            contest.status = "settled"
            await session.commit()
            print(f"   ✅ Contest settled at: {contest.settled_at}")
            print(f"   ✅ Contest status: {contest.status}")
            
            # Create a contest entry
            print("6. Creating contest entry...")
            entry = ContestEntry(
                id=uuid4(),
                contest_id=contest.id,
                user_id=user.id,
                entry_code="ENTRY_TEST_001",
                amount_debited=Decimal("1.0"),
                payout_tx_id=None,
                created_at=datetime.now(timezone.utc)
            )
            session.add(entry)
            await session.commit()
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
            
            # Verify the schema changes in the database
            print("8. Verifying schema in database...")
            result = await session.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'contests' AND column_name IN ('settled_at', 'updated_at')
                ORDER BY column_name
            """))
            contest_columns = result.fetchall()
            print(f"   ✅ Contest schema columns: {contest_columns}")
            
            result = await session.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'contest_entries' AND column_name = 'payout_tx_id'
                ORDER BY column_name
            """))
            entry_columns = result.fetchall()
            print(f"   ✅ Contest entries schema columns: {entry_columns}")
            
            result = await session.execute(text("""
                SELECT unnest(enum_range(NULL::contest_status))
            """))
            enum_values = [row[0] for row in result.fetchall()]
            print(f"   ✅ Contest status enum values: {enum_values}")
            
            print("\n🎉 All schema tests passed! The new fields are working correctly.")
            return True
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = asyncio.run(test_schema_direct())
    sys.exit(0 if success else 1)
