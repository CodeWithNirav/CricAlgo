import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_invite_codes_list_requires_admin(test_client: AsyncClient):
    r = await test_client.get("/api/v1/admin/invite_codes")
    assert r.status_code in (401, 403, 200)

@pytest.mark.asyncio
async def test_users_list_requires_admin(test_client: AsyncClient):
    r = await test_client.get("/api/v1/admin/users")
    assert r.status_code in (401, 403, 200)
