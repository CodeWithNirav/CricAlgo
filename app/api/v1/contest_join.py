from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/contests", tags=["contests"])

class JoinReq(BaseModel):
    telegram_id: int

@router.post("/{contest_id}/join")
async def join_contest(contest_id: str, body: JoinReq, db: AsyncSession = Depends(get_db)):
    """Join a contest - simplified version for testing"""
    try:
        # For now, return a simple success response
        # In a real implementation, this would check wallet balance, deduct entry fee, etc.
        return {
            "ok": True, 
            "message": "Successfully joined contest",
            "contest_id": contest_id,
            "telegram_id": body.telegram_id,
            "contest_title": f"Contest {contest_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not join contest: {str(e)}")
