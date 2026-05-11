import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.search import Search, Collection
from models.user import User
from routers.deps import get_current_user

router = APIRouter(prefix="/api/collections", tags=["collections"])
UTC = timezone.utc


class CollectionCreate(BaseModel):
    name: str


@router.get("/")
async def list_collections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Collection).where(Collection.user_id == current_user.id).order_by(Collection.created_at.desc())
    )
    cols = result.scalars().all()

    out = []
    for col in cols:
        count_r = await db.execute(
            select(func.count()).where(Search.collection_id == col.id)
        )
        out.append({
            "id": str(col.id),
            "name": col.name,
            "search_count": count_r.scalar(),
            "created_at": col.created_at.isoformat(),
        })
    return out


@router.post("/")
async def create_collection(
    body: CollectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    col = Collection(user_id=current_user.id, name=body.name)
    db.add(col)
    await db.commit()
    await db.refresh(col)
    return {"id": str(col.id), "name": col.name}


@router.get("/{collection_id}/searches")
async def collection_searches(
    collection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    col = await db.get(Collection, uuid.UUID(collection_id))
    if not col or col.user_id != current_user.id:
        raise HTTPException(404, "Not found")
    result = await db.execute(
        select(Search).where(Search.collection_id == col.id).order_by(Search.created_at.desc())
    )
    items = result.scalars().all()
    return [
        {"search_id": str(s.id), "filename": s.filename, "status": s.status.value, "created_at": s.created_at.isoformat()}
        for s in items
    ]


@router.patch("/{collection_id}")
async def rename_collection(
    collection_id: str,
    body: CollectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    col = await db.get(Collection, uuid.UUID(collection_id))
    if not col or col.user_id != current_user.id:
        raise HTTPException(404, "Not found")
    col.name = body.name
    await db.commit()
    return {"ok": True}


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    col = await db.get(Collection, uuid.UUID(collection_id))
    if not col or col.user_id != current_user.id:
        raise HTTPException(404, "Not found")
    # Detach searches
    result = await db.execute(select(Search).where(Search.collection_id == col.id))
    for s in result.scalars().all():
        s.collection_id = None
    await db.delete(col)
    await db.commit()
    return {"ok": True}


@router.post("/add-search")
async def add_search_to_collection(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    search = await db.get(Search, uuid.UUID(body["search_id"]))
    if not search or search.user_id != current_user.id:
        raise HTTPException(404, "Search not found")
    col = await db.get(Collection, uuid.UUID(body["collection_id"]))
    if not col or col.user_id != current_user.id:
        raise HTTPException(404, "Collection not found")
    search.collection_id = col.id
    await db.commit()
    return {"ok": True}
