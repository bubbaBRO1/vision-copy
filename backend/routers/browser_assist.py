import asyncio
import uuid
from typing import Literal

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from models.search import BrowserAssistArtifact, BrowserAssistRun, Project, Search
from routers.deps import get_current_user_or_guest
from services.browser_assist import run_browser_assist, stream_browser_assist, validate_browser_assist_url
from services import rate_limiter

router = APIRouter(prefix="/api/browser-assist", tags=["browser-assist"])
settings = get_settings()


class BrowserAssistOptions(BaseModel):
    mode: Literal["isolated", "profile"] = "isolated"
    max_pages: int = Field(default=5, ge=1, le=10)
    screenshot: bool = True


class BrowserAssistCreateRequest(BaseModel):
    search_id: str | None = None
    project_id: str | None = None
    urls: list[str] = Field(default_factory=list, min_length=1, max_length=10)
    options: BrowserAssistOptions = Field(default_factory=BrowserAssistOptions)
    is_incognito: bool = False
    confirm_incognito: bool = False
    persist_artifacts: bool = True


def _owned_resource_or_404(resource, current_user):
    if not resource or resource.user_id != current_user.id:
        raise HTTPException(404, "Run not found")


@router.post("/runs", status_code=201)
async def create_run(
    request: BrowserAssistCreateRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user_or_guest),
    db: AsyncSession = Depends(get_db),
):
    allowed, _, _, _ = await rate_limiter.check_rate_limit(str(current_user.id), "api", getattr(current_user, "role", "user"))
    if not allowed:
        raise HTTPException(429, "Rate limit exceeded")

    if request.is_incognito and not request.confirm_incognito:
        raise HTTPException(400, "Incognito Browser Assist requires explicit confirmation")

    if request.project_id:
        project = await db.get(Project, uuid.UUID(request.project_id))
        _owned_resource_or_404(project, current_user)

    if request.search_id:
        search = await db.get(Search, uuid.UUID(request.search_id))
        if not search or search.user_id != current_user.id:
            raise HTTPException(404, "Search not found")

    normalized_urls = []
    for url in request.urls[: request.options.max_pages]:
        try:
            normalized_urls.append(validate_browser_assist_url(url))
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    run = BrowserAssistRun(
        user_id=current_user.id,
        search_id=uuid.UUID(request.search_id) if request.search_id else None,
        project_id=uuid.UUID(request.project_id) if request.project_id else None,
        status="queued",
        mode=request.options.mode,
        approved_urls=normalized_urls,
        visited_urls=[],
        run_log=[{"message": "Run queued", "urls": normalized_urls}],
        is_incognito=request.is_incognito,
        persist_artifacts=request.persist_artifacts and not request.is_incognito,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    background_tasks.add_task(run_browser_assist, run.id)

    return {"run_id": str(run.id), "status": run.status, "approved_urls": normalized_urls}


@router.get("/runs/{run_id}")
async def get_run(run_id: str, current_user=Depends(get_current_user_or_guest), db: AsyncSession = Depends(get_db)):
    run = await db.get(BrowserAssistRun, uuid.UUID(run_id))
    _owned_resource_or_404(run, current_user)

    artifact_result = await db.execute(
        select(BrowserAssistArtifact).where(BrowserAssistArtifact.run_id == run.id).order_by(BrowserAssistArtifact.created_at)
    )
    artifacts = [
        {
            "id": str(a.id),
            "source_url": a.source_url,
            "final_url": a.final_url,
            "title": a.title,
            "snippet": a.snippet,
            "screenshot_path": a.screenshot_path,
            "metadata": a.metadata_json,
        }
        for a in artifact_result.scalars().all()
    ]
    return {
        "id": str(run.id),
        "search_id": str(run.search_id) if run.search_id else None,
        "project_id": str(run.project_id) if run.project_id else None,
        "status": run.status,
        "mode": run.mode,
        "approved_urls": run.approved_urls,
        "visited_urls": run.visited_urls,
        "run_log": run.run_log,
        "is_incognito": run.is_incognito,
        "persist_artifacts": run.persist_artifacts,
        "artifacts": artifacts,
        "error": run.error,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str, current_user=Depends(get_current_user_or_guest), db: AsyncSession = Depends(get_db)):
    run = await db.get(BrowserAssistRun, uuid.UUID(run_id))
    _owned_resource_or_404(run, current_user)
    return StreamingResponse(stream_browser_assist(run.id), media_type="text/event-stream")


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str, current_user=Depends(get_current_user_or_guest), db: AsyncSession = Depends(get_db)):
    run = await db.get(BrowserAssistRun, uuid.UUID(run_id))
    _owned_resource_or_404(run, current_user)
    run.status = "cancelled"
    logs = list(run.run_log or [])
    logs.append({"message": "Run cancelled"})
    run.run_log = logs
    await db.commit()
    return {"ok": True, "status": run.status}


@router.get("/runs/{run_id}/artifacts/{artifact_id}/screenshot")
async def get_artifact_screenshot(
    run_id: str,
    artifact_id: str,
    current_user=Depends(get_current_user_or_guest),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(BrowserAssistRun, uuid.UUID(run_id))
    _owned_resource_or_404(run, current_user)

    artifact = await db.get(BrowserAssistArtifact, uuid.UUID(artifact_id))
    if not artifact or artifact.run_id != run.id or artifact.user_id != current_user.id:
        raise HTTPException(404, "Artifact not found")

    if not artifact.screenshot_path:
        raise HTTPException(404, "Screenshot not available")

    screenshot_path = Path(artifact.screenshot_path).resolve()
    settings_root = Path(settings.upload_dir).resolve()
    if settings_root not in screenshot_path.parents:
        raise HTTPException(403, "Screenshot path is outside the upload directory")
    if not screenshot_path.exists():
        raise HTTPException(404, "Screenshot file not found")

    return FileResponse(screenshot_path, media_type="image/png")
