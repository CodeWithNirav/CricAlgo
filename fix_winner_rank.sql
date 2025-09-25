-- Fix winner_rank column issue
-- Run this SQL in your PostgreSQL database

-- Step 1: Check if the column already exists
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'entries' AND column_name = 'winner_rank';

-- If the above query returns no rows, run these commands:

-- Step 2: Add the winner_rank column
ALTER TABLE entries ADD COLUMN winner_rank INTEGER;

-- Step 3: Add index for better performance
CREATE INDEX idx_entries_winner_rank ON entries(winner_rank);

-- Step 4: Verify the column was added
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'entries' AND column_name = 'winner_rank';

-- Step 5: Check existing entries
SELECT COUNT(*) as total_entries FROM entries;

-- Step 6: Check if any entries have winner_rank set
SELECT COUNT(*) as entries_with_winner_rank FROM entries WHERE winner_rank IS NOT NULL;
