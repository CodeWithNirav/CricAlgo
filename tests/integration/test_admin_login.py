import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_admin_login_seeded(event_loop):
    # assume seed_admin ran in CI or test fixture
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/admin/login", json={"username":"admin@staging.local","password":"ChangeMeNow!"})
        assert resp.status_code in (200,201)
        data = resp.json()
        assert "access_token" in data
