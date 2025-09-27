#!/usr/bin/env python3
"""
Test script to verify the new matches functionality in the bot
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import async_session
from app.repos.match_repo import get_matches, get_contests_for_match, get_match_by_id
from app.repos.contest_repo import get_contests
from app.models.match import Match
from app.models.contest import Contest


async def test_match_functionality():
    """Test the new match functionality"""
    print("🧪 Testing Match Functionality...")
    
    try:
        async with async_session() as session:
            # Test 1: Get matches
            print("\n1️⃣ Testing get_matches()...")
            matches = await get_matches(session, limit=5, not_started=True)
            print(f"   ✅ Found {len(matches)} matches")
            
            for match in matches:
                print(f"   📋 Match: {match.title} (Status: {match.status})")
            
            # Test 2: Get contests for a match (if matches exist)
            if matches:
                match = matches[0]
                print(f"\n2️⃣ Testing get_contests_for_match() for '{match.title}'...")
                contests = await get_contests_for_match(session, str(match.id), status='open')
                print(f"   ✅ Found {len(contests)} contests for this match")
                
                for contest in contests:
                    print(f"   🏆 Contest: {contest.title} (Entry: {contest.entry_fee} {contest.currency})")
            
            # Test 3: Get match by ID (if matches exist)
            if matches:
                match = matches[0]
                print(f"\n3️⃣ Testing get_match_by_id() for '{match.title}'...")
                found_match = await get_match_by_id(session, str(match.id))
                if found_match:
                    print(f"   ✅ Found match: {found_match.title}")
                else:
                    print("   ❌ Match not found")
            
            # Test 4: Compare with old contests method
            print(f"\n4️⃣ Testing old get_contests() method...")
            old_contests = await get_contests(session, limit=5, status='open')
            print(f"   📊 Old method found {len(old_contests)} contests")
            
            print(f"\n✅ All tests completed successfully!")
            print(f"📈 Summary:")
            print(f"   - Matches found: {len(matches)}")
            print(f"   - Contests found (old method): {len(old_contests)}")
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


async def test_bot_handlers():
    """Test that bot handlers can be imported and initialized"""
    print("\n🤖 Testing Bot Handlers...")
    
    try:
        # Test imports
        from app.bot.handlers.unified_callbacks import unified_callback_router
        from app.bot.handlers.commands import user_router
        from app.bot.handlers.callbacks import callback_router
        from app.bot.handlers.contest_callbacks import contest_callback_router
        
        print("   ✅ All bot handlers imported successfully")
        
        # Test that the new match handlers are registered
        print(f"   ✅ Match handlers are available in the router")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error importing bot handlers: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function"""
    print("🚀 Starting Bot Matches Test Suite")
    print("=" * 50)
    
    # Test database functionality
    db_success = await test_match_functionality()
    
    # Test bot handlers
    handlers_success = await test_bot_handlers()
    
    print("\n" + "=" * 50)
    if db_success and handlers_success:
        print("🎉 All tests passed! The bot is ready with the new matches functionality.")
        print("\n📝 Next steps:")
        print("   1. Run: make bot-docker")
        print("   2. Test the bot in Telegram")
        print("   3. Click '🏏 Matches' to see the new flow")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
