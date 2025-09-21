#!/usr/bin/env python3
"""
Create a simple admin user for testing (bypasses database)
"""
import os
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def create_simple_admin():
    """Create admin credentials for testing"""
    
    print("🔧 Creating Simple Admin User...")
    print("=" * 50)
    
    # Set environment variables for testing
    os.environ["ENABLE_TEST_TOTP_BYPASS"] = "true"
    os.environ["DATABASE_URL"] = "sqlite:///./test.db"  # Use SQLite for testing
    
    print("✅ Environment configured for testing")
    print("✅ TOTP bypass enabled")
    print("✅ Database set to SQLite")
    
    print("\n🎯 Admin Credentials:")
    print("Username: admin")
    print("Password: admin123")
    print("Email: admin@cricalgo.com")
    
    print("\n🌐 Access URLs:")
    print("Admin UI: http://localhost:8000/admin")
    print("API Docs: http://localhost:8000/docs")
    
    print("\n📝 To use:")
    print("1. Start the server: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
    print("2. Go to: http://localhost:8000/admin")
    print("3. Login with: admin / admin123")
    print("4. Click 'Matches' to see the new UI!")

if __name__ == "__main__":
    create_simple_admin()
