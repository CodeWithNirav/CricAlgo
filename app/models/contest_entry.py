"""
Contest entry model matching the DDL schema
"""

from sqlalchemy import Column, String, Numeric, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base
import uuid


class ContestEntry(Base):
    """Contest entry model - matches contest_entries table in DDL"""
    __tablename__ = "contest_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contest_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    entry_code = Column(String(64), nullable=False, unique=True)
    amount_debited = Column(Numeric(30, 8), nullable=False)
    payout_tx_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Constraints
    __table_args__ = (
        UniqueConstraint('contest_id', 'user_id', name='uq_contest_user'),
    )

    def __repr__(self):
        return f"<ContestEntry(id={self.id}, contest_id={self.contest_id}, user_id={self.user_id}, amount={self.amount_debited})>"
