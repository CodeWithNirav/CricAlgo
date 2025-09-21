#!/usr/bin/env python3
"""
Simple admin user creation for testing with SQLite
"""

import asyncio
import os
import sys
import uuid
from decimal import Decimal

# Add current directory to Python path
sys.path.insert(0, '.')

from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

# Set environment variables
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_admin_user():
    """Create an admin user for testing"""
    
    # Create async engine for SQLite
    engine = create_async_engine(
        "sqlite+aiosqlite:///./test.db",
        echo=True,
        future=True
    )
    
    # Create async session factory
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with AsyncSessionLocal() as session:
        try:
            # Create the admins table if it doesn't exist
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS admins (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    email TEXT,
                    totp_secret TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME
                )
            """))
            
            # Check if admin already exists
            result = await session.execute(text("SELECT id FROM admins WHERE username = 'admin'"))
            existing_admin = result.fetchone()
            
            if existing_admin:
                print("Admin user already exists")
                return
            
            # Create admin user
            admin_id = str(uuid.uuid4())
            hashed_password = pwd_context.hash("admin123")
            
            await session.execute(text("""
                INSERT INTO admins (id, username, password_hash, email, totp_secret, created_at)
                VALUES (:id, :username, :password_hash, :email, :totp_secret, CURRENT_TIMESTAMP)
            """), {
                "id": admin_id,
                "username": "admin",
                "password_hash": hashed_password,
                "email": "admin@cricalgo.com",
                "totp_secret": None
            })
            
            await session.commit()
            
            print("Admin user created successfully!")
            print("Username: admin")
            print("Password: admin123")
            print(f"Admin ID: {admin_id}")
            
        except Exception as e:
            print(f"Error creating admin user: {e}")
            await session.rollback()
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_admin_user())