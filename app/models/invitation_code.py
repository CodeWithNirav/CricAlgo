"""
Invitation code model matching the DDL schema
"""

from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base


class InvitationCode(Base):
    """Invitation code model - matches invitation_codes table in DDL"""
    __tablename__ = "invitation_codes"

    code = Column(String(64), primary_key=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("admins.id"), nullable=True)
    max_uses = Column(Integer, nullable=True)  # NULL = unlimited
    uses = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    admin = relationship("Admin", back_populates="invitation_codes")

    def __repr__(self):
        return f"<InvitationCode(code={self.code}, uses={self.uses}/{self.max_uses or '∞'})>"
    
    def to_dict(self):
        return {
            "code": self.code,
            "created_by": str(self.created_by) if self.created_by else None,
            "max_uses": self.max_uses,
            "uses": self.uses,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
