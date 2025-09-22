#!/usr/bin/env python3
"""
Test bot functionality inside container
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.db.session import async_session
from app.models.user import User
from sqlalchemy import select

async def test_database_connection():
    """Test database connection"""
    try:
        async with async_session() as session:
            result = await session.execute(select(User).limit(1))
            users = result.scalars().all()
            print("✅ Database connection: OK")
            print(f"   Found {len(users)} users in database")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

async def test_user_operations():
    """Test basic user operations"""
    try:
        from app.repos.user_repo import create_user, get_user_by_telegram_id
        from app.repos.wallet_repo import create_wallet_for_user, get_wallet_for_user
        from app.models.enums import UserStatus
        
        async with async_session() as session:
            # Test user creation
            test_telegram_id = 123456789
            test_username = "test_user_bot_container"
            
            # Clean up any existing test user
            existing_user = await get_user_by_telegram_id(session, test_telegram_id)
            if existing_user:
                print("   Cleaning up existing test user...")
                await session.delete(existing_user)
                await session.commit()
            
            # Create test user
            user = await create_user(
                session=session,
                telegram_id=test_telegram_id,
                username=test_username,
                status=UserStatus.ACTIVE
            )
            print(f"✅ User creation: OK (ID: {user.id})")
            
            # Create wallet
            wallet = await create_wallet_for_user(session, user.id)
            print(f"✅ Wallet creation: OK (ID: {wallet.id})")
            
            # Test wallet retrieval
            retrieved_wallet = await get_wallet_for_user(session, user.id)
            if retrieved_wallet:
                print(f"✅ Wallet retrieval: OK (Balance: {retrieved_wallet.deposit_balance})")
            else:
                print("❌ Wallet retrieval: Failed")
                return False
            
            # Clean up test user
            await session.delete(user)
            await session.commit()
            print("✅ Test cleanup: OK")
            
            return True
    except Exception as e:
        print(f"❌ User operations failed: {e}")
        return False

async def test_contest_operations():
    """Test basic contest operations"""
    try:
        from app.repos.contest_repo import get_contests
        from decimal import Decimal
        
        async with async_session() as session:
            # Test contest retrieval
            contests = await get_contests(session, limit=5)
            print(f"✅ Contest retrieval: OK (Found {len(contests)} contests)")
            
            if contests:
                contest = contests[0]
                print(f"   Sample contest: {contest.title} (Entry: {contest.entry_fee} {contest.currency})")
            
            return True
    except Exception as e:
        print(f"❌ Contest operations failed: {e}")
        return False

async def test_bot_creation():
    """Test bot creation"""
    try:
        from app.bot.telegram_bot import create_bot, create_dispatcher
        bot = create_bot()
        dp = create_dispatcher()
        print("✅ Bot creation: OK")
        print(f"   Bot token configured: {'Yes' if settings.telegram_bot_token else 'No'}")
        return True
    except Exception as e:
        print(f"❌ Bot creation failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🧪 Testing CricAlgo Bot Inside Container")
    print("=" * 50)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Bot Creation", test_bot_creation),
        ("User Operations", test_user_operations),
        ("Contest Operations", test_contest_operations),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 Testing {test_name}...")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 All tests passed! Bot should be ready to run.")
    else:
        print(f"\n⚠️  {len(results) - passed} tests failed. Check the issues above.")

if __name__ == "__main__":
    asyncio.run(main())
