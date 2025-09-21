#!/usr/bin/env python3
"""
Seed script to create sample match and contest data for testing
"""
import os
import asyncio
from datetime import datetime, timezone
from app.db.session import async_session
from app.models.match import Match
from app.models.contest import Contest

async def run():
    """Create sample match and contest data"""
    async with async_session() as db:
        # Create a sample match
        m = Match(
            title="E2E Sample Match", 
            start_time=datetime.now(timezone.utc),
            external_id="SAMPLE_MATCH_001"
        )
        db.add(m)
        await db.flush()  # Get the ID without committing
        
        # Create a sample contest for this match
        c = Contest(
            match_id=m.id,
            title="Sample Contest",
            entry_fee="5.0",
            max_players=10,
            prize_structure={"1": 0.6, "2": 0.4}
        )
        db.add(c)
        
        await db.commit()
        print(f"Seeded match {m.id} with contest {c.id}")

if __name__ == "__main__":
    asyncio.run(run())
