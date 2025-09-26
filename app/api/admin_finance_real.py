from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import get_current_admin
from app.db.session import get_db
from app.models.transaction import Transaction
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.admin import Admin
from pydantic import BaseModel
import csv
import io
from decimal import Decimal

class ApproveDepositRequest(BaseModel):
    amount: float
    note: str = ""

class RejectDepositRequest(BaseModel):
    note: str = ""

router = APIRouter(prefix="/api/v1/admin", tags=["admin_finance_real"])

@router.get("/deposits")
async def list_deposits(
    status: str = "pending",
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """List deposits from database"""
    try:
        # Query transactions with type 'deposit'
        if status == "all":
            # Show all deposits regardless of status
            stmt = select(Transaction).where(
                Transaction.tx_type == "deposit"
            ).order_by(Transaction.created_at.desc())
        elif status == "pending":
            # Show only pending deposits (no status or status = pending)
            stmt = select(Transaction).where(
                and_(
                    Transaction.tx_type == "deposit",
                    or_(
                        Transaction.tx_metadata["status"].as_string() == "pending",
                        Transaction.tx_metadata["status"].as_string().is_(None)
                    )
                )
            ).order_by(Transaction.created_at.desc())
        else:
            # Filter by specific status if provided
            stmt = select(Transaction).where(
                and_(
                    Transaction.tx_type == "deposit",
                    Transaction.tx_metadata["status"].as_string() == status
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
            status_code=500, 
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
                Transaction.tx_metadata["status"].as_string() == status
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
                "address": tx.tx_metadata.get("withdrawal_address", "") if tx.tx_metadata else "",
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
            status_code=500, 
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
            status_code=500, 
            detail={"error": f"Failed to fetch audit logs: {str(e)}"}
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
        # Convert string ID to UUID
        from uuid import UUID
        try:
            withdrawal_uuid = UUID(withdrawal_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid withdrawal ID format")
        
        # Get current transaction to update metadata
        stmt = select(Transaction).where(
            and_(
                Transaction.id == withdrawal_uuid,
                Transaction.tx_type == "withdrawal"
            )
        )
        result = await db.execute(stmt)
        transaction = result.scalar_one_or_none()
        
        if not transaction:
            raise HTTPException(status_code=404, detail="Withdrawal not found")
        
        # Update metadata
        current_metadata = transaction.tx_metadata or {}
        current_metadata["status"] = "confirmed"
        
        update_stmt = update(Transaction).where(
            Transaction.id == withdrawal_uuid
        ).values(tx_metadata=current_metadata)
        
        await db.execute(update_stmt)
        
        # Log the approval
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Approving withdrawal {withdrawal_id}: status updated to confirmed")
        
        # Complete the withdrawal by removing amount from held balance
        from app.repos.wallet_repo import complete_withdrawal_atomic
        from decimal import Decimal
        
        success, error = await complete_withdrawal_atomic(
            session=db,
            user_id=transaction.user_id,
            amount=Decimal(str(transaction.amount))
        )
        
        if not success:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to complete withdrawal {withdrawal_id}: {error}")
            raise HTTPException(status_code=500, detail=f"Failed to complete withdrawal: {error}")
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Withdrawal {withdrawal_id} approved and completed - {transaction.amount} removed from held balance")
        
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
            status_code=500, 
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
        # Convert string ID to UUID
        from uuid import UUID
        try:
            withdrawal_uuid = UUID(withdrawal_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid withdrawal ID format")
        
        # Get current transaction to update metadata
        stmt = select(Transaction).where(
            and_(
                Transaction.id == withdrawal_uuid,
                Transaction.tx_type == "withdrawal"
            )
        )
        result = await db.execute(stmt)
        transaction = result.scalar_one_or_none()
        
        if not transaction:
            raise HTTPException(status_code=404, detail="Withdrawal not found")
        
        # Update metadata
        current_metadata = transaction.tx_metadata or {}
        current_metadata["status"] = "rejected"
        
        update_stmt = update(Transaction).where(
            Transaction.id == withdrawal_uuid
        ).values(tx_metadata=current_metadata)
        
        await db.execute(update_stmt)
        
        # Release the held balance back to winning balance
        from app.repos.wallet_repo import release_withdrawal_hold_atomic
        from decimal import Decimal

        success, error = await release_withdrawal_hold_atomic(
            session=db,
            user_id=transaction.user_id,
            amount=Decimal(str(transaction.amount))
        )

        if not success:
            # Log the error but don't fail the rejection
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to release held balance for rejected withdrawal {withdrawal_id}: {error}")
        else:
            logger.info(f"Held balance released for rejected withdrawal {withdrawal_id}: {transaction.amount} USDT moved back to winning balance")
        
        # Create audit log
        audit_log = AuditLog(
            admin_id=current_admin.id,
            action="reject_withdrawal",
            details={"note": note, "transaction_id": withdrawal_id}
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
        
        return {"success": True, "message": "Withdrawal rejected successfully"}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={"error": f"Failed to reject withdrawal: {str(e)}"}
        )


@router.post("/deposits/{deposit_id}/approve")
async def approve_deposit(
    deposit_id: str,
    request: ApproveDepositRequest,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Approve a manual deposit"""
    try:
        # Get the deposit transaction
        stmt = select(Transaction).where(
            and_(
                Transaction.id == deposit_id,
                Transaction.tx_type == "deposit"
            )
        )
        result = await db.execute(stmt)
        transaction = result.scalar_one_or_none()
        
        if not transaction:
            raise HTTPException(
                status_code=404,
                detail="Deposit not found"
            )
        
        # Update transaction amount and status
        transaction.amount = Decimal(str(request.amount))
        
        # Update metadata using the same pattern as withdrawal approval
        current_metadata = transaction.tx_metadata or {}
        current_metadata["status"] = "approved"
        current_metadata["approved_by"] = str(current_admin.id)
        current_metadata["approved_amount"] = str(request.amount)
        current_metadata["approval_note"] = request.note
        
        update_stmt = update(Transaction).where(
            Transaction.id == deposit_id
        ).values(amount=transaction.amount, tx_metadata=current_metadata)
        
        await db.execute(update_stmt)
        
        # Update user wallet balance
        from app.repos.wallet_repo import get_wallet_for_user, update_balances_atomic
        wallet = await get_wallet_for_user(db, transaction.user_id)
        if wallet:
            success, error = await update_balances_atomic(
                db,
                transaction.user_id,
                deposit_delta=Decimal(str(request.amount))
            )
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to update wallet: {error}"
                )
        
        # Create audit log
        audit_log = AuditLog(
            admin_id=current_admin.id,
            action="approve_deposit",
            details={
                "deposit_id": str(deposit_id),
                "amount": str(request.amount),
                "note": request.note,
                "user_id": str(transaction.user_id)
            }
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
        
        return {"success": True, "message": "Deposit approved successfully"}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to approve deposit: {str(e)}"
        )


@router.post("/deposits/{deposit_id}/reject")
async def reject_deposit(
    deposit_id: str,
    request: RejectDepositRequest,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reject a manual deposit"""
    try:
        # Get the deposit transaction
        stmt = select(Transaction).where(
            and_(
                Transaction.id == deposit_id,
                Transaction.tx_type == "deposit"
            )
        )
        result = await db.execute(stmt)
        transaction = result.scalar_one_or_none()
        
        if not transaction:
            raise HTTPException(
                status_code=404,
                detail="Deposit not found"
            )
        
        # Update metadata
        current_metadata = transaction.tx_metadata or {}
        current_metadata["status"] = "rejected"
        current_metadata["rejected_by"] = str(current_admin.id)
        current_metadata["rejection_note"] = request.note
        
        update_stmt = update(Transaction).where(
            Transaction.id == deposit_id
        ).values(tx_metadata=current_metadata)
        
        await db.execute(update_stmt)
        
        # Create audit log
        audit_log = AuditLog(
            admin_id=current_admin.id,
            action="reject_deposit",
            details={
                "deposit_id": str(deposit_id),
                "note": request.note,
                "user_id": str(transaction.user_id)
            }
        )
        db.add(audit_log)
        
        await db.commit()
        
        # Send notification to user
        from app.tasks.notify import send_deposit_rejection
        try:
            await send_deposit_rejection(deposit_id, request.note)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send deposit rejection notification: {e}")
        
        return {"success": True, "message": "Deposit rejected successfully"}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reject deposit: {str(e)}"
        )
