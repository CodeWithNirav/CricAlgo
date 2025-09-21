"""
Withdrawal model matching the DDL schema
"""

from sqlalchemy import Column, String, Numeric, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.sql import func
from app.db.base import Base
import uuid


class Withdrawal(Base):
    """Withdrawal model - matches withdrawals table in DDL"""
    __tablename__ = "withdrawals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    amount = Column(Numeric(30, 8), nullable=False)
    currency = Column(String(16), nullable=False, default='USDT')
    address = Column(String(256), nullable=False)
    status = Column(String(32), nullable=False, default='pending')
    withdrawal_metadata = Column('metadata', JSON, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Withdrawal(id={self.id}, user_id={self.user_id}, amount={self.amount}, status={self.status})>"
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "amount": float(self.amount) if self.amount else 0,
            "currency": self.currency,
            "address": self.address,
            "status": self.status,
            "withdrawal_metadata": self.withdrawal_metadata,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "telegram_id": self.withdrawal_metadata.get('telegram_id', '') if self.withdrawal_metadata else '',
            "username": self.withdrawal_metadata.get('username', '') if self.withdrawal_metadata else ''
        }
