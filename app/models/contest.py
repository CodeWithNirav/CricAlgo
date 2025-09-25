"""
Contest model matching the DDL schema
"""

from sqlalchemy import Column, String, Numeric, DateTime, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base
import sqlalchemy as sa
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
    prize_structure = Column(JSON, nullable=False, default={})
    commission_pct = Column(Numeric(5, 2), nullable=False, default=0)
    join_cutoff = Column(DateTime(timezone=True), nullable=True)
    status = Column(sa.Enum('open','closed','settled','cancelled', name='contest_status', create_type=False), nullable=False, default='open')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Contest(id={self.id}, code={self.code}, title={self.title}, entry_fee={self.entry_fee})>"

    def to_dict(self):
        """Convert contest to dictionary for API responses"""
        # Convert prize structure from list format to object format for frontend
        prize_structure_obj = {}
        if self.prize_structure and isinstance(self.prize_structure, list):
            for item in self.prize_structure:
                if isinstance(item, dict) and 'pos' in item and 'pct' in item:
                    prize_structure_obj[str(item['pos'])] = item['pct'] / 100.0
        elif self.prize_structure and isinstance(self.prize_structure, dict):
            prize_structure_obj = self.prize_structure
        
        return {
            "id": str(self.id),
            "match_id": str(self.match_id),
            "code": self.code,
            "title": self.title,
            "entry_fee": str(self.entry_fee),
            "currency": self.currency,
            "max_players": self.max_players,
            "prize_structure": prize_structure_obj,
            "commission_pct": float(self.commission_pct) if self.commission_pct else 0,
            "join_cutoff": self.join_cutoff.isoformat() if self.join_cutoff else None,
            "status": self.status if self.status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
