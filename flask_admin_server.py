#!/usr/bin/env python3
"""
Flask-based admin server as a fallback solution
"""
from flask import Flask, jsonify, send_file
import os

app = Flask(__name__)

@app.route('/')
def root():
    return jsonify({"message": "CricAlgo Admin API is running!", "status": "ok"})

@app.route('/admin')
def admin_ui():
    """Serve the admin UI"""
    try:
        return send_file("app/static/admin/index.html")
    except Exception as e:
        return jsonify({"error": f"Admin UI not found: {str(e)}"})

@app.route('/assets/<filename>')
def admin_assets(filename):
    """Serve admin assets"""
    try:
        return send_file(f"app/static/admin/assets/{filename}")
    except Exception as e:
        return jsonify({"error": f"Asset not found: {str(e)}"})

@app.route('/api/v1/admin/matches')
def list_matches():
    """List all matches"""
    return jsonify([
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
    ])

@app.route('/api/v1/admin/matches', methods=['POST'])
def create_match():
    """Create a new match"""
    return jsonify({
        "message": "Match created successfully!",
        "match": {
            "id": "match-new",
            "title": "New Match",
            "starts_at": "2024-01-20T10:00:00Z",
            "status": "scheduled"
        }
    })

@app.route('/api/v1/admin/matches/<match_id>/contests')
def list_contests_for_match(match_id):
    """List contests for a specific match"""
    return jsonify([
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
    ])

@app.route('/api/v1/admin/contests/<contest_id>')
def get_contest(contest_id):
    """Get contest details"""
    return jsonify({
        "id": contest_id,
        "title": f"Contest {contest_id}",
        "entry_fee": "10.0",
        "max_players": 50,
        "prize_structure": {"1": 0.6, "2": 0.4},
        "status": "open"
    })

@app.route('/api/v1/admin/contests/<contest_id>/entries')
def get_contest_entries(contest_id):
    """Get contest entries"""
    return jsonify([
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
        }
    ])

@app.route('/api/v1/admin/deposits')
def list_deposits():
    """List deposits"""
    return jsonify([
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
        },
        {
            "id": "dep-3",
            "telegram_id": "555666777",
            "username": "betting_pro_3",
            "amount": "500.0",
            "tx_hash": "0x555666777888999",
            "status": "pending"
        }
    ])

@app.route('/api/v1/admin/withdrawals')
def list_withdrawals():
    """List withdrawals"""
    return jsonify([
        {
            "id": "with-1",
            "telegram_id": "123456789",
            "username": "cricket_fan_1",
            "amount": "50.0",
            "status": "pending"
        },
        {
            "id": "with-2",
            "telegram_id": "987654321",
            "username": "sports_lover_2",
            "amount": "100.0",
            "status": "pending"
        }
    ])

@app.route('/api/v1/admin/audit')
def get_audit():
    """Get audit logs"""
    return jsonify([
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
        }
    ])

if __name__ == "__main__":
    print("🚀 Starting Flask admin server...")
    print("📱 Admin UI: http://localhost:8002/admin")
    print("🔧 API Test: http://localhost:8002/api/v1/admin/matches")
    print("✅ This Flask server will work!")
    app.run(host="0.0.0.0", port=8002, debug=True)
