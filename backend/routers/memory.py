import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.research import UserMemory
from models.user import User
from routers.deps import get_current_user

router = APIRouter(prefix="/api/memory", tags=["memory"])


def _require_real_user(current_user):
    if getattr(current_user, "is_guest", False) or getattr(getattr(current_user, "role", None), "value", current_user.role if isinstance(current_user.role, str) else None) == "guest":
        raise HTTPException(403, "Memory not available for guest sessions")


class MemoryCreate(BaseModel):
    content: str
    project_id: str | None = None
    tags: list[str] | None = None


@router.get("/")
async def list_memory(
    project_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(UserMemory).where(UserMemory.user_id == current_user.id)
    if project_id:
        q = q.where(UserMemory.project_id == uuid.UUID(project_id))
    q = q.order_by(desc(UserMemory.created_at)).limit(200)
    result = await db.execute(q)
    items = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "content": m.content,
            "project_id": str(m.project_id) if m.project_id else None,
            "tags": m.tags,
            "created_at": m.created_at.isoformat(),
        }
        for m in items
    ]


@router.post("/", status_code=201)
async def create_memory(
    body: MemoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_real_user(current_user)
    if not body.content.strip():
        raise HTTPException(400, "Content cannot be empty")
    mem = UserMemory(
        user_id=current_user.id,
        project_id=uuid.UUID(body.project_id) if body.project_id else None,
        content=body.content.strip(),
        tags=body.tags,
    )
    db.add(mem)
    await db.commit()
    await db.refresh(mem)
    return {"id": str(mem.id), "content": mem.content, "created_at": mem.created_at.isoformat()}


@router.get("/export")
async def export_memory(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import json
    from fastapi.responses import Response
    _require_real_user(current_user)
    result = await db.execute(
        select(UserMemory)
        .where(UserMemory.user_id == current_user.id)
        .order_by(desc(UserMemory.created_at))
    )
    items = result.scalars().all()
    data = [{"id": str(m.id), "content": m.content, "tags": m.tags, "project_id": str(m.project_id) if m.project_id else None, "created_at": m.created_at.isoformat()} for m in items]
    return Response(
        json.dumps(data, indent=2).encode(),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=vision-memory.json"},
    )


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    mem = await db.get(UserMemory, memory_id)
    if not mem or mem.user_id != current_user.id:
        raise HTTPException(404, "Memory not found")
    await db.delete(mem)
    await db.commit()
    return {"ok": True}
