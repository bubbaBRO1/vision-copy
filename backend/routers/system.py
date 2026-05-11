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

    return {
        "service": "vision-backend",
        "status": "ok" if database_status == "ok" and all(v["present"] and v["safe"] for v in required.values()) else "degraded",
        "checks": {
            "database": {"status": database_status, "detail": database_detail, "url_scheme": settings.database_url.split(":", 1)[0]},
            "required_env": required,
            "optional_integrations": optional,
            "ollama": {"configured_url": settings.ollama_url},
            "uploads": {"path": settings.upload_dir},
        },
        "privacy": {
            "default": "self-hosted/local-first",
            "data_retention": "uploaded files and case evidence remain on this instance unless exported or deleted",
            "ai_notice": "AI-generated insights are assistance, not proof.",
        },
    }
