"""Add processed_at field to transactions table

Revision ID: 0003_deposit_processed_flag
Revises: 0001_initial
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0003_deposit_processed_flag'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    """Add processed_at field to transactions table for deposit processing idempotency."""
    # Add processed_at column to transactions table
    op.add_column('transactions', sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True))
    
    # Add index for better query performance on processed_at
    op.create_index('idx_transactions_processed_at', 'transactions', ['processed_at'])


def downgrade():
    """Remove processed_at field from transactions table."""
    # Drop index first
    op.drop_index('idx_transactions_processed_at', table_name='transactions')
    
    # Drop processed_at column
    op.drop_column('transactions', 'processed_at')
