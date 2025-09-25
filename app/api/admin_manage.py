from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.core.auth import get_current_admin
from app.db.session import get_db
from app.models.invitation_code import InvitationCode
from app.models.user import User
from app.models.wallet import Wallet
from app.models.audit_log import AuditLog
from decimal import Decimal

router = APIRouter(prefix="/api/v1/admin", tags=["admin_manage"])


class CreateInviteCodeRequest(BaseModel):
    """Request model for creating invite codes"""
    code: str
    max_uses: int = 10
    expires_at: Optional[datetime] = None
    enabled: bool = True

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
async def create_invite_code(
    payload: CreateInviteCodeRequest, 
    current_admin=Depends(get_current_admin), 
    db=Depends(get_db)
):
    """
    Create a new invite code.
    """
    try:
        # Check if code already exists
        existing_code = await db.execute(
            select(InvitationCode).where(InvitationCode.code == payload.code)
        )
        if existing_code.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invite code already exists"}
            )
        
        # Create new invite code
        code = InvitationCode(
            code=payload.code,
            max_uses=payload.max_uses,
            expires_at=payload.expires_at,
            enabled=payload.enabled,
            created_by=None
        )
        db.add(code)
        
        # Log the action
        db.add(AuditLog(
            action="create_invite_code", 
            details={
                "code": payload.code,
                "max_uses": payload.max_uses,
                "expires_at": payload.expires_at.isoformat() if payload.expires_at else None,
                "enabled": payload.enabled
            }
        ))
        
        await db.commit()
        await db.refresh(code)
        return code.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to create invite code: {str(e)}"}
        )

@router.post("/invite_codes/{code}/disable")
async def disable_invite_code(code: str, current_admin=Depends(get_current_admin), db=Depends(get_db)):
    """
    Disable an invite code.
    """
    try:
        # Check if code exists
        existing_code = await db.execute(
            select(InvitationCode).where(InvitationCode.code == code)
        )
        if not existing_code.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Invite code not found"}
            )
        
        await db.execute(update(InvitationCode).where(InvitationCode.code==code).values(enabled=False))
        db.add(AuditLog(action="disable_invite_code", details={"code":code}))
        await db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to disable invite code: {str(e)}"}
        )


@router.post("/invite_codes/{code}/enable")
async def enable_invite_code(code: str, current_admin=Depends(get_current_admin), db=Depends(get_db)):
    """
    Enable an invite code.
    """
    try:
        # Check if code exists
        existing_code = await db.execute(
            select(InvitationCode).where(InvitationCode.code == code)
        )
        if not existing_code.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Invite code not found"}
            )
        
        await db.execute(update(InvitationCode).where(InvitationCode.code==code).values(enabled=True))
        db.add(AuditLog(action="enable_invite_code", details={"code":code}))
        await db.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to enable invite code: {str(e)}"}
        )

# Users endpoint
@router.get("/users")
async def get_users_list(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, description="Filter by user status"),
    q: Optional[str] = Query(None, description="Search query (username or telegram ID)"),
    current_admin=Depends(get_current_admin),
    db=Depends(get_db)
):
    """
    Get list of users (admin only).
    """
    try:
        from app.repos.user_repo import get_users, search_users
        
        if q:
            # Use search functionality
            users = await search_users(
                db,
                query=q,
                limit=limit,
                offset=offset
            )
        else:
            # Use regular get_users
            users = await get_users(
                db,
                limit=limit,
                offset=offset,
                status=status_filter
            )
        
        # Return just the users array for frontend compatibility
        return [
            {
                "id": str(user.id),
                "username": user.username,
                "telegram_id": user.telegram_id,
                "status": user.status.value,
                "created_at": user.created_at.isoformat()
            }
            for user in users
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get users: {str(e)}"
        )

@router.post("/users/{user_id}/freeze")
async def freeze_user(user_id: str, payload: dict = {}, db=Depends(get_db)):
    try:
        await db.execute(update(User).where(User.id==user_id).values(status="frozen"))
        db.add(AuditLog(action="freeze_user", details={"user_id":user_id,"reason":payload.get("reason")}))
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
        db.add(AuditLog(action="unfreeze_user", details={"user_id":user_id}))
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
        db.add(AuditLog(action="adjust_balance", details={"user_id":user_id,"bucket":bucket,"amount":str(amount),"reason":payload.get("reason")}))
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

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str, 
    current_admin=Depends(get_current_admin), 
    db=Depends(get_db)
):
    """
    Delete a user and all associated data.
    WARNING: This is a destructive operation that cannot be undone.
    """
    try:
        from sqlalchemy import delete
        from app.models.contest_entry import ContestEntry
        from app.models.transaction import Transaction
        from app.models.chat_map import ChatMap
        
        # Check if user exists
        user_stmt = await db.execute(select(User).where(User.id == user_id))
        user = user_stmt.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "User not found"}
            )
        
        # Store user info for audit log
        user_info = {
            "username": user.username,
            "telegram_id": user.telegram_id,
            "status": user.status.value if hasattr(user.status, 'value') else str(user.status)
        }
        
        # Delete related data in order (to respect foreign key constraints)
        # 1. Delete contest entries
        await db.execute(delete(ContestEntry).where(ContestEntry.user_id == user_id))
        
        # 2. Delete transactions
        await db.execute(delete(Transaction).where(Transaction.user_id == user_id))
        
        # 3. Delete chat mappings
        await db.execute(delete(ChatMap).where(ChatMap.user_id == user_id))
        
        # 4. Delete wallet
        await db.execute(delete(Wallet).where(Wallet.user_id == user_id))
        
        # 5. Finally delete the user
        await db.execute(delete(User).where(User.id == user_id))
        
        # Log the deletion
        db.add(AuditLog(
            action="delete_user", 
            details={
                "deleted_user": user_info,
                "deleted_by": current_admin.username
            }
        ))
        
        await db.commit()
        return {"ok": True, "message": f"User {user_info['username']} (ID: {user_id}) deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to delete user: {str(e)}"}
        )