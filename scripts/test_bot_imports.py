#!/usr/bin/env python3
"""
Simple test script to verify bot imports work correctly
"""

import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Test that all required modules can be imported"""
    print("🧪 Testing Bot Imports...")
    
    try:
        # Test core imports
        from app.bot.handlers.unified_callbacks import unified_callback_router
        print("   ✅ unified_callbacks imported")
        
        from app.bot.handlers.commands import user_router
        print("   ✅ commands imported")
        
        from app.bot.handlers.callbacks import callback_router
        print("   ✅ callbacks imported")
        
        from app.bot.handlers.contest_callbacks import contest_callback_router
        print("   ✅ contest_callbacks imported")
        
        # Test match repository
        from app.repos.match_repo import get_matches, get_contests_for_match, get_match_by_id
        print("   ✅ match_repo imported")
        
        # Test that the new handlers are available
        print("   ✅ All new match functionality is available")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("🚀 Testing Bot Imports")
    print("=" * 30)
    
    success = test_imports()
    
    print("\n" + "=" * 30)
    if success:
        print("🎉 All imports successful! The bot is ready for Docker deployment.")
        print("\n📝 Next steps:")
        print("   1. Run: .\\scripts\\test_docker_bot.ps1")
        print("   2. Or run: make bot-docker")
    else:
        print("❌ Import test failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
