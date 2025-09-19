#!/usr/bin/env python3
"""
Debug script to test contest creation
"""

import asyncio
import os
import sys
from decimal import Decimal

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import AsyncSessionLocal
from app.repos.contest_repo import create_contest

async def test_contest_creation():
    """Test contest creation directly"""
    try:
        async with AsyncSessionLocal() as session:
            print("Testing contest creation...")
            
            contest = await create_contest(
                session=session,
                match_id="test_match_123",
                title="Debug Test Contest",
                description="Test contest for debugging",
                entry_fee=Decimal("1.0"),
                max_participants=2,
                prize_structure=[{"pos": 1, "pct": 100}],
                created_by=None
            )
            
            print(f"✓ Contest created successfully: {contest.id}")
            print(f"  Title: {contest.title}")
            print(f"  Match ID: {contest.match_id}")
            print(f"  Code: {contest.code}")
            
    except Exception as e:
        print(f"✗ Contest creation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_contest_creation())
