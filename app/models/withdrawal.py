"""
Withdrawal model for testing
"""

from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.sql import func
from app.db.base import Base

class Withdrawal(Base):
    """Withdrawal model - simplified for testing"""
    __tablename__ = "withdrawals"

    id = Column(String(255), primary_key=True)
    telegram_id = Column(String(255), nullable=False)
    amount = Column(String(50), nullable=False)
    address = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Withdrawal(id={self.id}, telegram_id={self.telegram_id}, amount={self.amount}, status={self.status})>"