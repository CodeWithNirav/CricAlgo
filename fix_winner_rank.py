#!/usr/bin/env python3
"""
Fix winner_rank column in entries table
This script checks if the winner_rank column exists, adds it if missing,
and creates an index for better performance.
"""

import asyncio
import sys
import os
from typing import Optional

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.core.config import settings
from app.db.session import async_session


class WinnerRankFixer:
    """Handles winner_rank column fixes for the entries table"""
    
    def __init__(self):
        self.engine = None
        self.session = None
    
    async def connect(self):
        """Establish database connection"""
        try:
            # Set database URL for local development
            os.environ['DATABASE_URL'] = 'postgresql+asyncpg://postgres:password@localhost:5432/cricalgo'
            
            # Import after setting environment variable
            from app.db.session import async_session
            
            self.session = async_session()
            print("✅ Database connection established")
            return True
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
    
    async def check_column_exists(self) -> bool:
        """Check if winner_rank column exists in entries table"""
        try:
            async with self.session as session:
                # Check if column exists
                result = await session.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'entries' 
                    AND column_name = 'winner_rank'
                """))
                
                column_exists = result.fetchone() is not None
                print(f"🔍 Checking winner_rank column: {'EXISTS' if column_exists else 'MISSING'}")
                return column_exists
                
        except Exception as e:
            print(f"❌ Error checking column: {e}")
            return False
    
    async def add_winner_rank_column(self) -> bool:
        """Add winner_rank column to entries table"""
        try:
            async with self.session as session:
                # Add the column
                await session.execute(text("""
                    ALTER TABLE entries 
                    ADD COLUMN winner_rank INTEGER NULL
                """))
                await session.commit()
                print("✅ Added winner_rank column to entries table")
                return True
                
        except Exception as e:
            print(f"❌ Error adding column: {e}")
            return False
    
    async def create_index(self) -> bool:
        """Create index on winner_rank column for better performance"""
        try:
            async with self.session as session:
                # Check if index already exists
                result = await session.execute(text("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename = 'entries' 
                    AND indexname = 'idx_entries_winner_rank'
                """))
                
                if result.fetchone():
                    print("📊 Index idx_entries_winner_rank already exists")
                    return True
                
                # Create the index
                await session.execute(text("""
                    CREATE INDEX idx_entries_winner_rank 
                    ON entries (winner_rank)
                """))
                await session.commit()
                print("✅ Created index idx_entries_winner_rank")
                return True
                
        except Exception as e:
            print(f"❌ Error creating index: {e}")
            return False
    
    async def verify_setup(self) -> bool:
        """Verify that everything is working correctly"""
        try:
            async with self.session as session:
                # Test query to verify column and index
                result = await session.execute(text("""
                    SELECT COUNT(*) as total_entries,
                           COUNT(winner_rank) as entries_with_rank
                    FROM entries
                """))
                
                row = result.fetchone()
                total_entries = row[0] if row else 0
                entries_with_rank = row[1] if row else 0
                
                print(f"📊 Database verification:")
                print(f"   Total entries: {total_entries}")
                print(f"   Entries with winner_rank: {entries_with_rank}")
                
                # Test index exists
                index_result = await session.execute(text("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE tablename = 'entries' 
                    AND indexname = 'idx_entries_winner_rank'
                """))
                
                index_exists = index_result.fetchone() is not None
                print(f"   Index exists: {'YES' if index_exists else 'NO'}")
                
                return True
                
        except Exception as e:
            print(f"❌ Error during verification: {e}")
            return False
    
    async def run_fix(self):
        """Main function to run the complete fix process"""
        print("🚀 Starting winner_rank column fix process...")
        print("=" * 50)
        
        # Step 1: Connect to database
        if not await self.connect():
            return False
        
        # Step 2: Check if column exists
        column_exists = await self.check_column_exists()
        
        # Step 3: Add column if missing
        if not column_exists:
            print("\n🔧 Adding winner_rank column...")
            if not await self.add_winner_rank_column():
                return False
        else:
            print("✅ winner_rank column already exists")
        
        # Step 4: Create index
        print("\n📊 Creating index for performance...")
        if not await self.create_index():
            return False
        
        # Step 5: Verify everything works
        print("\n🔍 Verifying setup...")
        if not await self.verify_setup():
            return False
        
        print("\n" + "=" * 50)
        print("✅ winner_rank column fix completed successfully!")
        print("   The entries table now has:")
        print("   - winner_rank column (INTEGER, nullable)")
        print("   - idx_entries_winner_rank index for performance")
        print("   - Ready for contest settlement operations")
        
        return True
    
    async def close(self):
        """Close database connections"""
        if self.session:
            await self.session.close()


async def main():
    """Main entry point"""
    fixer = WinnerRankFixer()
    
    try:
        success = await fixer.run_fix()
        if success:
            print("\n🎉 All done! Your database is ready for contest settlements.")
            sys.exit(0)
        else:
            print("\n💥 Fix process failed. Please check the errors above.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)
    finally:
        await fixer.close()


if __name__ == "__main__":
    asyncio.run(main())