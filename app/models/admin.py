"""
Admin model matching the DDL schema
"""

from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base
import uuid


class Admin(Base):
    """Admin model - matches admins table in DDL"""
    __tablename__ = "admins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(64), nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    email = Column(String(255), nullable=True)
    totp_secret = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Admin(id={self.id}, username={self.username})>"
