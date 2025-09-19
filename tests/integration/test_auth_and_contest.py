"""
Integration test for admin authentication and contest creation
"""

import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.repos.user_repo import get_user_by_username
from app.repos.admin_repo import is_admin_user


@pytest.mark.asyncio
async def test_admin_auth_and_contest_flow():
    """Test admin authentication and contest creation flow"""
    
    # Test data
    admin_username = "admin"
    admin_password = "admin123"
    base_url = "http://localhost:8001"  # Adjust based on your setup
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Step 1: Login as admin
        login_response = await client.post(f"{base_url}/api/v1/login", json={
            "username": admin_username,
            "password": admin_password
        })
        
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        login_data = login_response.json()
        admin_token = login_data["access_token"]
        
        print(f"✓ Admin login successful, token: {admin_token[:20]}...")
        
        # Step 2: Test admin authentication by creating a contest
        headers = {"Authorization": f"Bearer {admin_token}"}
        contest_data = {
            "match_id": "test_match_123",
            "title": "Test Contest",
            "description": "Test contest for auth verification",
            "entry_fee": "1.0",
            "max_participants": 2,
            "prize_structure": [{"pos": 1, "pct": 100}]
        }
        
        contest_response = await client.post(
            f"{base_url}/api/v1/admin/contest",
            json=contest_data,
            headers=headers
        )
        
        # This should succeed if auth is working
        if contest_response.status_code == 200:
            print("✓ Contest creation successful - admin auth working")
            contest_data = contest_response.json()
            contest_id = contest_data["id"]
            
            # Clean up - delete the test contest
            await client.delete(f"{base_url}/api/v1/admin/contest/{contest_id}", headers=headers)
            print("✓ Test contest cleaned up")
        else:
            print(f"✗ Contest creation failed: {contest_response.status_code} - {contest_response.text}")
            # This is expected to fail if there are auth issues
            assert False, f"Contest creation failed: {contest_response.text}"
        
        # Step 3: Verify admin status in database
        async with AsyncSessionLocal() as session:
            user = await get_user_by_username(session, admin_username)
            assert user is not None, "Admin user not found in database"
            
            is_admin = await is_admin_user(session, user.id)
            assert is_admin, f"User {admin_username} is not marked as admin in database"
            
            print(f"✓ Database verification: User {admin_username} is admin")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_admin_auth_and_contest_flow())
