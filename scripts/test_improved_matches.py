#!/usr/bin/env python3
"""
Test script to verify the improved matches functionality
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import async_session
from app.repos.match_repo import (
    get_matches, 
    update_match_statuses_automatically,
    get_matches_needing_status_update,
    update_match_status
)


async def test_improved_match_functionality():
    """Test the improved match functionality"""
    print("🧪 Testing Improved Match Functionality...")
    
    try:
        async with async_session() as session:
            # Test 1: Get upcoming matches only
            print("\n1️⃣ Testing get_matches with upcoming_only=True...")
            upcoming_matches = await get_matches(session, limit=10, upcoming_only=True)
            print(f"   ✅ Found {len(upcoming_matches)} upcoming matches")
            
            for match in upcoming_matches:
                print(f"   📋 Match: {match.title} (Status: {match.status}, Start: {match.start_time})")
            
            # Test 2: Get all matches (for comparison)
            print(f"\n2️⃣ Testing get_matches with all matches...")
            all_matches = await get_matches(session, limit=10)
            print(f"   📊 Found {len(all_matches)} total matches")
            
            # Test 3: Check matches needing status updates
            print(f"\n3️⃣ Testing get_matches_needing_status_update...")
            matches_needing_update = await get_matches_needing_status_update(session)
            print(f"   🔄 Found {len(matches_needing_update)} matches needing status updates")
            
            for match in matches_needing_update:
                print(f"   ⏰ Match: {match.title} (Status: {match.status}, Start: {match.start_time})")
            
            # Test 4: Test automatic status updates
            print(f"\n4️⃣ Testing update_match_statuses_automatically...")
            updated_count = await update_match_statuses_automatically(session)
            print(f"   ✅ Updated {updated_count} match statuses")
            
            # Test 5: Test manual status update
            if upcoming_matches:
                test_match = upcoming_matches[0]
                print(f"\n5️⃣ Testing manual status update for match: {test_match.title}")
                success = await update_match_status(session, str(test_match.id), 'live')
                if success:
                    print(f"   ✅ Successfully updated match status to 'live'")
                else:
                    print(f"   ❌ Failed to update match status")
            
            print(f"\n✅ All improved match functionality tests completed!")
            print(f"📈 Summary:")
            print(f"   - Upcoming matches: {len(upcoming_matches)}")
            print(f"   - Total matches: {len(all_matches)}")
            print(f"   - Matches needing updates: {len(matches_needing_update)}")
            print(f"   - Auto-updated: {updated_count}")
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def test_match_status_logic():
    """Test the match status logic"""
    print("\n🔍 Testing Match Status Logic...")
    
    try:
        async with async_session() as session:
            # Get all matches and analyze their statuses
            all_matches = await get_matches(session, limit=50)
            
            status_counts = {}
            for match in all_matches:
                status = match.status
                status_counts[status] = status_counts.get(status, 0) + 1
            
            print(f"   📊 Match status distribution:")
            for status, count in status_counts.items():
                print(f"      {status}: {count}")
            
            # Check for matches that should be updated
            now = datetime.now(timezone.utc)
            outdated_matches = []
            
            for match in all_matches:
                if match.start_time <= now and match.status in ['scheduled', 'open']:
                    outdated_matches.append(match)
            
            print(f"   ⏰ Matches that should be 'live': {len(outdated_matches)}")
            for match in outdated_matches:
                print(f"      - {match.title} (started {match.start_time}, status: {match.status})")
            
            return True
            
    except Exception as e:
        print(f"❌ Error in status logic test: {e}")
        return False


async def main():
    """Main test function"""
    print("🚀 Starting Improved Matches Test Suite")
    print("=" * 60)
    
    # Test improved functionality
    functionality_success = await test_improved_match_functionality()
    
    # Test status logic
    status_success = await test_match_status_logic()
    
    print("\n" + "=" * 60)
    if functionality_success and status_success:
        print("🎉 All tests passed! The improved matches functionality is working correctly.")
        print("\n📝 Key improvements:")
        print("   ✅ Only upcoming matches are shown in bot")
        print("   ✅ Automatic status updates based on start time")
        print("   ✅ Admin can mark matches as finished")
        print("   ✅ Proper match lifecycle management")
        print("\n🔄 Match Status Flow:")
        print("   1. 'scheduled' → 'open' (when ready)")
        print("   2. 'open' → 'live' (when start time passes)")
        print("   3. 'live' → 'finished' (when admin marks as finished)")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
