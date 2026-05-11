import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from database import engine
from routers import auth, search, research, chat, admin, waitlist, collections, analysis
from routers import facedb, projects, memory, system, evidence
from routers import browser_assist

settings = get_settings()

_REQUIRED_ENV = ["DATABASE_URL", "REDIS_URL", "JWT_SECRET"]
_OPTIONAL_KEYS = {
    "ANTHROPIC_API_KEY": "Claude AI fallback",
    "TINEYE_API_KEY": "TinEye reverse search",
    "SHODAN_API_KEY": "Shodan host lookup",
    "SIGHTENGINE_USER": "Sightengine deepfake detection",
    "GEOSPY_API_KEY": "GeoSpy visual geolocation",
    "VIRUSTOTAL_API_KEY": "VirusTotal URL scanning",
    "HIBP_API_KEY": "HaveIBeenPwned breach check",
}

def _validate_env():
    missing = [k for k in _REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        print(f"[VISION] FATAL: Missing required env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    if os.environ.get("JWT_SECRET") in ("changeme", "changeme-use-a-real-secret-in-production"):
        print("[VISION] FATAL: JWT_SECRET is set to an insecure default. Set a real secret.", file=sys.stderr)
        sys.exit(1)
    active, disabled = [], []
    for key, desc in _OPTIONAL_KEYS.items():
        (active if os.environ.get(key) else disabled).append(desc)
    print(f"[VISION] Active features: {', '.join(active) or 'none'}")
    if disabled:
        print(f"[VISION] Disabled (no API key): {', '.join(disabled)}")

_validate_env()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    # Download YOLO models in background if missing
    try:
        from stages.download_models import ensure_models
        import asyncio
        asyncio.get_event_loop().run_in_executor(None, ensure_models)
    except Exception:
        pass
    # Start file cleanup background task
    from services.cleanup_service import run_cleanup_loop
    cleanup_task = asyncio.ensure_future(run_cleanup_loop())
    yield
    cleanup_task.cancel()
    await engine.dispose()


app = FastAPI(
    title="VISION OSINT Platform",
    description="Reverse image search, geolocation, deep research, and AI assistant",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset", "X-Session-Id"],
)


# Security headers middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://accounts.google.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://accounts.google.com https://oauth2.googleapis.com; "
        "frame-src https://accounts.google.com; "
        "frame-ancestors 'none';"
    )
    return response


# Rate limit headers middleware
@app.middleware("http")
async def rate_limit_headers(request: Request, call_next):
    response = await call_next(request)
    # Headers are added per-endpoint; this just ensures they're not stripped
    return response


app.include_router(auth.router)
app.include_router(waitlist.router)
app.include_router(search.router)
app.include_router(research.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(collections.router)
app.include_router(facedb.router)
app.include_router(projects.router)
app.include_router(memory.router)
app.include_router(browser_assist.router)
app.include_router(analysis.router)
app.include_router(system.router)
app.include_router(evidence.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "vision-backend"}


@app.get("/")
async def root():
    return {"name": "VISION OSINT API", "version": "1.0.0", "docs": "/docs"}
