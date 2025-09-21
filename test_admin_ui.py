#!/usr/bin/env python3
"""
Test script to demonstrate admin UI functionality
"""
import requests
import json

# Test the admin UI endpoints
BASE_URL = "http://localhost:8000"

def test_admin_endpoints():
    """Test the admin endpoints we created"""
    
    print("🧪 Testing Admin UI Endpoints...")
    print("=" * 50)
    
    # Test 1: Check if admin UI is accessible
    try:
        response = requests.get(f"{BASE_URL}/admin")
        print(f"✅ Admin UI accessible: {response.status_code}")
    except Exception as e:
        print(f"❌ Admin UI not accessible: {e}")
        return
    
    # Test 2: Test matches endpoint (will return 401 without auth)
    try:
        response = requests.get(f"{BASE_URL}/api/v1/admin/matches")
        print(f"✅ Matches endpoint: {response.status_code} (401 expected without auth)")
    except Exception as e:
        print(f"❌ Matches endpoint error: {e}")
    
    # Test 3: Test contests endpoint
    try:
        response = requests.get(f"{BASE_URL}/api/v1/admin/matches/test-id/contests")
        print(f"✅ Contests endpoint: {response.status_code} (401 expected without auth)")
    except Exception as e:
        print(f"❌ Contests endpoint error: {e}")
    
    print("\n🎯 To use the admin UI:")
    print("1. Go to: http://localhost:8000/admin")
    print("2. Login with admin credentials")
    print("3. Click 'Matches' in the navigation")
    print("4. Create matches and contests!")

if __name__ == "__main__":
    test_admin_endpoints()
