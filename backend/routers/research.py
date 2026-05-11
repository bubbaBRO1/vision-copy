import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.research import ResearchJob, ResearchStatus, ResearchDepth
from models.user import User
from routers.deps import get_current_user
from services.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api", tags=["research"])
UTC = timezone.utc


class ResearchRequest(BaseModel):
    query: str
    depth: str = "standard"


@router.post("/research", status_code=202)
async def start_research(
    req: ResearchRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allowed, limit, remaining, reset_ts = await check_rate_limit(
        str(current_user.id), "deep_research", current_user.role.value
    )
    if not allowed:
        raise HTTPException(429, "Rate limit exceeded", headers={
            "X-RateLimit-Limit": str(limit), "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset_ts)
        })

    depth = req.depth if req.depth in ("quick", "standard", "deep") else "standard"
    job = ResearchJob(
        user_id=current_user.id,
        query=req.query,
        depth=ResearchDepth(depth),
        status=ResearchStatus.running,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    return {"job_id": str(job.id), "status": "running"}


@router.get("/research/{job_id}/stream")
async def stream_research(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(ResearchJob, uuid.UUID(job_id))
    if not job or job.user_id != current_user.id:
        raise HTTPException(404, "Job not found")

    from ai.research_pipeline import run_research

    async def _stream():
        report = ""
        async for token in run_research(job_id, job.query, job.depth.value):
            report += token
            yield f"data: {token}\n\n"
        # Save report
        job.report_json = {"markdown": report}
        job.status = ResearchStatus.done
        job.completed_at = datetime.now(UTC)
        await db.commit()

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/research/{job_id}")
async def get_research(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(ResearchJob, uuid.UUID(job_id))
    if not job or job.user_id != current_user.id:
        raise HTTPException(404, "Job not found")
    return {
        "job_id": str(job.id),
        "query": job.query,
        "depth": job.depth.value,
        "status": job.status.value,
        "report": job.report_json,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
