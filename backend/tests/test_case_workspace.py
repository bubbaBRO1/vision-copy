import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def fake_token_for(monkeypatch):
    from models.user import UserRole

    injected: dict[str, str] = {}

    def _make_user(uid: uuid.UUID):
        user = MagicMock()
        user.id = uid
        user.role = UserRole.user
        user.is_banned = False
        user.username = f"user_{str(uid)[:8]}"
        user.email = f"{str(uid)[:8]}@test.com"
        return user

    def _decode(token: str):
        return {"sub": injected["uid"], "role": "user"}

    async def _get_user(db, uid):
        return _make_user(uid)

    monkeypatch.setattr("services.auth_service.decode_access_token", _decode)
    monkeypatch.setattr("services.auth_service.get_user_by_id", _get_user)
    monkeypatch.setattr("routers.deps.decode_access_token", _decode)
    monkeypatch.setattr("routers.deps.get_user_by_id", _get_user)

    def _factory(user_id: uuid.UUID):
        injected["uid"] = str(user_id)
        return {"Authorization": f"Bearer fake-{user_id}"}

    return _factory


@pytest.mark.anyio
async def test_app_imports_cleanly():
    import main

    assert main.app.title == "VISION OSINT Platform"


@pytest.mark.anyio
async def test_case_workspace_summarizes_project_assets(fake_token_for):
    from database import AsyncSessionLocal
    from main import app
    from models.search import CaseEvidence, Project, Search, SearchStatus

    user_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        project = Project(user_id=user_id, name="Find source image", description="Personal OSINT case")
        db.add(project)
        await db.flush()
        db.add(
            Search(
                user_id=user_id,
                project_id=project.id,
                filename="subject.jpg",
                status=SearchStatus.done,
                results_json={"Scoring & Report": {"intel_score": 82}},
            )
        )
        db.add(
            CaseEvidence(
                user_id=user_id,
                project_id=project.id,
                title="Original source page",
                evidence_type="url",
                status="verified",
                confidence=88,
                source_url="https://example.com/source",
                tags=["source", "verified"],
            )
        )
        await db.commit()
        case_id = str(project.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/projects/{case_id}/workspace", headers=fake_token_for(user_id))

    assert response.status_code == 200
    data = response.json()
    assert data["case"]["name"] == "Find source image"
    assert data["stats"]["searches"] == 1
    assert data["stats"]["evidence"] == 1
    assert data["stats"]["verified_evidence"] == 1
    assert data["evidence"][0]["title"] == "Original source page"
    assert data["sources"][0]["url"] == "https://example.com/source"
    assert data["timeline"][0]["kind"] in {"evidence", "search"}


@pytest.mark.anyio
async def test_evidence_crud_and_ownership(fake_token_for):
    from database import AsyncSessionLocal
    from main import app
    from models.search import Project

    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        project = Project(user_id=owner_id, name="Private case")
        db.add(project)
        await db.commit()
        await db.refresh(project)
        case_id = str(project.id)

    payload = {
        "title": "Search result lead",
        "evidence_type": "search_result",
        "source_url": "https://example.com/lead",
        "confidence": 73,
        "status": "needs_review",
        "tags": ["lead"],
        "provenance": {"engine": "TinEye"},
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(f"/api/projects/{case_id}/evidence", json=payload, headers=fake_token_for(owner_id))
        assert created.status_code == 201
        evidence_id = created.json()["id"]

        blocked = await client.patch(
            f"/api/evidence/{evidence_id}",
            json={"status": "verified"},
            headers=fake_token_for(other_id),
        )
        assert blocked.status_code == 404

        updated = await client.patch(
            f"/api/evidence/{evidence_id}",
            json={"status": "verified", "confidence": 91, "notes": "Confirmed by source page"},
            headers=fake_token_for(owner_id),
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "verified"
        assert updated.json()["confidence"] == 91

        deleted = await client.delete(f"/api/evidence/{evidence_id}", headers=fake_token_for(owner_id))
        assert deleted.status_code == 200


@pytest.mark.anyio
async def test_case_ai_action_creates_labeled_insight(fake_token_for):
    from database import AsyncSessionLocal
    from main import app
    from models.search import CaseEvidence, Project

    user_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        project = Project(user_id=user_id, name="AI case")
        db.add(project)
        await db.flush()
        db.add(CaseEvidence(user_id=user_id, project_id=project.id, title="Known source", status="verified"))
        await db.commit()
        case_id = str(project.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/projects/{case_id}/ai/summary", headers=fake_token_for(user_id))

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "summary"
    assert data["disclaimer"]
    assert "AI-assisted" in data["content"]


@pytest.mark.anyio
async def test_case_ai_what_missing_action(fake_token_for):
    from database import AsyncSessionLocal
    from main import app
    from models.search import Project

    user_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        project = Project(user_id=user_id, name="Gap case")
        db.add(project)
        await db.commit()
        await db.refresh(project)
        case_id = str(project.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/projects/{case_id}/ai/what_missing", headers=fake_token_for(user_id))

    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "what_missing"
    assert "gap" in data["content"].lower()


@pytest.mark.anyio
async def test_case_export_supports_markdown_and_zip(fake_token_for):
    from database import AsyncSessionLocal
    from main import app
    from models.search import CaseEvidence, Project

    user_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        project = Project(user_id=user_id, name="Export case")
        db.add(project)
        await db.flush()
        db.add(CaseEvidence(user_id=user_id, project_id=project.id, title="Exported evidence", status="verified"))
        await db.commit()
        case_id = str(project.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        markdown = await client.get(f"/api/projects/{case_id}/export?format=md", headers=fake_token_for(user_id))
        zipped = await client.get(f"/api/projects/{case_id}/export?format=zip", headers=fake_token_for(user_id))

    assert markdown.status_code == 200
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert b"# VISION Case Report" in markdown.content
    assert zipped.status_code == 200
    assert zipped.headers["content-type"].startswith("application/zip")
