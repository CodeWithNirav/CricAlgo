#!/usr/bin/env python3
"""
Test admin login without database
"""
import requests
import json

def test_admin_login():
    """Test admin login and get token"""
    BASE_URL = "http://localhost:8000"
    
    # Test login endpoint
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    try:
        # Try to login
        response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
        print(f"Login response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            print(f"✅ Login successful!")
            print(f"Token: {token[:50]}...")
            return token
        else:
            print(f"❌ Login failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None

def test_admin_ui_access(token):
    """Test admin UI access with token"""
    BASE_URL = "http://localhost:8000"
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # Test matches endpoint
        response = requests.get(f"{BASE_URL}/api/v1/admin/matches", headers=headers)
        print(f"Matches endpoint: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Admin UI accessible!")
            print("🎯 You can now access: http://localhost:8000/admin")
            print("Use these credentials:")
            print("Username: admin")
            print("Password: admin123")
        else:
            print(f"❌ Admin UI not accessible: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🧪 Testing Admin Login...")
    print("=" * 50)
    
    token = test_admin_login()
    if token:
        test_admin_ui_access(token)
