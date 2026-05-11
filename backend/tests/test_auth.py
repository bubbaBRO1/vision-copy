import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from main import app


@pytest.mark.anyio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.anyio
async def test_login_invalid_credentials():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/auth/login", json={"identifier": "nobody@example.com", "password": "wrongpass"})
    assert r.status_code == 401


@pytest.mark.anyio
async def test_stream_unknown_search_returns_404():
    """SSE stream on a non-existent search_id should return 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(f"/api/search/{uuid.uuid4()}/stream")
    assert r.status_code == 404


@pytest.mark.anyio
async def test_get_search_unknown_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(f"/api/search/{uuid.uuid4()}")
    assert r.status_code == 404
