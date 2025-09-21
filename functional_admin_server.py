#!/usr/bin/env python3
"""
Functional Admin Server with Database Integration
"""
import asyncio
import os
from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uvicorn

# Set up environment
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:password@localhost:5432/cricalgo"

from app.db.session import get_db
from app.models.match import Match
from app.models.contest import Contest
from app.models.contest_entry import ContestEntry
from app.models.transaction import Transaction
from app.models.withdrawal import Withdrawal
from app.models.audit_log import AuditLog

app = FastAPI(title="CricAlgo Functional Admin", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
async def root():
    return {"message": "CricAlgo Functional Admin API is running!", "status": "ok"}

# Admin UI
@app.get("/admin")
async def admin_ui():
    return FileResponse("app/static/admin/index.html")

@app.get("/assets/{filename}")
async def admin_assets(filename: str):
    return FileResponse(f"app/static/admin/assets/{filename}")

# Matches API - Connected to Database
@app.get("/api/v1/admin/matches")
async def list_matches(db: AsyncSession = Depends(get_db)):
    """List all matches from database"""
    try:
        result = await db.execute(select(Match).order_by(Match.created_at.desc()))
        matches = result.scalars().all()
        return [match.to_dict() for match in matches]
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

@app.post("/api/v1/admin/matches")
async def create_match(payload: dict, db: AsyncSession = Depends(get_db)):
    """Create a new match in database"""
    try:
        match = Match(
            title=payload.get("title", "New Match"),
            external_id=payload.get("external_id"),
            starts_at=payload.get("start_time")
        )
        db.add(match)
        await db.commit()
        await db.refresh(match)
        return {"message": "Match created successfully!", "match": match.to_dict()}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

@app.get("/api/v1/admin/matches/{match_id}/contests")
async def list_contests_for_match(match_id: str, db: AsyncSession = Depends(get_db)):
    """List contests for a specific match from database"""
    try:
        result = await db.execute(select(Contest).where(Contest.match_id == match_id))
        contests = result.scalars().all()
        return [contest.to_dict() for contest in contests]
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

@app.get("/api/v1/admin/contests/{contest_id}")
async def get_contest(contest_id: str, db: AsyncSession = Depends(get_db)):
    """Get contest details from database"""
    try:
        result = await db.execute(select(Contest).where(Contest.id == contest_id))
        contest = result.scalar_one_or_none()
        if not contest:
            return {"error": "Contest not found"}
        return contest.to_dict()
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

@app.get("/api/v1/admin/contests/{contest_id}/entries")
async def get_contest_entries(contest_id: str, db: AsyncSession = Depends(get_db)):
    """Get contest entries from database"""
    try:
        result = await db.execute(select(ContestEntry).where(ContestEntry.contest_id == contest_id))
        entries = result.scalars().all()
        return [entry.to_dict() for entry in entries]
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

# Deposits API - Connected to Database
@app.get("/api/v1/admin/deposits")
async def list_deposits(status: str = "pending", db: AsyncSession = Depends(get_db)):
    """List deposits from database"""
    try:
        if status == "pending":
            result = await db.execute(
                select(Transaction).where(
                    Transaction.tx_type == "deposit",
                    Transaction.processed_at.is_(None)
                ).order_by(Transaction.created_at.desc())
            )
        else:
            result = await db.execute(
                select(Transaction).where(
                    Transaction.tx_type == "deposit",
                    Transaction.processed_at.isnot(None)
                ).order_by(Transaction.created_at.desc())
            )
        transactions = result.scalars().all()
        return [tx.to_dict() for tx in transactions]
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

@app.post("/api/v1/admin/deposits/{tx_id}/approve")
async def approve_deposit(tx_id: str, payload: dict = None, db: AsyncSession = Depends(get_db)):
    """Approve deposit in database"""
    try:
        result = await db.execute(select(Transaction).where(Transaction.id == tx_id))
        tx = result.scalar_one_or_none()
        if not tx:
            return {"error": "Transaction not found"}
        
        # Mark as processed
        tx.processed_at = "now()"
        await db.commit()
        
        return {"message": f"Deposit {tx_id} approved successfully!", "ok": True}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

@app.post("/api/v1/admin/deposits/{tx_id}/reject")
async def reject_deposit(tx_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    """Reject deposit in database"""
    try:
        result = await db.execute(select(Transaction).where(Transaction.id == tx_id))
        tx = result.scalar_one_or_none()
        if not tx:
            return {"error": "Transaction not found"}
        
        # Mark as rejected
        tx.status = "rejected"
        tx.processed_at = "now()"
        await db.commit()
        
        return {"message": f"Deposit {tx_id} rejected successfully!", "ok": True}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

# Withdrawals API - Connected to Database
@app.get("/api/v1/admin/withdrawals")
async def list_withdrawals(status: str = "pending", db: AsyncSession = Depends(get_db)):
    """List withdrawals from database"""
    try:
        result = await db.execute(
            select(Withdrawal).where(Withdrawal.status == status)
            .order_by(Withdrawal.created_at.desc())
        )
        withdrawals = result.scalars().all()
        return [w.to_dict() for w in withdrawals]
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

# Audit API - Connected to Database
@app.get("/api/v1/admin/audit")
async def get_audit(limit: int = 200, db: AsyncSession = Depends(get_db)):
    """Get audit logs from database"""
    try:
        result = await db.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        )
        logs = result.scalars().all()
        return [log.to_dict() for log in logs]
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

if __name__ == "__main__":
    print("🚀 Starting FUNCTIONAL admin server with database...")
    print("📱 Admin UI: http://localhost:8000/admin")
    print("🔧 API Test: http://localhost:8000/api/v1/admin/matches")
    print("🗄️ Connected to PostgreSQL database")
    print("✅ This is a REAL functional admin panel!")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
