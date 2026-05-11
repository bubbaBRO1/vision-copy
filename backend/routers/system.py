import os

from fastapi import APIRouter
from sqlalchemy import text

from database import AsyncSessionLocal
from config import get_settings

router = APIRouter(prefix="/api/system", tags=["system"])

REQUIRED_ENV = ["DATABASE_URL", "REDIS_URL", "JWT_SECRET"]
OPTIONAL_INTEGRATIONS = [
    "ANTHROPIC_API_KEY",
    "TINEYE_API_KEY",
    "GEOSPY_API_KEY",
    "SHODAN_API_KEY",
    "VIRUSTOTAL_API_KEY",
    "HIBP_API_KEY",
    "GITHUB_TOKEN",
]


@router.get("/health")
async def system_health():
    settings = get_settings()
    database_status = "ok"
    database_detail = "reachable"
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("select 1"))
    except Exception as exc:
        database_status = "error"
        database_detail = str(exc)

    required = {
        key: {
            "present": bool(os.environ.get(key)),
            "safe": key != "JWT_SECRET" or os.environ.get(key) not in {"changeme", "changeme-use-a-real-secret-in-production"},
        }
        for key in REQUIRED_ENV
    }
    optional = {key: bool(os.environ.get(key)) for key in OPTIONAL_INTEGRATIONS}
    redis_status = "unknown"
    redis_detail = "redis client not installed"
    try:
        import redis.asyncio as redis

        client = redis.from_url(settings.redis_url)
        await client.ping()
        await client.aclose()
        redis_status = "ok"
        redis_detail = "reachable"
    except Exception as exc:
        redis_status = "error"
        redis_detail = str(exc)

    browser_status = "ok"
    browser_detail = "playwright import available"
    try:
        import playwright.async_api  # noqa: F401
    except Exception as exc:
        browser_status = "degraded"
        browser_detail = f"Playwright unavailable; Browser Assist will use fallback capture: {exc}"

    return {
        "service": "vision-backend",
        "status": "ok" if database_status == "ok" and all(v["present"] and v["safe"] for v in required.values()) else "degraded",
        "checks": {
            "database": {"status": database_status, "detail": database_detail, "url_scheme": settings.database_url.split(":", 1)[0]},
            "redis": {"status": redis_status, "detail": redis_detail, "url_scheme": settings.redis_url.split(":", 1)[0]},
            "required_env": required,
            "optional_integrations": optional,
            "ollama": {"configured_url": settings.ollama_url},
            "uploads": {"path": settings.upload_dir},
            "browser_automation": {
                "status": browser_status,
                "detail": browser_detail,
                "safe_mode": "approved-urls-only",
                "desktop_control": "experimental hook only; not enabled",
            },
            "docker": {
                "compose_file": "docker-compose.yml",
                "services": ["postgres", "redis", "ollama", "backend", "frontend", "nginx"],
                "note": "Use docker compose ps for live container state.",
            },
            "setup_checklist": [
                "Copy .env.example to .env",
                "Set a non-default JWT_SECRET",
                "Start Docker Desktop before docker compose up",
                "Install/pull Ollama models if local AI actions are needed",
                "Open System Health after startup and resolve degraded checks",
            ],
        },
        "privacy": {
            "default": "self-hosted/local-first",
            "data_retention": "uploaded files and case evidence remain on this instance unless exported or deleted",
            "ai_notice": "AI-generated insights are assistance, not proof.",
        },
    }
