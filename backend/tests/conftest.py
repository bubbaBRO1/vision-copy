"""Shared test configuration and fixtures."""
import asyncio
import os

import pytest

# Ensure required env vars are set before importing app modules
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests-only-not-production")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_db():
    """Recreate the schema before each test."""
    from database import Base, engine
    import models  # noqa: F401 - populate metadata

    async def _reset():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_reset())
    yield
