"""
Transaction model matching the DDL schema
"""

from sqlalchemy import Column, String, Numeric, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.sql import func
from app.db.base import Base
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
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Transaction(id={self.id}, user_id={self.user_id}, type={self.tx_type}, amount={self.amount})>"
