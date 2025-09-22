"""fix_contest_status_enum

Revision ID: a199f1aba872
Revises: normalize_enums
Create Date: 2025-09-22 14:39:41.508872

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a199f1aba872'
down_revision = 'normalize_enums'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add 'settled' to contest_status enum
    op.execute("ALTER TYPE contest_status ADD VALUE 'settled'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values
    # This would require recreating the enum type
    pass
