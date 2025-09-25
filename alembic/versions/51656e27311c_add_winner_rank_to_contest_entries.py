"""add_winner_rank_to_contest_entries

Revision ID: 51656e27311c
Revises: a199f1aba872
Create Date: 2025-09-24 13:43:14.967144

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '51656e27311c'
down_revision = 'a199f1aba872'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add winner_rank column to entries table
    op.add_column('entries', sa.Column('winner_rank', sa.Integer(), nullable=True))
    
    # Add index for better query performance
    op.create_index('idx_entries_winner_rank', 'entries', ['winner_rank'])


def downgrade() -> None:
    # Remove index first
    op.drop_index('idx_entries_winner_rank', 'entries')
    
    # Remove winner_rank column
    op.drop_column('entries', 'winner_rank')
