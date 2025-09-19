"""Initial migration

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto;')
    
    # ENUM types will be created automatically by SQLAlchemy models
    
    # Create admins table
    op.create_table('admins',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('totp_secret', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        sa.Column('last_login', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username')
    )
    
    # Create users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(length=48), nullable=False),
        sa.Column('status', postgresql.ENUM('ACTIVE', 'FROZEN', 'DISABLED', name='user_status'), nullable=False, server_default='ACTIVE'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id'),
        sa.UniqueConstraint('username')
    )
    
    # Create wallets table
    op.create_table('wallets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('deposit_balance', sa.Numeric(precision=30, scale=8), nullable=False, server_default='0'),
        sa.Column('winning_balance', sa.Numeric(precision=30, scale=8), nullable=False, server_default='0'),
        sa.Column('bonus_balance', sa.Numeric(precision=30, scale=8), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # Create invitation_codes table
    op.create_table('invitation_codes',
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('max_uses', sa.Integer(), nullable=True),
        sa.Column('uses', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('code'),
        sa.ForeignKeyConstraint(['created_by'], ['admins.id'], ondelete='SET NULL')
    )
    
    # Create matches table
    op.create_table('matches',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('external_id', sa.String(length=128), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('start_time', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('status', postgresql.ENUM('scheduled', 'open', 'closed', 'cancelled', name='contest_status'), nullable=False, server_default='scheduled'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create contests table
    op.create_table('contests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('match_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('entry_fee', sa.Numeric(precision=30, scale=8), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(length=16), nullable=False, server_default='USDT'),
        sa.Column('max_players', sa.Integer(), nullable=True),
        sa.Column('prize_structure', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('commission_pct', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0'),
        sa.Column('join_cutoff', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('status', postgresql.ENUM('scheduled', 'open', 'closed', 'cancelled', name='contest_status'), nullable=False, server_default='open'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ondelete='CASCADE')
    )
    
    # Create entries table
    op.create_table('entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('contest_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entry_code', sa.String(length=64), nullable=False),
        sa.Column('amount_debited', sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entry_code'),
        sa.UniqueConstraint('contest_id', 'user_id', name='uq_contest_user'),
        sa.ForeignKeyConstraint(['contest_id'], ['contests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # Create deposit_requests table
    op.create_table('deposit_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tx_hash', sa.String(length=128), nullable=False),
        sa.Column('amount', sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column('chain', sa.String(length=32), nullable=False, server_default='BEP20'),
        sa.Column('status', postgresql.ENUM('pending', 'approved', 'rejected', name='deposit_status'), nullable=False, server_default='pending'),
        sa.Column('admin_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('admin_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        sa.Column('processed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tx_hash'),
        sa.ForeignKeyConstraint(['admin_id'], ['admins.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # Create withdraw_requests table
    op.create_table('withdraw_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('to_address', sa.Text(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'paid', 'failed', 'cancelled', name='withdraw_status'), nullable=False, server_default='pending'),
        sa.Column('admin_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('admin_tx_hash', sa.String(length=128), nullable=True),
        sa.Column('admin_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        sa.Column('processed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['admin_id'], ['admins.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # Create transactions table
    op.create_table('transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tx_type', sa.String(length=64), nullable=False),
        sa.Column('amount', sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column('currency', sa.String(length=16), nullable=False, server_default='USDT'),
        sa.Column('related_entity', sa.String(length=64), nullable=True),
        sa.Column('related_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL')
    )
    
    # Create audit_logs table
    op.create_table('audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('admin_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(length=128), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['admin_id'], ['admins.id'], ondelete='SET NULL')
    )
    
    # Create indexes
    op.create_index('idx_users_telegram_id', 'users', ['telegram_id'])
    op.create_index('idx_deposit_requests_status', 'deposit_requests', ['status'])
    op.create_index('idx_withdraw_requests_status', 'withdraw_requests', ['status'])
    op.create_index('idx_contests_match_id', 'contests', ['match_id'])
    op.create_index('idx_entries_contest_id', 'entries', ['contest_id'])
    op.create_index('idx_transactions_user_id', 'transactions', ['user_id'])
    
    # Create constraints
    op.create_check_constraint('chk_deposit_nonneg', 'wallets', 'deposit_balance >= 0')
    op.create_check_constraint('chk_winning_nonneg', 'wallets', 'winning_balance >= 0')
    op.create_check_constraint('chk_bonus_nonneg', 'wallets', 'bonus_balance >= 0')
    op.create_check_constraint('chk_entry_fee_nonneg', 'contests', 'entry_fee >= 0')
    op.create_check_constraint('chk_amount_debited_nonneg', 'entries', 'amount_debited >= 0')
    
    # Create function and trigger for wallet creation
    op.execute('''
        CREATE FUNCTION fn_create_wallet_for_user() RETURNS trigger AS $$
        BEGIN
          INSERT INTO wallets(user_id) VALUES (NEW.id);
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    ''')
    
    op.execute('''
        CREATE TRIGGER tr_create_wallet AFTER INSERT ON users
          FOR EACH ROW EXECUTE FUNCTION fn_create_wallet_for_user();
    ''')
    
    # Create view
    op.execute('''
        CREATE VIEW vw_user_balances AS
        SELECT u.id AS user_id, u.telegram_id, u.username,
               w.deposit_balance, w.bonus_balance, w.winning_balance, w.updated_at
        FROM users u
        JOIN wallets w ON w.user_id = u.id;
    ''')


def downgrade() -> None:
    # Drop view
    op.execute('DROP VIEW IF EXISTS vw_user_balances;')
    
    # Drop trigger and function
    op.execute('DROP TRIGGER IF EXISTS tr_create_wallet ON users;')
    op.execute('DROP FUNCTION IF EXISTS fn_create_wallet_for_user();')
    
    # Drop tables
    op.drop_table('audit_logs')
    op.drop_table('transactions')
    op.drop_table('withdraw_requests')
    op.drop_table('deposit_requests')
    op.drop_table('entries')
    op.drop_table('contests')
    op.drop_table('matches')
    op.drop_table('invitation_codes')
    op.drop_table('wallets')
    op.drop_table('users')
    op.drop_table('admins')
    
    # Drop ENUM types
    op.execute('DROP TYPE IF EXISTS contest_status;')
    op.execute('DROP TYPE IF EXISTS withdraw_status;')
    op.execute('DROP TYPE IF EXISTS deposit_status;')
    op.execute('DROP TYPE IF EXISTS user_status;')
