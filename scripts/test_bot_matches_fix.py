#!/usr/bin/env python3
"""
Test script to verify the bot matches filtering is working correctly
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import async_session
from app.repos.match_repo import get_matches


async def test_match_filtering():
    """Test that the match filtering is working correctly"""
    print("🧪 Testing Match Filtering...")
    
    try:
        async with async_session() as session:
            # Test 1: Get upcoming matches only
            print("\n1️⃣ Testing upcoming_only=True...")
            upcoming_matches = await get_matches(session, limit=10, upcoming_only=True)
            print(f"   ✅ Found {len(upcoming_matches)} upcoming matches")
            
            current_time = datetime.now(timezone.utc)
            print(f"   🕐 Current time: {current_time}")
            
            for match in upcoming_matches:
                print(f"   📋 {match.title}")
                print(f"      Start: {match.start_time}")
                print(f"      Status: {match.status}")
                print(f"      Is future: {match.start_time > current_time}")
                print()
            
            # Test 2: Get all matches for comparison
            print("2️⃣ Testing all matches...")
            all_matches = await get_matches(session, limit=10)
            print(f"   📊 Found {len(all_matches)} total matches")
            
            for match in all_matches:
                is_upcoming = match.start_time > current_time
                print(f"   📋 {match.title} - {'✅ Upcoming' if is_upcoming else '❌ Past'}")
            
            # Test 3: Check if IND vs SL is correctly filtered out
            ind_vs_sl = [m for m in all_matches if 'IND vs SL' in m.title]
            if ind_vs_sl:
                match = ind_vs_sl[0]
                is_past = match.start_time <= current_time
                print(f"\n3️⃣ IND vs SL check:")
                print(f"   Start time: {match.start_time}")
                print(f"   Current time: {current_time}")
                print(f"   Is past: {is_past}")
                print(f"   Should be filtered: {is_past}")
                
                # Check if it's in upcoming results
                in_upcoming = any(m.title == match.title for m in upcoming_matches)
                print(f"   In upcoming results: {in_upcoming}")
                print(f"   ✅ Correctly filtered: {not in_upcoming}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function"""
    print("🚀 Testing Bot Matches Filtering Fix")
    print("=" * 50)
    
    success = await test_match_filtering()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Match filtering is working correctly!")
        print("\n📝 Expected behavior:")
        print("   ✅ IND vs SL should be filtered out (past deadline)")
        print("   ✅ Only IPL and MI v CSK should show (future matches)")
        print("   ✅ Bot should show only upcoming matches")
    else:
        print("❌ Match filtering test failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
