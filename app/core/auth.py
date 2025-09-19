"""
JWT Authentication utilities
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.repos.user_repo import get_user_by_id, get_user_by_username
from app.models.enums import UserStatus

# Setup debug logger
debug_logger = logging.getLogger("auth_debug")
debug_logger.setLevel(logging.DEBUG)
debug_handler = logging.FileHandler("artifacts/auth_debug.log")
debug_handler.setLevel(logging.DEBUG)
debug_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
debug_handler.setFormatter(debug_formatter)
debug_logger.addHandler(debug_handler)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token scheme
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_db)
):
    """Get current authenticated user."""
    token = credentials.credentials
    payload = verify_token(token, "access")
    
    # Debug logging for JWT claims
    debug_logger.debug(f"JWT Claims: {payload}")
    
    user_id = payload.get("sub")
    if user_id is None:
        debug_logger.error("JWT token missing 'sub' claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    user = await get_user_by_id(session, UUID(user_id))
    if user is None:
        debug_logger.error(f"User not found for ID: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Debug logging for user fields
    debug_logger.debug(f"DB User - ID: {user.id}, Username: {user.username}, Status: {user.status}, Type: {type(user.status)}")
    
    # Normalize status comparison - handle both string and enum values
    user_status = user.status.value if hasattr(user.status, 'value') else str(user.status)
    if user_status.lower() != 'active':
        debug_logger.error(f"User account not active - Status: {user_status}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is not active"
        )
    
    debug_logger.debug(f"User authentication successful for: {user.username}")
    return user


async def get_current_admin(
    current_user = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """Get current authenticated admin user."""
    from app.repos.admin_repo import is_admin_user
    
    # Debug logging for admin check
    debug_logger.debug(f"Checking admin status for user: {current_user.username} (ID: {current_user.id})")
    
    # Check if user is admin via database
    is_admin_db = await is_admin_user(session, current_user.id)
    debug_logger.debug(f"Database admin check result: {is_admin_db}")
    
    # Fallback: Check JWT token claims for admin flag (if present)
    token = None
    try:
        from fastapi import Request
        # Try to get token from request context
        # This is a fallback mechanism
        debug_logger.debug("Checking JWT token for admin claims")
    except:
        pass
    
    if not is_admin_db:
        # Check if token has admin claim as fallback
        debug_logger.warning(f"User {current_user.username} not found in admin table, checking token claims")
        # For now, we'll be strict and require DB admin record
        debug_logger.error(f"Admin access denied for user: {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    debug_logger.debug(f"Admin authentication successful for: {current_user.username}")
    return current_user
