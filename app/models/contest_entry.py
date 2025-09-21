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

    def to_dict(self):
        """Convert contest entry to dictionary for API responses"""
        return {
            "id": str(self.id),
            "contest_id": str(self.contest_id),
            "user_id": str(self.user_id),
            "entry_code": self.entry_code,
            "amount_debited": str(self.amount_debited),
            "payout_tx_id": str(self.payout_tx_id) if self.payout_tx_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "telegram_id": getattr(self, 'telegram_id', None),  # Will be joined from user
            "username": getattr(self, 'username', None),  # Will be joined from user
            "winner_rank": getattr(self, 'winner_rank', None),  # Will be added by settlement
            "payout_amount": getattr(self, 'payout_amount', None)  # Will be added by settlement
        }
