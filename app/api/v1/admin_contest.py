"""
Admin contest management API endpoints
"""

from typing import Dict
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_admin
from app.db.session import get_db
from app.models.user import User
from app.services.settlement import settle_contest

router = APIRouter()


class SettlementResponse(BaseModel):
    """Settlement response model"""
    success: bool
    contest_id: str
    settlement_time: str
    num_players: int
    total_prize_pool: str
    commission_pct: float
    commission_amount: str
    distributable_pool: str
    total_payouts: str
    payouts: list
    prize_structure: list


@router.post("/contest/{contest_id}/settle", response_model=SettlementResponse)
async def settle_contest_endpoint(
    contest_id: str,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Settle a contest and distribute payouts (admin only).
    
    This endpoint triggers the settlement process for a contest, which:
    1. Locks the contest to prevent concurrent settlements
    2. Calculates prize pool, commission, and payouts
    3. Credits winning balances to participants
    4. Creates transaction records
    5. Marks contest as settled
    6. Records audit log
    
    The operation is atomic and idempotent - it can be called multiple times
    safely without double-paying winners.
    """
    try:
        contest_uuid = UUID(contest_id)
        
        # Call the settlement service
        settlement_result = await settle_contest(
            session=session,
            contest_id=contest_uuid,
            admin_id=current_admin.id
        )
        
        if not settlement_result.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Settlement failed: {settlement_result.get('error', 'Unknown error')}"
            )
        
        return SettlementResponse(**settlement_result)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid contest ID format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to settle contest: {str(e)}"
        )
