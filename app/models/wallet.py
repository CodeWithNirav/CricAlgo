"""
Wallet model matching the DDL schema
"""

from sqlalchemy import Column, Numeric, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base
import uuid


class Wallet(Base):
    """Wallet model - matches wallets table in DDL"""
    __tablename__ = "wallets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    deposit_balance = Column(Numeric(30, 8), nullable=False, default=0)
    winning_balance = Column(Numeric(30, 8), nullable=False, default=0)
    bonus_balance = Column(Numeric(30, 8), nullable=False, default=0)
    held_balance = Column(Numeric(30, 8), nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    # Constraints
    __table_args__ = (
        CheckConstraint('deposit_balance >= 0', name='chk_deposit_nonneg'),
        CheckConstraint('winning_balance >= 0', name='chk_winning_nonneg'),
        CheckConstraint('bonus_balance >= 0', name='chk_bonus_nonneg'),
        CheckConstraint('held_balance >= 0', name='chk_held_nonneg'),
    )

    def __repr__(self):
        return f"<Wallet(id={self.id}, user_id={self.user_id}, deposit={self.deposit_balance}, winning={self.winning_balance}, bonus={self.bonus_balance})>"
