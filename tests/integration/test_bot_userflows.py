import pytest, asyncio
from app.bot.handlers.user_commands import cmd_start, cmd_contests
# Basic import test - more thorough tests require aiogram test harness
def test_imports():
    assert cmd_start is not None
    assert cmd_contests is not None
