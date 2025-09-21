#!/usr/bin/env python3
import os
import asyncio
from app.db.session import async_session
from app.models.admin import Admin
from passlib.hash import bcrypt

ADMIN_USER = os.environ.get("SEED_ADMIN_USERNAME", "admin")
ADMIN_PASS = os.environ.get("SEED_ADMIN_PASSWORD", "admin123")
NO_2FA = os.environ.get("SEED_ADMIN_NO_2FA", "false").lower() in ("1", "true", "yes")

async def run():
    async with async_session() as db:
        q = await db.execute(__import__("sqlalchemy").select(Admin).where(Admin.username == ADMIN_USER))
        if q.scalar_one_or_none():
            print("admin exists:", ADMIN_USER)
            return
        adm = Admin(username=ADMIN_USER, password_hash=bcrypt.hash(ADMIN_PASS))
        if NO_2FA:
            adm.totp_secret = None
        db.add(adm)
        await db.commit()
        print("Seeded admin", ADMIN_USER)

if __name__ == "__main__":
    asyncio.run(run())
