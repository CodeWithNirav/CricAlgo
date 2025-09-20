"""
Audit log repository for admin action tracking
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.audit_log import AuditLog


async def create_audit_log(
    session: AsyncSession,
    admin_id: UUID,
    action: str,
    resource_type: str,
    resource_id: UUID,
    details: dict
) -> AuditLog:
    """
    Create an audit log entry.
    
    Args:
        session: Database session
        admin_id: Admin user ID who performed the action
        action: Action performed
        resource_type: Type of resource affected
        resource_id: ID of resource affected
        details: Additional details as JSON
    
    Returns:
        Created AuditLog instance
    """
    # Include resource info in details since the model doesn't have separate fields
    enhanced_details = {
        **details,
        "resource_type": resource_type,
        "resource_id": str(resource_id)
    }
    
    audit_log = AuditLog(
        admin_id=admin_id,
        action=action,
        details=enhanced_details
    )
    session.add(audit_log)
    await session.commit()
    await session.refresh(audit_log)
    return audit_log


async def get_audit_logs(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    action: Optional[str] = None,
    admin_id: Optional[UUID] = None
) -> List[AuditLog]:
    """
    Get audit logs.
    
    Args:
        session: Database session
        limit: Maximum number of logs to return
        offset: Number of logs to skip
        action: Filter by action type
        admin_id: Filter by admin ID
    
    Returns:
        List of AuditLog instances
    """
    query = select(AuditLog).order_by(desc(AuditLog.created_at))
    
    if action:
        query = query.where(AuditLog.action == action)
    
    if admin_id:
        query = query.where(AuditLog.admin_id == admin_id)
    
    query = query.limit(limit).offset(offset)
    
    result = await session.execute(query)
    return result.scalars().all()


async def get_audit_log_by_id(session: AsyncSession, log_id: UUID) -> Optional[AuditLog]:
    """
    Get audit log by ID.
    
    Args:
        session: Database session
        log_id: Audit log UUID
    
    Returns:
        AuditLog instance or None if not found
    """
    result = await session.execute(
        select(AuditLog).where(AuditLog.id == log_id)
    )
    return result.scalar_one_or_none()
