"""
Admin API endpoints
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_admin, verify_password, create_access_token
from app.db.session import get_db
from app.repos.user_repo import get_users, get_user_by_id
from app.repos.transaction_repo import get_transaction_by_id, update_transaction_metadata
from app.repos.audit_log_repo import create_audit_log, get_audit_logs
from app.tasks.tasks import process_withdrawal
from app.models.user import User
from app.models.admin import Admin
from app.repos.admin_repo import get_admin_by_username
from datetime import timedelta

router = APIRouter()


class AdminLoginRequest(BaseModel):
    """Admin login request model"""
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    """Admin login response model"""
    access_token: str
    token_type: str = "bearer"


@router.post("/admin/login", response_model=AdminLoginResponse)
async def admin_login(
    login_data: AdminLoginRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Admin login endpoint.
    """
    try:
        # Get admin by username
        admin = await get_admin_by_username(session, login_data.username)
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Verify password
        if not verify_password(login_data.password, admin.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Create admin access token
        access_token_expires = timedelta(hours=24)
        from jose import jwt
        from app.core.config import settings
        from datetime import datetime
        
        to_encode = {
            "sub": str(admin.id), 
            "username": admin.username, 
            "type": "admin",
            "exp": datetime.utcnow() + access_token_expires
        }
        access_token = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        
        return AdminLoginResponse(
            access_token=access_token,
            token_type="bearer"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


class UserListResponse(BaseModel):
    """User list response model"""
    users: List[dict]
    total: int
    limit: int
    offset: int


class TransactionApprovalResponse(BaseModel):
    """Transaction approval response model"""
    success: bool
    message: str
    transaction_id: str


class AuditLogResponse(BaseModel):
    """Audit log response model"""
    logs: List[dict]
    total: int
    limit: int
    offset: int


@router.get("/users", response_model=UserListResponse)
async def get_users_list(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, description="Filter by user status"),
    current_admin: Admin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Get list of users (admin only).
    """
    try:
        users = await get_users(
            session,
            limit=limit,
            offset=offset,
            status=status_filter
        )
        
        return UserListResponse(
            users=[
                {
                    "id": str(user.id),
                    "username": user.username,
                    "telegram_id": user.telegram_id,
                    "status": user.status.value,
                    "created_at": user.created_at.isoformat()
                }
                for user in users
            ],
            total=len(users),  # In a real implementation, you'd get total count
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get users: {str(e)}"
        )


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: str,
    current_admin: Admin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Get detailed user information (admin only).
    """
    try:
        user_uuid = UUID(user_id)
        user = await get_user_by_id(session, user_uuid)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get user's wallet
        from app.repos.wallet_repo import get_wallet_for_user
        wallet = await get_wallet_for_user(session, user_uuid)
        
        # Get user's transactions
        from app.repos.transaction_repo import get_transactions_by_user
        transactions = await get_transactions_by_user(session, user_uuid, limit=10)
        
        return {
            "id": str(user.id),
            "username": user.username,
            "telegram_id": user.telegram_id,
            "status": user.status.value,
            "created_at": user.created_at.isoformat(),
            "wallet": {
                "deposit_balance": str(wallet.deposit_balance) if wallet else "0",
                "bonus_balance": str(wallet.bonus_balance) if wallet else "0",
                "winning_balance": str(wallet.winning_balance) if wallet else "0"
            } if wallet else None,
            "recent_transactions": [
                {
                    "id": str(tx.id),
                    "type": tx.tx_type,
                    "amount": str(tx.amount),
                    "currency": tx.currency,
                    "created_at": tx.created_at.isoformat()
                }
                for tx in transactions
            ]
        }
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user details: {str(e)}"
        )


@router.post("/transactions/{tx_id}/approve", response_model=TransactionApprovalResponse)
async def approve_transaction(
    tx_id: str,
    current_admin: Admin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Approve a withdrawal transaction (admin only).
    
    Enqueues the withdrawal processing task.
    """
    try:
        transaction_uuid = UUID(tx_id)
        transaction = await get_transaction_by_id(session, transaction_uuid)
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )
        
        if transaction.tx_type != "withdrawal":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction is not a withdrawal"
            )
        
        # Check if already processed
        current_status = transaction.tx_metadata.get("status", "pending") if transaction.tx_metadata else "pending"
        if current_status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transaction already {current_status}"
            )
        
        # Update transaction status
        await update_transaction_metadata(
            session,
            transaction_uuid,
            {
                **transaction.tx_metadata,
                "status": "approved",
                "approved_by": str(current_admin.id),
                "approved_at": "now()"
            }
        )
        
        # Enqueue withdrawal processing task
        process_withdrawal.delay(str(transaction_uuid))
        
        # Create audit log
        await create_audit_log(
            session=session,
            admin_id=current_admin.id,
            action="approve_withdrawal",
            resource_type="transaction",
            resource_id=transaction_uuid,
            details={
                "transaction_id": str(transaction_uuid),
                "user_id": str(transaction.user_id),
                "amount": str(transaction.amount),
                "currency": transaction.currency
            }
        )
        
        return TransactionApprovalResponse(
            success=True,
            message="Transaction approved successfully",
            transaction_id=str(transaction_uuid)
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid transaction ID format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve transaction: {str(e)}"
        )


@router.get("/audit-logs", response_model=AuditLogResponse)
async def get_audit_logs_endpoint(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    action_filter: Optional[str] = Query(None, description="Filter by action type"),
    current_admin: Admin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Get audit logs (admin only).
    """
    try:
        logs = await get_audit_logs(
            session,
            limit=limit,
            offset=offset,
            action=action_filter
        )
        
        return AuditLogResponse(
            logs=[
                {
                    "id": str(log.id),
                    "admin_id": str(log.admin_id),
                    "action": log.action,
                    "resource_type": log.resource_type,
                    "resource_id": str(log.resource_id),
                    "details": log.details,
                    "created_at": log.created_at.isoformat()
                }
                for log in logs
            ],
            total=len(logs),  # In a real implementation, you'd get total count
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audit logs: {str(e)}"
        )


@router.get("/stats")
async def get_admin_stats(
    current_admin: Admin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Get admin dashboard statistics.
    """
    try:
        # Get basic counts
        from app.repos.user_repo import get_users
        from app.repos.contest_repo import get_contests
        from app.repos.transaction_repo import get_transactions_by_type
        
        # Get user count
        users = await get_users(session, limit=1000)  # Get all users for count
        user_count = len(users)
        
        # Get contest count
        contests = await get_contests(session, limit=1000)
        contest_count = len(contests)
        
        # Get transaction counts
        deposits = await get_transactions_by_type(session, "deposit", limit=1000)
        withdrawals = await get_transactions_by_type(session, "withdrawal", limit=1000)
        
        # Calculate total volumes
        total_deposits = sum(tx.amount for tx in deposits)
        total_withdrawals = sum(tx.amount for tx in withdrawals)
        
        return {
            "users": {
                "total": user_count,
                "active": len([u for u in users if u.status.value == "active"])
            },
            "contests": {
                "total": contest_count,
                "open": len([c for c in contests if c.status.value == "open"])
            },
            "transactions": {
                "deposits": {
                    "count": len(deposits),
                    "total_amount": str(total_deposits)
                },
                "withdrawals": {
                    "count": len(withdrawals),
                    "total_amount": str(total_withdrawals)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get admin stats: {str(e)}"
        )
