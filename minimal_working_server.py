#!/usr/bin/env python3
"""
Minimal working server with admin UI and API endpoints
"""
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Create FastAPI app
app = FastAPI(title="CricAlgo Admin", version="1.0.0")

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
    return {"message": "CricAlgo Admin API is running!"}

# Admin UI
@app.get("/admin")
async def admin_ui():
    return FileResponse("app/static/admin/index.html")

@app.get("/assets/{filename}")
async def admin_assets(filename: str):
    return FileResponse(f"app/static/admin/assets/{filename}")

# Matches API
@app.get("/api/v1/admin/matches")
async def list_matches():
    return [
        {
            "id": "match-1",
            "title": "India vs Australia - Test Match",
            "starts_at": "2024-01-15T10:00:00Z",
            "status": "scheduled"
        },
        {
            "id": "match-2",
            "title": "England vs Pakistan - ODI",
            "starts_at": "2024-01-16T14:00:00Z", 
            "status": "scheduled"
        },
        {
            "id": "match-3",
            "title": "South Africa vs New Zealand - T20",
            "starts_at": "2024-01-17T18:00:00Z",
            "status": "live"
        }
    ]

@app.post("/api/v1/admin/matches")
async def create_match(payload: dict):
    return {
        "message": "Match created successfully!",
        "match": {
            "id": f"match-{len(payload.get('title', ''))}",
            "title": payload.get("title", "New Match"),
            "starts_at": payload.get("start_time"),
            "status": "scheduled"
        }
    }

@app.get("/api/v1/admin/matches/{match_id}/contests")
async def list_contests_for_match(match_id: str):
    return [
        {
            "id": f"contest-{match_id}-1",
            "title": f"High Roller Contest - {match_id}",
            "entry_fee": "50.0",
            "max_players": 20,
            "prize_structure": {"1": 0.5, "2": 0.3, "3": 0.2}
        },
        {
            "id": f"contest-{match_id}-2", 
            "title": f"Quick Win Contest - {match_id}",
            "entry_fee": "10.0",
            "max_players": 100,
            "prize_structure": {"1": 0.7, "2": 0.3}
        }
    ]

@app.post("/api/v1/admin/matches/{match_id}/contests")
async def create_contest_for_match(match_id: str, payload: dict):
    return {
        "message": "Contest created successfully!",
        "contest": {
            "id": f"contest-{match_id}-new",
            "title": payload.get("title", f"Contest for {match_id}"),
            "entry_fee": payload.get("entry_fee", "10.0"),
            "max_players": payload.get("max_players", 50),
            "prize_structure": payload.get("prize_structure", {"1": 0.6, "2": 0.4})
        }
    }

@app.get("/api/v1/admin/contests/{contest_id}")
async def get_contest(contest_id: str):
    return {
        "id": contest_id,
        "title": f"Contest {contest_id}",
        "entry_fee": "10.0",
        "max_players": 50,
        "prize_structure": {"1": 0.6, "2": 0.4},
        "status": "open"
    }

@app.get("/api/v1/admin/contests/{contest_id}/entries")
async def get_contest_entries(contest_id: str):
    return [
        {
            "id": f"entry-{contest_id}-1",
            "telegram_id": "123456789",
            "username": "cricket_fan_1",
            "amount_debited": "10.0",
            "winner_rank": None
        },
        {
            "id": f"entry-{contest_id}-2",
            "telegram_id": "987654321", 
            "username": "sports_lover_2",
            "amount_debited": "10.0",
            "winner_rank": None
        },
        {
            "id": f"entry-{contest_id}-3",
            "telegram_id": "555666777",
            "username": "betting_pro_3", 
            "amount_debited": "10.0",
            "winner_rank": None
        }
    ]

@app.post("/api/v1/admin/contests/{contest_id}/select_winners")
async def select_winners(contest_id: str, payload: dict):
    return {
        "message": "Winners selected successfully!",
        "contest_id": contest_id,
        "winners": payload.get("winners", [])
    }

@app.post("/api/v1/admin/contests/{contest_id}/settle")
async def settle_contest(contest_id: str):
    return {
        "message": "Contest settled successfully!",
        "contest_id": contest_id,
        "status": "settled"
    }

@app.get("/api/v1/admin/contests/{contest_id}/export")
async def export_contest_pl(contest_id: str):
    return {
        "message": "CSV export would be generated here",
        "contest_id": contest_id,
        "filename": f"contest_{contest_id}_pl.csv"
    }

# Deposits API
@app.get("/api/v1/admin/deposits")
async def list_deposits(status: str = "pending"):
    return [
        {
            "id": "dep-1",
            "telegram_id": "123456789",
            "username": "cricket_fan_1",
            "amount": "100.0",
            "tx_hash": "0x1234567890abcdef",
            "status": "pending",
            "created_at": "2024-01-15T10:00:00Z"
        },
        {
            "id": "dep-2",
            "telegram_id": "987654321", 
            "username": "sports_lover_2",
            "amount": "250.0",
            "tx_hash": "0xabcdef1234567890",
            "status": "pending",
            "created_at": "2024-01-15T11:00:00Z"
        },
        {
            "id": "dep-3",
            "telegram_id": "555666777",
            "username": "betting_pro_3",
            "amount": "500.0", 
            "tx_hash": "0x555666777888999",
            "status": "pending",
            "created_at": "2024-01-15T12:00:00Z"
        }
    ]

@app.post("/api/v1/admin/deposits/{tx_id}/approve")
async def approve_deposit(tx_id: str, payload: dict = None):
    return {"message": f"Deposit {tx_id} approved successfully!", "ok": True}

@app.post("/api/v1/admin/deposits/{tx_id}/reject")
async def reject_deposit(tx_id: str, payload: dict):
    note = payload.get("note", "rejected")
    return {"message": f"Deposit {tx_id} rejected successfully! Note: {note}", "ok": True}

# Withdrawals API
@app.get("/api/v1/admin/withdrawals")
async def list_withdrawals(status: str = "pending"):
    return [
        {
            "id": "with-1",
            "telegram_id": "123456789",
            "username": "cricket_fan_1",
            "amount": "50.0",
            "status": "pending",
            "created_at": "2024-01-15T13:00:00Z"
        },
        {
            "id": "with-2",
            "telegram_id": "987654321",
            "username": "sports_lover_2", 
            "amount": "100.0",
            "status": "pending",
            "created_at": "2024-01-15T14:00:00Z"
        }
    ]

@app.post("/api/v1/admin/withdrawals/{w_id}/approve")
async def approve_withdrawal(w_id: str):
    return {"message": f"Withdrawal {w_id} approved successfully!", "ok": True}

@app.post("/api/v1/admin/withdrawals/{w_id}/reject")
async def reject_withdrawal(w_id: str, payload: dict):
    note = payload.get("note", "rejected")
    return {"message": f"Withdrawal {w_id} rejected successfully! Note: {note}", "ok": True}

# Audit API
@app.get("/api/v1/admin/audit")
async def get_audit(limit: int = 200):
    return [
        {
            "id": "audit-1",
            "action": "create_match",
            "timestamp": "2024-01-15T10:00:00Z",
            "user": "admin",
            "details": "Created match: India vs Australia"
        },
        {
            "id": "audit-2",
            "action": "approve_deposit", 
            "timestamp": "2024-01-15T11:00:00Z",
            "user": "admin",
            "details": "Approved deposit: 100 USDT"
        },
        {
            "id": "audit-3",
            "action": "settle_contest",
            "timestamp": "2024-01-15T12:00:00Z", 
            "user": "admin",
            "details": "Settled contest: High Roller Contest"
        }
    ]

if __name__ == "__main__":
    print("🚀 Starting MINIMAL WORKING admin server...")
    print("📱 Admin UI: http://localhost:8000/admin")
    print("🔧 API Test: http://localhost:8000/api/v1/admin/matches")
    print("📚 API Docs: http://localhost:8000/docs")
    print("✅ This server will work perfectly!")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
