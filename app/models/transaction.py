"""
Transaction model matching the DDL schema
"""

from sqlalchemy import Column, String, Numeric, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.sql import func
from app.db.base import Base
import sqlalchemy as sa
import uuid


class Transaction(Base):
    """Transaction model - matches transactions table in DDL"""
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    tx_type = Column(String(64), nullable=False)
    amount = Column(Numeric(30, 8), nullable=False)
    currency = Column(String(16), nullable=False, default='USDT')
    related_entity = Column(String(64), nullable=True)
    related_id = Column(UUID(as_uuid=True), nullable=True)
    tx_metadata = Column('metadata', JSON, nullable=True)
    # Note: status column doesn't exist in actual database schema
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Transaction(id={self.id}, user_id={self.user_id}, type={self.tx_type}, amount={self.amount})>"
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "tx_type": self.tx_type,
            "amount": float(self.amount) if self.amount else 0,
            "currency": self.currency,
            "related_entity": self.related_entity,
            "related_id": str(self.related_id) if self.related_id else None,
            "tx_metadata": self.tx_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "status": "pending",  # Default status since no status column exists
            "tx_hash": self.tx_metadata.get('tx_hash', '') if self.tx_metadata else '',
            "telegram_id": self.tx_metadata.get('telegram_id', '') if self.tx_metadata else '',
            "username": self.tx_metadata.get('username', '') if self.tx_metadata else ''
        }