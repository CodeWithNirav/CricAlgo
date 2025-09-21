from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.db.session import async_session
from app.repos.user_repo import create_user_if_not_exists, get_user_by_telegram, save_chat_id
from app.repos.contest_repo import list_active_contests, join_contest_atomic, get_contest_detail
from app.repos.wallet_repo import get_wallet_by_user
from app.core.redis_client import redis_client
import json, uuid, asyncio

router = Router()

@router.message(Command("start"))
async def cmd_start(msg: types.Message):
    # Expect optional invite code: "/start INV123"
    parts = (msg.text or "").strip().split()
    invite = parts[1] if len(parts)>1 else None
    async with async_session() as db:
        user = await create_user_if_not_exists(db, msg.from_user.id, msg.from_user.username or str(msg.from_user.id), invite_code=invite)
        # save chat id for notifications
        await save_chat_id(db, user.id, msg.chat.id)
    await msg.reply(f"Welcome, {user.username}. Use /contests to list contests, /balance to check wallet.")

@router.message(Command("balance"))
async def cmd_balance(msg: types.Message):
    async with async_session() as db:
        u = await get_user_by_telegram(db, msg.from_user.id)
        if not u:
            return await msg.reply("User not registered. Please /start with invite code.")
        w = await get_wallet_by_user(db, u.id)
        text = f"Balances:\nDeposit: {w.deposit_balance}\nWinning: {w.winning_balance}\nBonus: {w.bonus_balance}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton("Transactions", callback_data=f"txs:{u.id}")]])
        await msg.reply(text, reply_markup=kb)

@router.message(Command("contests"))
async def cmd_contests(msg: types.Message):
    async with async_session() as db:
        contests = await list_active_contests(db)
    if not contests:
        return await msg.reply("No open contests right now.")
    kb = InlineKeyboardMarkup(row_width=1)
    for c in contests:
        kb.add(InlineKeyboardButton(f"{c.title} — {c.entry_fee}", callback_data=f"details:{c.id}"))
    await msg.reply("Open contests:", reply_markup=kb)

@router.callback_query(lambda c: c.data and c.data.startswith("details:"))
async def cb_contest_details(query: types.CallbackQuery):
    _, cid = query.data.split(":",1)
    async with async_session() as db:
        contest = await get_contest_detail(db, cid)
    if not contest:
        return await query.answer("Contest not found", show_alert=True)
    kb = InlineKeyboardMarkup(row_width=2)
    nonce = str(uuid.uuid4().hex)
    kb.add(InlineKeyboardButton("Join", callback_data=f"join:{cid}:{nonce}"))
    kb.add(InlineKeyboardButton("Refresh", callback_data=f"details:{cid}"))
    text = f"{contest.title}\nEntry fee: {contest.entry_fee}\nMax players: {contest.max_players}"
    await query.message.edit_text(text, reply_markup=kb)
    await query.answer()

@router.callback_query(lambda c: c.data and c.data.startswith("join:"))
async def cb_join(query: types.CallbackQuery):
    # join:<contest_id>:<nonce>
    parts = query.data.split(":")
    if len(parts) < 3:
        return await query.answer("Invalid request", show_alert=True)
    _, cid, nonce = parts
    uid = query.from_user.id
    idempotency_key = f"bot:join:{cid}:{uid}"
    # simple redis idempotency
    taken = await redis_client.get(idempotency_key)
    if taken:
        return await query.answer("Processing or already joined.", show_alert=False)
    await redis_client.setex(idempotency_key, 30, "1")
    try:
        async with async_session() as db:
            # atomically try to join (wallet debit inside repo)
            res = await join_contest_atomic(db, contest_id=cid, telegram_id=uid)
            if res["ok"]:
                await query.message.edit_text(f"✅ Joined contest: {res['contest_title']}\nEntry fee: {res['entry_fee']}")
                await query.answer("Joined")
            else:
                await query.answer(res.get("error","Could not join"), show_alert=True)
    except Exception as e:
        await query.answer("Error joining contest", show_alert=True)
    finally:
        await redis_client.delete(idempotency_key)
