import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.anyio
async def test_system_health_reports_setup_status():
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/system/health")

    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "vision-backend"
    assert data["checks"]["database"]["status"] in {"ok", "error"}
    assert "required_env" in data["checks"]
    assert "optional_integrations" in data["checks"]
    assert "privacy" in data
