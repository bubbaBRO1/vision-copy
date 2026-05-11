"""
Tests for ownership enforcement on search/project/chat endpoints.
Verifies that authenticated users cannot access other users' resources.
"""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def fake_token_for(monkeypatch):
    """
    Patch decode_access_token and get_user_by_id to return a synthetic user.
    Returns a callable: fake_token_for(user_id) → header dict.
    """
    from unittest.mock import AsyncMock, MagicMock
    from models.user import UserRole

    def _make_user(uid: uuid.UUID):
        u = MagicMock()
        u.id = uid
        u.role = UserRole.user
        u.is_banned = False
        u.username = f"user_{str(uid)[:8]}"
        u.email = f"{str(uid)[:8]}@test.com"
        return u

    injected: dict = {}

    def _decode(token: str):
        return {"sub": injected.get("uid", str(uuid.uuid4())), "role": "user"}

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


class TestSearchOwnership:
    @pytest.mark.anyio
    async def test_cannot_access_other_users_search(self, fake_token_for):
        """A search owned by user_a must return 403 for user_b."""
        from main import app
        from database import AsyncSessionLocal
        from models.search import Search, SearchStatus

        user_a = uuid.uuid4()
        user_b = uuid.uuid4()

        # Create a search owned by user_a directly in DB
        async with AsyncSessionLocal() as db:
            s = Search(
                user_id=user_a,
                filename="private.jpg",
                file_hash="abc123",
                file_path="/tmp/private.jpg",
                status=SearchStatus.done,
            )
            db.add(s)
            await db.commit()
            await db.refresh(s)
            sid = str(s.id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/api/search/{sid}", headers=fake_token_for(user_b))

        assert r.status_code == 403

    @pytest.mark.anyio
    async def test_anonymous_search_is_public(self):
        """An anonymous search (user_id=None) must be readable without auth."""
        from main import app
        from database import AsyncSessionLocal
        from models.search import Search, SearchStatus

        async with AsyncSessionLocal() as db:
            s = Search(
                user_id=None,
                filename="anon.jpg",
                file_hash="def456",
                file_path="/tmp/anon.jpg",
                status=SearchStatus.done,
                results_json={},
            )
            db.add(s)
            await db.commit()
            await db.refresh(s)
            sid = str(s.id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/api/search/{sid}")

        assert r.status_code == 200


class TestChatOwnership:
    @pytest.mark.anyio
    async def test_cannot_delete_other_users_session(self, fake_token_for):
        """user_b cannot delete user_a's chat session."""
        from main import app
        from database import AsyncSessionLocal
        from models.research import ChatSession

        user_a = uuid.uuid4()
        user_b = uuid.uuid4()

        async with AsyncSessionLocal() as db:
            sess = ChatSession(
                user_id=user_a,
                title="user_a's secret chat",
                model="llama3:8b",
                messages_json=[],
            )
            db.add(sess)
            await db.commit()
            await db.refresh(sess)
            sid = str(sess.id)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.delete(f"/api/chat/sessions/{sid}", headers=fake_token_for(user_b))

        assert r.status_code == 404  # returns 404 not 403 to avoid enumeration
