"""normalize contest & transaction enums

Revision ID: normalize_enums
Revises: 0005_normalize_contests_schema
Create Date: 2025-09-21 15:04:19.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'normalize_enums'
down_revision = '0005_normalize_contests_schema'
branch_labels = None
depends_on = None


def upgrade():
    # create new enum types
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'contest_status') THEN CREATE TYPE contest_status AS ENUM ('open','closed','settled','cancelled'); END IF; END$$;")
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'transaction_status') THEN CREATE TYPE transaction_status AS ENUM ('pending','confirmed','processed','rejected'); END IF; END$$;")
    
    # Attempt to alter columns to use the types (idempotent)
    try:
        op.execute("""ALTER TABLE contests ALTER COLUMN status TYPE contest_status USING status::text::contest_status;""")
    except Exception:
        pass
    try:
        op.execute("""ALTER TABLE transactions ALTER COLUMN status TYPE transaction_status USING status::text::transaction_status;""")
    except Exception:
        pass


def downgrade():
    # no-op downgrade (safe for now)
    pass
