#!/usr/bin/env python3
"""
Simple test server to verify FastAPI is working
"""
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World", "status": "working"}

@app.get("/test")
def read_test():
    return {"Test": "Success", "message": "Server is working"}

@app.get("/api/v1/admin/matches")
def get_matches():
    return [
        {"id": "1", "title": "Test Match 1", "status": "scheduled"},
        {"id": "2", "title": "Test Match 2", "status": "scheduled"}
    ]

@app.get("/api/v1/admin/deposits")
def get_deposits():
    return [
        {"id": "dep1", "username": "user1", "amount": "100.0", "status": "pending"},
        {"id": "dep2", "username": "user2", "amount": "200.0", "status": "pending"}
    ]

if __name__ == "__main__":
    print("Starting simple test server on port 8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
