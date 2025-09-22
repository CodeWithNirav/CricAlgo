"""
Match model matching the DDL schema
"""

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.sql import func
from app.db.base import Base
import uuid


class Match(Base):
    """Match model - matches matches table in DDL"""
    __tablename__ = "matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String(128), nullable=True)
    title = Column(String(255), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(ENUM('scheduled', 'open', 'closed', 'cancelled', 'settled', name='contest_status'), nullable=False, default='scheduled')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Match(id={self.id}, title={self.title}, start_time={self.start_time})>"

    def to_dict(self):
        """Convert match to dictionary for API responses"""
        return {
            "id": str(self.id),
            "external_id": self.external_id,
            "title": self.title,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "starts_at": self.start_time.isoformat() if self.start_time else None,  # alias for frontend
            "status": self.status if self.status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
