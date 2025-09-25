"""
Wallet API endpoints
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.session import get_db
from app.repos.wallet_repo import get_wallet_for_user
from app.repos.transaction_repo import create_transaction
from app.models.user import User
from app.tasks.tasks import process_withdrawal

router = APIRouter()


class WalletBalance(BaseModel):
    """Wallet balance response model"""
    deposit_balance: str
    bonus_balance: str
    winning_balance: str
    held_balance: str
    total_balance: str


class WithdrawalRequest(BaseModel):
    """Withdrawal request model"""
    amount: str = Field(..., description="Amount to withdraw (USDT)")
    currency: str = Field(default="USDT", description="Currency code")
    withdrawal_address: str = Field(..., description="External wallet address")
    notes: Optional[str] = Field(None, description="Optional notes")


class WithdrawalResponse(BaseModel):
    """Withdrawal response model"""
    transaction_id: str
    status: str
    message: str


@router.get("/", response_model=WalletBalance)
async def get_wallet_balance(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Get current user's wallet balances.
    """
    wallet = await get_wallet_for_user(session, current_user.id)
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    
    total_balance = wallet.deposit_balance + wallet.bonus_balance + wallet.winning_balance
    
    return WalletBalance(
        deposit_balance=str(wallet.deposit_balance),
        bonus_balance=str(wallet.bonus_balance),
        winning_balance=str(wallet.winning_balance),
        held_balance=str(wallet.held_balance),
        total_balance=str(total_balance)
    )


@router.post("/withdraw", response_model=WithdrawalResponse)
async def create_withdrawal_request(
    withdrawal_data: WithdrawalRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Create a withdrawal request.
    
    Creates a pending withdrawal transaction and enqueues a background task
    to process the withdrawal.
    """
    try:
        amount = Decimal(withdrawal_data.amount)
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Withdrawal amount must be positive"
            )
        
        # Get user's wallet
        wallet = await get_wallet_for_user(session, current_user.id)
        if not wallet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Wallet not found"
            )
        
        # Check if user has sufficient winning balance (only winning balance can be withdrawn)
        if wallet.winning_balance < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient winning balance for withdrawal. Only winning balance can be withdrawn."
            )
        
        # Process withdrawal hold (move from winning to held balance)
        from app.repos.wallet_repo import process_withdrawal_hold_atomic
        success, error = await process_withdrawal_hold_atomic(
            session=session,
            user_id=current_user.id,
            amount=amount
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to process withdrawal hold: {error}"
            )
        
        # Create withdrawal transaction
        transaction = await create_transaction(
            session=session,
            user_id=current_user.id,
            tx_type="withdrawal",
            amount=amount,
            currency=withdrawal_data.currency,
            related_entity="withdrawal_request",
            related_id=current_user.id,
            tx_metadata={
                "withdrawal_address": withdrawal_data.withdrawal_address,
                "notes": withdrawal_data.notes,
                "status": "pending",
                "amount_held": str(amount)
            }
        )
        
        # Enqueue withdrawal processing task
        process_withdrawal.delay(str(transaction.id))
        
        return WithdrawalResponse(
            transaction_id=str(transaction.id),
            status="pending",
            message="Withdrawal request created successfully"
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid amount format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create withdrawal request: {str(e)}"
        )


@router.get("/transactions")
async def get_wallet_transactions(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Get user's wallet transactions.
    """
    from app.repos.transaction_repo import get_transactions_by_user
    
    transactions = await get_transactions_by_user(
        session, current_user.id, limit=limit, offset=offset
    )
    
    return {
        "transactions": [
            {
                "id": str(tx.id),
                "type": tx.tx_type,
                "amount": str(tx.amount),
                "currency": tx.currency,
                "status": tx.tx_metadata.get("status", "unknown") if tx.tx_metadata else "unknown",
                "created_at": tx.created_at.isoformat(),
                "metadata": tx.tx_metadata
            }
            for tx in transactions
        ],
        "limit": limit,
        "offset": offset
    }
