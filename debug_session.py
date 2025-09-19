#!/usr/bin/env python3
import asyncio
from app.db.session import get_db

async def test_session():
    async with get_db() as session:
        print('Session type:', type(session))
        print('Session has execute:', hasattr(session, 'execute'))

if __name__ == "__main__":
    asyncio.run(test_session())
