from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from app.core.auth import get_current_admin
from app.db.session import get_db
from app.models.invitation_code import InvitationCode
from app.models.user import User
from app.models.wallet import Wallet
from app.models.audit_log import AuditLog
from decimal import Decimal

router = APIRouter(prefix="/api/v1/admin", tags=["admin_manage"], dependencies=[Depends(get_current_admin)])

@router.get("/invite_codes")
async def list_invite_codes(db=Depends(get_db)):
    q = await db.execute(select(InvitationCode).order_by(InvitationCode.created_at.desc()).limit(500))
    return [r.to_dict() for r in q.scalars().all()]

@router.post("/invite_codes")
async def create_invite_code(payload: dict, db=Depends(get_db)):
    code = InvitationCode(
        code=payload.get("code"), 
        max_uses=payload.get("max_uses"), 
        expires_at=payload.get("expires_at"), 
        enabled=payload.get("enabled", True), 
        created_by=None
    )
    db.add(code)
    db.add(AuditLog(action="create_invite_code", details=payload, actor="web_admin"))
    await db.commit()
    await db.refresh(code)
    return code.to_dict()

@router.post("/invite_codes/{code}/disable")
async def disable_invite_code(code: str, db=Depends(get_db)):
    await db.execute(update(InvitationCode).where(InvitationCode.code==code).values(enabled=False))
    db.add(AuditLog(action="disable_invite_code", details={"code":code}, actor="web_admin"))
    await db.commit()
    return {"ok": True}

@router.get("/users")
async def list_users(q: str = "", limit: int = 100, db=Depends(get_db)):
    stmt = select(User).limit(limit)
    if q:
        stmt = select(User).where((User.username.ilike(f"%{q}%")) | (User.telegram_id.cast("text").ilike(f"%{q}%"))).limit(limit)
    r = await db.execute(stmt)
    return [u.to_dict() for u in r.scalars().all()]

@router.post("/users/{user_id}/freeze")
async def freeze_user(user_id: str, payload: dict = {}, db=Depends(get_db)):
    await db.execute(update(User).where(User.id==user_id).values(status="frozen"))
    db.add(AuditLog(action="freeze_user", details={"user_id":user_id,"reason":payload.get("reason")}, actor="web_admin"))
    await db.commit()
    return {"ok": True}

@router.post("/users/{user_id}/unfreeze")
async def unfreeze_user(user_id: str, payload: dict = {}, db=Depends(get_db)):
    await db.execute(update(User).where(User.id==user_id).values(status="active"))
    db.add(AuditLog(action="unfreeze_user", details={"user_id":user_id}, actor="web_admin"))
    await db.commit()
    return {"ok": True}

@router.post("/users/{user_id}/adjust_balance")
async def adjust_balance(user_id: str, payload: dict, db=Depends(get_db)):
    """
    payload: { bucket: 'deposit'|'winning'|'bonus', amount: '10.0', reason: 'manual credit' }
    """
    bucket = payload.get("bucket")
    amount = Decimal(str(payload.get("amount", "0")))
    if bucket not in ("deposit","winning","bonus"):
        raise HTTPException(status_code=400, detail="invalid bucket")
    wallet_stmt = await db.execute(select(Wallet).where(Wallet.user_id==user_id).with_for_update())
    w = wallet_stmt.scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="wallet not found")
    # apply change
    if bucket == "deposit":
        w.deposit_balance = w.deposit_balance + amount
    elif bucket == "winning":
        w.winning_balance = w.winning_balance + amount
    else:
        w.bonus_balance = w.bonus_balance + amount
    db.add(AuditLog(action="adjust_balance", details={"user_id":user_id,"bucket":bucket,"amount":str(amount),"reason":payload.get("reason")}, actor="web_admin"))
    await db.commit()
    return {"ok": True}
