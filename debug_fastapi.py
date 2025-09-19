#!/usr/bin/env python3
import asyncio
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db

app = FastAPI()

@app.get("/test")
async def test_endpoint(session: AsyncSession = Depends(get_db)):
    print('Session type:', type(session))
    print('Session has execute:', hasattr(session, 'execute'))
    return {"session_type": str(type(session))}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
