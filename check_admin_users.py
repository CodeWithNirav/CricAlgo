#!/usr/bin/env python3
"""
Check existing admin users
"""
import asyncio
from app.db.session import async_session
from app.models.admin import Admin
from app.models.user import User
from sqlalchemy import select

async def check_admin_users():
    """Check existing admin users"""
    async with async_session() as db:
        # Get all admins
        result = await db.execute(select(Admin))
        admins = result.scalars().all()
        
        if not admins:
            print("❌ No admin users found!")
            print("Run 'python create_admin_user.py' to create one.")
            return
        
        print("✅ Found admin users:")
        print("=" * 50)
        
        for admin in admins:
            print(f"Username: {admin.username}")
            print(f"Email: {admin.email}")
            print(f"Created: {admin.created_at}")
            print("-" * 30)
        
        print(f"\nTotal admins: {len(admins)}")
        print("\n🎯 You can login with any of these usernames!")
        print("Password: admin123 (if created with our script)")

if __name__ == "__main__":
    asyncio.run(check_admin_users())
