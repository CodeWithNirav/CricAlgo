"""
User model matching the DDL schema
"""

from sqlalchemy import Column, String, BigInteger, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.sql import func
from app.db.base import Base
from app.models.enums import UserStatus
import uuid


class User(Base):
    """User model - matches users table in DDL"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BigInteger, nullable=False, unique=True)
    username = Column(String(48), nullable=False, unique=True)
    status = Column(ENUM(UserStatus, name='user_status'), nullable=False, default=UserStatus.ACTIVE)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, telegram_id={self.telegram_id})>"
