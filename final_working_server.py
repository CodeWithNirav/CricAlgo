#!/usr/bin/env python3
"""
Final working admin server with fake data - guaranteed to work
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import json

app = FastAPI(title="CricAlgo Admin API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fake data storage
fake_data = {
    "matches": [
        {
            "id": "match-1",
            "title": "India vs Australia - Test Match",
            "starts_at": "2024-01-15T10:00:00Z",
            "status": "scheduled",
            "external_id": "IND-AUS-001"
        },
        {
            "id": "match-2", 
            "title": "England vs Pakistan - ODI",
            "starts_at": "2024-01-16T14:00:00Z",
            "status": "scheduled",
            "external_id": "ENG-PAK-002"
        },
        {
            "id": "match-3",
            "title": "South Africa vs New Zealand - T20",
            "starts_at": "2024-01-17T18:00:00Z",
            "status": "live",
            "external_id": "SA-NZ-003"
        }
    ],
    "contests": {
        "match-1": [
            {
                "id": "contest-1-1",
                "title": "High Roller Contest",
                "entry_fee": "50.0",
                "max_players": 20,
                "prize_structure": {"1": 0.5, "2": 0.3, "3": 0.2},
                "status": "open"
            },
            {
                "id": "contest-1-2",
                "title": "Quick Win Contest",
                "entry_fee": "10.0",
                "max_players": 100,
                "prize_structure": {"1": 0.7, "2": 0.3},
                "status": "open"
            }
        ],
        "match-2": [
            {
                "id": "contest-2-1",
                "title": "Mega Contest",
                "entry_fee": "25.0",
                "max_players": 50,
                "prize_structure": {"1": 0.6, "2": 0.4},
                "status": "open"
            }
        ]
    },
    "entries": {
        "contest-1-1": [
            {
                "id": "entry-1-1-1",
                "telegram_id": "123456789",
                "username": "cricket_fan_1",
                "amount_debited": "50.0",
                "winner_rank": None,
                "payout_amount": None
            },
            {
                "id": "entry-1-1-2",
                "telegram_id": "987654321",
                "username": "sports_lover_2",
                "amount_debited": "50.0",
                "winner_rank": None,
                "payout_amount": None
            },
            {
                "id": "entry-1-1-3",
                "telegram_id": "555666777",
                "username": "betting_pro_3",
                "amount_debited": "50.0",
                "winner_rank": None,
                "payout_amount": None
            }
        ],
        "contest-1-2": [
            {
                "id": "entry-1-2-1",
                "telegram_id": "111222333",
                "username": "quick_bet_1",
                "amount_debited": "10.0",
                "winner_rank": None,
                "payout_amount": None
            },
            {
                "id": "entry-1-2-2",
                "telegram_id": "444555666",
                "username": "fast_money_2",
                "amount_debited": "10.0",
                "winner_rank": None,
                "payout_amount": None
            }
        ]
    },
    "deposits": [
        {
            "id": "dep-1",
            "telegram_id": "123456789",
            "username": "cricket_fan_1",
            "amount": "100.0",
            "tx_hash": "0x1234567890abcdef",
            "status": "pending"
        },
        {
            "id": "dep-2",
            "telegram_id": "987654321",
            "username": "sports_lover_2",
            "amount": "250.0",
            "tx_hash": "0xabcdef1234567890",
            "status": "pending"
        }
    ]
}

# Root endpoint
@app.get("/")
async def root():
    return {"message": "CricAlgo Admin API is running!", "version": "1.0.0"}

# Admin UI
@app.get("/admin")
async def admin_ui():
    """Serve admin UI"""
    return FileResponse("app/static/admin/index.html")

@app.get("/assets/{filename}")
async def admin_assets(filename: str):
    """Serve admin assets"""
    return FileResponse(f"app/static/admin/assets/{filename}")

# Matches API
@app.get("/api/v1/admin/matches")
async def list_matches():
    """List all matches"""
    return fake_data["matches"]

@app.post("/api/v1/admin/matches")
async def create_match(payload: dict):
    """Create a new match"""
    new_match = {
        "id": f"match-{len(fake_data['matches']) + 1}",
        "title": payload.get("title", "New Match"),
        "starts_at": payload.get("start_time"),
        "status": "scheduled",
        "external_id": payload.get("external_id")
    }
    fake_data["matches"].append(new_match)
    return {"message": "Match created successfully!", "match": new_match}

@app.get("/api/v1/admin/matches/{match_id}/contests")
async def list_contests_for_match(match_id: str):
    """List contests for a specific match"""
    contests = fake_data["contests"].get(match_id, [])
    return contests

@app.post("/api/v1/admin/matches/{match_id}/contests")
async def create_contest_for_match(match_id: str, payload: dict):
    """Create a contest for a specific match"""
    new_contest = {
        "id": f"contest-{match_id}-{len(fake_data['contests'].get(match_id, [])) + 1}",
        "title": payload.get("title", f"Contest for {match_id}"),
        "entry_fee": payload.get("entry_fee", "10.0"),
        "max_players": payload.get("max_players", 50),
        "prize_structure": payload.get("prize_structure", {"1": 0.6, "2": 0.4}),
        "status": "open"
    }
    
    if match_id not in fake_data["contests"]:
        fake_data["contests"][match_id] = []
    fake_data["contests"][match_id].append(new_contest)
    
    return {"message": "Contest created successfully!", "contest": new_contest}

# Contest API
@app.get("/api/v1/admin/contests/{contest_id}")
async def get_contest(contest_id: str):
    """Get contest details"""
    # Find contest in all matches
    for match_contests in fake_data["contests"].values():
        for contest in match_contests:
            if contest["id"] == contest_id:
                return contest
    
    raise HTTPException(status_code=404, detail="Contest not found")

@app.get("/api/v1/admin/contests/{contest_id}/entries")
async def get_contest_entries(contest_id: str):
    """Get contest entries"""
    entries = fake_data["entries"].get(contest_id, [])
    return entries

@app.post("/api/v1/admin/contests/{contest_id}/select_winners")
async def select_winners(contest_id: str, payload: dict):
    """Select winners for a contest"""
    winners = payload.get("winners", [])
    
    # Update winner ranks
    for i, entry_id in enumerate(winners, 1):
        for entry in fake_data["entries"].get(contest_id, []):
            if entry["id"] == entry_id:
                entry["winner_rank"] = i
    
    return {
        "message": "Winners selected successfully!",
        "contest_id": contest_id,
        "winners": winners
    }

@app.post("/api/v1/admin/contests/{contest_id}/settle")
async def settle_contest(contest_id: str):
    """Settle a contest"""
    # Calculate payouts based on prize structure
    entries = fake_data["entries"].get(contest_id, [])
    contest = None
    
    # Find contest details
    for match_contests in fake_data["contests"].values():
        for c in match_contests:
            if c["id"] == contest_id:
                contest = c
                break
    
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    
    # Calculate payouts
    total_pool = sum(float(entry["amount_debited"]) for entry in entries)
    prize_structure = contest["prize_structure"]
    
    for entry in entries:
        if entry["winner_rank"]:
            rank = str(entry["winner_rank"])
            if rank in prize_structure:
                entry["payout_amount"] = str(total_pool * prize_structure[rank])
    
    return {
        "message": "Contest settled successfully!",
        "contest_id": contest_id,
        "status": "settled",
        "total_pool": str(total_pool)
    }

@app.get("/api/v1/admin/contests/{contest_id}/export")
async def export_contest_pl(contest_id: str):
    """Export contest P&L as CSV"""
    entries = fake_data["entries"].get(contest_id, [])
    
    csv_content = "entry_id,user,amount,winner_rank,payout\n"
    for entry in entries:
        csv_content += f"{entry['id']},{entry['username']},{entry['amount_debited']},{entry['winner_rank'] or ''},{entry['payout_amount'] or ''}\n"
    
    return JSONResponse(
        content={"csv": csv_content},
        headers={"Content-Disposition": f"attachment; filename=contest_{contest_id}_pl.csv"}
    )

# Deposits API (to fix the loading issue)
@app.get("/api/v1/admin/deposits")
async def list_deposits(status: str = "pending"):
    """List deposits"""
    deposits = [d for d in fake_data["deposits"] if d["status"] == status]
    return deposits

@app.post("/api/v1/admin/deposits/{tx_id}/approve")
async def approve_deposit(tx_id: str, payload: dict):
    """Approve deposit"""
    for deposit in fake_data["deposits"]:
        if deposit["id"] == tx_id:
            deposit["status"] = "approved"
            return {"message": "Deposit approved successfully!"}
    raise HTTPException(status_code=404, detail="Deposit not found")

@app.post("/api/v1/admin/deposits/{tx_id}/reject")
async def reject_deposit(tx_id: str, payload: dict):
    """Reject deposit"""
    for deposit in fake_data["deposits"]:
        if deposit["id"] == tx_id:
            deposit["status"] = "rejected"
            return {"message": "Deposit rejected successfully!"}
    raise HTTPException(status_code=404, detail="Deposit not found")

# Withdrawals API
@app.get("/api/v1/admin/withdrawals")
async def list_withdrawals():
    """List withdrawals"""
    return [
        {
            "id": "with-1",
            "telegram_id": "123456789",
            "username": "cricket_fan_1",
            "amount": "50.0",
            "status": "pending"
        }
    ]

# Audit API
@app.get("/api/v1/admin/audit")
async def get_audit():
    """Get audit logs"""
    return [
        {
            "id": "audit-1",
            "action": "create_match",
            "timestamp": "2024-01-15T10:00:00Z",
            "user": "admin",
            "details": "Created match: India vs Australia"
        }
    ]

if __name__ == "__main__":
    print("🚀 Starting FINAL WORKING admin server...")
    print("📱 Admin UI: http://localhost:8000/admin")
    print("🔧 API Test: http://localhost:8000/api/v1/admin/matches")
    print("📚 API Docs: http://localhost:8000/docs")
    print("🎯 This server has FAKE DATA and will work perfectly!")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
