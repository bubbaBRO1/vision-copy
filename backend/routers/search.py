import hashlib
import uuid
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from models.search import Search, SearchResultState, SearchStatus
from models.user import User, UserRole
from routers.deps import get_current_user, get_current_user_optional
from schemas.search import SearchResponse, SearchResultResponse, SearchHistoryItem
from services.browser_assist import normalize_result_url
from services.osint_intel import analyze_result_cluster
from services import search_service
from services.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api", tags=["search"])
settings = get_settings()


def _check_search_access(search: Search, current_user: User | None) -> None:
    """Raise 403 if the search is user-owned and the caller is not the owner or admin."""
    if search.user_id is None:
        return  # anonymous search — publicly readable
    if current_user is None:
        raise HTTPException(403, "Access denied")
    if current_user.id != search.user_id and current_user.role != UserRole.admin:
        raise HTTPException(403, "Access denied")

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/tiff", "image/bmp"}
MAX_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
ENGINE_WEIGHTS = {
    "TinEyeScraper": 1.0,
    "GoogleLensScraper": 0.9,
    "YandexScraper": 0.85,
    "SauceNAOScraper": 0.8,
    "BingVisualScraper": 0.7,
    "IQDBScraper": 0.65,
}


def _magic_bytes_ok(data: bytes) -> bool:
    sigs = [b"\xff\xd8\xff", b"\x89PNG", b"RIFF", b"GIF8", b"II*", b"MM\x00*", b"RIFF"]
    return any(data[:8].startswith(s) for s in sigs)


def _flatten_results(results: dict | None) -> list[dict]:
    if not results:
        return []
    flat = list(results.get("Reverse Image Search", {}).get("results", []))
    for engine_name, engine_results in (results.get("web_scrapers") or {}).items():
        for item in engine_results or []:
            if item.get("url") and not item.get("error"):
                merged = dict(item)
                merged.setdefault("engine", engine_name)
                flat.append(merged)
    return flat


def _domain_for(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return (urlparse(url).hostname or "").replace("www.", "") or None
    except Exception:
        return None


def _result_rank_score(item: dict) -> float:
    similarity = max(0.0, min(float(item.get("similarity_pct", 0) or 0), 100.0)) / 100.0
    engine = item.get("engine")
    engine_weight = ENGINE_WEIGHTS.get(engine, 0.5)
    return round(similarity * 0.7 + engine_weight * 0.3, 4)


def _score_label(score_pct: float) -> str:
    if score_pct >= 85:
        return "Very High"
    if score_pct >= 70:
        return "High"
    if score_pct >= 50:
        return "Moderate"
    if score_pct >= 30:
        return "Low"
    return "Speculative"


def _ranking_reasons(best: dict, engines: list[str], cluster_size: int) -> list[str]:
    reasons: list[str] = []
    similarity = round(float(best.get("similarity_pct", 0) or 0))
    if similarity >= 90:
        reasons.append("Strong visual similarity score")
    elif similarity >= 75:
        reasons.append("Good visual similarity score")
    if "TinEyeScraper" in engines:
        reasons.append("TinEye corroboration")
    if "GoogleLensScraper" in engines or "YandexScraper" in engines:
        reasons.append("Search-engine corroboration")
    if cluster_size > 1:
        reasons.append(f"{cluster_size} duplicate or near-duplicate hits")
    return reasons[:3]


def _normalize_geolocation_payload(payload: dict | None) -> dict:
    payload = payload or {}
    best = payload.get("best_result") or {}
    overpass = payload.get("overpass_poi") or {}
    weather = payload.get("weather_corroboration") or {}
    timezone_info = payload.get("timezone") or {}
    deep_ocr = payload.get("deep_ocr_geocoding") or {}
    sun_angle = payload.get("sun_angle") or {}
    vegetation = payload.get("vegetation_zone") or {}
    architecture = payload.get("architecture_hint") or {}
    landmark = payload.get("landmark_detection") or {}
    ocr_geo = payload.get("ocr_geolocation") or {}
    geospy = payload.get("geospy") or {}
    location_signals = payload.get("location_signals") or []

    primary = None
    if isinstance(best, dict) and best.get("lat") is not None and best.get("lon") is not None:
        confidence_pct = 90 if payload.get("source") == "EXIF GPS" else 78 if payload.get("source") == "GeoSpy AI" else 68
        address = (
            best.get("city")
            or overpass.get("verdict")
            or geospy.get("description")
            or geospy.get("city")
            or "Evidence-backed estimate"
        )
        primary = {
            "lat": best.get("lat"),
            "lon": best.get("lon"),
            "address": address,
            "confidence": confidence_pct,
            "confidence_label": "Likely" if confidence_pct >= 75 else "Possible",
            "source": payload.get("source") or "Visual inference",
            "maps_link": best.get("maps_link"),
        }

    evidence = []
    if payload.get("source"):
        evidence.append({"title": "Primary source", "detail": str(payload["source"]), "strength": "High"})
    if overpass.get("verdict"):
        evidence.append({"title": "Nearby map context", "detail": overpass.get("verdict"), "strength": "High"})
    if ocr_geo.get("verdict"):
        evidence.append({"title": "OCR clues", "detail": ocr_geo.get("verdict"), "strength": "Medium"})
    if deep_ocr.get("best_country"):
        evidence.append({"title": "Text-country hint", "detail": deep_ocr.get("best_country"), "strength": "Medium"})
    if landmark.get("best_match"):
        evidence.append({
            "title": "Landmark match",
            "detail": landmark["best_match"].get("location") or landmark["best_match"].get("keyword"),
            "strength": "Medium",
        })
    if sun_angle.get("verdict") and not sun_angle.get("skipped"):
        evidence.append({"title": "Sun angle", "detail": sun_angle["verdict"], "strength": "Low"})
    if vegetation.get("verdict"):
        evidence.append({"title": "Climate/terrain", "detail": vegetation["verdict"], "strength": "Low"})
    if architecture.get("region_hint"):
        evidence.append({"title": "Architecture", "detail": architecture["region_hint"], "strength": "Low"})
    if timezone_info.get("corroborates"):
        evidence.append({"title": "Timezone", "detail": timezone_info["corroborates"][0], "strength": "Low"})
    if weather.get("weather_summary"):
        evidence.append({"title": "Weather corroboration", "detail": weather["weather_summary"], "strength": "Low"})

    next_steps = []
    if not primary:
        next_steps.append("Verify whether the image contains trustworthy EXIF GPS metadata.")
    if not overpass.get("street_names"):
        next_steps.append("Check signage, storefront text, and road markings for location clues.")
    if not weather.get("image_corroboration"):
        next_steps.append("Compare the scene against regional climate and vegetation patterns.")
    if not location_signals:
        next_steps.append("Run additional reverse-search and source-page review for contextual clues.")

    confidence_label = "Unknown"
    if primary:
        confidence_label = primary["confidence_label"]
    elif evidence:
        confidence_label = "Possible"

    return {
        "primary": primary,
        "alternates": [],
        "confidence_label": confidence_label,
        "overall_verdict": payload.get("overall_verdict") or "Unknown",
        "evidence": evidence[:6],
        "location_signals": location_signals[:8],
        "what_to_verify_next": next_steps[:4],
        "raw": payload,
    }


def _cluster_results(items: list[dict]) -> list[dict]:
    clusters: dict[str, dict] = {}
    for raw in items:
        url = raw.get("url")
        if not url:
            continue
        key = normalize_result_url(url)
        cluster = clusters.setdefault(key, {"result_key": key, "items": []})
        cluster["items"].append(raw)

    ordered = []
    for key, cluster in clusters.items():
        normalized_items = []
        for item in cluster["items"]:
            enriched = dict(item)
            enriched["source_domain"] = enriched.get("source_domain") or _domain_for(enriched.get("url"))
            enriched["rank_score"] = _result_rank_score(enriched)
            normalized_items.append(enriched)
        best = max(normalized_items, key=lambda item: (item.get("rank_score", 0), item.get("similarity_pct", 0)))
        engines = sorted({item.get("engine") for item in normalized_items if item.get("engine")})
        domains = sorted({_domain_for(item.get("url")) for item in normalized_items if _domain_for(item.get("url"))})
        score_pct = round(best.get("rank_score", 0) * 100)
        ordered.append({
            "result_key": key,
            "cluster_size": len(normalized_items),
            "rank_score": best.get("rank_score", 0),
            "score_label": _score_label(score_pct),
            "engines": engines,
            "domains": domains,
            "ranking_reasons": _ranking_reasons(best, engines, len(normalized_items)),
            "top_result": best,
            "items": sorted(normalized_items, key=lambda item: (item.get("rank_score", 0), item.get("similarity_pct", 0)), reverse=True),
        })
    ordered.sort(key=lambda item: (item.get("rank_score", 0), item["top_result"].get("similarity_pct", 0)), reverse=True)
    return ordered


@router.post("/search", response_model=SearchResponse, status_code=202)
async def start_search(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    role = current_user.role.value if current_user else "anonymous"
    user_id_str = str(current_user.id) if current_user else None

    allowed, limit, remaining, reset_ts = await check_rate_limit(user_id_str, "image_search", role)
    if not allowed:
        raise HTTPException(
            429,
            "Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_ts),
            },
        )

    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(413, "File too large (max 50MB)")
    if not _magic_bytes_ok(content):
        raise HTTPException(400, "File content does not match image signature")

    file_hash = hashlib.sha256(content).hexdigest()

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{file_hash}{Path(file.filename or 'image.jpg').suffix}"
    if not dest.exists():
        dest.write_bytes(content)

    search = Search(
        user_id=current_user.id if current_user else None,
        filename=file.filename,
        file_hash=file_hash,
        file_path=str(dest),
        status=SearchStatus.pending,
    )
    db.add(search)
    await db.commit()
    await db.refresh(search)

    background_tasks.add_task(search_service.run_analysis, search.id, str(dest))

    return SearchResponse(
        search_id=str(search.id),
        status=search.status.value,
        filename=search.filename,
        created_at=search.created_at.isoformat(),
    )


@router.get("/search/{search_id}/stream")
async def stream_search(
    search_id: str,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    search = await db.get(Search, uuid.UUID(search_id))
    if not search:
        raise HTTPException(404, "Search not found")
    _check_search_access(search, current_user)

    return StreamingResponse(
        search_service.stream_search_events(search_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/search/{search_id}", response_model=SearchResultResponse)
async def get_search(
    search_id: str,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    search = await db.get(Search, uuid.UUID(search_id))
    if not search:
        raise HTTPException(404, "Search not found")
    _check_search_access(search, current_user)
    return SearchResultResponse(
        search_id=str(search.id),
        status=search.status.value,
        results=search.results_json,
        error=search.error,
        duration_ms=search.duration_ms,
        created_at=search.created_at.isoformat(),
        completed_at=search.completed_at.isoformat() if search.completed_at else None,
    )


@router.get("/search/{search_id}/results")
async def get_search_results(
    search_id: str,
    include_hidden: bool = False,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    search = await db.get(Search, uuid.UUID(search_id))
    if not search:
        raise HTTPException(404, "Search not found")
    _check_search_access(search, current_user)

    if not search.results_json:
        return {"results": [], "total_clusters": 0}

    clusters = _cluster_results(_flatten_results(search.results_json))
    state_rows = []
    if current_user:
        state_result = await db.execute(
            select(SearchResultState).where(
                SearchResultState.user_id == current_user.id,
                SearchResultState.search_id == search.id,
            )
        )
        state_rows = state_result.scalars().all()
    state_map = {row.result_key: row for row in state_rows}

    final = []
    for cluster in clusters:
        state = state_map.get(cluster["result_key"])
        payload = {
            **cluster,
            "saved": state.saved if state else False,
            "hidden": state.hidden if state else False,
            "note": state.note if state else None,
        }
        intelligence = analyze_result_cluster(payload)
        payload.update(intelligence)
        if not include_hidden and payload["hidden"]:
            continue
        final.append(payload)

    return {"results": final, "total_clusters": len(final)}


@router.get("/search/{search_id}/intel")
async def get_search_intel(
    search_id: str,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    search = await db.get(Search, uuid.UUID(search_id))
    if not search:
        raise HTTPException(404, "Search not found")
    _check_search_access(search, current_user)
    if not search.results_json:
        raise HTTPException(404, "No results yet")

    clusters = [dict(cluster, **analyze_result_cluster(cluster)) for cluster in _cluster_results(_flatten_results(search.results_json))]
    location = _normalize_geolocation_payload(search.results_json.get("Geolocation", {}))
    entity_domains = sorted({
        domain
        for cluster in clusters
        for domain in (cluster.get("entities") or {}).get("domains", [])
    })[:20]
    contradiction_hints = [
        hint
        for cluster in clusters
        for hint in cluster.get("contradiction_hints", [])
    ][:20]
    recommended_next_steps = [
        "Review the strongest clusters first and reject weak reposts",
        "Run Browser Assist on source-like pages to capture artifacts",
        "Promote only evidence-backed findings into the case workspace",
    ]
    if location.get("what_to_verify_next"):
        recommended_next_steps.extend(location["what_to_verify_next"][:3])
    return {
        "search_id": str(search.id),
        "filename": search.filename,
        "cluster_count": len(clusters),
        "strong_matches": len([c for c in clusters if c.get("triage_lane") == "strong_match"]),
        "possible_matches": len([c for c in clusters if c.get("triage_lane") == "possible_match"]),
        "entity_clues": {"domains": entity_domains},
        "location_hints": location,
        "contradictions": contradiction_hints,
        "recommended_next_steps": recommended_next_steps[:8],
        "clusters": clusters[:25],
        "disclaimer": "OSINT intelligence is an investigative aid, not proof. Verify claims against source provenance.",
    }


@router.patch("/search/{search_id}/results/state")
async def save_result_state(
    search_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    search = await db.get(Search, uuid.UUID(search_id))
    if not search or search.user_id != current_user.id:
        raise HTTPException(404, "Search not found")

    result_key = body.get("result_key")
    if not result_key:
        raise HTTPException(400, "result_key is required")

    state_result = await db.execute(
        select(SearchResultState).where(
            SearchResultState.user_id == current_user.id,
            SearchResultState.search_id == search.id,
            SearchResultState.result_key == result_key,
        )
    )
    state = state_result.scalar_one_or_none()
    if not state:
        state = SearchResultState(user_id=current_user.id, search_id=search.id, result_key=result_key)
        db.add(state)

    if "saved" in body:
        state.saved = bool(body["saved"])
    if "hidden" in body:
        state.hidden = bool(body["hidden"])
    if "note" in body:
        state.note = body["note"] or None
    await db.commit()
    return {"ok": True}


@router.get("/history", response_model=list[SearchHistoryItem])
async def get_history(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Search)
        .where(Search.user_id == current_user.id)
        .order_by(desc(Search.created_at))
        .limit(limit)
        .offset(offset)
    )
    searches = result.scalars().all()
    return [
        SearchHistoryItem(
            search_id=str(s.id),
            filename=s.filename,
            status=s.status.value,
            created_at=s.created_at.isoformat(),
        )
        for s in searches
    ]


@router.delete("/history/{search_id}")
async def delete_search(
    search_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    search = await db.get(Search, uuid.UUID(search_id))
    if not search or search.user_id != current_user.id:
        raise HTTPException(404, "Search not found")
    await db.delete(search)
    await db.commit()
    return {"ok": True}


@router.patch("/search/{search_id}/project")
async def assign_search_project(
    search_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    search = await db.get(Search, uuid.UUID(search_id))
    if not search or search.user_id != current_user.id:
        raise HTTPException(404, "Search not found")
    project_id = body.get("project_id")
    if project_id:
        from models.search import Project
        proj = await db.get(Project, uuid.UUID(project_id))
        if not proj or proj.user_id != current_user.id:
            raise HTTPException(404, "Project not found")
        search.project_id = proj.id
    else:
        search.project_id = None
    await db.commit()
    return {"ok": True, "project_id": str(search.project_id) if search.project_id else None}


@router.get("/metadata/{search_id}")
async def get_metadata(
    search_id: str,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    search = await db.get(Search, uuid.UUID(search_id))
    if not search:
        raise HTTPException(404, "Search not found")
    _check_search_access(search, current_user)
    if not search.results_json:
        raise HTTPException(404, "No results yet")
    results = search.results_json
    return {
        "exif": results.get("EXIF & Metadata"),
        "forensics": results.get("Forensics (ELA)"),
        "steganography": results.get("Steganography"),
        "ai_analysis": results.get("AI Analysis (CLIP/DeepFace)"),
    }


@router.get("/geolocate/{search_id}")
async def get_geolocation(
    search_id: str,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    search = await db.get(Search, uuid.UUID(search_id))
    if not search:
        raise HTTPException(404, "Search not found")
    _check_search_access(search, current_user)
    if not search.results_json:
        raise HTTPException(404, "No results yet")
    return _normalize_geolocation_payload(search.results_json.get("Geolocation", {}))


@router.get("/search/{search_id}/export")
async def export_search(
    search_id: str,
    format: str = Query("json", pattern="^(json|md|pdf|html)$"),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    import json as _json
    from fastapi.responses import Response

    search = await db.get(Search, uuid.UUID(search_id))
    if not search:
        raise HTTPException(404, "Search not found")
    _check_search_access(search, current_user)
    if not search.results_json:
        raise HTTPException(404, "No results yet")

    results = search.results_json
    base = search.filename or "vision-report"

    if format == "json":
        content = _json.dumps(results, indent=2, default=str).encode()
        return Response(content, media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{base}.json"'})

    elif format == "md":
        lines = [f"# VISION OSINT Report\n\n**Image:** {base}\n"]
        dossier = results.get("AI Dossier", {})
        if dossier.get("dossier"):
            lines.append(dossier["dossier"])
        else:
            for stage, data in results.items():
                if isinstance(data, dict) and not data.get("error") and not data.get("skipped"):
                    lines.append(f"\n## {stage}\n```json\n{_json.dumps(data, indent=2, default=str)[:2000]}\n```")
        content = "\n".join(lines).encode()
        return Response(content, media_type="text/markdown",
                        headers={"Content-Disposition": f'attachment; filename="{base}.md"'})

    elif format == "html":
        dossier_md = results.get("AI Dossier", {}).get("dossier", "")
        # Convert basic markdown to HTML inline (no external dep needed for simple output)
        import re
        html_body = dossier_md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_body = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html_body, flags=re.MULTILINE)
        html_body = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html_body, flags=re.MULTILINE)
        html_body = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html_body)
        html_body = re.sub(r"^- (.+)$", r"<li>\1</li>", html_body, flags=re.MULTILINE)
        html_body = f"<ul>{html_body}</ul>" if "<li>" in html_body else html_body
        html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>VISION Report — {base}</title>
<style>body{{font-family:monospace;background:#0d1117;color:#e6edf3;padding:2rem;max-width:900px;margin:auto}}
h1,h2{{color:#00ff88}}pre{{background:#161b22;padding:1rem;border-radius:.5rem;overflow-x:auto}}</style>
</head><body><h1>VISION OSINT Report</h1><p><strong>Image:</strong> {base}</p>
{html_body}</body></html>"""
        return Response(html.encode(), media_type="text/html",
                        headers={"Content-Disposition": f'attachment; filename="{base}.html"'})

    elif format == "pdf":
        try:
            import weasyprint
            html_res = await export_search(search_id, "html", current_user, db)
            pdf_bytes = weasyprint.HTML(string=html_res.body.decode()).write_pdf()
            return Response(pdf_bytes, media_type="application/pdf",
                            headers={"Content-Disposition": f'attachment; filename="{base}.pdf"'})
        except ImportError:
            raise HTTPException(501, "PDF export requires weasyprint. Install it or use html/md format.")


@router.get("/search/global")
async def global_search(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(20, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search across projects, searches, collections, and chat sessions."""
    from sqlalchemy import func
    from models.search import Project, Collection
    from models.research import ChatSession

    pattern = f"%{q.lower()}%"
    results = []

    proj_r = await db.execute(
        select(Project)
        .where(Project.user_id == current_user.id)
        .where(func.lower(Project.name).like(pattern))
        .limit(limit)
    )
    for p in proj_r.scalars().all():
        results.append({"type": "project", "id": str(p.id), "label": p.name, "url": f"/projects/{p.id}"})

    srch_r = await db.execute(
        select(Search)
        .where(Search.user_id == current_user.id)
        .where(func.lower(Search.filename).like(pattern))
        .order_by(desc(Search.created_at))
        .limit(limit)
    )
    for s in srch_r.scalars().all():
        results.append({"type": "search", "id": str(s.id), "label": s.filename or str(s.id), "url": f"/search?id={s.id}"})

    col_r = await db.execute(
        select(Collection)
        .where(Collection.user_id == current_user.id)
        .where(func.lower(Collection.name).like(pattern))
        .limit(limit)
    )
    for c in col_r.scalars().all():
        results.append({"type": "collection", "id": str(c.id), "label": c.name, "url": "/collections"})

    chat_r = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .where(ChatSession.is_incognito == False)  # noqa: E712
        .where(func.lower(ChatSession.title).like(pattern))
        .limit(limit)
    )
    for c in chat_r.scalars().all():
        results.append({"type": "chat", "id": str(c.id), "label": c.title, "url": "/research"})

    return {"results": results, "query": q}


@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate stats for the current user's searches."""
    from sqlalchemy import select, func
    from datetime import date, timedelta
    result = await db.execute(
        select(Search).where(Search.user_id == current_user.id, Search.status == SearchStatus.done)
    )
    searches = result.scalars().all()

    total_faces = 0
    total_geolocated = 0
    total_threats = 0

    # Build daily counts for last 30 days
    today = date.today()
    daily: dict[str, int] = {str(today - timedelta(days=i)): 0 for i in range(29, -1, -1)}

    for s in searches:
        day_str = str(s.created_at.date()) if s.created_at else None
        if day_str and day_str in daily:
            daily[day_str] += 1

        if not s.results_json:
            continue
        r = s.results_json
        face_data = r.get("Face & Object Detection", {})
        total_faces += len(face_data.get("faces", []))
        geo = r.get("Geolocation", {})
        if geo.get("best_guess") or geo.get("gps") or geo.get("primary"):
            total_geolocated += 1
        leaks = r.get("Leaked Credentials", {})
        total_threats += sum(e.get("breach_count", 0) for e in leaks.get("emails_checked", []))
        dw = r.get("Dark Web Mentions", {})
        total_threats += dw.get("summary", {}).get("total_dark_web_mentions", 0)

    return {
        "total_searches": len(searches),
        "total_faces": total_faces,
        "total_geolocated": total_geolocated,
        "total_threats": total_threats,
        "daily": daily,
    }
