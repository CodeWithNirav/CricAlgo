from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.db.session import get_db
from app.models.transaction import Transaction
from app.models.withdrawal import Withdrawal
from app.models.audit_log import AuditLog
from sqlalchemy import select, update
from datetime import datetime
from fastapi.responses import StreamingResponse
import csv, io

router = APIRouter(prefix="/api/v1/admin", tags=["admin_finance"])

# Simple admin authentication for finance endpoints
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from app.core.config import settings

security = HTTPBearer()

async def get_current_admin_simple(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Simple admin authentication for finance endpoints."""
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_type = payload.get("type")
        if user_type != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

@router.get("/deposits", dependencies=[Depends(get_current_admin_simple)])
async def list_deposits(status: str = "pending", db=Depends(get_db)):
    if status == "pending":
        # Pending deposits are those without processed_at timestamp
        q = await db.execute(select(Transaction).where(Transaction.tx_type == "deposit", Transaction.processed_at.is_(None)).order_by(Transaction.created_at.desc()).limit(200))
    else:
        # For other statuses, filter by processed_at
        q = await db.execute(select(Transaction).where(Transaction.tx_type == "deposit", Transaction.processed_at.isnot(None)).order_by(Transaction.created_at.desc()).limit(200))
    rows = q.scalars().all()
    return [r.to_dict() for r in rows]

@router.post("/deposits/{tx_id}/approve", dependencies=[Depends(get_current_admin_simple)])
async def approve_deposit(tx_id: str, payload: dict = None, db=Depends(get_db)):
    # simple approve: mark processed and credit wallet (use existing wallet repo)
    from app.repos.transaction_repo import mark_transaction_processed, get_transaction_by_id
    from app.repos.wallet_repo import credit_deposit_atomic
    tx = await get_transaction_by_id(db, tx_id)
    if not tx: raise HTTPException(status_code=404, detail="tx not found")
    if tx.status != "pending": raise HTTPException(status_code=400, detail="tx not pending")
    # credit wallet
    await credit_deposit_atomic(db, tx.user_id, tx.amount, {"tx_id": tx.tx_hash})
    await mark_transaction_processed(db, tx_id)
    # audit
    db.add(AuditLog(action="approve_deposit", details={"tx": tx.tx_hash}, actor="web_admin"))
    await db.commit()
    return {"ok": True}

@router.post("/deposits/{tx_id}/reject", dependencies=[Depends(get_current_admin_simple)])
async def reject_deposit(tx_id: str, payload: dict, db=Depends(get_db)):
    from app.repos.transaction_repo import mark_transaction_rejected, get_transaction_by_id
    tx = await get_transaction_by_id(db, tx_id)
    if not tx: raise HTTPException(status_code=404)
    await mark_transaction_rejected(db, tx_id, reason=payload.get("note","rejected"))
    db.add(AuditLog(action="reject_deposit", details={"tx": tx.tx_hash, "note": payload.get("note","")}, actor="web_admin"))
    await db.commit()
    return {"ok": True}

@router.get("/withdrawals", dependencies=[Depends(get_current_admin_simple)])
async def list_withdrawals(status: str = "pending", db=Depends(get_db)):
    q = await db.execute(select(Withdrawal).where(Withdrawal.status==status).order_by(Withdrawal.created_at.desc()).limit(200))
    rows = q.scalars().all()
    return [r.to_dict() for r in rows]

@router.post("/withdrawals/{w_id}/approve", dependencies=[Depends(get_current_admin_simple)])
async def approve_withdrawal(w_id: str, db=Depends(get_db)):
    from app.repos.withdrawal_repo import mark_withdrawal_approved, get_withdrawal_by_id
    w = await get_withdrawal_by_id(db, w_id)
    if not w: raise HTTPException(status_code=404)
    await mark_withdrawal_approved(db, w_id)
    db.add(AuditLog(action="approve_withdrawal", details={"withdrawal_id": w_id}, actor="web_admin"))
    await db.commit()
    return {"ok": True}

@router.post("/withdrawals/{w_id}/reject", dependencies=[Depends(get_current_admin_simple)])
async def reject_withdrawal(w_id: str, payload: dict, db=Depends(get_db)):
    from app.repos.withdrawal_repo import mark_withdrawal_rejected, get_withdrawal_by_id
    w = await get_withdrawal_by_id(db, w_id)
    if not w: raise HTTPException(status_code=404)
    await mark_withdrawal_rejected(db, w_id, reason=payload.get("note","rejected"))
    db.add(AuditLog(action="reject_withdrawal", details={"withdrawal_id": w_id, "note": payload.get("note","")}, actor="web_admin"))
    await db.commit()
    return {"ok": True}

@router.get("/audit", dependencies=[Depends(get_current_admin_simple)])
async def get_audit(limit:int=200, db=Depends(get_db)):
    q = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
    rows = q.scalars().all()
    return [r.to_dict() for r in rows]

@router.get("/audit/export", dependencies=[Depends(get_current_admin_simple)])
async def export_audit_csv(db=Depends(get_db)):
    q = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(10000))
    rows = q.scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id","created_at","actor","action","details"])
    for r in rows:
        writer.writerow([r.id, r.created_at.isoformat(), r.actor, r.action, r.details])
    buf.seek(0)
    return StreamingResponse(io.BytesIO(buf.getvalue().encode()), media_type="text/csv", headers={"Content-Disposition":"attachment; filename=audit.csv"})
