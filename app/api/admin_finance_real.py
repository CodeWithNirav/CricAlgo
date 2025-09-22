from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import get_current_admin
from app.db.session import get_db
from app.models.transaction import Transaction
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.admin import Admin
import csv
import io
from decimal import Decimal

router = APIRouter(prefix="/api/v1/admin", tags=["admin_finance_real"])

@router.get("/deposits")
async def list_deposits(
    status: str = "pending",
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """List deposits from database"""
    try:
        # Query transactions with type 'deposit' and specified status in metadata
        stmt = select(Transaction).where(
            and_(
                Transaction.tx_type == "deposit",
                Transaction.tx_metadata["status"].astext == status
            )
        ).order_by(Transaction.created_at.desc())
        
        result = await db.execute(stmt)
        transactions = result.scalars().all()
        
        # Convert to format expected by admin UI
        deposits = []
        for tx in transactions:
            # Get user info if user_id exists
            user_info = {}
            if tx.user_id:
                user_stmt = select(User).where(User.id == tx.user_id)
                user_result = await db.execute(user_stmt)
                user = user_result.scalar_one_or_none()
                if user:
                    user_info = {
                        "telegram_id": str(user.telegram_id),
                        "username": user.username
                    }
            
            deposit = {
                "id": str(tx.id),
                "telegram_id": tx.tx_metadata.get("telegram_id", "") if tx.tx_metadata else "",
                "username": tx.tx_metadata.get("username", "") if tx.tx_metadata else "",
                "amount": str(tx.amount),
                "tx_hash": tx.tx_metadata.get("tx_hash", "") if tx.tx_metadata else "",
                "status": tx.tx_metadata.get("status", "pending") if tx.tx_metadata else "pending",
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
                "currency": tx.currency
            }
            
            # Use user info from database if available
            if user_info:
                deposit.update(user_info)
                
            deposits.append(deposit)
        
        return deposits
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail={"error": f"Failed to fetch deposits: {str(e)}"}
        )

@router.get("/withdrawals")
async def list_withdrawals(
    status: str = "pending",
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """List withdrawals from database"""
    try:
        # Query transactions with type 'withdrawal' and specified status in metadata
        stmt = select(Transaction).where(
            and_(
                Transaction.tx_type == "withdrawal",
                Transaction.tx_metadata["status"].astext == status
            )
        ).order_by(Transaction.created_at.desc())
        
        result = await db.execute(stmt)
        transactions = result.scalars().all()
        
        # Convert to format expected by admin UI
        withdrawals = []
        for tx in transactions:
            # Get user info if user_id exists
            user_info = {}
            if tx.user_id:
                user_stmt = select(User).where(User.id == tx.user_id)
                user_result = await db.execute(user_stmt)
                user = user_result.scalar_one_or_none()
                if user:
                    user_info = {
                        "telegram_id": str(user.telegram_id),
                        "username": user.username
                    }
            
            withdrawal = {
                "id": str(tx.id),
                "telegram_id": tx.tx_metadata.get("telegram_id", "") if tx.tx_metadata else "",
                "username": tx.tx_metadata.get("username", "") if tx.tx_metadata else "",
                "amount": str(tx.amount),
                "address": tx.tx_metadata.get("address", "") if tx.tx_metadata else "",
                "status": tx.tx_metadata.get("status", "pending") if tx.tx_metadata else "pending",
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
                "currency": tx.currency
            }
            
            # Use user info from database if available
            if user_info:
                withdrawal.update(user_info)
                
            withdrawals.append(withdrawal)
        
        return withdrawals
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail={"error": f"Failed to fetch withdrawals: {str(e)}"}
        )

@router.get("/audit")
async def list_audit_logs(
    limit: int = 50,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """List audit logs from database"""
    try:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        logs = result.scalars().all()
        
        audit_logs = []
        for log in logs:
            audit_logs.append({
                "id": str(log.id),
                "admin_id": str(log.admin_id),
                "action": log.action,
                "details": log.details,
                "created_at": log.created_at.isoformat() if log.created_at else None
            })
        
        return audit_logs
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail={"error": f"Failed to fetch audit logs: {str(e)}"}
        )

@router.post("/deposits/{deposit_id}/approve")
async def approve_deposit(
    deposit_id: str,
    note: str = "",
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Approve a deposit"""
    try:
        # Update transaction status in metadata
        stmt = update(Transaction).where(
            and_(
                Transaction.id == deposit_id,
                Transaction.tx_type == "deposit"
            )
        ).values(tx_metadata=Transaction.tx_metadata.op('||')({"status": "confirmed"}))
        
        await db.execute(stmt)
        
        # Create audit log
        audit_log = AuditLog(
            admin_id=current_admin.id,
            action="approve_deposit",
            details={"note": note, "transaction_id": deposit_id}
        )
        db.add(audit_log)
        
        await db.commit()
        
        return {"success": True, "message": "Deposit approved successfully"}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail={"error": f"Failed to approve deposit: {str(e)}"}
        )

@router.post("/deposits/{deposit_id}/reject")
async def reject_deposit(
    deposit_id: str,
    note: str = "",
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reject a deposit"""
    try:
        # Update transaction status in metadata
        stmt = update(Transaction).where(
            and_(
                Transaction.id == deposit_id,
                Transaction.tx_type == "deposit"
            )
        ).values(tx_metadata=Transaction.tx_metadata.op('||')({"status": "rejected"}))
        
        await db.execute(stmt)
        
        # Create audit log
        audit_log = AuditLog(
            admin_id=current_admin.id,
            action="reject_deposit",
            details={"note": note, "transaction_id": deposit_id}
        )
        db.add(audit_log)
        
        await db.commit()
        
        return {"success": True, "message": "Deposit rejected successfully"}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail={"error": f"Failed to reject deposit: {str(e)}"}
        )

@router.post("/withdrawals/{withdrawal_id}/approve")
async def approve_withdrawal(
    withdrawal_id: str,
    note: str = "",
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Approve a withdrawal"""
    try:
        # Update transaction status in metadata
        stmt = update(Transaction).where(
            and_(
                Transaction.id == withdrawal_id,
                Transaction.tx_type == "withdrawal"
            )
        ).values(tx_metadata=Transaction.tx_metadata.op('||')({"status": "confirmed"}))
        
        await db.execute(stmt)
        
        # Create audit log
        audit_log = AuditLog(
            admin_id=current_admin.id,
            action="approve_withdrawal",
            details={"note": note, "transaction_id": withdrawal_id}
        )
        db.add(audit_log)
        
        await db.commit()
        
        # Send notification to user
        try:
            from app.tasks.notify import send_withdrawal_approval
            await send_withdrawal_approval(withdrawal_id)
        except Exception as e:
            # Log error but don't fail the approval
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send withdrawal approval notification for {withdrawal_id}: {e}")
        
        return {"success": True, "message": "Withdrawal approved successfully"}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail={"error": f"Failed to approve withdrawal: {str(e)}"}
        )

@router.post("/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(
    withdrawal_id: str,
    note: str = "",
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reject a withdrawal"""
    try:
        # Update transaction status in metadata
        stmt = update(Transaction).where(
            and_(
                Transaction.id == withdrawal_id,
                Transaction.tx_type == "withdrawal"
            )
        ).values(tx_metadata=Transaction.tx_metadata.op('||')({"status": "rejected"}))
        
        await db.execute(stmt)
        
        # Create audit log
        audit_log = AuditLog(
            admin_id=current_admin.id,
            action="reject_withdrawal",
            details={"note": note, "transaction_id": withdrawal_id}
        )
        db.add(audit_log)
        
        await db.commit()
        
        return {"success": True, "message": "Withdrawal rejected successfully"}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail={"error": f"Failed to reject withdrawal: {str(e)}"}
        )
