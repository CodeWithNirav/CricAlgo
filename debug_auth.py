#!/usr/bin/env python3
import asyncio
from app.db.session import get_db
from app.repos.user_repo import get_user_by_username

async def test_auth():
    async with get_db() as session:
        print('Testing get_user_by_username...')
        try:
            user = await get_user_by_username(session, "admin_admin")
            print('User found:', user.username if user else None)
        except Exception as e:
            print('Error:', e)

if __name__ == "__main__":
    asyncio.run(test_auth())
