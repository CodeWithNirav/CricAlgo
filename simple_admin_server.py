#!/usr/bin/env python3
"""
Simple admin server for testing
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

app = FastAPI()

# Serve static files
app.mount("/assets", StaticFiles(directory="app/static/admin/assets"), name="assets")

@app.get("/admin")
async def admin_ui():
    """Serve admin UI"""
    return FileResponse("app/static/admin/index.html")

@app.get("/api/v1/admin/matches")
async def list_matches():
    """List matches - working version"""
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

@app.post("/api/v1/admin/matches")
async def create_match(payload: dict):
    """Create match - working version"""
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
    """List contests for match - working version"""
    return [
        {
            "id": f"contest-{match_id}-1",
            "title": f"Contest for {match_id}",
            "entry_fee": "5.0",
            "max_players": 10,
            "prize_structure": {"1": 0.6, "2": 0.4}
        }
    ]

@app.get("/api/v1/admin/contests/{contest_id}")
async def get_contest(contest_id: str):
    """Get contest details - working version"""
    return {
        "id": contest_id,
        "title": f"Contest {contest_id}",
        "entry_fee": "5.0",
        "max_players": 10,
        "prize_structure": {"1": 0.6, "2": 0.4},
        "status": "open"
    }

@app.get("/api/v1/admin/contests/{contest_id}/entries")
async def get_contest_entries(contest_id: str):
    """Get contest entries - working version"""
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

@app.post("/api/v1/admin/contests/{contest_id}/select_winners")
async def select_winners(contest_id: str, payload: dict):
    """Select winners - working version"""
    return {
        "message": "Winners selected successfully!",
        "contest_id": contest_id,
        "winners": payload.get("winners", [])
    }

@app.post("/api/v1/admin/contests/{contest_id}/settle")
async def settle_contest(contest_id: str):
    """Settle contest - working version"""
    return {
        "message": "Contest settled successfully!",
        "contest_id": contest_id,
        "status": "settled"
    }

if __name__ == "__main__":
    print("🚀 Starting simple admin server...")
    print("📱 Admin UI: http://localhost:8000/admin")
    print("🔧 API Docs: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
