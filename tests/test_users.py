import pytest
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager
from main import app

@pytest.mark.asyncio
async def test_get_users():
    async with LifespanManager(app) as manager:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/users")

    assert response.status_code == 200
    assert len(response.json()) > 0
