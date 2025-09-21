#!/usr/bin/env python3
"""
Test script to verify admin interface fixes
"""

import asyncio
import aiohttp
import json
import sys
from typing import Optional

BASE_URL = "http://localhost:8000"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

async def test_admin_fixes():
    """Test all the admin interface fixes"""
    print("=== Testing Admin Interface Fixes ===\n")
    
    async with aiohttp.ClientSession() as session:
        # Test 1: Health check
        print("1. Testing health endpoint...")
        try:
            async with session.get(f"{BASE_URL}/health") as resp:
                if resp.status == 200:
                    print("   ✓ Health endpoint working")
                else:
                    print(f"   ✗ Health endpoint failed: {resp.status}")
        except Exception as e:
            print(f"   ✗ Health endpoint error: {e}")
        
        # Test 2: Admin login
        print("\n2. Testing admin login...")
        admin_token = None
        try:
            login_data = {"username": ADMIN_USER, "password": ADMIN_PASS}
            async with session.post(f"{BASE_URL}/api/v1/auth/admin/login", 
                                  json=login_data) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    admin_token = data.get("access_token")
                    if admin_token:
                        print("   ✓ Admin login successful")
                    else:
                        print("   ✗ Admin login response invalid")
                else:
                    print(f"   ✗ Admin login failed: {resp.status}")
        except Exception as e:
            print(f"   ✗ Admin login error: {e}")
        
        if not admin_token:
            print("   ✗ Cannot continue without admin token")
            return
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Test 3: Invite codes endpoint (canonical)
        print("\n3. Testing invite codes endpoint (canonical)...")
        try:
            async with session.get(f"{BASE_URL}/api/v1/admin/invite_codes", 
                                 headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   ✓ Invite codes endpoint working ({len(data)} codes)")
                else:
                    text = await resp.text()
                    print(f"   ✗ Invite codes endpoint failed: {resp.status} - {text}")
        except Exception as e:
            print(f"   ✗ Invite codes endpoint error: {e}")
        
        # Test 4: Invite codes endpoint (alias)
        print("\n4. Testing invite codes endpoint (alias)...")
        try:
            async with session.get(f"{BASE_URL}/api/v1/admin/invitecodes", 
                                 headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   ✓ Invite codes alias endpoint working ({len(data)} codes)")
                else:
                    text = await resp.text()
                    print(f"   ✗ Invite codes alias endpoint failed: {resp.status} - {text}")
        except Exception as e:
            print(f"   ✗ Invite codes alias endpoint error: {e}")
        
        # Test 5: Users endpoint
        print("\n5. Testing users endpoint...")
        try:
            async with session.get(f"{BASE_URL}/api/v1/admin/users?limit=10", 
                                 headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   ✓ Users endpoint working ({len(data)} users)")
                else:
                    text = await resp.text()
                    print(f"   ✗ Users endpoint failed: {resp.status} - {text}")
        except Exception as e:
            print(f"   ✗ Users endpoint error: {e}")
        
        # Test 6: Admin UI static files
        print("\n6. Testing admin UI static files...")
        try:
            async with session.get(f"{BASE_URL}/static/admin/index.html") as resp:
                if resp.status == 200:
                    print("   ✓ Admin UI static files accessible")
                else:
                    print(f"   ✗ Admin UI static files failed: {resp.status}")
        except Exception as e:
            print(f"   ✗ Admin UI static files error: {e}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(test_admin_fixes())
