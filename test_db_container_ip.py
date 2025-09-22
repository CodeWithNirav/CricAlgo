#!/usr/bin/env python3
"""
Test database connection using container IP
"""

import asyncio
import asyncpg

async def test_db_connection():
    """Test direct database connection using container IP"""
    try:
        # Test direct connection using container IP
        conn = await asyncpg.connect(
            host='172.18.0.2',  # Container IP
            port=5432,
            user='postgres',
            password='password',
            database='cricalgo'
        )
        
        # Test query
        result = await conn.fetchval('SELECT 1')
        print(f"✅ Container IP database connection: OK (Result: {result})")
        
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
            
            # List tables
            tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            print(f"✅ Available tables: {[t['table_name'] for t in tables]}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Container IP database connection failed: {e}")
        return False

async def test_sqlalchemy_container_ip():
    """Test SQLAlchemy connection using container IP"""
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        
        # Create engine with container IP
        engine = create_async_engine(
            'postgresql+asyncpg://postgres:password@172.18.0.2:5432/cricalgo'
        )
        
        async with engine.begin() as conn:
            result = await conn.execute(text('SELECT 1'))
            value = result.scalar()
            print(f"✅ SQLAlchemy container IP connection: OK (Result: {value})")
        
        await engine.dispose()
        return True
        
    except Exception as e:
        print(f"❌ SQLAlchemy container IP connection failed: {e}")
        return False

async def main():
    print("🧪 Testing Database Connection with Container IP")
    print("=" * 50)
    
    # Test direct connection
    print("\n🔍 Testing direct asyncpg connection with container IP...")
    direct_ok = await test_db_connection()
    
    # Test SQLAlchemy connection
    print("\n🔍 Testing SQLAlchemy connection with container IP...")
    sqlalchemy_ok = await test_sqlalchemy_container_ip()
    
    print("\n" + "=" * 50)
    if direct_ok and sqlalchemy_ok:
        print("🎉 All database tests passed with container IP!")
    else:
        print("⚠️  Some database tests failed with container IP.")

if __name__ == "__main__":
    asyncio.run(main())
