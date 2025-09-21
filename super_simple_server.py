from fastapi import FastAPI
from fastapi.responses import FileResponse
import uvicorn

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Server is running!"}

@app.get("/admin")
def admin():
    return FileResponse("app/static/admin/index.html")

@app.get("/assets/{filename}")
def assets(filename: str):
    return FileResponse(f"app/static/admin/assets/{filename}")

@app.get("/api/v1/admin/matches")
def matches():
    return [
        {"id": "1", "title": "India vs Australia", "starts_at": "2024-01-15T10:00:00Z", "status": "scheduled"},
        {"id": "2", "title": "England vs Pakistan", "starts_at": "2024-01-16T14:00:00Z", "status": "scheduled"}
    ]

@app.post("/api/v1/admin/matches")
def create_match(payload: dict):
    return {"message": "Match created!", "match": {"id": "3", "title": payload.get("title", "New Match")}}

@app.get("/api/v1/admin/matches/{match_id}/contests")
def contests(match_id: str):
    return [{"id": f"contest-{match_id}", "title": f"Contest for {match_id}", "entry_fee": "10.0"}]

@app.get("/api/v1/admin/contests/{contest_id}")
def contest(contest_id: str):
    return {"id": contest_id, "title": f"Contest {contest_id}", "entry_fee": "10.0", "status": "open"}

@app.get("/api/v1/admin/contests/{contest_id}/entries")
def entries(contest_id: str):
    return [
        {"id": "entry1", "telegram_id": "123456789", "username": "user1", "amount_debited": "10.0"},
        {"id": "entry2", "telegram_id": "987654321", "username": "user2", "amount_debited": "10.0"}
    ]

@app.post("/api/v1/admin/contests/{contest_id}/select_winners")
def select_winners(contest_id: str, payload: dict):
    return {"message": "Winners selected!", "winners": payload.get("winners", [])}

@app.post("/api/v1/admin/contests/{contest_id}/settle")
def settle(contest_id: str):
    return {"message": "Contest settled!", "status": "settled"}

@app.get("/api/v1/admin/deposits")
def deposits():
    return [
        {"id": "dep1", "telegram_id": "123456789", "username": "user1", "amount": "100.0", "tx_hash": "0x123", "status": "pending"},
        {"id": "dep2", "telegram_id": "987654321", "username": "user2", "amount": "200.0", "tx_hash": "0x456", "status": "pending"}
    ]

@app.post("/api/v1/admin/deposits/{tx_id}/approve")
def approve_deposit(tx_id: str, payload: dict):
    return {"message": "Deposit approved!"}

@app.post("/api/v1/admin/deposits/{tx_id}/reject")
def reject_deposit(tx_id: str, payload: dict):
    return {"message": "Deposit rejected!"}

@app.get("/api/v1/admin/withdrawals")
def withdrawals():
    return [{"id": "with1", "telegram_id": "123456789", "username": "user1", "amount": "50.0", "status": "pending"}]

@app.get("/api/v1/admin/audit")
def audit():
    return [{"id": "audit1", "action": "create_match", "timestamp": "2024-01-15T10:00:00Z", "user": "admin"}]

if __name__ == "__main__":
    print("🚀 Starting SUPER SIMPLE server...")
    print("📱 Go to: http://localhost:8000/admin")
    uvicorn.run(app, host="0.0.0.0", port=8000)
