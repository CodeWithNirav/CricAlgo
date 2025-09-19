"""Add settlement fields to contests table

Revision ID: 0004_contest_settlement
Revises: 0003_deposit_processed_flag
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0004_contest_settlement'
down_revision = '0003_deposit_processed_flag'
branch_labels = None
depends_on = None


def upgrade():
    """Add settlement fields to contests table."""
    # Add settled_at column to contests table
    op.add_column('contests', sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True))
    
    # Add SETTLED status to contest_status enum
    op.execute("ALTER TYPE contest_status ADD VALUE 'settled'")
    
    # Add index for better query performance on settled_at
    op.create_index('idx_contests_settled_at', 'contests', ['settled_at'])


def downgrade():
    """Remove settlement fields from contests table."""
    # Drop index first
    op.drop_index('idx_contests_settled_at', table_name='contests')
    
    # Drop settled_at column
    op.drop_column('contests', 'settled_at')
    
    # Note: PostgreSQL doesn't support removing enum values easily
    # In production, you'd need to recreate the enum type
    # For now, we'll leave the 'settled' value in the enum
