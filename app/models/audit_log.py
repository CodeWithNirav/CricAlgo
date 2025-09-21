"""
Audit log model matching the DDL schema
"""

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.sql import func
from app.db.base import Base
import uuid


class AuditLog(Base):
    """Audit log model - matches audit_logs table in DDL"""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), nullable=True)
    actor = Column(String(128), nullable=True)  # For web_admin or other actors
    action = Column(String(128), nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<AuditLog(id={self.id}, admin_id={self.admin_id}, action={self.action})>"
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "admin_id": str(self.admin_id) if self.admin_id else None,
            "actor": self.actor,
            "action": self.action,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
