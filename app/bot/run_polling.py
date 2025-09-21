import os, asyncio
from aiogram import Bot, Dispatcher
from app.bot.handlers.user_commands import router as user_router
from aiogram.fsm.storage.memory import MemoryStorage

async def run_bot():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN not set - bot will not run")
        return
    bot = Bot(token=token, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(user_router)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(run_bot())
