"""normalize contests schema

Revision ID: 0005_normalize_contests_schema
Revises: 0004_contest_settlement
Create Date: 2025-09-20 17:11:37.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0005_normalize_contests_schema'
down_revision = '0004_contest_settlement'
branch_labels = None
depends_on = None

def upgrade():
    # Add 'settled' to contest_status enum
    with op.get_context().autocommit_block():
        conn = op.get_bind()
        # Add 'settled' value to contest_status enum
        conn.execute("ALTER TYPE contest_status ADD VALUE 'settled'")
    
    # Add settled_at column to contests if missing
    with op.get_context().autocommit_block():
        conn = op.get_bind()
        conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='contests' AND column_name='settled_at'
            ) THEN
                ALTER TABLE contests ADD COLUMN settled_at TIMESTAMP WITH TIME ZONE;
            END IF;
        END$$;
        """)
    
    # Add updated_at column to contests if missing
    with op.get_context().autocommit_block():
        conn = op.get_bind()
        conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='contests' AND column_name='updated_at'
            ) THEN
                ALTER TABLE contests ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT now();
            END IF;
        END$$;
        """)
    
    # Rename entries table to contest_entries
    with op.get_context().autocommit_block():
        conn = op.get_bind()
        conn.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name='entries' AND table_schema='public'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name='contest_entries' AND table_schema='public'
            ) THEN
                ALTER TABLE entries RENAME TO contest_entries;
            END IF;
        END$$;
        """)
    
    # Add payout_tx_id column to contest_entries if missing
    with op.get_context().autocommit_block():
        conn = op.get_bind()
        conn.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='contest_entries' AND column_name='payout_tx_id'
            ) THEN
                ALTER TABLE contest_entries ADD COLUMN payout_tx_id UUID;
            END IF;
        END$$;
        """)

def downgrade():
    with op.get_context().autocommit_block():
        conn = op.get_bind()
        
        # Rename contest_entries back to entries
        conn.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name='contest_entries' AND table_schema='public'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name='entries' AND table_schema='public'
            ) THEN
                ALTER TABLE contest_entries RENAME TO entries;
            END IF;
        END$$;
        """)
        
        # Note: We don't remove 'settled' from enum or drop columns to avoid data loss
        # The enum value and columns will remain for safety
