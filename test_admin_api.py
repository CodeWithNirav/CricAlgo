#!/usr/bin/env python3
"""
Test admin API endpoints
"""
import requests
import json

def test_admin_api():
    """Test admin API endpoints"""
    BASE_URL = "http://localhost:8000"
    
    print("🧪 Testing Admin API...")
    print("=" * 50)
    
    # Test 1: Check if admin UI is accessible
    try:
        response = requests.get(f"{BASE_URL}/admin")
        print(f"✅ Admin UI: {response.status_code}")
    except Exception as e:
        print(f"❌ Admin UI error: {e}")
        return
    
    # Test 2: Test matches endpoint without auth (should return 401)
    try:
        response = requests.get(f"{BASE_URL}/api/v1/admin/matches")
        print(f"✅ Matches endpoint (no auth): {response.status_code}")
        if response.status_code == 401:
            print("   Expected: 401 Unauthorized")
        else:
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Matches endpoint error: {e}")
    
    # Test 3: Test with fake token
    try:
        headers = {"Authorization": "Bearer fake-token"}
        response = requests.get(f"{BASE_URL}/api/v1/admin/matches", headers=headers)
        print(f"✅ Matches endpoint (fake token): {response.status_code}")
        print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Matches endpoint error: {e}")
    
    print("\n🎯 Next steps:")
    print("1. Go to: http://localhost:8000/admin")
    print("2. Open browser developer tools (F12)")
    print("3. Check the Console tab for any errors")
    print("4. Click on 'Matches' tab")
    print("5. Look for debug messages in console")

if __name__ == "__main__":
    test_admin_api()
