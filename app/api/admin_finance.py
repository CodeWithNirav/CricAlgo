from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import csv, io

router = APIRouter(prefix="/api/v1/admin", tags=["admin_finance"])

# Matches endpoints are handled by admin_matches_contests.py

# Authentication removed for simplified testing

@router.get("/deposits")
async def list_deposits(status: str = "pending"):
    """List deposits - simplified version with fake data"""
    fake_deposits = [
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
    
    if status == "pending":
        return [d for d in fake_deposits if d["status"] == "pending"]
    else:
        return [d for d in fake_deposits if d["status"] == status]

@router.post("/deposits/{tx_id}/approve")
async def approve_deposit(tx_id: str, payload: dict = None):
    """Approve deposit - simplified version"""
    return {"message": f"Deposit {tx_id} approved successfully!", "ok": True}

@router.post("/deposits/{tx_id}/reject")
async def reject_deposit(tx_id: str, payload: dict):
    """Reject deposit - simplified version"""
    note = payload.get("note", "rejected")
    return {"message": f"Deposit {tx_id} rejected successfully! Note: {note}", "ok": True}

@router.get("/withdrawals")
async def list_withdrawals(status: str = "pending"):
    """List withdrawals - simplified version with fake data"""
    fake_withdrawals = [
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
    return [w for w in fake_withdrawals if w["status"] == status]

@router.post("/withdrawals/{w_id}/approve")
async def approve_withdrawal(w_id: str):
    """Approve withdrawal - simplified version"""
    return {"message": f"Withdrawal {w_id} approved successfully!", "ok": True}

@router.post("/withdrawals/{w_id}/reject")
async def reject_withdrawal(w_id: str, payload: dict):
    """Reject withdrawal - simplified version"""
    note = payload.get("note", "rejected")
    return {"message": f"Withdrawal {w_id} rejected successfully! Note: {note}", "ok": True}

@router.get("/audit")
async def get_audit(limit: int = 200):
    """Get audit logs - simplified version with fake data"""
    fake_audit_logs = [
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
    return fake_audit_logs[:limit]

@router.get("/audit/export")
async def export_audit_csv():
    """Export audit CSV - simplified version"""
    fake_audit_logs = [
        {"id": "audit-1", "created_at": "2024-01-15T10:00:00Z", "actor": "admin", "action": "create_match", "details": "Created match: India vs Australia"},
        {"id": "audit-2", "created_at": "2024-01-15T11:00:00Z", "actor": "admin", "action": "approve_deposit", "details": "Approved deposit: 100 USDT"},
        {"id": "audit-3", "created_at": "2024-01-15T12:00:00Z", "actor": "admin", "action": "settle_contest", "details": "Settled contest: High Roller Contest"}
    ]
    
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id","created_at","actor","action","details"])
    for r in fake_audit_logs:
        writer.writerow([r["id"], r["created_at"], r["actor"], r["action"], r["details"]])
    buf.seek(0)
    return StreamingResponse(io.BytesIO(buf.getvalue().encode()), media_type="text/csv", headers={"Content-Disposition":"attachment; filename=audit.csv"})
