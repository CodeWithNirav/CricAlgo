from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
import csv
import io
import logging
from typing import List, Dict, Any
from pydantic import BaseModel
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.core.auth import get_current_admin
from app.core.config import settings
from app.db.session import get_db
from app.models.match import Match
from app.models.contest import Contest
from app.models.contest_entry import ContestEntry
from app.models.user import User
from app.models.admin import Admin
from app.services.settlement import settle_contest
from app.repos.contest_repo import get_contest_by_id
from app.repos.contest_entry_repo import get_contest_entries

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin_matches_contests"])


class MatchCreate(BaseModel):
    title: str
    start_time: str = None
    external_id: str = None


class ContestCreate(BaseModel):
    title: str
    entry_fee: str
    max_players: int = None
    prize_structure: List[Dict[str, Any]] = [{"pos": 1, "pct": 100}]


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


@router.get("/contests")
async def list_contests(
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """List all contests from database"""
    try:
        # Query all contests from database
        stmt = select(Contest).order_by(Contest.created_at.desc())
        result = await db.execute(stmt)
        contests = result.scalars().all()
        
        # Convert to format expected by frontend
        return [contest.to_dict() for contest in contests]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to fetch contests: {str(e)}"}
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
        
        # Ensure default prize structure (100% to 1st rank only)
        # Always use 100% for rank 1, regardless of what's sent from frontend
        prize_structure = [{"pos": 1, "pct": 100}]
        
        # Create new contest
        contest = Contest(
            match_id=match_id,
            code=contest_code,
            title=payload.title,
            entry_fee=float(payload.entry_fee),
            max_players=payload.max_players,
            prize_structure=prize_structure,
            commission_pct=settings.platform_commission_pct
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
async def get_contest_entries_endpoint(
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
async def select_winners(
    contest_id: str,
    payload: WinnerSelection,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Select winners for a contest"""
    try:
        logger.info(f"🔍 DEBUG: Starting select_winners for contest {contest_id}")
        logger.info(f"🔍 DEBUG: Payload received: {payload}")
        logger.info(f"🔍 DEBUG: Winners: {payload.winners}")
        logger.info(f"🔍 DEBUG: Admin: {current_admin.username}")
        
        contest_uuid = UUID(contest_id)
        logger.info(f"🔍 DEBUG: Contest UUID: {contest_uuid}")
        
        # Get contest
        logger.info(f"🔍 DEBUG: Getting contest by ID...")
        contest = await get_contest_by_id(db, contest_uuid)
        if not contest:
            logger.error(f"❌ DEBUG: Contest not found: {contest_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contest not found"
            )
        
        logger.info(f"🔍 DEBUG: Contest found: {contest.title}, status: {contest.status}")
        
        # Check if contest can have winners selected
        if contest.status not in ["open", "closed"]:
            logger.error(f"❌ DEBUG: Invalid contest status: {contest.status}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contest cannot have winners selected in current status"
            )
        
        # Get contest entries
        logger.info(f"🔍 DEBUG: Getting contest entries...")
        entries = await get_contest_entries(db, contest_uuid)
        if not entries:
            logger.error(f"❌ DEBUG: No entries found for contest: {contest_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No participants in contest"
            )
        
        logger.info(f"🔍 DEBUG: Found {len(entries)} entries")
        entry_ids = [str(entry.id) for entry in entries]
        logger.info(f"🔍 DEBUG: Entry IDs: {entry_ids}")
        
        # Validate winner IDs exist in contest entries
        invalid_winners = [w for w in payload.winners if w not in entry_ids]
        if invalid_winners:
            logger.error(f"❌ DEBUG: Invalid winner IDs: {invalid_winners}")
            logger.error(f"❌ DEBUG: Valid entry IDs: {entry_ids}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid winner IDs: {invalid_winners}"
            )
        
        logger.info(f"🔍 DEBUG: All winner IDs are valid")
        
        # Update contest entries with winner ranks
        for i, winner_id in enumerate(payload.winners, 1):
            try:
                logger.info(f"🔍 DEBUG: Processing winner {i}: {winner_id}")
                entry_stmt = select(ContestEntry).where(ContestEntry.id == UUID(winner_id))
                entry_result = await db.execute(entry_stmt)
                entry = entry_result.scalar_one_or_none()
                if entry:
                    logger.info(f"🔍 DEBUG: Setting winner_rank={i} for entry {winner_id}")
                    entry.winner_rank = i
                    db.add(entry)
                else:
                    logger.error(f"❌ DEBUG: Contest entry {winner_id} not found in DB")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Contest entry {winner_id} not found"
                    )
            except ValueError as ve:
                logger.error(f"❌ DEBUG: ValueError for {winner_id}: {str(ve)}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid entry ID format: {winner_id}"
                )
        
        logger.info(f"🔍 DEBUG: Committing changes to database...")
        await db.commit()
        logger.info(f"✅ DEBUG: Successfully committed changes!")
        
        # Automatically trigger settlement after selecting winners
        logger.info(f"🔍 DEBUG: Starting automatic settlement for contest {contest_id}")
        try:
            from app.services.settlement import settle_contest
            settlement_result = await settle_contest(
                session=db,
                contest_id=contest_uuid,
                admin_id=current_admin.id
            )
            
            if settlement_result.get("success", False):
                logger.info(f"✅ DEBUG: Contest {contest_id} settled successfully!")
                return {
                    "message": "Winners selected and contest settled successfully!",
                    "contest_id": contest_id,
                    "winners": payload.winners,
                    "num_winners": len(payload.winners),
                    "settlement": settlement_result
                }
            else:
                logger.error(f"❌ DEBUG: Settlement failed: {settlement_result.get('error', 'Unknown error')}")
                return {
                    "message": "Winners selected but settlement failed. Please try settling manually.",
                    "contest_id": contest_id,
                    "winners": payload.winners,
                    "num_winners": len(payload.winners),
                    "settlement_error": settlement_result.get('error', 'Unknown error')
                }
        except Exception as settlement_error:
            logger.error(f"❌ DEBUG: Settlement exception: {str(settlement_error)}")
            return {
                "message": "Winners selected but settlement failed. Please try settling manually.",
                "contest_id": contest_id,
                "winners": payload.winners,
                "num_winners": len(payload.winners),
                "settlement_error": str(settlement_error)
            }
        
    except ValueError as ve:
        logger.error(f"❌ DEBUG: ValueError in select_winners: {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid contest ID format"
        )
    except HTTPException as he:
        logger.error(f"❌ DEBUG: HTTPException in select_winners: {he.detail}")
        raise he
    except Exception as e:
        logger.error(f"❌ DEBUG: Unexpected error in select_winners: {str(e)}")
        logger.error(f"❌ DEBUG: Exception type: {type(e)}")
        import traceback
        logger.error(f"❌ DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to select winners: {str(e)}"
        )


@router.post("/contests/{contest_id}/settle")
async def settle_contest_endpoint(
    contest_id: str,
    current_admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Settle a contest and distribute payouts"""
    try:
        # Handle both string and UUID contest_id
        if isinstance(contest_id, str):
            contest_uuid = UUID(contest_id)
        else:
            contest_uuid = contest_id
        
        # Call the settlement service
        settlement_result = await settle_contest(
            session=db,
            contest_id=contest_uuid,
            admin_id=current_admin.id
        )
        
        # Check if settlement_result is a dict and has success field
        if isinstance(settlement_result, dict) and not settlement_result.get("success", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Settlement failed: {settlement_result.get('error', 'Unknown error')}"
            )
        elif not isinstance(settlement_result, dict):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Settlement service returned unexpected result: {type(settlement_result)}"
            )
        
        return {
            "message": "Contest settled successfully!",
            "contest_id": contest_id,
            "status": "settled",
            "settlement_details": settlement_result
        }
        
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