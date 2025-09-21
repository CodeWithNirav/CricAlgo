from fastapi import APIRouter, Depends, HTTPException
from app.db.session import get_db
from app.core.auth import get_current_admin
from sqlalchemy import select, update
from app.models.match import Match
from app.models.contest import Contest
from app.models.contest_entry import ContestEntry
from app.models.audit_log import AuditLog
from app.models.user import User
from fastapi.responses import StreamingResponse
import csv
import io
from typing import List, Dict, Any
from pydantic import BaseModel
from uuid import UUID

router = APIRouter(prefix="/api/v1/admin", tags=["admin_matches_contests"], dependencies=[Depends(get_current_admin)])


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
async def list_matches(db=Depends(get_db)):
    """List all matches"""
    q = await db.execute(select(Match).order_by(Match.start_time.desc()).limit(500))
    rows = q.scalars().all()
    return [r.to_dict() for r in rows]


@router.post("/matches")
async def create_match(payload: MatchCreate, db=Depends(get_db)):
    """Create a new match"""
    from datetime import datetime
    
    start_time = None
    if payload.start_time:
        try:
            start_time = datetime.fromisoformat(payload.start_time.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_time format")
    
    m = Match(
        title=payload.title, 
        start_time=start_time,
        external_id=payload.external_id
    )
    db.add(m)
    db.add(AuditLog(action="create_match", details=payload.dict(), actor="web_admin"))
    await db.commit()
    await db.refresh(m)
    return m.to_dict()


@router.get("/matches/{match_id}/contests")
async def list_contests_for_match(match_id: str, db=Depends(get_db)):
    """List contests for a specific match"""
    try:
        match_uuid = UUID(match_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid match ID format")
    
    q = await db.execute(
        select(Contest)
        .where(Contest.match_id == match_uuid)
        .order_by(Contest.created_at.desc())
        .limit(500)
    )
    rows = q.scalars().all()
    return [r.to_dict() for r in rows]


@router.post("/matches/{match_id}/contests")
async def create_contest_for_match(match_id: str, payload: ContestCreate, db=Depends(get_db)):
    """Create a contest for a specific match"""
    try:
        match_uuid = UUID(match_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid match ID format")
    
    from decimal import Decimal
    import time
    import uuid
    
    # Generate unique contest code
    contest_code = f"CONTEST_{int(time.time())}{uuid.uuid4().hex[:6].upper()}"
    
    c = Contest(
        match_id=match_uuid,
        code=contest_code,
        title=payload.title,
        entry_fee=Decimal(payload.entry_fee),
        max_players=payload.max_players,
        prize_structure=payload.prize_structure
    )
    db.add(c)
    db.add(AuditLog(
        action="create_contest", 
        details={"match_id": match_id, "payload": payload.dict()}, 
        actor="web_admin"
    ))
    await db.commit()
    await db.refresh(c)
    return c.to_dict()


@router.get("/contests/{contest_id}")
async def get_contest(contest_id: str, db=Depends(get_db)):
    """Get contest details"""
    try:
        contest_uuid = UUID(contest_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contest ID format")
    
    q = await db.execute(select(Contest).where(Contest.id == contest_uuid))
    c = q.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="Contest not found")
    return c.to_dict()


@router.get("/contests/{contest_id}/entries")
async def get_contest_entries(contest_id: str, db=Depends(get_db)):
    """Get contest entries with user information"""
    try:
        contest_uuid = UUID(contest_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contest ID format")
    
    # Join with users table to get telegram_id and username
    q = await db.execute(
        select(ContestEntry, User.telegram_id, User.username)
        .join(User, ContestEntry.user_id == User.id)
        .where(ContestEntry.contest_id == contest_uuid)
    )
    rows = q.all()
    
    entries = []
    for entry, telegram_id, username in rows:
        entry_dict = entry.to_dict()
        entry_dict['telegram_id'] = telegram_id
        entry_dict['username'] = username
        entries.append(entry_dict)
    
    return entries


@router.post("/contests/{contest_id}/select_winners")
async def select_winners(contest_id: str, payload: WinnerSelection, db=Depends(get_db)):
    """Select winners for a contest"""
    try:
        contest_uuid = UUID(contest_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contest ID format")
    
    winners = payload.winners
    if not winners:
        raise HTTPException(status_code=400, detail="No winners provided")
    
    # Update contest entries with winner ranks
    for idx, entry_id in enumerate(winners, start=1):
        try:
            entry_uuid = UUID(entry_id)
            await db.execute(
                update(ContestEntry)
                .where(ContestEntry.id == entry_uuid)
                .values(winner_rank=idx)
            )
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid entry ID: {entry_id}")
    
    db.add(AuditLog(
        action="select_winners", 
        details={"contest_id": contest_id, "winners": winners}, 
        actor="web_admin"
    ))
    await db.commit()
    return {"ok": True}


@router.post("/contests/{contest_id}/settle")
async def settle_contest(contest_id: str, db=Depends(get_db)):
    """Settle a contest using the existing settlement service"""
    try:
        contest_uuid = UUID(contest_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contest ID format")
    
    # Call existing settlement service
    try:
        from app.services.settlement import settle_contest
        result = await settle_contest(db, contest_uuid)
        if not result.get("success", False):
            raise HTTPException(status_code=400, detail=result.get("error", "Settlement failed"))
    except ImportError:
        # Fallback if settlement service doesn't exist
        raise HTTPException(status_code=501, detail="Settlement service not available")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    db.add(AuditLog(
        action="settle_contest", 
        details={"contest_id": contest_id}, 
        actor="web_admin"
    ))
    await db.commit()
    return {"ok": True}


@router.get("/contests/{contest_id}/export")
async def export_contest_pl(contest_id: str, db=Depends(get_db)):
    """Export contest P&L as CSV"""
    try:
        contest_uuid = UUID(contest_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid contest ID format")
    
    # Get contest details
    q = await db.execute(select(Contest).where(Contest.id == contest_uuid))
    contest = q.scalar_one_or_none()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    
    # Get contest entries with user info
    q2 = await db.execute(
        select(ContestEntry, User.telegram_id, User.username)
        .join(User, ContestEntry.user_id == User.id)
        .where(ContestEntry.contest_id == contest_uuid)
    )
    rows = q2.all()
    
    # Create CSV
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["entry_id", "user", "amount", "winner_rank", "payout"])
    
    for entry, telegram_id, username in rows:
        user_identifier = telegram_id or username or str(entry.user_id)
        w.writerow([
            str(entry.id),
            user_identifier,
            str(entry.amount_debited),
            getattr(entry, 'winner_rank', None),
            getattr(entry, 'payout_amount', None)
        ])
    
    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=contest_{contest_id}_pl.csv"}
    )
