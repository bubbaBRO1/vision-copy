import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.search import CaseEvidence, Project
from models.user import User
from routers.deps import get_current_user
from routers.projects import _evidence_payload, _validate_confidence

router = APIRouter(prefix="/api/evidence", tags=["evidence"])
UTC = timezone.utc


class EvidenceUpdate(BaseModel):
    title: str | None = None
    evidence_type: str | None = None
    status: str | None = None
    confidence: int | None = None
    source_url: str | None = None
    summary: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    provenance: dict | None = None
    metadata_json: dict | None = None
    include_in_report: bool | None = None


async def _owned_evidence_or_404(evidence_id: uuid.UUID, current_user: User, db: AsyncSession) -> CaseEvidence:
    evidence = await db.get(CaseEvidence, evidence_id)
    if not evidence or evidence.user_id != current_user.id:
        raise HTTPException(404, "Evidence not found")
    return evidence


@router.patch("/{evidence_id}")
async def update_evidence(
    evidence_id: uuid.UUID,
    body: EvidenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    evidence = await _owned_evidence_or_404(evidence_id, current_user, db)
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if key == "confidence":
            value = _validate_confidence(value)
        if key == "title" and value is not None:
            value = value.strip()
            if not value:
                raise HTTPException(400, "Evidence title is required")
        setattr(evidence, key, value)
    evidence.updated_at = datetime.now(UTC)
    project = await db.get(Project, evidence.project_id)
    if project:
        project.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(evidence)
    return _evidence_payload(evidence)


@router.delete("/{evidence_id}")
async def delete_evidence(
    evidence_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    evidence = await _owned_evidence_or_404(evidence_id, current_user, db)
    project = await db.get(Project, evidence.project_id)
    if project:
        project.updated_at = datetime.now(UTC)
    await db.delete(evidence)
    await db.commit()
    return {"ok": True}
