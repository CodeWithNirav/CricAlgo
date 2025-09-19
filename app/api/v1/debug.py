"""
Debug API endpoints for development and testing
"""

import os
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_admin, verify_token
from app.db.session import get_db
from app.repos.user_repo import get_user_by_id
from app.repos.admin_repo import is_admin_user

router = APIRouter()


@router.get("/token-info")
async def get_token_info(
    current_admin = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Debug endpoint to introspect token claims and user info.
    Only available when ENABLE_DEBUG_ENDPOINT=true
    """
    # Check if debug endpoints are enabled
    if not os.getenv("ENABLE_DEBUG_ENDPOINT", "false").lower() == "true":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug endpoints not enabled"
        )
    
    # Get token from request (this is a simplified version)
    # In a real implementation, you'd extract the token from the request headers
    
    # Get user info
    user_info = {
        "id": str(current_admin.id),
        "username": current_admin.username,
        "status": current_admin.status.value if hasattr(current_admin.status, 'value') else str(current_admin.status),
        "telegram_id": current_admin.telegram_id,
        "created_at": current_admin.created_at.isoformat() if current_admin.created_at else None
    }
    
    # Check admin status
    is_admin = await is_admin_user(session, current_admin.id)
    
    return {
        "user_info": user_info,
        "is_admin": is_admin,
        "debug_info": {
            "endpoint_enabled": True,
            "admin_authenticated": True
        }
    }
