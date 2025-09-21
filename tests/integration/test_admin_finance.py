import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_admin_finance_endpoints():
    # This requires seed admin and running app; we perform smoke calls and expect JSON responses or 403 if no auth
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/api/v1/admin/deposits")
        assert r.status_code in (200,401,403)
        r2 = await ac.get("/api/v1/admin/withdrawals")
        assert r2.status_code in (200,401,403)
        r3 = await ac.get("/api/v1/admin/audit")
        assert r3.status_code in (200,401,403)
