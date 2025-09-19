"""
Contest model matching the DDL schema
"""

from sqlalchemy import Column, String, Numeric, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy import JSON
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
    prize_structure = Column(JSON, nullable=False, default={})
    commission_pct = Column(Numeric(5, 2), nullable=False, default=0)
    join_cutoff = Column(DateTime(timezone=True), nullable=True)
    status = Column(ENUM('scheduled', 'open', 'closed', 'cancelled', 'settled', name='contest_status'), nullable=False, default='open')
    settled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Contest(id={self.id}, code={self.code}, title={self.title}, entry_fee={self.entry_fee})>"
