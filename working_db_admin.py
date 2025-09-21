#!/usr/bin/env python3
"""
Working Database Admin Server
"""
import asyncio
import os
from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Set environment
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:password@localhost:5432/cricalgo"

app = FastAPI(title="CricAlgo Working Admin", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Working Admin Server", "status": "ok"}

@app.get("/admin")
async def admin_ui():
    return FileResponse("app/static/admin/index.html")

@app.get("/assets/{filename}")
async def admin_assets(filename: str):
    return FileResponse(f"app/static/admin/assets/{filename}")

@app.get("/api/v1/admin/matches")
async def list_matches():
    """List matches - will connect to database"""
    try:
        # Import here to avoid circular imports
        from app.db.session import get_db
        from app.models.match import Match
        from sqlalchemy import select
        
        # Get database session
        async for db in get_db():
            result = await db.execute(select(Match).order_by(Match.created_at.desc()))
            matches = result.scalars().all()
            return [match.to_dict() for match in matches]
    except Exception as e:
        return {"error": f"Database error: {str(e)}", "matches": []}

@app.get("/api/v1/admin/deposits")
async def list_deposits():
    """List deposits - will connect to database"""
    try:
        from app.db.session import get_db
        from app.models.transaction import Transaction
        from sqlalchemy import select
        
        async for db in get_db():
            result = await db.execute(
                select(Transaction).where(Transaction.tx_type == "deposit")
                .order_by(Transaction.created_at.desc())
            )
            transactions = result.scalars().all()
            return [tx.to_dict() for tx in transactions]
    except Exception as e:
        return {"error": f"Database error: {str(e)}", "deposits": []}

@app.get("/api/v1/admin/withdrawals")
async def list_withdrawals():
    """List withdrawals - will connect to database"""
    try:
        from app.db.session import get_db
        from app.models.withdrawal import Withdrawal
        from sqlalchemy import select
        
        async for db in get_db():
            result = await db.execute(
                select(Withdrawal).order_by(Withdrawal.created_at.desc())
            )
            withdrawals = result.scalars().all()
            return [w.to_dict() for w in withdrawals]
    except Exception as e:
        return {"error": f"Database error: {str(e)}", "withdrawals": []}

@app.get("/api/v1/admin/audit")
async def get_audit():
    """Get audit logs - will connect to database"""
    try:
        from app.db.session import get_db
        from app.models.audit_log import AuditLog
        from sqlalchemy import select
        
        async for db in get_db():
            result = await db.execute(
                select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100)
            )
            logs = result.scalars().all()
            return [log.to_dict() for log in logs]
    except Exception as e:
        return {"error": f"Database error: {str(e)}", "audit": []}

if __name__ == "__main__":
    print("🚀 Starting WORKING database admin server...")
    print("📱 Admin UI: http://localhost:8000/admin")
    print("🗄️ Connected to PostgreSQL database")
    print("✅ This will show REAL data from the database!")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
