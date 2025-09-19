-- CricAlgo: PostgreSQL DDL (initial schema)
-- Uses pgcrypto for gen_random_uuid()

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ENUM-like types
CREATE TYPE user_status AS ENUM ('ACTIVE', 'FROZEN', 'DISABLED');
CREATE TYPE deposit_status AS ENUM ('pending', 'approved', 'rejected');
CREATE TYPE withdraw_status AS ENUM ('pending', 'paid', 'failed', 'cancelled');
CREATE TYPE contest_status AS ENUM ('scheduled', 'open', 'closed', 'cancelled');

-- Admins (single super-admin to start)
CREATE TABLE admins (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username VARCHAR(64) NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  email VARCHAR(255),
  totp_secret TEXT, -- TOTP secret (encrypted at rest in app)
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  last_login TIMESTAMP WITH TIME ZONE
);

-- Users
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  telegram_id BIGINT NOT NULL UNIQUE,
  username VARCHAR(48) NOT NULL UNIQUE,
  status user_status NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Wallets: three buckets per user
CREATE TABLE wallets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  deposit_balance NUMERIC(30,8) NOT NULL DEFAULT 0,
  winning_balance NUMERIC(30,8) NOT NULL DEFAULT 0,
  bonus_balance NUMERIC(30,8) NOT NULL DEFAULT 0,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Trigger to create wallet when user inserted
CREATE FUNCTION fn_create_wallet_for_user() RETURNS trigger AS $$
BEGIN
  INSERT INTO wallets(user_id) VALUES (NEW.id);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_create_wallet AFTER INSERT ON users
  FOR EACH ROW EXECUTE FUNCTION fn_create_wallet_for_user();

-- Invitation codes
CREATE TABLE invitation_codes (
  code VARCHAR(64) PRIMARY KEY,
  created_by UUID REFERENCES admins(id) ON DELETE SET NULL,
  max_uses INT NULL, -- NULL = unlimited
  uses INT NOT NULL DEFAULT 0,
  expires_at TIMESTAMP WITH TIME ZONE NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Matches
CREATE TABLE matches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  external_id VARCHAR(128), -- optional link to external match id
  title VARCHAR(255) NOT NULL,
  start_time TIMESTAMP WITH TIME ZONE NOT NULL,
  status contest_status NOT NULL DEFAULT 'scheduled',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Contests
CREATE TABLE contests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  match_id UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
  code VARCHAR(64) NOT NULL UNIQUE, -- unique contest code
  title VARCHAR(255),
  entry_fee NUMERIC(30,8) NOT NULL DEFAULT 0,
  currency VARCHAR(16) NOT NULL DEFAULT 'USDT',
  max_players INT NULL, -- NULL = unlimited
  prize_structure JSONB NOT NULL DEFAULT '{}'::jsonb, -- flexible: tiers, percentages, etc.
  commission_pct NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (commission_pct >= 0 AND commission_pct <= 100),
  join_cutoff TIMESTAMP WITH TIME ZONE NULL,
  status contest_status NOT NULL DEFAULT 'open',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Entries: users joining contests
CREATE TABLE entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contest_id UUID NOT NULL REFERENCES contests(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  entry_code VARCHAR(64) NOT NULL UNIQUE,
  amount_debited NUMERIC(30,8) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  CONSTRAINT uq_contest_user UNIQUE (contest_id, user_id)
);

-- Deposit requests (user-submitted tx hash) -- dedupe by tx_hash
CREATE TABLE deposit_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  tx_hash VARCHAR(128) NOT NULL UNIQUE,
  amount NUMERIC(30,8) NOT NULL,
  chain VARCHAR(32) NOT NULL DEFAULT 'BEP20',
  status deposit_status NOT NULL DEFAULT 'pending',
  admin_id UUID REFERENCES admins(id) ON DELETE SET NULL,
  admin_note TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  processed_at TIMESTAMP WITH TIME ZONE
);

-- Withdraw requests
CREATE TABLE withdraw_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  to_address TEXT NOT NULL,
  amount NUMERIC(30,8) NOT NULL,
  status withdraw_status NOT NULL DEFAULT 'pending',
  admin_id UUID REFERENCES admins(id) ON DELETE SET NULL,
  admin_tx_hash VARCHAR(128),
  admin_note TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  processed_at TIMESTAMP WITH TIME ZONE
);

-- Transactions: ledger of all balance movements
CREATE TABLE transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  tx_type VARCHAR(64) NOT NULL, -- e.g., deposit, withdraw, join, payout, refund, commission
  amount NUMERIC(30,8) NOT NULL,
  currency VARCHAR(16) NOT NULL DEFAULT 'USDT',
  related_entity VARCHAR(64), -- e.g., contest:<id> or deposit:<id>
  related_id UUID NULL,
  metadata JSONB NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Audit logs for admin actions
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  admin_id UUID REFERENCES admins(id) ON DELETE SET NULL,
  action VARCHAR(128) NOT NULL,
  details JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Useful indexes
CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_deposit_requests_status ON deposit_requests(status);
CREATE INDEX idx_withdraw_requests_status ON withdraw_requests(status);
CREATE INDEX idx_contests_match_id ON contests(match_id);
CREATE INDEX idx_entries_contest_id ON entries(contest_id);
CREATE INDEX idx_transactions_user_id ON transactions(user_id);

-- Constraints and checks
ALTER TABLE wallets ADD CONSTRAINT chk_deposit_nonneg CHECK (deposit_balance >= 0);
ALTER TABLE wallets ADD CONSTRAINT chk_winning_nonneg CHECK (winning_balance >= 0);
ALTER TABLE wallets ADD CONSTRAINT chk_bonus_nonneg CHECK (bonus_balance >= 0);
ALTER TABLE contests ADD CONSTRAINT chk_entry_fee_nonneg CHECK (entry_fee >= 0);
ALTER TABLE entries ADD CONSTRAINT chk_amount_debited_nonneg CHECK (amount_debited >= 0);

-- Sample helper: function to safely debit wallet buckets in ordered manner
-- This is a simplified version; application logic should perform these steps in a transaction.

/*
Possible application workflow for joining a contest (explicit steps, executed inside a DB transaction):
1. SELECT FOR UPDATE wallets WHERE user_id = :user_id
2. Check available amount: attempt to debit deposit_balance, then bonus_balance, then winning_balance.
3. Ensure total debited equals entry_fee; if insufficient, rollback and return error.
4. INSERT into entries (with unique constraint to prevent double-join)
5. INSERT transaction records for each debit applied
6. Commit
*/

-- Maintenance: simple view to get user balances
CREATE VIEW vw_user_balances AS
SELECT u.id AS user_id, u.telegram_id, u.username,
       w.deposit_balance, w.bonus_balance, w.winning_balance, w.updated_at
FROM users u
JOIN wallets w ON w.user_id = u.id;

-- End of initial schema
