from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import csv
import io
from typing import List, Dict, Any
from pydantic import BaseModel
from uuid import UUID

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
async def list_matches():
    """List all matches - simplified version"""
    return [
        {
            "id": "match-1",
            "title": "Test Cricket Match 1",
            "starts_at": "2024-01-15T10:00:00Z",
            "status": "scheduled"
        },
        {
            "id": "match-2", 
            "title": "Test Cricket Match 2",
            "starts_at": "2024-01-16T14:00:00Z",
            "status": "scheduled"
        }
    ]


@router.post("/matches")
async def create_match(payload: MatchCreate):
    """Create a new match - simplified version"""
    return {
        "message": "Match created successfully!",
        "match": {
            "id": f"match-{len(payload.title)}",
            "title": payload.title,
            "starts_at": payload.start_time,
            "status": "scheduled"
        }
    }


@router.get("/matches/{match_id}/contests")
async def list_contests_for_match(match_id: str):
    """List contests for a specific match - simplified version"""
    return [
        {
            "id": f"contest-{match_id}-1",
            "title": f"Contest for {match_id}",
            "entry_fee": "5.0",
            "max_players": 10,
            "prize_structure": {"1": 0.6, "2": 0.4}
        }
    ]


@router.post("/matches/{match_id}/contests")
async def create_contest_for_match(match_id: str, payload: ContestCreate):
    """Create a contest for a specific match - simplified version"""
    return {
        "message": "Contest created successfully!",
        "contest": {
            "id": f"contest-{match_id}-new",
            "title": payload.title,
            "entry_fee": payload.entry_fee,
            "max_players": payload.max_players,
            "prize_structure": payload.prize_structure
        }
    }


@router.get("/contests/{contest_id}")
async def get_contest(contest_id: str):
    """Get contest details - simplified version"""
    return {
        "id": contest_id,
        "title": f"Contest {contest_id}",
        "entry_fee": "5.0",
        "max_players": 10,
        "prize_structure": {"1": 0.6, "2": 0.4},
        "status": "open"
    }


@router.get("/contests/{contest_id}/entries")
async def get_contest_entries(contest_id: str):
    """Get contest entries - simplified version"""
    return [
        {
            "id": f"entry-{contest_id}-1",
            "telegram_id": "123456789",
            "username": "testuser1",
            "amount_debited": "5.0",
            "winner_rank": None
        },
        {
            "id": f"entry-{contest_id}-2",
            "telegram_id": "987654321",
            "username": "testuser2", 
            "amount_debited": "5.0",
            "winner_rank": None
        }
    ]


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