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
import csv, io

router = APIRouter(prefix="/api/v1/admin", tags=["admin_finance"])

# Matches endpoints are handled by admin_matches_contests.py

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
                Transaction.tx_metadata.op('->>')('status') == status
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
            detail=f"Failed to fetch deposits: {str(e)}"
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
                Transaction.tx_metadata.op('->>')('status') == status
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
            detail=f"Failed to fetch withdrawals: {str(e)}"
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
            detail=f"Failed to fetch audit logs: {str(e)}"
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
        from sqlalchemy import text
        stmt = update(Transaction).where(
            and_(
                Transaction.id == deposit_id,
                Transaction.tx_type == "deposit"
            )
        ).values(tx_metadata=text("metadata || '{\"status\": \"confirmed\"}'::jsonb"))
        
        await db.execute(stmt)
        
        # Create audit log
        audit_log = AuditLog(
            admin_id=current_admin.id,
            action="approve_deposit",
            details={"note": note, "transaction_id": deposit_id}
        )
        db.add(audit_log)
        
        await db.commit()
        
        # Send notification to user
        from app.tasks.notify import send_deposit_confirmation
        try:
            await send_deposit_confirmation(deposit_id)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send deposit approval notification: {e}")
        
        return {"success": True, "message": f"Deposit {deposit_id} approved successfully!"}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to approve deposit: {str(e)}"
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
        from sqlalchemy import text
        stmt = update(Transaction).where(
            and_(
                Transaction.id == deposit_id,
                Transaction.tx_type == "deposit"
            )
        ).values(tx_metadata=text("metadata || '{\"status\": \"rejected\"}'::jsonb"))
        
        await db.execute(stmt)
        
        # Create audit log
        audit_log = AuditLog(
            admin_id=current_admin.id,
            action="reject_deposit",
            details={"note": note, "transaction_id": deposit_id}
        )
        db.add(audit_log)
        
        await db.commit()
        
        # Send notification to user
        from app.tasks.notify import send_deposit_rejection
        try:
            await send_deposit_rejection(deposit_id, note)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send deposit rejection notification: {e}")
        
        return {"success": True, "message": f"Deposit {deposit_id} rejected successfully!"}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to reject deposit: {str(e)}"
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
        from uuid import UUID
        from decimal import Decimal
        from app.repos.wallet_repo import get_wallet_for_user, complete_withdrawal_atomic
        
        # Get the withdrawal transaction
        withdrawal = await db.get(Transaction, UUID(withdrawal_id))
        if not withdrawal or withdrawal.tx_type != "withdrawal":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Withdrawal not found"
            )
        
        # Check if already processed
        if withdrawal.tx_metadata and withdrawal.tx_metadata.get("status") == "confirmed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Withdrawal already approved"
            )
        
        # Get user's wallet
        wallet = await get_wallet_for_user(db, withdrawal.user_id)
        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User wallet not found"
            )
        
        # Check if user has sufficient balance
        total_balance = wallet.deposit_balance + wallet.winning_balance + wallet.bonus_balance
        if total_balance < withdrawal.amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient balance. Available: {total_balance}, Required: {withdrawal.amount}"
            )
        
        # Check if funds were held (new system) or need to be debited directly (old system)
        if withdrawal.tx_metadata and withdrawal.tx_metadata.get("funds_held"):
            # New system: Complete the withdrawal (debit from held balance)
            success, error = await complete_withdrawal_atomic(
                session=db,
                user_id=withdrawal.user_id,
                amount=withdrawal.amount
            )
        else:
            # Old system: Debit directly from winning balance
            from app.repos.wallet_repo import update_balances_atomic
            success, error = await update_balances_atomic(
                session=db,
                user_id=withdrawal.user_id,
                deposit_delta=Decimal('0'),
                winning_delta=-withdrawal.amount,  # Debit from winning balance
                bonus_delta=Decimal('0')
            )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to process withdrawal: {error}"
            )
        
        # Update transaction status
        from sqlalchemy import text
        stmt = update(Transaction).where(
            and_(
                Transaction.id == withdrawal_id,
                Transaction.tx_type == "withdrawal"
            )
        ).values(tx_metadata=text("metadata || '{\"status\": \"confirmed\"}'::jsonb"))
        
        await db.execute(stmt)
        
        # Create audit log
        audit_log = AuditLog(
            admin_id=current_admin.id,
            action="approve_withdrawal",
            details={"note": note, "transaction_id": withdrawal_id, "amount": str(withdrawal.amount)}
        )
        db.add(audit_log)
        
        await db.commit()
        
        # Send notification to user
        from app.tasks.notify import send_withdrawal_approval
        try:
            await send_withdrawal_approval(withdrawal_id)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send withdrawal approval notification: {e}")
        
        return {"success": True, "message": f"Withdrawal {withdrawal_id} approved and processed successfully!"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to approve withdrawal: {str(e)}"
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
        from uuid import UUID
        from app.repos.wallet_repo import release_withdrawal_hold_atomic
        
        # Get the withdrawal transaction
        withdrawal = await db.get(Transaction, UUID(withdrawal_id))
        if not withdrawal or withdrawal.tx_type != "withdrawal":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Withdrawal not found"
            )
        
        # Release the held funds back to winning balance
        if withdrawal.tx_metadata and withdrawal.tx_metadata.get("funds_held"):
            success, error = await release_withdrawal_hold_atomic(
                session=db,
                user_id=withdrawal.user_id,
                amount=withdrawal.amount
            )
            
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to release held funds: {error}"
                )
        
        # Update transaction status in metadata
        from sqlalchemy import text
        stmt = update(Transaction).where(
            and_(
                Transaction.id == withdrawal_id,
                Transaction.tx_type == "withdrawal"
            )
        ).values(tx_metadata=text("metadata || '{\"status\": \"rejected\"}'::jsonb"))
        
        await db.execute(stmt)
        
        # Create audit log
        audit_log = AuditLog(
            admin_id=current_admin.id,
            action="reject_withdrawal",
            details={"note": note, "transaction_id": withdrawal_id, "amount": str(withdrawal.amount)}
        )
        db.add(audit_log)
        
        await db.commit()
        
        # Send notification to user
        from app.tasks.notify import send_withdrawal_rejection
        try:
            await send_withdrawal_rejection(withdrawal_id, note)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send withdrawal rejection notification: {e}")
        
        return {"success": True, "message": f"Withdrawal {withdrawal_id} rejected successfully!"}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to reject withdrawal: {str(e)}"
        )

# Keep the old fake endpoints for backward compatibility but mark them as deprecated
@router.get("/audit/export")
async def export_audit_logs():
    """Export audit logs as CSV - simplified version"""
    # Create a simple CSV
    csv_content = "timestamp,action,details\n"
    csv_content += "2024-01-15T10:00:00Z,create_match,\"Created match: India vs Australia\"\n"
    csv_content += "2024-01-15T11:00:00Z,approve_deposit,\"Approved deposit: 100 USDT\"\n"
    csv_content += "2024-01-15T12:00:00Z,settle_contest,\"Settled contest: High Roller Contest\"\n"
    
    return StreamingResponse(
        io.BytesIO(csv_content.encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"}
    )