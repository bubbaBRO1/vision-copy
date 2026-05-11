import uuid
from unittest.mock import AsyncMock
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def fake_token_for(monkeypatch):
    from unittest.mock import MagicMock
    from models.user import UserRole

    injected: dict[str, str] = {}

    def _decode(token: str):
        return {"sub": injected["uid"], "role": "user"}

    async def _get_user(db, uid):
        user = MagicMock()
        user.id = uid
        user.role = UserRole.user
        user.is_banned = False
        user.is_guest = False
        user.username = f"user_{str(uid)[:8]}"
        user.email = f"{str(uid)[:8]}@test.com"
        return user

    monkeypatch.setattr("services.auth_service.decode_access_token", _decode)
    monkeypatch.setattr("services.auth_service.get_user_by_id", _get_user)
    monkeypatch.setattr("routers.deps.decode_access_token", _decode)
    monkeypatch.setattr("routers.deps.get_user_by_id", _get_user)

    def _factory(user_id: uuid.UUID):
        injected["uid"] = str(user_id)
        return {"Authorization": f"Bearer fake-{user_id}"}

    return _factory


@pytest.mark.anyio
async def test_browser_assist_rejects_private_network_url(monkeypatch, fake_token_for):
    from main import app

    monkeypatch.setattr("services.rate_limiter.check_rate_limit", AsyncMock(return_value=(True, 10, 9, 9999999999)))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/browser-assist/runs",
            headers=fake_token_for(uuid.uuid4()),
            json={
                "urls": ["http://127.0.0.1:8000/private"],
                "options": {"mode": "isolated", "screenshot": True},
            },
        )

    assert response.status_code == 400
    assert "private" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_browser_assist_plan_is_bounded_and_safe(fake_token_for):
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/browser-assist/runs/plan",
            headers=fake_token_for(uuid.uuid4()),
            json={
                "urls": ["https://example.com/a", "https://example.org/b"],
                "max_pages": 1,
                "objective": "Find source context",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "bounded_browser_assist"
    assert payload["pages_to_visit"] == ["https://example.com/a"]
    assert payload["experimental_desktop_control"]["available"] is False


@pytest.mark.anyio
async def test_browser_assist_owner_only_read(monkeypatch, fake_token_for):
    from database import AsyncSessionLocal
    from main import app
    from models.search import BrowserAssistRun

    monkeypatch.setattr("services.rate_limiter.check_rate_limit", AsyncMock(return_value=(True, 10, 9, 9999999999)))

    owner_id = uuid.uuid4()
    other_user = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        run = BrowserAssistRun(
            user_id=owner_id,
            status="queued",
            mode="isolated",
            approved_urls=["https://example.com/a"],
            visited_urls=[],
            run_log=[],
            is_incognito=False,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id = str(run.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/browser-assist/runs/{run_id}", headers=fake_token_for(other_user))

    assert response.status_code == 404


@pytest.mark.anyio
async def test_search_results_cluster_duplicates_and_preserve_saved_state(fake_token_for):
    from database import AsyncSessionLocal
    from main import app
    from models.search import Search, SearchResultState, SearchStatus

    user_id = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        search = Search(
            user_id=user_id,
            filename="sample.jpg",
            file_hash="abc",
            file_path="/tmp/sample.jpg",
            status=SearchStatus.done,
            results_json={
                "Reverse Image Search": {
                    "results": [
                        {"url": "https://example.com/post?a=1&utm_source=ad", "title": "Match one", "similarity_pct": 92},
                        {"url": "https://example.com/post?a=1", "title": "Match duplicate", "similarity_pct": 90},
                    ]
                },
                "web_scrapers": {
                    "TinEyeScraper": [
                        {"url": "https://example.com/post?a=1", "title": "Match from TinEye", "similarity_pct": 88}
                    ]
                },
            },
        )
        db.add(search)
        await db.flush()
        state = SearchResultState(
            user_id=user_id,
            search_id=search.id,
            result_key="https://example.com/post?a=1",
            saved=True,
            hidden=False,
            note="Keep this cluster",
        )
        db.add(state)
        await db.commit()
        search_id = str(search.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/search/{search_id}/results", headers=fake_token_for(user_id))

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_clusters"] == 1
    assert payload["results"][0]["cluster_size"] == 3
    assert payload["results"][0]["saved"] is True
    assert payload["results"][0]["note"] == "Keep this cluster"
    assert payload["results"][0]["engines"] == ["TinEyeScraper"]
    assert payload["results"][0]["score_label"] in {"Very High", "High"}
    assert payload["results"][0]["ranking_reasons"]


@pytest.mark.anyio
async def test_browser_assist_screenshot_owner_only(fake_token_for):
    from config import get_settings
    from database import AsyncSessionLocal
    from main import app
    from models.search import BrowserAssistArtifact, BrowserAssistRun

    user_id = uuid.uuid4()
    settings = get_settings()
    screenshot_dir = Path(settings.upload_dir) / "browser-assist-tests"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshot_dir / "sample.png"
    screenshot_path.write_bytes(b"fake-png-data")

    async with AsyncSessionLocal() as db:
        run = BrowserAssistRun(
            user_id=user_id,
            status="completed",
            mode="isolated",
            approved_urls=["https://example.com/a"],
            visited_urls=["https://example.com/a"],
            run_log=[],
            is_incognito=False,
            persist_artifacts=True,
        )
        db.add(run)
        await db.flush()
        artifact = BrowserAssistArtifact(
            run_id=run.id,
            user_id=user_id,
            source_url="https://example.com/a",
            final_url="https://example.com/a",
            title="Example",
            snippet="artifact",
            screenshot_path=str(screenshot_path),
            metadata_json={"capture": "playwright"},
        )
        db.add(artifact)
        await db.commit()
        run_id = str(run.id)
        artifact_id = str(artifact.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            f"/api/browser-assist/runs/{run_id}/artifacts/{artifact_id}/screenshot",
            headers=fake_token_for(user_id),
        )

    assert response.status_code == 200
    assert response.content == b"fake-png-data"


@pytest.mark.anyio
async def test_geolocation_endpoint_returns_normalized_brief(fake_token_for):
    from database import AsyncSessionLocal
    from main import app
    from models.search import Search, SearchStatus

    user_id = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        search = Search(
            user_id=user_id,
            filename="geo.jpg",
            file_hash="geo123",
            file_path="/tmp/geo.jpg",
            status=SearchStatus.done,
            results_json={
                "Geolocation": {
                    "overall_verdict": "Likely location inferred",
                    "source": "GeoSpy AI",
                    "best_result": {
                        "lat": 40.758,
                        "lon": -73.9855,
                        "city": "Times Square, New York",
                        "maps_link": "https://example.com/map",
                    },
                    "ocr_geolocation": {"verdict": "OCR geocoded: New York, NY"},
                    "location_signals": ["GeoSpy AI: New York", "OCR geocoded: New York"],
                }
            },
        )
        db.add(search)
        await db.commit()
        await db.refresh(search)
        search_id = str(search.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/geolocate/{search_id}", headers=fake_token_for(user_id))

    assert response.status_code == 200
    payload = response.json()
    assert payload["primary"]["address"] == "Times Square, New York"
    assert payload["primary"]["confidence_label"] == "Likely"
    assert payload["evidence"]
    assert payload["location_signals"]


@pytest.mark.anyio
async def test_search_intel_endpoint_returns_cluster_brief(fake_token_for):
    from database import AsyncSessionLocal
    from main import app
    from models.search import Search, SearchStatus

    user_id = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        search = Search(
            user_id=user_id,
            filename="intel.jpg",
            file_hash="intel123",
            file_path="/tmp/intel.jpg",
            status=SearchStatus.done,
            results_json={
                "Reverse Image Search": {
                    "results": [
                        {"url": "https://example.com/source-new-york", "title": "Original New York source", "similarity_pct": 93},
                    ]
                },
                "web_scrapers": {
                    "GoogleLensScraper": [
                        {"url": "https://example.com/source-new-york", "title": "Original New York source", "similarity_pct": 91}
                    ]
                },
            },
        )
        db.add(search)
        await db.commit()
        await db.refresh(search)
        search_id = str(search.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/search/{search_id}/intel", headers=fake_token_for(user_id))

    assert response.status_code == 200
    payload = response.json()
    assert payload["cluster_count"] == 1
    assert payload["clusters"][0]["match_strength"]["label"] == "Very strong"
    assert payload["recommended_next_steps"]
