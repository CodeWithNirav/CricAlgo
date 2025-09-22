from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from app.core.auth import get_current_admin
from app.db.session import get_db
from app.models.invitation_code import InvitationCode
from app.models.user import User
from app.models.wallet import Wallet
from app.models.audit_log import AuditLog
from decimal import Decimal

router = APIRouter(prefix="/api/v1/admin", tags=["admin_manage"])

@router.get("/invite_codes")
async def list_invite_codes(current_admin=Depends(get_current_admin), db=Depends(get_db)):
    try:
        q = await db.execute(select(InvitationCode).order_by(InvitationCode.created_at.desc()).limit(500))
        return [r.to_dict() for r in q.scalars().all()]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to fetch invite codes: {str(e)}"}
        )

# Backwards-compatible alias: /invitecodes
@router.get("/invitecodes", include_in_schema=False)
async def list_invite_codes_alias(current_admin=Depends(get_current_admin), db=Depends(get_db)):
    # Forward to canonical endpoint to avoid duplication
    return await list_invite_codes(current_admin, db)

@router.post("/invite_codes")
async def create_invite_code(payload: dict, current_admin=Depends(get_current_admin), db=Depends(get_db)):
    try:
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
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to create invite code: {str(e)}"}
        )

@router.post("/invite_codes/{code}/disable")
async def disable_invite_code(code: str, db=Depends(get_db)):
    try:
        await db.execute(update(InvitationCode).where(InvitationCode.code==code).values(enabled=False))
        db.add(AuditLog(action="disable_invite_code", details={"code":code}, actor="web_admin"))
        await db.commit()
        return {"ok": True}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to disable invite code: {str(e)}"}
        )

# Users endpoint moved to v1/admin.py to avoid conflicts

@router.post("/users/{user_id}/freeze")
async def freeze_user(user_id: str, payload: dict = {}, db=Depends(get_db)):
    try:
        await db.execute(update(User).where(User.id==user_id).values(status="frozen"))
        db.add(AuditLog(action="freeze_user", details={"user_id":user_id,"reason":payload.get("reason")}, actor="web_admin"))
        await db.commit()
        return {"ok": True}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to freeze user: {str(e)}"}
        )

@router.post("/users/{user_id}/unfreeze")
async def unfreeze_user(user_id: str, payload: dict = {}, db=Depends(get_db)):
    try:
        await db.execute(update(User).where(User.id==user_id).values(status="active"))
        db.add(AuditLog(action="unfreeze_user", details={"user_id":user_id}, actor="web_admin"))
        await db.commit()
        return {"ok": True}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to unfreeze user: {str(e)}"}
        )

@router.post("/users/{user_id}/adjust_balance")
async def adjust_balance(user_id: str, payload: dict, db=Depends(get_db)):
    """
    payload: { bucket: 'deposit'|'winning'|'bonus', amount: '10.0', reason: 'manual credit' }
    """
    try:
        bucket = payload.get("bucket")
        amount = Decimal(str(payload.get("amount", "0")))
        if bucket not in ("deposit","winning","bonus"):
            raise HTTPException(status_code=400, detail={"error": "invalid bucket"})
        wallet_stmt = await db.execute(select(Wallet).where(Wallet.user_id==user_id).with_for_update())
        w = wallet_stmt.scalar_one_or_none()
        if not w:
            raise HTTPException(status_code=404, detail={"error": "wallet not found"})
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
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to adjust balance: {str(e)}"}
        )
