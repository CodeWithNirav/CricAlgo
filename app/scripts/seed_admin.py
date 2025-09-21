#!/usr/bin/env python3
"""
Seed a static super-admin user (no 2FA) for fast testing.
Usage:
  ADMIN_USERNAME=admin@staging.local ADMIN_PASSWORD=ChangeMeNow! python app/scripts/seed_admin.py
"""
import os
from sqlalchemy import select
from app.db.session import async_session
from app.models.admin import Admin
import asyncio
from app.core.auth import get_password_hash

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME","admin@staging.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD","ChangeMeNow!")

async def run():
    async with async_session() as session:
        # check existing
        q = await session.execute(select(Admin).where(Admin.username==ADMIN_USERNAME))
        admin = q.scalar_one_or_none()
        if admin:
            print("Admin exists:", ADMIN_USERNAME)
            return
        hashed = get_password_hash(ADMIN_PASSWORD)
        a = Admin(username=ADMIN_USERNAME, password_hash=hashed, totp_secret=None)
        session.add(a)
        await session.commit()
        print("Created admin:", ADMIN_USERNAME)

if __name__=="__main__":
    asyncio.run(run())
