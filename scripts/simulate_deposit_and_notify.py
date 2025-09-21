#!/usr/bin/env python3
"""
Simulate a deposit being processed and notify user via telegram bot (requires TELEGRAM_BOT_TOKEN and TELEGRAM_TEST_USER_ID)
"""
import os, asyncio
from aiogram import Bot
from app.db.session import async_session
from app.models.user import User
from app.models.chat_map import ChatMap

async def run():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Set TELEGRAM_BOT_TOKEN to simulate notifications")
        return
    bot = Bot(token=token)
    # find test user mapping
    async with async_session() as db:
        q = await db.execute(__import__("sqlalchemy").select(ChatMap).limit(1))
        m = q.scalar_one_or_none()
        if not m:
            print("No chat mapping found in DB. Run /start from user first.")
            return
        chat = m.chat_id
    await bot.send_message(chat, "Simulated deposit credited: +10.00 USDT ❤️")
    await bot.session.close()

if __name__=="__main__":
    asyncio.run(run())
