"""
FaceDB — Local ArcFace Face Database Engine
============================================
Builds and searches a local database of face embeddings using InsightFace
(ArcFace model, 99.4% LFW accuracy). Acts as your personal PimEyes —
index any folder of images, then search for matches with cosine similarity.

Usage:
    from facedb import FaceDB
    db = FaceDB()
    db.index_folder("./my_images/")
    results = db.search("suspect.jpg", top_k=10)

CLI:
    python facedb.py index ./photos/
    python facedb.py search face.jpg
    python facedb.py list
    python facedb.py stats
"""

import os
import json
import time
import sqlite3
import hashlib
import argparse
import numpy as np
from pathlib import Path
from typing import Optional

# ── Try InsightFace first, fall back to DeepFace, then face_recognition ───────
BACKEND = None

try:
    import insightface
    from insightface.app import FaceAnalysis
    BACKEND = "insightface"
except ImportError:
    pass

if BACKEND is None:
    try:
        from deepface import DeepFace
        BACKEND = "deepface"
    except ImportError:
        pass

if BACKEND is None:
    try:
        import face_recognition
        BACKEND = "face_recognition"
    except ImportError:
        pass

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}

DB_PATH = Path(__file__).parent.parent / "facedb" / "faces.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_DEFAULT_USER = "__global__"  # Legacy/CLI-only sentinel — HTTP routes always pass user_id


# ── InsightFace app singleton ──────────────────────────────────────────────────
_insight_app = None

def _get_insight_app():
    global _insight_app
    if _insight_app is None and BACKEND == "insightface":
        try:
            app = FaceAnalysis(
                name="buffalo_l",           # ArcFace R100 — most accurate
                providers=["CPUExecutionProvider"],
            )
            app.prepare(ctx_id=0, det_size=(640, 640))
            _insight_app = app
        except Exception as e:
            print(f"[FaceDB] InsightFace init failed: {e}")
    return _insight_app


# ── Embedding extraction ───────────────────────────────────────────────────────

def extract_embeddings(image_path: str) -> list[dict]:
    """
    Extract face embeddings from an image.
    Returns list of dicts: {embedding, bbox, confidence, age, gender}
    """
    results = []
    path = str(Path(image_path).resolve())

    if BACKEND == "insightface":
        app = _get_insight_app()
        if app is None:
            return results
        try:
            import cv2
            img = cv2.imread(path)
            if img is None:
                return results
            faces = app.get(img)
            for face in faces:
                emb = face.embedding
                results.append({
                    "embedding": emb.tolist(),
                    "bbox": [int(x) for x in face.bbox.tolist()],
                    "confidence": float(face.det_score),
                    "age": int(face.age) if hasattr(face, "age") else None,
                    "gender": ("M" if face.gender == 1 else "F") if hasattr(face, "gender") else None,
                })
        except Exception as e:
            print(f"[FaceDB] InsightFace extract error: {e}")

    elif BACKEND == "deepface":
        try:
            # DeepFace returns embeddings per detected face
            rep = DeepFace.represent(
                img_path=path,
                model_name="ArcFace",
                enforce_detection=False,
            )
            if isinstance(rep, list):
                for r in rep:
                    results.append({
                        "embedding": r.get("embedding", []),
                        "bbox": r.get("facial_area", {}),
                        "confidence": r.get("face_confidence", 1.0),
                        "age": None,
                        "gender": None,
                    })
            else:
                results.append({
                    "embedding": rep.get("embedding", []),
                    "bbox": rep.get("facial_area", {}),
                    "confidence": 1.0,
                    "age": None,
                    "gender": None,
                })
        except Exception as e:
            print(f"[FaceDB] DeepFace extract error: {e}")

    elif BACKEND == "face_recognition":
        try:
            import face_recognition as fr
            img = fr.load_image_file(path)
            locs = fr.face_locations(img, model="cnn" if _has_gpu() else "hog")
            encs = fr.face_encodings(img, locs)
            for enc, loc in zip(encs, locs):
                top, right, bottom, left = loc
                results.append({
                    "embedding": enc.tolist(),
                    "bbox": [left, top, right, bottom],
                    "confidence": 1.0,
                    "age": None,
                    "gender": None,
                })
        except Exception as e:
            print(f"[FaceDB] face_recognition extract error: {e}")

    return results


def _has_gpu() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def cosine_similarity(a: list, b: list) -> float:
    """Cosine similarity between two embedding vectors. 1.0 = identical."""
    va = np.array(a, dtype=float)
    vb = np.array(b, dtype=float)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def similarity_to_confidence(sim: float) -> tuple[float, str]:
    """Convert cosine similarity to a human-readable confidence label."""
    pct = round(sim * 100, 1)
    if sim >= 0.70:
        label = "🔴 HIGH MATCH"
    elif sim >= 0.55:
        label = "🟡 LIKELY MATCH"
    elif sim >= 0.40:
        label = "🟠 POSSIBLE MATCH"
    else:
        label = "⚪ LOW SIMILARITY"
    return pct, label


# ── Database layer ─────────────────────────────────────────────────────────────

class FaceDB:
    """
    SQLite-backed local face embedding database.
    Supports indexing folders of images, searching for matches,
    and exporting results.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._init_schema()

    def _init_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS faces (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL DEFAULT '__global__',
                image_path  TEXT NOT NULL,
                image_hash  TEXT NOT NULL,
                face_index  INTEGER NOT NULL,
                embedding   TEXT NOT NULL,
                bbox        TEXT,
                confidence  REAL,
                age         INTEGER,
                gender      TEXT,
                label       TEXT,
                tags        TEXT,
                indexed_at  TEXT NOT NULL,
                UNIQUE(user_id, image_hash, face_index)
            );
            CREATE TABLE IF NOT EXISTS labels (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL DEFAULT '__global__',
                image_hash  TEXT NOT NULL,
                face_index  INTEGER NOT NULL,
                label       TEXT NOT NULL,
                created_at  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_image_hash ON faces(image_hash);
            CREATE INDEX IF NOT EXISTS idx_label ON faces(label);
            CREATE INDEX IF NOT EXISTS idx_user_id ON faces(user_id);
        """)
        # Migrate existing rows that lack user_id (first deploy after schema change)
        self._conn.execute(
            "UPDATE faces SET user_id = '__global__' WHERE user_id IS NULL OR user_id = ''"
        )
        self._conn.commit()

    def _hash_file(self, path: str) -> str:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    # ── Index ──────────────────────────────────────────────────────────────────

    def index_image(self, image_path: str, label: str = "", tags: str = "", user_id: str = "") -> int:
        """
        Extract and store all faces from a single image.
        Returns number of faces indexed.
        """
        uid = user_id or _DEFAULT_USER
        path = Path(image_path).resolve()
        if not path.exists():
            print(f"[FaceDB] Not found: {image_path}")
            return 0

        img_hash = self._hash_file(str(path))

        # Check if already indexed for this user
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM faces WHERE user_id = ? AND image_hash = ?", (uid, img_hash)
        )
        existing = cur.fetchone()[0]
        if existing > 0:
            print(f"[FaceDB] Already indexed: {path.name} ({existing} face(s))")
            return 0

        embeddings = extract_embeddings(str(path))
        count = 0
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")

        for i, face in enumerate(embeddings):
            emb_json = json.dumps(face["embedding"])
            bbox_json = json.dumps(face.get("bbox", []))
            try:
                self._conn.execute(
                    """INSERT OR IGNORE INTO faces
                       (user_id, image_path, image_hash, face_index, embedding, bbox,
                        confidence, age, gender, label, tags, indexed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        uid, str(path), img_hash, i,
                        emb_json, bbox_json,
                        face.get("confidence", 1.0),
                        face.get("age"),
                        face.get("gender"),
                        label, tags, ts,
                    )
                )
                count += 1
            except sqlite3.IntegrityError:
                pass

        self._conn.commit()
        if count:
            print(f"[FaceDB] Indexed {count} face(s) from {path.name}")
        return count

    def index_folder(
        self,
        folder: str,
        label: str = "",
        tags: str = "",
        recursive: bool = True,
        user_id: str = "",
    ) -> dict:
        """Index all images in a folder (optionally recursive)."""
        folder_path = Path(folder).resolve()
        if not folder_path.is_dir():
            print(f"[FaceDB] Not a directory: {folder}")
            return {}

        glob = folder_path.rglob("*") if recursive else folder_path.glob("*")
        images = [p for p in glob if p.suffix.lower() in IMAGE_EXTS and p.is_file()]

        print(f"[FaceDB] Found {len(images)} image(s) in {folder}")
        total_faces = 0
        total_images = 0

        for img in images:
            n = self.index_image(str(img), label=label, tags=tags, user_id=user_id)
            if n > 0:
                total_faces += n
                total_images += 1

        return {
            "images_scanned": len(images),
            "images_with_faces": total_images,
            "faces_indexed": total_faces,
        }

    # ── Search ─────────────────────────────────────────────────────────────────

    def search(
        self,
        image_path: str,
        top_k: int = 20,
        min_similarity: float = 0.35,
        label_filter: str = "",
        user_id: str = "",
    ) -> list[dict]:
        """
        Search the database for faces matching those in image_path.
        Returns ranked list of matches with similarity scores.
        """
        uid = user_id or _DEFAULT_USER
        query_embeddings = extract_embeddings(image_path)
        if not query_embeddings:
            print(f"[FaceDB] No faces detected in query image: {image_path}")
            return []

        # Load embeddings scoped to this user
        query = "SELECT id, image_path, image_hash, face_index, embedding, bbox, confidence, age, gender, label, tags FROM faces WHERE user_id = ?"
        params: list = [uid]
        if label_filter:
            query += " AND label LIKE ?"
            params.append(f"%{label_filter}%")

        rows = self._conn.execute(query, params).fetchall()
        if not rows:
            print("[FaceDB] Database is empty — index some images first.")
            return []

        all_matches = []

        for q_face in query_embeddings:
            q_emb = q_face["embedding"]
            face_matches = []

            for row in rows:
                (row_id, img_path, img_hash, face_idx,
                 emb_json, bbox_json, conf, age, gender, lbl, tags) = row

                try:
                    stored_emb = json.loads(emb_json)
                    sim = cosine_similarity(q_emb, stored_emb)
                    if sim >= min_similarity:
                        pct, confidence_label = similarity_to_confidence(sim)
                        face_matches.append({
                            "db_id": row_id,
                            "image_path": img_path,
                            "image_hash": img_hash,
                            "face_index": face_idx,
                            "similarity": round(sim, 4),
                            "similarity_pct": pct,
                            "confidence_label": confidence_label,
                            "bbox": json.loads(bbox_json) if bbox_json else [],
                            "age": age,
                            "gender": gender,
                            "label": lbl,
                            "tags": tags,
                        })
                except Exception:
                    continue

            # Sort by similarity descending
            face_matches.sort(key=lambda x: x["similarity"], reverse=True)
            all_matches.extend(face_matches[:top_k])

        # Deduplicate by image_hash+face_index, keep highest similarity
        seen = {}
        for m in all_matches:
            key = f"{m['image_hash']}_{m['face_index']}"
            if key not in seen or m["similarity"] > seen[key]["similarity"]:
                seen[key] = m

        final = sorted(seen.values(), key=lambda x: x["similarity"], reverse=True)
        return final[:top_k]

    def search_embedding(
        self,
        embedding: list,
        top_k: int = 20,
        min_similarity: float = 0.35,
        user_id: str = "",
    ) -> list[dict]:
        """Search using a raw embedding vector (for pipeline integration)."""
        uid = user_id or _DEFAULT_USER
        rows = self._conn.execute(
            "SELECT id, image_path, image_hash, face_index, embedding, bbox, confidence, age, gender, label, tags FROM faces WHERE user_id = ?",
            (uid,)
        ).fetchall()

        matches = []
        for row in rows:
            (row_id, img_path, img_hash, face_idx,
             emb_json, bbox_json, conf, age, gender, lbl, tags) = row
            try:
                stored_emb = json.loads(emb_json)
                sim = cosine_similarity(embedding, stored_emb)
                if sim >= min_similarity:
                    pct, label = similarity_to_confidence(sim)
                    matches.append({
                        "db_id": row_id,
                        "image_path": img_path,
                        "similarity": round(sim, 4),
                        "similarity_pct": pct,
                        "confidence_label": label,
                        "bbox": json.loads(bbox_json) if bbox_json else [],
                        "age": age,
                        "gender": gender,
                        "label": lbl,
                    })
            except Exception:
                continue

        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches[:top_k]

    # ── Label management ───────────────────────────────────────────────────────

    def label_face(self, image_hash: str, face_index: int, label: str, user_id: str = ""):
        """Assign a name/label to a specific face in the database."""
        uid = user_id or _DEFAULT_USER
        self._conn.execute(
            "UPDATE faces SET label = ? WHERE user_id = ? AND image_hash = ? AND face_index = ?",
            (label, uid, image_hash, face_index)
        )
        self._conn.execute(
            "INSERT INTO labels (user_id, image_hash, face_index, label, created_at) VALUES (?, ?, ?, ?, ?)",
            (uid, image_hash, face_index, label, time.strftime("%Y-%m-%dT%H:%M:%S"))
        )
        self._conn.commit()
        print(f"[FaceDB] Labeled face {face_index} in hash {image_hash[:8]}... as '{label}'")

    # ── Stats & listing ────────────────────────────────────────────────────────

    def stats(self, user_id: str = "") -> dict:
        uid = user_id or _DEFAULT_USER
        total_faces  = self._conn.execute("SELECT COUNT(*) FROM faces WHERE user_id = ?", (uid,)).fetchone()[0]
        total_images = self._conn.execute("SELECT COUNT(DISTINCT image_hash) FROM faces WHERE user_id = ?", (uid,)).fetchone()[0]
        labeled      = self._conn.execute("SELECT COUNT(*) FROM faces WHERE user_id = ? AND label != ''", (uid,)).fetchone()[0]
        labels       = self._conn.execute(
            "SELECT label, COUNT(*) as c FROM faces WHERE user_id = ? AND label != '' GROUP BY label ORDER BY c DESC",
            (uid,)
        ).fetchall()

        return {
            "backend": BACKEND or "none",
            "db_path": str(self.db_path),
            "total_faces": total_faces,
            "total_images": total_images,
            "labeled_faces": labeled,
            "unlabeled_faces": total_faces - labeled,
            "known_people": [{"label": l, "face_count": c} for l, c in labels],
        }

    def list_images(self, limit: int = 50, user_id: str = "") -> list[dict]:
        uid = user_id or _DEFAULT_USER
        rows = self._conn.execute(
            """SELECT image_path, image_hash, COUNT(*) as face_count,
               GROUP_CONCAT(DISTINCT label) as labels, indexed_at
               FROM faces WHERE user_id = ? GROUP BY image_hash
               ORDER BY indexed_at DESC LIMIT ?""",
            (uid, limit)
        ).fetchall()
        return [
            {
                "image": Path(r[0]).name,
                "path": r[0],
                "hash": r[1],
                "face_count": r[2],
                "labels": r[3] or "",
                "indexed_at": r[4],
            }
            for r in rows
        ]

    def remove_image(self, image_hash: str, user_id: str = ""):
        """Remove all faces with a given image_hash for a user."""
        uid = user_id or _DEFAULT_USER
        self._conn.execute("DELETE FROM faces WHERE user_id = ? AND image_hash = ?", (uid, image_hash))
        self._conn.commit()
        print(f"[FaceDB] Removed faces for hash {image_hash[:8]}...")

    def export_csv(self, output_path: str):
        """Export the full database to CSV."""
        import csv
        rows = self._conn.execute(
            "SELECT image_path, face_index, confidence, age, gender, label, tags, indexed_at FROM faces"
        ).fetchall()
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["image_path", "face_index", "confidence", "age", "gender", "label", "tags", "indexed_at"])
            writer.writerows(rows)
        print(f"[FaceDB] Exported {len(rows)} faces to {output_path}")

    def close(self):
        self._conn.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def _print_results(results: list[dict]):
    if not results:
        print("No matches found.")
        return
    print(f"\n{'─'*70}")
    print(f"{'RANK':<5} {'SIMILARITY':>10} {'CONFIDENCE':<20} {'LABEL':<15} {'FILE'}")
    print(f"{'─'*70}")
    for i, r in enumerate(results, 1):
        label = r.get("label") or "—"
        fname = Path(r["image_path"]).name
        print(f"  {i:<3}  {r['similarity_pct']:>7.1f}%  {r['confidence_label']:<22}  {label:<15}  {fname}")
    print(f"{'─'*70}\n")


def main():
    p = argparse.ArgumentParser(description="FaceDB — Local ArcFace Face Database")
    sub = p.add_subparsers(dest="cmd", required=True)

    # index
    pi = sub.add_parser("index", help="Index images into the database")
    pi.add_argument("path", help="Image file or folder to index")
    pi.add_argument("--label", default="", help="Label/name for these faces")
    pi.add_argument("--tags",  default="", help="Tags for these faces")
    pi.add_argument("--no-recursive", action="store_true")

    # search
    ps = sub.add_parser("search", help="Search for matching faces")
    ps.add_argument("image", help="Query image")
    ps.add_argument("--top",     type=int,   default=20,   help="Max results")
    ps.add_argument("--min-sim", type=float, default=0.35, help="Min similarity (0-1)")
    ps.add_argument("--label",   default="",               help="Filter by label")

    # label
    pl = sub.add_parser("label", help="Label a face in the database")
    pl.add_argument("image", help="Image containing the face")
    pl.add_argument("face_index", type=int, help="Face index (0 = first face)")
    pl.add_argument("label", help="Name/label to assign")

    # list
    sub.add_parser("list", help="List indexed images")

    # stats
    sub.add_parser("stats", help="Show database statistics")

    # export
    pe = sub.add_parser("export", help="Export database to CSV")
    pe.add_argument("output", help="Output CSV file path")

    args = p.parse_args()
    db = FaceDB()

    if args.cmd == "index":
        target = Path(args.path)
        if target.is_dir():
            result = db.index_folder(
                str(target),
                label=args.label,
                tags=args.tags,
                recursive=not args.no_recursive,
            )
            print(f"\nIndexed: {result['faces_indexed']} face(s) from {result['images_with_faces']} image(s)")
        else:
            n = db.index_image(str(target), label=args.label, tags=args.tags)
            print(f"Indexed: {n} face(s)")

    elif args.cmd == "search":
        print(f"Searching for matches to: {args.image}")
        results = db.search(args.image, top_k=args.top, min_similarity=args.min_sim, label_filter=args.label)
        _print_results(results)

    elif args.cmd == "label":
        db.label_face(args.image, args.face_index, args.label)

    elif args.cmd == "list":
        images = db.list_images()
        print(f"\n{'FILE':<35} {'FACES':>6} {'LABELS':<20} {'INDEXED'}")
        print("─" * 80)
        for img in images:
            print(f"  {img['image']:<33}  {img['face_count']:>4}   {img['labels']:<20}  {img['indexed_at']}")

    elif args.cmd == "stats":
        s = db.stats()
        print(f"\n=== FaceDB Statistics ===")
        print(f"  Backend:        {s['backend']}")
        print(f"  DB path:        {s['db_path']}")
        print(f"  Total faces:    {s['total_faces']}")
        print(f"  Total images:   {s['total_images']}")
        print(f"  Labeled:        {s['labeled_faces']}")
        print(f"  Unlabeled:      {s['unlabeled_faces']}")
        if s["known_people"]:
            print(f"\n  Known people:")
            for p in s["known_people"]:
                print(f"    {p['label']}: {p['face_count']} face(s)")

    elif args.cmd == "export":
        db.export_csv(args.output)

    db.close()


if __name__ == "__main__":
    main()
