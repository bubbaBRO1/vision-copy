import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.search import (
    BrowserAssistArtifact,
    BrowserAssistRun,
    CaseAIInsight,
    CaseEntity,
    CaseEvidence,
    CaseReportDraft,
    CaseTimelineEvent,
    Project,
    ProjectStatus,
    Search,
    Collection,
)
from models.research import ChatSession
from models.user import User
from routers.deps import get_current_user

router = APIRouter(prefix="/api/projects", tags=["projects"])
UTC = timezone.utc


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    notes: str | None = None
    status: str | None = None


class EvidenceCreate(BaseModel):
    title: str
    evidence_type: str = "note"
    search_id: str | None = None
    result_key: str | None = None
    status: str = "needs_review"
    confidence: int | None = None
    source_url: str | None = None
    summary: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    provenance: dict | None = None
    metadata_json: dict | None = None
    include_in_report: bool = True


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


def _owned_or_404(project: Project | None, user_id: uuid.UUID) -> Project:
    if not project or project.user_id != user_id:
        raise HTTPException(404, "Project not found")
    return project


def _validate_confidence(value: int | None) -> int | None:
    if value is None:
        return None
    return max(0, min(100, int(value)))


def _evidence_payload(item: CaseEvidence) -> dict:
    return {
        "id": str(item.id),
        "project_id": str(item.project_id),
        "search_id": str(item.search_id) if item.search_id else None,
        "result_key": item.result_key,
        "title": item.title,
        "evidence_type": item.evidence_type,
        "status": item.status,
        "confidence": item.confidence,
        "source_url": item.source_url,
        "summary": item.summary,
        "notes": item.notes,
        "tags": item.tags or [],
        "provenance": item.provenance or {},
        "metadata_json": item.metadata_json or {},
        "include_in_report": item.include_in_report,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _render_case_markdown(workspace: dict) -> str:
    case = workspace["case"]
    lines = [
        "# VISION Case Report",
        "",
        f"**Case:** {case['name']}",
        f"**Status:** {case['status']}",
        "",
        "> AI outputs and confidence scores are investigative aids, not proof. Verify every important claim against the listed source evidence.",
        "",
        "## Summary",
        "",
        f"- Searches: {workspace['stats']['searches']}",
        f"- Evidence items: {workspace['stats']['evidence']}",
        f"- Verified evidence: {workspace['stats']['verified_evidence']}",
        f"- Average confidence: {workspace['stats']['avg_confidence'] if workspace['stats']['avg_confidence'] is not None else 'n/a'}",
        "",
        "## Evidence",
        "",
    ]
    for item in workspace["evidence"]:
        if not item.get("include_in_report", True):
            continue
        lines.extend([
            f"### {item['title']}",
            "",
            f"- Type: {item['evidence_type']}",
            f"- Status: {item['status']}",
            f"- Confidence: {item['confidence'] if item['confidence'] is not None else 'n/a'}",
            f"- Source: {item['source_url'] or 'n/a'}",
        ])
        if item.get("summary"):
            lines.append(f"- Summary: {item['summary']}")
        if item.get("notes"):
            lines.append(f"- Notes: {item['notes']}")
        if item.get("tags"):
            lines.append(f"- Tags: {', '.join(item['tags'])}")
        lines.append("")
    lines.extend(["## Timeline", ""])
    for event in workspace["timeline"][:50]:
        lines.append(f"- {event['at']} - {event['kind']}: {event['title']} ({event.get('status') or 'n/a'})")
    lines.append("")
    return "\n".join(lines)


async def _case_workspace(project: Project, db: AsyncSession) -> dict:
    searches = (await db.execute(
        select(Search).where(Search.project_id == project.id).order_by(desc(Search.created_at)).limit(100)
    )).scalars().all()
    evidence = (await db.execute(
        select(CaseEvidence).where(CaseEvidence.project_id == project.id).order_by(desc(CaseEvidence.updated_at)).limit(250)
    )).scalars().all()
    entities = (await db.execute(
        select(CaseEntity).where(CaseEntity.project_id == project.id).order_by(desc(CaseEntity.created_at)).limit(250)
    )).scalars().all()
    report_drafts = (await db.execute(
        select(CaseReportDraft).where(CaseReportDraft.project_id == project.id).order_by(desc(CaseReportDraft.updated_at)).limit(20)
    )).scalars().all()
    insights = (await db.execute(
        select(CaseAIInsight).where(CaseAIInsight.project_id == project.id).order_by(desc(CaseAIInsight.created_at)).limit(20)
    )).scalars().all()
    browser_runs = (await db.execute(
        select(BrowserAssistRun).where(BrowserAssistRun.project_id == project.id).order_by(desc(BrowserAssistRun.created_at)).limit(20)
    )).scalars().all()
    run_ids = [run.id for run in browser_runs]
    artifacts = []
    if run_ids:
        artifacts = (await db.execute(
            select(BrowserAssistArtifact).where(BrowserAssistArtifact.run_id.in_(run_ids)).order_by(desc(BrowserAssistArtifact.created_at)).limit(100)
        )).scalars().all()

    timeline = []
    for search in searches:
        timeline.append({
            "kind": "search",
            "title": search.filename or "Image search",
            "status": search.status.value,
            "at": search.created_at.isoformat(),
            "id": str(search.id),
        })
    for item in evidence:
        timeline.append({
            "kind": "evidence",
            "title": item.title,
            "status": item.status,
            "at": item.updated_at.isoformat(),
            "id": str(item.id),
        })
    for insight in insights:
        timeline.append({
            "kind": "ai",
            "title": f"AI {insight.action.replace('_', ' ')}",
            "status": "assistant",
            "at": insight.created_at.isoformat(),
            "id": str(insight.id),
        })
    timeline.sort(key=lambda item: item["at"], reverse=True)

    verified = [item for item in evidence if item.status == "verified"]
    avg_confidence = None
    scored = [item.confidence for item in evidence if item.confidence is not None]
    if scored:
        avg_confidence = round(sum(scored) / len(scored))

    return {
        "case": {
            "id": str(project.id),
            "name": project.name,
            "description": project.description,
            "notes": project.notes,
            "status": project.status.value,
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat(),
        },
        "stats": {
            "searches": len(searches),
            "evidence": len(evidence),
            "verified_evidence": len(verified),
            "entities": len(entities),
            "ai_insights": len(insights),
            "browser_artifacts": len(artifacts),
            "avg_confidence": avg_confidence,
        },
        "searches": [
            {
                "id": str(s.id),
                "filename": s.filename,
                "status": s.status.value,
                "intel_score": (s.results_json or {}).get("Scoring & Report", {}).get("intel_score"),
                "created_at": s.created_at.isoformat(),
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            }
            for s in searches
        ],
        "evidence": [_evidence_payload(item) for item in evidence],
        "entities": [
            {
                "id": str(e.id),
                "label": e.label,
                "entity_type": e.entity_type,
                "confidence": e.confidence,
                "notes": e.notes,
                "metadata_json": e.metadata_json or {},
                "created_at": e.created_at.isoformat(),
            }
            for e in entities
        ],
        "reports": [
            {
                "id": str(r.id),
                "title": r.title,
                "format": r.format,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in report_drafts
        ],
        "ai_insights": [
            {
                "id": str(i.id),
                "action": i.action,
                "content": i.content,
                "disclaimer": i.disclaimer,
                "created_at": i.created_at.isoformat(),
            }
            for i in insights
        ],
        "browser_artifacts": [
            {
                "id": str(a.id),
                "run_id": str(a.run_id),
                "source_url": a.source_url,
                "final_url": a.final_url,
                "title": a.title,
                "snippet": a.snippet,
                "screenshot_path": a.screenshot_path,
                "created_at": a.created_at.isoformat(),
            }
            for a in artifacts
        ],
        "timeline": timeline[:150],
    }


@router.get("/")
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project)
        .where(Project.user_id == current_user.id)
        .order_by(desc(Project.updated_at))
    )
    projects = result.scalars().all()

    out = []
    for p in projects:
        search_count = (await db.execute(
            select(func.count()).select_from(Search).where(Search.project_id == p.id)
        )).scalar() or 0
        chat_count = (await db.execute(
            select(func.count()).select_from(ChatSession).where(ChatSession.project_id == p.id)
        )).scalar() or 0
        collection_count = (await db.execute(
            select(func.count()).select_from(Collection).where(Collection.project_id == p.id)
        )).scalar() or 0
        out.append({
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "status": p.status.value,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat(),
            "search_count": search_count,
            "chat_count": chat_count,
            "collection_count": collection_count,
        })
    return out


@router.post("/", status_code=201)
async def create_project(
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = Project(
        user_id=current_user.id,
        name=body.name.strip(),
        description=body.description,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return {"id": str(project.id), "name": project.name, "status": project.status.value, "created_at": project.created_at.isoformat()}


@router.get("/{project_id}")
async def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = _owned_or_404(await db.get(Project, project_id), current_user.id)

    searches_r = await db.execute(
        select(Search).where(Search.project_id == project.id).order_by(desc(Search.created_at)).limit(50)
    )
    searches = [{"id": str(s.id), "filename": s.filename, "status": s.status.value, "created_at": s.created_at.isoformat()} for s in searches_r.scalars().all()]

    chats_r = await db.execute(
        select(ChatSession).where(ChatSession.project_id == project.id).order_by(desc(ChatSession.updated_at)).limit(50)
    )
    chats = [{"id": str(c.id), "title": c.title, "model": c.model, "updated_at": c.updated_at.isoformat()} for c in chats_r.scalars().all()]

    collections_r = await db.execute(
        select(Collection).where(Collection.project_id == project.id).order_by(desc(Collection.created_at)).limit(50)
    )
    collections = [{"id": str(c.id), "name": c.name, "created_at": c.created_at.isoformat()} for c in collections_r.scalars().all()]

    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "notes": project.notes,
        "status": project.status.value,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
        "searches": searches,
        "chats": chats,
        "collections": collections,
    }


@router.get("/{project_id}/workspace")
async def get_case_workspace(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = _owned_or_404(await db.get(Project, project_id), current_user.id)
    return await _case_workspace(project, db)


@router.post("/{project_id}/evidence", status_code=201)
async def create_case_evidence(
    project_id: uuid.UUID,
    body: EvidenceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = _owned_or_404(await db.get(Project, project_id), current_user.id)
    if not body.title.strip():
        raise HTTPException(400, "Evidence title is required")
    search_id = uuid.UUID(body.search_id) if body.search_id else None
    if search_id:
        search = await db.get(Search, search_id)
        if not search or search.user_id != current_user.id:
            raise HTTPException(404, "Search not found")

    evidence = CaseEvidence(
        user_id=current_user.id,
        project_id=project.id,
        search_id=search_id,
        result_key=body.result_key,
        title=body.title.strip(),
        evidence_type=body.evidence_type,
        status=body.status,
        confidence=_validate_confidence(body.confidence),
        source_url=body.source_url,
        summary=body.summary,
        notes=body.notes,
        tags=body.tags,
        provenance=body.provenance,
        metadata_json=body.metadata_json,
        include_in_report=body.include_in_report,
    )
    db.add(evidence)
    project.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(evidence)
    return _evidence_payload(evidence)


@router.post("/{project_id}/ai/{action}")
async def run_case_ai_action(
    project_id: uuid.UUID,
    action: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allowed = {"summary", "next_steps", "report", "source_review", "contradictions", "entities", "timeline"}
    if action not in allowed:
        raise HTTPException(404, "AI action not found")
    project = _owned_or_404(await db.get(Project, project_id), current_user.id)
    workspace = await _case_workspace(project, db)
    disclaimer = "AI-assisted analysis. Treat as a lead, not proof; verify against cited evidence and source provenance."
    evidence_count = workspace["stats"]["evidence"]
    verified_count = workspace["stats"]["verified_evidence"]
    if action == "summary":
        content = (
            f"AI-assisted case summary for {project.name}: "
            f"{evidence_count} evidence item(s), {verified_count} verified, "
            f"{workspace['stats']['searches']} linked search(es). "
            "Review unverified leads before using this in a final report."
        )
    elif action == "next_steps":
        content = (
            "AI-assisted next steps: verify high-confidence sources, resolve rejected or conflicting leads, "
            "capture screenshots for volatile pages, and add timeline notes for every important finding."
        )
    elif action == "report":
        content = _render_case_markdown(workspace)
    elif action == "source_review":
        content = "AI-assisted source review: prioritize original pages, archived copies, corroborated domains, and sources with screenshots."
    elif action == "contradictions":
        content = "AI-assisted contradiction scan: no automated contradictions detected; manually compare timestamps, domains, and identity claims."
    elif action == "entities":
        content = "AI-assisted entity extraction: review evidence titles, notes, source domains, face matches, and geolocation clues for people, places, and accounts."
    else:
        content = "AI-assisted timeline synthesis: order searches, evidence, browser captures, and report drafts by timestamp to preserve investigative context."

    insight = CaseAIInsight(
        user_id=current_user.id,
        project_id=project.id,
        action=action,
        content=content,
        disclaimer=disclaimer,
        metadata_json={"evidence_count": evidence_count, "verified_count": verified_count},
    )
    db.add(insight)
    await db.commit()
    await db.refresh(insight)
    return {
        "id": str(insight.id),
        "action": insight.action,
        "content": insight.content,
        "disclaimer": insight.disclaimer,
        "created_at": insight.created_at.isoformat(),
    }


@router.patch("/{project_id}")
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = _owned_or_404(await db.get(Project, project_id), current_user.id)
    if body.name is not None:
        project.name = body.name.strip()
    if body.description is not None:
        project.description = body.description
    if body.notes is not None:
        project.notes = body.notes
    if body.status is not None:
        try:
            project.status = ProjectStatus(body.status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {body.status}")
    project.updated_at = datetime.now(UTC)
    await db.commit()
    return {"ok": True}


@router.post("/{project_id}/archive")
async def archive_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = _owned_or_404(await db.get(Project, project_id), current_user.id)
    project.status = ProjectStatus.archived
    project.updated_at = datetime.now(UTC)
    await db.commit()
    return {"ok": True}


@router.get("/{project_id}/export")
async def export_project(
    project_id: uuid.UUID,
    format: str = Query("zip", pattern="^(json|md|html|zip)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import io, json, zipfile
    project = _owned_or_404(await db.get(Project, project_id), current_user.id)
    workspace = await _case_workspace(project, db)
    safe_name = project.name.replace(" ", "_").lower()[:40] or "case"

    if format == "json":
        return Response(
            json.dumps(workspace, indent=2, default=str).encode(),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="vision-case-{safe_name}.json"'},
        )

    markdown = _render_case_markdown(workspace)
    if format == "md":
        return Response(
            markdown.encode(),
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="vision-case-{safe_name}.md"'},
        )

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>VISION Case Report - {project.name}</title>
<style>body{{font-family:Inter,system-ui,sans-serif;background:#101113;color:#f2f2f2;line-height:1.55;max-width:980px;margin:0 auto;padding:40px}}a{{color:#66aaff}}code,pre{{background:#1f2228}}h1,h2,h3{{color:#fff}}blockquote{{border-left:3px solid #66aaff;padding-left:14px;color:#bbb}}</style>
</head><body><pre>{markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")}</pre></body></html>"""
    if format == "html":
        return Response(
            html.encode(),
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="vision-case-{safe_name}.html"'},
        )

    chats_r = await db.execute(select(ChatSession).where(ChatSession.project_id == project.id))
    chats = [
        {"id": str(c.id), "title": c.title, "model": c.model, "messages": c.messages_json, "created_at": c.created_at.isoformat()}
        for c in chats_r.scalars().all()
        if not c.is_incognito
    ]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("workspace.json", json.dumps(workspace, indent=2, default=str))
        zf.writestr("report.md", markdown)
        zf.writestr("report.html", html)
        zf.writestr("chats.json", json.dumps(chats, indent=2, default=str))
        if project.notes:
            zf.writestr("notes.txt", project.notes)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="vision-case-{safe_name}.zip"'},
    )


@router.delete("/{project_id}")
async def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = _owned_or_404(await db.get(Project, project_id), current_user.id)

    # Detach linked items
    searches_r = await db.execute(select(Search).where(Search.project_id == project.id))
    for s in searches_r.scalars().all():
        s.project_id = None

    chats_r = await db.execute(select(ChatSession).where(ChatSession.project_id == project.id))
    for c in chats_r.scalars().all():
        c.project_id = None

    collections_r = await db.execute(select(Collection).where(Collection.project_id == project.id))
    for col in collections_r.scalars().all():
        col.project_id = None

    await db.delete(project)
    await db.commit()
    return {"ok": True}
