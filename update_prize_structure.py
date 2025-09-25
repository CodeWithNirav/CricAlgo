#!/usr/bin/env python3
"""
Update prize structure for all contests to single winner (100%)
"""

import asyncio
import asyncpg
from app.core.config import settings

async def update_prize_structure():
    """Update all contests to use single winner prize structure"""
    try:
        # Connect to database
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="password",
            database="cricalgo"
        )
        
        # Update prize structure to single winner
        await conn.execute("""
            UPDATE contests 
            SET prize_structure = '[{"pos": 1, "pct": 100}]'::json
        """)
        
        # Verify the update
        rows = await conn.fetch("SELECT id, title, prize_structure FROM contests")
        print("Updated contests:")
        for row in rows:
            print(f"ID: {row['id']}, Title: {row['title']}, Prize Structure: {row['prize_structure']}")
        
        await conn.close()
        print("✅ Prize structure updated successfully!")
        
    except Exception as e:
        print(f"❌ Error updating prize structure: {e}")

if __name__ == "__main__":
    asyncio.run(update_prize_structure())
