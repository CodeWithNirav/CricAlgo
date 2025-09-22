#!/usr/bin/env python3
"""
Simple database connection test
"""

import asyncio
import asyncpg

async def test_db_connection():
    """Test direct database connection"""
    try:
        # Test direct connection
        conn = await asyncpg.connect(
            host='localhost',
            port=5432,
            user='postgres',
            password='password',
            database='cricalgo'
        )
        
        # Test query
        result = await conn.fetchval('SELECT 1')
        print(f"✅ Direct database connection: OK (Result: {result})")
        
        # Test if users table exists
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'users'
            )
        """)
        print(f"✅ Users table exists: {table_exists}")
        
        if table_exists:
            # Count users
            user_count = await conn.fetchval('SELECT COUNT(*) FROM users')
            print(f"✅ User count: {user_count}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Direct database connection failed: {e}")
        return False

async def test_sqlalchemy_connection():
    """Test SQLAlchemy connection"""
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        
        # Create engine with localhost
        engine = create_async_engine(
            'postgresql+asyncpg://postgres:password@localhost:5432/cricalgo'
        )
        
        async with engine.begin() as conn:
            result = await conn.execute(text('SELECT 1'))
            value = result.scalar()
            print(f"✅ SQLAlchemy connection: OK (Result: {value})")
        
        await engine.dispose()
        return True
        
    except Exception as e:
        print(f"❌ SQLAlchemy connection failed: {e}")
        return False

async def main():
    print("🧪 Testing Database Connections")
    print("=" * 40)
    
    # Test direct connection
    print("\n🔍 Testing direct asyncpg connection...")
    direct_ok = await test_db_connection()
    
    # Test SQLAlchemy connection
    print("\n🔍 Testing SQLAlchemy connection...")
    sqlalchemy_ok = await test_sqlalchemy_connection()
    
    print("\n" + "=" * 40)
    if direct_ok and sqlalchemy_ok:
        print("🎉 All database tests passed!")
    else:
        print("⚠️  Some database tests failed.")

if __name__ == "__main__":
    asyncio.run(main())
