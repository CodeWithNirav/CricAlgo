"""
Database enums matching the DDL schema
"""

import enum


class UserStatus(enum.Enum):
    """User status enum"""
    ACTIVE = "active"
    FROZEN = "frozen"
    DISABLED = "disabled"


class DepositStatus(enum.Enum):
    """Deposit status enum"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class WithdrawStatus(enum.Enum):
    """Withdraw status enum"""
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ContestStatus(enum.Enum):
    """Contest status enum"""
    SCHEDULED = "scheduled"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
