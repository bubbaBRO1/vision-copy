"""
FaceDB HTTP Router — Local Face Database API

Exposes the FaceDB engine over HTTP for the frontend DIY PimEyes feature.
All routes require authentication. Folder indexing runs as a background task.
"""

import sys
import json
import base64
import tempfile
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Auth dependency — reuse existing
sys.path.insert(0, str(Path(__file__).parent.parent))
from routers.deps import get_current_user
from models.user import User

router = APIRouter(prefix="/api/faces", tags=["facedb"])


def _image_thumbnail_b64(image_path: str | None, size: tuple[int, int] = (96, 96)) -> str | None:
    if not image_path:
        return None
    try:
        from PIL import Image as PILImage
        import io

        path = Path(image_path)
        if not path.exists():
            return None
        with PILImage.open(path) as img:
            img.thumbnail(size)
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=80)
            return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def _get_db():
    """Lazy import FaceDB to avoid import-time errors if face libs are missing."""
    try:
        from stages.facedb import FaceDB
        return FaceDB()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"FaceDB unavailable: {e}")


# ── Schemas ────────────────────────────────────────────────────────────────────

class IndexFolderRequest(BaseModel):
    folder: str
    label: Optional[str] = ""
    tags:  Optional[str] = ""

class RemoveRequest(BaseModel):
    image_hash: str

class LabelRequest(BaseModel):
    image_hash: str
    face_index: int
    label: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(current_user: User = Depends(get_current_user)):
    db = _get_db()
    try:
        stats = db.stats(user_id=str(current_user.id))
        stats["known_people"] = len(stats.get("known_people", []))
        return stats
    finally:
        db.close()


@router.get("/index/stats")
async def get_index_stats(current_user: User = Depends(get_current_user)):
    """Alias stats endpoint for face index health."""
    return await get_stats(current_user)


@router.get("/list")
async def list_faces(
    limit: int = 100,
    current_user: User = Depends(get_current_user),
):
    """List indexed images grouped by person label, scoped to current user."""
    db = _get_db()
    uid = str(current_user.id)
    try:
        conn = db._conn
        rows = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(label,''), '__unlabeled__') as person_label,
                image_hash,
                image_path,
                COUNT(*) as face_count,
                MIN(indexed_at) as indexed_at,
                AVG(confidence) as avg_confidence
            FROM faces
            WHERE user_id = ?
            GROUP BY COALESCE(NULLIF(label,''), '__unlabeled__'), image_hash
            ORDER BY person_label, indexed_at DESC
            LIMIT ?
            """,
            (uid, limit)
        ).fetchall()

        # Group by person label
        persons: dict = {}
        for person_label, image_hash, image_path, face_count, indexed_at, avg_conf in rows:
            if person_label not in persons:
                persons[person_label] = {
                    "id": image_hash,  # Use first hash as person ID
                    "label": "" if person_label == "__unlabeled__" else person_label,
                    "face_count": 0,
                    "indexed_at": indexed_at,
                    "thumbnail": None,
                    "crops": [],
                }
            persons[person_label]["face_count"] += face_count

            # Get a thumbnail crop for the first image
            if persons[person_label]["thumbnail"] is None:
                try:
                    from PIL import Image as PILImage
                    import io
                    img_path = Path(image_path)
                    if img_path.exists():
                        with PILImage.open(img_path) as img:
                            img.thumbnail((96, 96))
                            buf = io.BytesIO()
                            img.save(buf, format="JPEG", quality=80)
                            persons[person_label]["thumbnail"] = base64.b64encode(buf.getvalue()).decode()
                except Exception:
                    pass

        return list(persons.values())
    finally:
        db.close()


_ALLOWED_INDEX_ROOT: str | None = None

def _get_allowed_index_root() -> str:
    """Server-side folder indexing is restricted to a configured base path."""
    import os
    root = os.environ.get("FACEDB_INDEX_ROOT", "")
    return root


@router.post("/index")
async def index_folder(
    request: IndexFolderRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Index all images in a server-side folder path.

    Requires FACEDB_INDEX_ROOT env var to be set; paths outside it are rejected
    to prevent path traversal attacks.
    """
    allowed_root = _get_allowed_index_root()
    if not allowed_root:
        raise HTTPException(
            status_code=503,
            detail="Server-side folder indexing is disabled. Use /index-upload instead.",
        )

    try:
        folder = Path(request.folder).resolve()
        root = Path(allowed_root).resolve()
        folder.relative_to(root)  # raises ValueError if outside root
    except ValueError:
        raise HTTPException(status_code=403, detail="Folder path outside allowed root")

    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"Folder not found: {request.folder}")

    uid = str(current_user.id)

    def _run_index():
        db = _get_db()
        try:
            db.index_folder(str(folder), label=request.label or "", tags=request.tags or "", user_id=uid)
        finally:
            db.close()

    background_tasks.add_task(_run_index)
    return {"status": "indexing_started", "folder": str(folder), "label": request.label}


ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp", "image/tiff"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB


@router.post("/index-upload")
async def index_upload(
    file: UploadFile = File(...),
    label: str = Form(default=""),
    current_user: User = Depends(get_current_user),
):
    """Index a single uploaded image file."""
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="File must be an image (jpeg/png/webp/gif/bmp/tiff)")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 20MB)")

    suffix = Path(file.filename or "upload.jpg").suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif"}:
        suffix = ".jpg"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        db = _get_db()
        n = db.index_image(tmp_path, label=label, user_id=str(current_user.id))
        db.close()
        return {"faces_indexed": n, "label": label}
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@router.delete("/remove")
async def remove_face(
    request: RemoveRequest,
    current_user: User = Depends(get_current_user),
):
    """Remove all faces with a given image_hash owned by the current user."""
    db = _get_db()
    try:
        db.remove_image(request.image_hash, user_id=str(current_user.id))
        return {"status": "removed", "image_hash": request.image_hash}
    finally:
        db.close()


@router.post("/label")
async def label_face(
    request: LabelRequest,
    current_user: User = Depends(get_current_user),
):
    """Update the label for a face owned by the current user."""
    db = _get_db()
    try:
        db.label_face(request.image_hash, request.face_index, request.label, user_id=str(current_user.id))
        return {"status": "labeled", "label": request.label}
    finally:
        db.close()


@router.get("/search/{search_id}")
async def search_face_db(
    search_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Search the local face database using embeddings from a completed search.
    Pulls stored face crops/embeddings from the search results JSON.
    """
    from database import AsyncSessionLocal
    from models.search import Search
    from sqlalchemy import select

    import uuid as uuid_lib
    try:
        sid = uuid_lib.UUID(search_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid search ID")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Search).where(Search.id == sid))
        search = result.scalar_one_or_none()

    if not search:
        raise HTTPException(status_code=404, detail="Search not found")

    if search.user_id and search.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    results_json = search.results_json or {}
    if isinstance(results_json, str):
        try:
            results_json = json.loads(results_json)
        except Exception:
            return {"results": [], "message": "Could not parse search results"}

    # Extract face crops from Stage 4 results
    face_data = results_json.get("Face & Object Detection", {})
    faces = face_data.get("faces", [])

    if not faces:
        return {"results": [], "message": "No faces detected in this search"}

    db = _get_db()
    try:
        all_matches = []
        for face in faces:
            crop_b64 = face.get("crop_b64")
            if not crop_b64:
                continue

            # Save crop to temp file and extract embedding
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(base64.b64decode(crop_b64))
                crop_path = tmp.name

            try:
                from stages.facedb import extract_embeddings
                embeddings = extract_embeddings(crop_path)
                for emb_data in embeddings:
                    matches = db.search_embedding(emb_data["embedding"], top_k=5, user_id=str(current_user.id))
                    for m in matches:
                        all_matches.append({
                            "label":      m.get("label") or "Unknown",
                            "similarity": round(m.get("similarity_pct", 0)),
                            "confidence": m.get("confidence_label", ""),
                            "thumbnail":  _image_thumbnail_b64(m.get("image_path")),
                            "source_url": m.get("source_url"),
                            "page_url": m.get("page_url"),
                            "tags": m.get("tags", []),
                        })
            finally:
                try:
                    os.unlink(crop_path)
                except Exception:
                    pass

        # Deduplicate by label, keep highest similarity
        seen: dict = {}
        for m in all_matches:
            key = m["label"]
            if key not in seen or m["similarity"] > seen[key]["similarity"]:
                seen[key] = m

        final = sorted(seen.values(), key=lambda x: x["similarity"], reverse=True)
        return {"results": final[:10], "total": len(final)}

    finally:
        db.close()


@router.post("/search")
async def search_face_upload(
    image: UploadFile = File(...),
    top_k: int = Form(default=20),
    min_similarity: float = Form(default=0.35),
    current_user: User = Depends(get_current_user),
):
    """Search the local face database directly from an uploaded image."""
    if image.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="File must be an image (jpeg/png/webp/gif/bmp/tiff)")

    data = await image.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 20MB)")

    suffix = Path(image.filename or "query.jpg").suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif"}:
        suffix = ".jpg"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    started = time.perf_counter()
    db = _get_db()
    try:
        from stages.facedb import extract_embeddings

        embeddings = extract_embeddings(tmp_path)
        matches = []
        for emb_data in embeddings:
            for match in db.search_embedding(emb_data["embedding"], top_k=top_k, user_id=str(current_user.id)):
                similarity = float(match.get("similarity_pct", 0)) / 100.0
                if similarity < min_similarity:
                    continue
                if similarity >= 0.90:
                    label = "Likely Match"
                elif similarity >= 0.70:
                    label = "Possible Match"
                else:
                    label = "Weak Signal"
                matches.append({
                    "id": match.get("id") or f"{match.get('image_hash')}:{match.get('face_index', 0)}",
                    "similarity_score": round(similarity, 4),
                    "confidence_label": label,
                    "face_crop_url": None,
                    "thumbnail": _image_thumbnail_b64(match.get("image_path")),
                    "source_url": match.get("source_url"),
                    "page_url": match.get("page_url"),
                    "indexed_at": match.get("indexed_at"),
                    "label": match.get("label"),
                    "tags": match.get("tags", []),
                })

        matches.sort(key=lambda item: item["similarity_score"], reverse=True)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "query_face_crop": None,
            "search_time_ms": elapsed_ms,
            "total_matches": len(matches),
            "matches": matches[:top_k],
            "pagination": {"limit": top_k, "offset": 0, "total": len(matches)},
        }
    finally:
        db.close()
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
