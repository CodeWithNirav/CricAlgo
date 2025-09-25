# Fix Winner Rank Column Script

This script (`fix_winner_rank.py`) ensures that the `winner_rank` column exists in the `entries` table and is properly indexed for optimal performance.

## What it does

1. **Checks** if the `winner_rank` column exists in the `entries` table
2. **Adds** the column if it doesn't exist (INTEGER, nullable)
3. **Creates** an index `idx_entries_winner_rank` for better query performance
4. **Verifies** that everything is working correctly

## Prerequisites

- Python 3.8+
- Database connection configured in your environment
- Required dependencies installed (`sqlalchemy`, `asyncpg`, etc.)

## Usage

### Basic Usage
```bash
python fix_winner_rank.py
```

### With Docker (if using docker-compose)
```bash
# If your app is running in Docker
docker-compose exec app python fix_winner_rank.py

# Or run directly in the container
docker-compose run --rm app python fix_winner_rank.py
```

### Test the Script
```bash
python test_fix_script.py
```

## What the Script Does Step by Step

### 1. Database Connection
- Connects to your PostgreSQL database using the configured `DATABASE_URL`
- Handles both local and Docker environments automatically

### 2. Column Check
- Queries `information_schema.columns` to check if `winner_rank` exists
- Reports whether the column is present or missing

### 3. Column Creation (if needed)
- Adds `winner_rank INTEGER NULL` column to the `entries` table
- Only runs if the column doesn't exist

### 4. Index Creation
- Creates `idx_entries_winner_rank` index on the `winner_rank` column
- Checks if index already exists before creating
- Improves query performance for winner ranking operations

### 5. Verification
- Runs test queries to verify everything works
- Shows statistics about entries and winner ranks
- Confirms index creation

## Expected Output

```
🚀 Starting winner_rank column fix process...
==================================================
✅ Database connection established
🔍 Checking winner_rank column: EXISTS/MISSING

🔧 Adding winner_rank column... (if needed)
✅ Added winner_rank column to entries table

📊 Creating index for performance...
✅ Created index idx_entries_winner_rank

🔍 Verifying setup...
📊 Database verification:
   Total entries: 150
   Entries with winner_rank: 0
   Index exists: YES

==================================================
✅ winner_rank column fix completed successfully!
   The entries table now has:
   - winner_rank column (INTEGER, nullable)
   - idx_entries_winner_rank index for performance
   - Ready for contest settlement operations

🎉 All done! Your database is ready for contest settlements.
```

## Database Schema Impact

The script modifies the `entries` table:

```sql
-- Adds this column (if missing)
ALTER TABLE entries ADD COLUMN winner_rank INTEGER NULL;

-- Creates this index
CREATE INDEX idx_entries_winner_rank ON entries (winner_rank);
```

## Safety Features

- **Idempotent**: Safe to run multiple times
- **Non-destructive**: Only adds missing elements
- **Verification**: Confirms everything works after changes
- **Error handling**: Graceful failure with clear error messages

## Troubleshooting

### Connection Issues
If you get connection errors, check:
- Database is running
- `DATABASE_URL` environment variable is set correctly
- Network connectivity to database

### Permission Issues
Ensure your database user has:
- `ALTER TABLE` permissions on the `entries` table
- `CREATE INDEX` permissions

### Column Already Exists
If the column already exists, the script will:
- Skip column creation
- Still verify the index exists
- Report success

## Integration with Contest Settlement

This script prepares your database for contest settlement operations where:
- Winners are ranked (1st, 2nd, 3rd, etc.)
- Payouts are calculated based on rank
- Performance is optimized with proper indexing

## Related Files

- `app/models/contest_entry.py` - Model definition with `winner_rank` field
- `alembic/versions/51656e27311c_add_winner_rank_to_contest_entries.py` - Migration file
- `app/services/settlement.py` - Contest settlement logic
