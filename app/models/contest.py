"""
Contest model matching the DDL schema
"""

from sqlalchemy import Column, String, Numeric, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID, ENUM, JSONB
from sqlalchemy.sql import func
from app.db.base import Base
from app.models.enums import ContestStatus
import uuid


class Contest(Base):
    """Contest model - matches contests table in DDL"""
    __tablename__ = "contests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id = Column(UUID(as_uuid=True), nullable=False)
    code = Column(String(64), nullable=False, unique=True)
    title = Column(String(255), nullable=True)
    entry_fee = Column(Numeric(30, 8), nullable=False, default=0)
    currency = Column(String(16), nullable=False, default='USDT')
    max_players = Column(Integer, nullable=True)
    prize_structure = Column(JSONB, nullable=False, default={})
    commission_pct = Column(Numeric(5, 2), nullable=False, default=0)
    join_cutoff = Column(DateTime(timezone=True), nullable=True)
    status = Column(ENUM(ContestStatus, name='contest_status'), nullable=False, default=ContestStatus.OPEN)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Contest(id={self.id}, code={self.code}, title={self.title}, entry_fee={self.entry_fee})>"

    def to_dict(self):
        """Convert contest to dictionary for API responses"""
        return {
            "id": str(self.id),
            "match_id": str(self.match_id),
            "code": self.code,
            "title": self.title,
            "entry_fee": str(self.entry_fee),
            "currency": self.currency,
            "max_players": self.max_players,
            "prize_structure": self.prize_structure,
            "commission_pct": float(self.commission_pct) if self.commission_pct else 0,
            "join_cutoff": self.join_cutoff.isoformat() if self.join_cutoff else None,
            "status": self.status.value if self.status else None,
            "settled_at": self.settled_at.isoformat() if self.settled_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
