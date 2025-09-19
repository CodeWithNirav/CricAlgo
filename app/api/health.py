"""
Health check endpoints
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint
    Returns HTTP 200 with status ok
    """
    return {"status": "ok"}
