-- Add held_balance column to wallets table
-- This script adds the held_balance column if it doesn't exist

-- Check if column exists and add if not
DO $$
BEGIN
    -- Add held_balance column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'wallets' 
        AND column_name = 'held_balance'
    ) THEN
        ALTER TABLE wallets ADD COLUMN held_balance NUMERIC(30,8) NOT NULL DEFAULT 0;
        
        -- Add constraint for non-negative held balance
        ALTER TABLE wallets ADD CONSTRAINT chk_held_nonneg CHECK (held_balance >= 0);
        
        RAISE NOTICE 'held_balance column added to wallets table';
    ELSE
        RAISE NOTICE 'held_balance column already exists in wallets table';
    END IF;
END $$;
