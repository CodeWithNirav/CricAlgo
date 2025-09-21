#!/usr/bin/env python3
"""
Seed invite_codes table with sample data if it doesn't exist
Safe to run multiple times - only inserts if no codes exist
"""

import asyncio
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import get_db
from app.models.invitation_code import InvitationCode

async def seed_invite_codes():
    """Seed invite_codes table with sample data if empty"""
    async for db in get_db():
        try:
            # Check if any invite codes exist
            result = await db.execute(select(InvitationCode).limit(1))
            existing_codes = result.scalars().all()
            
            if existing_codes:
                print(f"✓ Invite codes table already has {len(existing_codes)} codes, skipping seed")
                return
            
            # Create sample invite code
            sample_code = InvitationCode(
                code="TEST-CODE-001",
                max_uses=10,
                uses=0,
                enabled=True,
                created_by=None
            )
            
            db.add(sample_code)
            await db.commit()
            print("✓ Created sample invite code: TEST-CODE-001")
            
        except Exception as e:
            print(f"✗ Error seeding invite codes: {e}")
            await db.rollback()
        finally:
            await db.close()
        break

if __name__ == "__main__":
    asyncio.run(seed_invite_codes())
