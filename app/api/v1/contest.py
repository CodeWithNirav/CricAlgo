"""
Contest API endpoints
"""

from decimal import Decimal
from typing import List, Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, get_current_admin
from app.core.config import settings
from app.db.session import get_db
from app.repos.contest_repo import (
    create_contest, get_contest_by_id, get_contests,
    join_contest, settle_contest
)
from app.repos.wallet_repo import debit_for_contest_entry
from app.repos.contest_entry_repo import create_contest_entry, get_contest_entries
from app.tasks.tasks import compute_and_distribute_payouts
from app.models.user import User

router = APIRouter()


class ContestCreate(BaseModel):
    """Contest creation request model"""
    match_id: str = Field(..., description="Cricket match ID")
    title: str = Field(..., description="Contest title")
    description: Optional[str] = Field(None, description="Contest description")
    entry_fee: str = Field(..., description="Entry fee in USDT")
    max_participants: int = Field(..., description="Maximum number of participants")
    prize_structure: List[Dict[str, Any]] = Field(..., description="Prize structure as list of position/percentage objects")
    start_time: Optional[str] = Field(None, description="Contest start time (ISO format)")
    end_time: Optional[str] = Field(None, description="Contest end time (ISO format)")


class ContestResponse(BaseModel):
    """Contest response model"""
    id: str
    match_id: str
    title: str
    description: Optional[str]
    entry_fee: str
    max_participants: int
    current_participants: int
    prize_structure: List[Dict[str, Any]]
    status: str
    created_at: str


class ContestJoinRequest(BaseModel):
    """Contest join request model"""
    contest_id: str = Field(..., description="Contest ID to join")


class ContestJoinResponse(BaseModel):
    """Contest join response model"""
    success: bool
    message: str
    entry_id: Optional[str] = None


class ContestSettleResponse(BaseModel):
    """Contest settlement response model"""
    success: bool
    message: str
    total_payouts: int
    total_commission: str


@router.post("/admin/contest", response_model=ContestResponse)
async def create_contest_endpoint(
    contest_data: ContestCreate,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Create a new contest (admin only).
    """
    try:
        entry_fee = Decimal(contest_data.entry_fee)
        if entry_fee <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Entry fee must be positive"
            )
        
        if contest_data.max_participants <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Max participants must be positive"
            )
        
        # Validate prize structure
        if not isinstance(contest_data.prize_structure, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prize structure must be a list of position/percentage objects"
            )
        
        # Create contest
        contest = await create_contest(
            session=session,
            match_id=contest_data.match_id,
            title=contest_data.title,
            description=contest_data.description,
            entry_fee=entry_fee,
            max_participants=contest_data.max_participants,
            prize_structure=contest_data.prize_structure,
            created_by=current_admin.id
        )
        
        return ContestResponse(
            id=str(contest.id),
            match_id=contest.match_id,
            title=contest.title,
            description=contest.description,
            entry_fee=str(contest.entry_fee),
            max_participants=contest.max_players,
            current_participants=0,  # New contest has no participants
            prize_structure=contest.prize_structure,
            status=contest.status,
            created_at=contest.created_at.isoformat()
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid entry fee format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create contest: {str(e)}"
        )


@router.post("/{contest_id}/join", response_model=ContestJoinResponse)
async def join_contest_endpoint(
    contest_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Join a contest.
    
    Atomically debits user's wallet and creates a contest entry.
    If contest becomes full, enqueues payout computation task.
    """
    try:
        contest_uuid = UUID(contest_id)
        
        # Get contest
        contest = await get_contest_by_id(session, contest_uuid)
        if not contest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contest not found"
            )
        
        # Check if contest is open for joining
        if contest.status != "open":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contest is not open for joining"
            )
        
        # Check if user already joined
        existing_entries = await get_contest_entries(session, contest_uuid, user_id=current_user.id)
        if existing_entries:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already joined this contest"
            )
        
        # Check if contest is full
        current_entries = await get_contest_entries(session, contest_uuid)
        if len(current_entries) >= contest.max_participants:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contest is full"
            )
        
        # Debit user's wallet atomically
        success, error = await debit_for_contest_entry(
            session,
            current_user.id,
            contest.entry_fee
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient balance: {error}"
            )
        
        # Create contest entry
        entry = await create_contest_entry(
            session=session,
            contest_id=contest_uuid,
            user_id=current_user.id,
            entry_fee=contest.entry_fee
        )
        
        # Check if contest is now full
        updated_entries = await get_contest_entries(session, contest_uuid)
        if len(updated_entries) >= contest.max_participants:
            # Enqueue payout computation task
            compute_and_distribute_payouts.delay(str(contest_uuid))
        
        return ContestJoinResponse(
            success=True,
            message="Successfully joined contest",
            entry_id=str(entry.id)
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid contest ID format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to join contest: {str(e)}"
        )


@router.post("/admin/{contest_id}/settle", response_model=ContestSettleResponse)
async def settle_contest_endpoint(
    contest_id: str,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Manually trigger contest settlement (admin only).
    
    Computes winners and enqueues payout distribution.
    """
    try:
        contest_uuid = UUID(contest_id)
        
        # Get contest
        contest = await get_contest_by_id(session, contest_uuid)
        if not contest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contest not found"
            )
        
        # Check if contest can be settled
        if contest.status not in ["open", "closed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contest cannot be settled in current status"
            )
        
        # Get contest entries
        entries = await get_contest_entries(session, contest_uuid)
        if not entries:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No participants in contest"
            )
        
        # Enqueue payout computation task
        compute_and_distribute_payouts.delay(str(contest_uuid))
        
        # Calculate total commission
        total_entry_fees = sum(entry.entry_fee for entry in entries)
        total_commission = total_entry_fees * Decimal(str(settings.platform_commission_pct / 100))
        
        return ContestSettleResponse(
            success=True,
            message="Contest settlement initiated",
            total_payouts=len(entries),
            total_commission=str(total_commission)
        )
        
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


@router.get("/")
async def get_contests_endpoint(
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
    session: AsyncSession = Depends(get_db)
):
    """
    Get list of contests.
    """
    contests = await get_contests(
        session, 
        limit=limit, 
        offset=offset, 
        status=status_filter
    )
    
    return {
        "contests": [
            {
                "id": str(contest.id),
                "match_id": contest.match_id,
                "title": contest.title,
                "description": contest.description,
                "entry_fee": str(contest.entry_fee),
                "max_participants": contest.max_participants,
                "current_participants": len(await get_contest_entries(session, contest.id)),
                "prize_structure": contest.prize_structure,
                "status": contest.status,
                "created_at": contest.created_at.isoformat()
            }
            for contest in contests
        ],
        "limit": limit,
        "offset": offset
    }


@router.get("/{contest_id}")
async def get_contest_endpoint(
    contest_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Get contest details.
    """
    try:
        contest_uuid = UUID(contest_id)
        contest = await get_contest_by_id(session, contest_uuid)
        
        if not contest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contest not found"
            )
        
        entries = await get_contest_entries(session, contest_uuid)
        
        return {
            "id": str(contest.id),
            "match_id": contest.match_id,
            "title": contest.title,
            "description": contest.description,
            "entry_fee": str(contest.entry_fee),
            "max_participants": contest.max_participants,
            "current_participants": len(entries),
            "prize_structure": contest.prize_structure,
            "status": contest.status,
            "created_at": contest.created_at.isoformat(),
            "participants": [
                {
                    "user_id": str(entry.user_id),
                    "entry_fee": str(entry.entry_fee),
                    "joined_at": entry.created_at.isoformat()
                }
                for entry in entries
            ]
        }
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid contest ID format"
        )
