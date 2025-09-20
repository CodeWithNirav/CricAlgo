"""
Test contest seeding endpoints for E2E testing
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_admin
from app.db.session import get_db
from app.repos.contest_repo import create_contest
from app.models.enums import ContestStatus

router = APIRouter()


@router.post("/seed-test-contest")
async def seed_test_contest(
    current_admin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Seed a test contest if none exist.
    Only available when ENABLE_TEST_CONTEST_SEED=true.
    """
    # Check if contest seeding is enabled
    if os.getenv("ENABLE_TEST_CONTEST_SEED", "false").lower() != "true":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test contest seeding is disabled"
        )
    
    try:
        # Check if any contests exist
        from app.repos.contest_repo import get_contests
        existing_contests = await get_contests(session, limit=1)
        
        if existing_contests:
            return {
                "message": "Contests already exist, skipping seed",
                "contest_count": len(existing_contests)
            }
        
        # Create a test contest
        from decimal import Decimal
        
        contest = await create_contest(
            session=session,
            match_id="test_match_e2e_001",
            title="E2E Test Cricket Contest",
            entry_fee=Decimal("10.0"),
            max_participants=10,
            prize_structure=[
                {"position": 1, "percentage": 50.0},
                {"position": 2, "percentage": 30.0},
                {"position": 3, "percentage": 20.0}
            ],
            created_by=current_admin.id
        )
        
        return {
            "message": "Test contest created successfully",
            "contest_id": str(contest.id),
            "title": contest.title,
            "entry_fee": contest.entry_fee,
            "max_participants": contest.max_participants
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed test contest: {str(e)}"
        )
