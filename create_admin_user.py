#!/usr/bin/env python3
"""
Create admin user for testing
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import hashlib

# Set environment
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:password@localhost:5432/cricalgo"

from app.db.session import get_db
from app.models.admin import Admin

async def create_admin():
    """Create admin user"""
    try:
        async for db in get_db():
            # Check if admin already exists
            result = await db.execute(select(Admin).where(Admin.username == "admin"))
            existing_admin = result.scalar_one_or_none()
            
            if existing_admin:
                print("✅ Admin user already exists!")
                print(f"Username: admin")
                print(f"Password: admin123")
                return
            
            # Create new admin
            admin = Admin(
                username="admin",
                email="admin@cricalgo.com",
                hashed_password=hashlib.sha256("admin123".encode()).hexdigest(),  # Simple hash for testing
                is_active=True
            )
            
            db.add(admin)
            await db.commit()
            await db.refresh(admin)
            
            print("✅ Admin user created successfully!")
            print(f"Username: admin")
            print(f"Password: admin123")
            print(f"Email: admin@cricalgo.com")
            
    except Exception as e:
        print(f"❌ Error creating admin: {e}")

if __name__ == "__main__":
    asyncio.run(create_admin())