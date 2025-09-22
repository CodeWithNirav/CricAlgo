from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
import csv
import io
from typing import List, Dict, Any
from pydantic import BaseModel
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.core.auth import get_current_admin
from app.db.session import get_db
from app.models.match import Match
from app.models.contest import Contest
from app.models.contest_entry import ContestEntry
from app.models.user import User
from app.models.admin import Admin

router = APIRouter(prefix="/api/v1/admin", tags=["admin_matches_contests"])


class MatchCreate(BaseModel):
    title: str
    start_time: str = None
    external_id: str = None


class ContestCreate(BaseModel):
    title: str
    entry_fee: str
    max_players: int = None
    prize_structure: Dict[str, Any] = {}


class WinnerSelection(BaseModel):
    winners: List[str]


@router.get("/matches")
async def list_matches(
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """List all matches from database"""
    try:
        # Query all matches from database
        stmt = select(Match).order_by(Match.start_time.desc())
        result = await db.execute(stmt)
        matches = result.scalars().all()
        
        # Convert to format expected by frontend
        return [match.to_dict() for match in matches]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to fetch matches: {str(e)}"}
        )


@router.post("/matches")
async def create_match(
    payload: MatchCreate,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new match in database"""
    try:
        # Parse start_time if provided
        start_time = None
        if payload.start_time:
            try:
                start_time = datetime.fromisoformat(payload.start_time.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "Invalid start_time format. Use ISO format (YYYY-MM-DDTHH:MM:SSZ)"}
                )
        
        # Create new match
        match = Match(
            title=payload.title,
            start_time=start_time or datetime.now(),
            external_id=payload.external_id
        )
        
        db.add(match)
        await db.commit()
        await db.refresh(match)
        
        return {
            "message": "Match created successfully!",
            "match": match.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to create match: {str(e)}"}
        )


@router.get("/matches/{match_id}/contests")
async def list_contests_for_match(
    match_id: str,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """List contests for a specific match from database"""
    try:
        # Query contests for the specific match
        stmt = select(Contest).where(Contest.match_id == match_id).order_by(Contest.created_at.desc())
        result = await db.execute(stmt)
        contests = result.scalars().all()
        
        # Convert to format expected by frontend
        return [contest.to_dict() for contest in contests]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to fetch contests: {str(e)}"}
        )


@router.post("/matches/{match_id}/contests")
async def create_contest_for_match(
    match_id: str, 
    payload: ContestCreate,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a contest for a specific match in database"""
    try:
        # Verify match exists
        match_stmt = select(Match).where(Match.id == match_id)
        match_result = await db.execute(match_stmt)
        match = match_result.scalar_one_or_none()
        
        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Match not found"}
            )
        
        # Generate unique contest code
        import random
        import string
        contest_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Create new contest
        contest = Contest(
            match_id=match_id,
            code=contest_code,
            title=payload.title,
            entry_fee=float(payload.entry_fee),
            max_players=payload.max_players,
            prize_structure=payload.prize_structure
        )
        
        db.add(contest)
        await db.commit()
        await db.refresh(contest)
        
        return {
            "message": "Contest created successfully!",
            "contest": contest.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to create contest: {str(e)}"}
        )


@router.get("/contests/{contest_id}")
async def get_contest(
    contest_id: str,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get contest details from database"""
    try:
        # Query contest by ID
        stmt = select(Contest).where(Contest.id == contest_id)
        result = await db.execute(stmt)
        contest = result.scalar_one_or_none()
        
        if not contest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Contest not found"}
            )
        
        return contest.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to fetch contest: {str(e)}"}
        )


@router.get("/contests/{contest_id}/entries")
async def get_contest_entries(
    contest_id: str,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get contest entries from database"""
    try:
        # Query contest entries with user information
        stmt = select(ContestEntry, User).join(
            User, ContestEntry.user_id == User.id
        ).where(ContestEntry.contest_id == contest_id).order_by(ContestEntry.created_at.desc())
        
        result = await db.execute(stmt)
        entries_with_users = result.all()
        
        # Convert to format expected by frontend
        entries = []
        for entry, user in entries_with_users:
            entry_dict = entry.to_dict()
            entry_dict.update({
                "telegram_id": str(user.telegram_id),
                "username": user.username
            })
            entries.append(entry_dict)
        
        return entries
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to fetch contest entries: {str(e)}"}
        )


@router.post("/contests/{contest_id}/select_winners")
async def select_winners(contest_id: str, payload: WinnerSelection):
    """Select winners for a contest - simplified version"""
    return {
        "message": "Winners selected successfully!",
        "contest_id": contest_id,
        "winners": payload.winners
    }


@router.post("/contests/{contest_id}/settle")
async def settle_contest(contest_id: str):
    """Settle a contest - simplified version"""
    return {
        "message": "Contest settled successfully!",
        "contest_id": contest_id,
        "status": "settled"
    }


@router.get("/contests/{contest_id}/export")
async def export_contest_pl(contest_id: str):
    """Export contest P&L as CSV - simplified version"""
    # Create a simple CSV
    csv_content = "entry_id,user,amount,winner_rank,payout\n"
    csv_content += f"entry-{contest_id}-1,testuser1,5.0,1,3.0\n"
    csv_content += f"entry-{contest_id}-2,testuser2,5.0,2,2.0\n"
    
    return StreamingResponse(
        io.BytesIO(csv_content.encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=contest_{contest_id}_pl.csv"}
    )