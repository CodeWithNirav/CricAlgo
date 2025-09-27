"""create_match_status_enum

Revision ID: bc2fb10cef1e
Revises: 51656e27311c
Create Date: 2025-09-27 05:33:13.352622

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bc2fb10cef1e'
down_revision = '51656e27311c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create match_status enum
    op.execute("CREATE TYPE match_status AS ENUM ('scheduled', 'live', 'finished')")
    
    # Add new status column with match_status enum
    op.add_column('matches', sa.Column('new_status', sa.Enum('scheduled', 'live', 'finished', name='match_status'), nullable=True))
    
    # Copy data from old status column, mapping contest_status to match_status
    op.execute("""
        UPDATE matches 
        SET new_status = CASE 
            WHEN status = 'scheduled' THEN 'scheduled'::match_status
            WHEN status = 'open' THEN 'scheduled'::match_status
            WHEN status = 'closed' THEN 'finished'::match_status
            WHEN status = 'cancelled' THEN 'finished'::match_status
            ELSE 'scheduled'::match_status
        END
    """)
    
    # Drop old status column
    op.drop_column('matches', 'status')
    
    # Rename new_status to status
    op.alter_column('matches', 'new_status', new_column_name='status', nullable=False)


def downgrade() -> None:
    # Create contest_status enum if it doesn't exist
    op.execute("CREATE TYPE contest_status AS ENUM ('scheduled', 'open', 'closed', 'cancelled', 'settled')")
    
    # Add old status column
    op.add_column('matches', sa.Column('old_status', sa.Enum('scheduled', 'open', 'closed', 'cancelled', 'settled', name='contest_status'), nullable=True))
    
    # Copy data back
    op.execute("""
        UPDATE matches 
        SET old_status = CASE 
            WHEN status = 'scheduled' THEN 'scheduled'::contest_status
            WHEN status = 'live' THEN 'open'::contest_status
            WHEN status = 'finished' THEN 'closed'::contest_status
            ELSE 'scheduled'::contest_status
        END
    """)
    
    # Drop new status column
    op.drop_column('matches', 'status')
    
    # Rename old_status to status
    op.alter_column('matches', 'old_status', new_column_name='status', nullable=False)
    
    # Drop match_status enum
    op.execute("DROP TYPE match_status")
