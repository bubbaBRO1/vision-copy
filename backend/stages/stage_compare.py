"""
Stage — Image Comparison
========================
Compare two images for: perceptual hash similarity, face match, GPS distance,
ELA difference, and metadata divergence.

Usage:
    from stages.stage_compare import compare_images
    result = compare_images("image_a.jpg", "image_b.jpg")

    # CLI:
    python stages/stage_compare.py imageA.jpg imageB.jpg
"""

import os
import math
import hashlib
import struct
from pathlib import Path

# ── Haversine GPS distance ────────────────────────────────────────────────────

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in metres between two GPS coordinates."""
    R = 6_371_000  # Earth radius metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlam  = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── pHash similarity ──────────────────────────────────────────────────────────

def _phash_similarity(hex_a: str, hex_b: str) -> tuple[int, float]:
    """
    Compute Hamming distance and similarity % between two pHash hex strings.
    Returns (distance, similarity_pct).
    """
    try:
        import imagehash
        ha = imagehash.hex_to_hash(hex_a)
        hb = imagehash.hex_to_hash(hex_b)
        dist = ha - hb
        max_bits = len(ha.hash.flatten())
        sim = round((1 - dist / max_bits) * 100, 1)
        return dist, sim
    except ImportError:
        # Fallback: manual XOR count on hex strings
        try:
            ia = int(hex_a, 16)
            ib = int(hex_b, 16)
            xor = ia ^ ib
            dist = bin(xor).count("1")
            max_bits = max(len(hex_a), len(hex_b)) * 4
            sim = round((1 - dist / max_bits) * 100, 1)
            return dist, sim
        except Exception:
            return -1, 0.0


# ── SHA256 / pHash from file ──────────────────────────────────────────────────

def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _compute_phash(path: str) -> str | None:
    try:
        from PIL import Image
        import imagehash
        img = Image.open(path).convert("RGB")
        return str(imagehash.phash(img))
    except Exception:
        return None


# ── ELA comparison ────────────────────────────────────────────────────────────

def _ela_score(image_path: str, quality: int = 90) -> float | None:
    """
    Compute ELA mean absolute error score for an image.
    Higher score = more editing artifacts / more lossy compression history.
    Returns None if not a JPEG or if PIL unavailable.
    """
    try:
        from PIL import Image
        import numpy as np
        import io

        img = Image.open(image_path).convert("RGB")
        if img.format not in ("JPEG", "JPG", None):
            # Try to detect from extension
            ext = Path(image_path).suffix.lower()
            if ext not in (".jpg", ".jpeg"):
                return None

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        buf.seek(0)
        recompressed = Image.open(buf).convert("RGB")

        orig_arr = np.array(img, dtype=np.float32)
        comp_arr = np.array(recompressed, dtype=np.float32)
        ela_arr  = np.abs(orig_arr - comp_arr)
        return float(np.mean(ela_arr))
    except Exception:
        return None


# ── Face match ────────────────────────────────────────────────────────────────

def _match_faces(path_a: str, path_b: str) -> dict:
    """
    Compare faces between two images using InsightFace embeddings.
    Falls back to a simpler histogram-based similarity if InsightFace unavailable.
    """
    result = {
        "faces_in_a": 0,
        "faces_in_b": 0,
        "matched_pairs": [],
        "overall_verdict": "No faces detected",
        "method": None,
    }

    # Try InsightFace first
    try:
        import numpy as np
        import cv2
        import insightface
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(name="buffalo_sc", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640))

        img_a = cv2.imread(path_a)
        img_b = cv2.imread(path_b)
        if img_a is None or img_b is None:
            result["overall_verdict"] = "Could not load image(s)"
            return result

        faces_a = app.get(img_a)
        faces_b = app.get(img_b)

        result["faces_in_a"] = len(faces_a)
        result["faces_in_b"] = len(faces_b)
        result["method"] = "insightface"

        if not faces_a or not faces_b:
            result["overall_verdict"] = (
                f"No faces in {'A' if not faces_a else 'B'}"
            )
            return result

        # Compare all pairs
        pairs = []
        for i, fa in enumerate(faces_a):
            for j, fb in enumerate(faces_b):
                emb_a = fa.normed_embedding
                emb_b = fb.normed_embedding
                # Cosine similarity → distance (InsightFace uses L2-normalised embeds)
                cos_sim = float(np.dot(emb_a, emb_b))
                # Threshold: >0.28 = same person (InsightFace default)
                pairs.append({
                    "face_a_idx": i,
                    "face_b_idx": j,
                    "cosine_similarity": round(cos_sim, 4),
                    "distance": round(1 - cos_sim, 4),
                    "verdict": "Same person" if cos_sim > 0.28 else "Different person",
                })
        pairs.sort(key=lambda x: x["cosine_similarity"], reverse=True)
        result["matched_pairs"] = pairs

        same_count = sum(1 for p in pairs if p["verdict"] == "Same person")
        if same_count > 0:
            best = max(pairs, key=lambda x: x["cosine_similarity"])
            result["overall_verdict"] = (
                f"Face match found (similarity {best['cosine_similarity']:.3f})"
            )
        else:
            result["overall_verdict"] = "No matching faces found"

        return result

    except ImportError:
        pass

    # Fallback: OpenCV histogram comparison (rough, not identity-level)
    try:
        import cv2
        import numpy as np

        result["method"] = "histogram_fallback"
        img_a = cv2.imread(path_a)
        img_b = cv2.imread(path_b)
        if img_a is None or img_b is None:
            return result

        # Detect faces with OpenCV Haar
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        gray_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
        gray_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY)
        fa = face_cascade.detectMultiScale(gray_a, 1.1, 5, minSize=(40, 40))
        fb = face_cascade.detectMultiScale(gray_b, 1.1, 5, minSize=(40, 40))

        result["faces_in_a"] = len(fa)
        result["faces_in_b"] = len(fb)

        if len(fa) == 0 or len(fb) == 0:
            result["overall_verdict"] = "No faces detected (OpenCV fallback)"
            return result

        # Compare first face histograms
        x, y, w, h = fa[0]
        crop_a = img_a[y:y+h, x:x+w]
        x, y, w, h = fb[0]
        crop_b = img_b[y:y+h, x:x+w]

        # Resize to same size for comparison
        crop_a = cv2.resize(crop_a, (64, 64))
        crop_b = cv2.resize(crop_b, (64, 64))

        hist_a = cv2.calcHist([crop_a], [0,1,2], None, [8,8,8], [0,256,0,256,0,256])
        hist_b = cv2.calcHist([crop_b], [0,1,2], None, [8,8,8], [0,256,0,256,0,256])
        cv2.normalize(hist_a, hist_a)
        cv2.normalize(hist_b, hist_b)
        similarity = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)

        result["matched_pairs"] = [{
            "face_a_idx": 0,
            "face_b_idx": 0,
            "cosine_similarity": round(similarity, 4),
            "distance": round(1 - similarity, 4),
            "verdict": "Possibly same" if similarity > 0.7 else "Different",
        }]
        result["overall_verdict"] = (
            f"Histogram similarity: {similarity:.3f} "
            f"({'Possibly same' if similarity > 0.7 else 'Different'})"
            " — Note: use InsightFace for reliable face match"
        )
    except Exception as e:
        result["overall_verdict"] = f"Face match failed: {e}"

    return result


# ── GPS extraction ────────────────────────────────────────────────────────────

def _extract_gps(image_path: str) -> tuple[float, float] | None:
    """Extract (lat, lon) from EXIF. Returns None if absent."""
    try:
        import piexif

        def _dms_to_dd(dms, ref):
            d = dms[0][0] / dms[0][1]
            m = dms[1][0] / dms[1][1] / 60
            s = dms[2][0] / dms[2][1] / 3600
            dd = d + m + s
            if ref in (b"S", b"W"):
                dd = -dd
            return dd

        exif = piexif.load(image_path)
        gps  = exif.get("GPS", {})
        if not gps:
            return None
        lat = _dms_to_dd(gps[piexif.GPSIFD.GPSLatitude],
                         gps[piexif.GPSIFD.GPSLatitudeRef])
        lon = _dms_to_dd(gps[piexif.GPSIFD.GPSLongitude],
                         gps[piexif.GPSIFD.GPSLongitudeRef])
        return lat, lon
    except Exception:
        return None


# ── Metadata diff ─────────────────────────────────────────────────────────────

def _metadata_diff(path_a: str, path_b: str) -> dict:
    """
    Compare EXIF metadata between two images.
    Checks: device make/model, serial number, date delta, GPS distance, software.
    """
    result = {
        "same_device": None,
        "same_serial": None,
        "date_delta_days": None,
        "gps_distance_m": None,
        "gps_verdict": None,
        "diff_fields": [],
        "error": None,
    }

    try:
        import exifread
        from datetime import datetime

        def _read_exif(path):
            with open(path, "rb") as f:
                return exifread.process_file(f, details=False)

        tags_a = _read_exif(path_a)
        tags_b = _read_exif(path_b)

        # Device identity fields
        make_a  = str(tags_a.get("Image Make",  "")).strip()
        make_b  = str(tags_b.get("Image Make",  "")).strip()
        model_a = str(tags_a.get("Image Model", "")).strip()
        model_b = str(tags_b.get("Image Model", "")).strip()
        serial_a = str(tags_a.get("MakerNote BodySerialNumber",
                                  tags_a.get("EXIF BodySerialNumber", ""))).strip()
        serial_b = str(tags_b.get("MakerNote BodySerialNumber",
                                  tags_b.get("EXIF BodySerialNumber", ""))).strip()
        sw_a = str(tags_a.get("Image Software", "")).strip()
        sw_b = str(tags_b.get("Image Software", "")).strip()

        result["same_device"] = (make_a == make_b and model_a == model_b
                                 and bool(make_a))

        if serial_a and serial_b:
            result["same_serial"] = (serial_a == serial_b)

        if make_a != make_b and make_a and make_b:
            result["diff_fields"].append(f"Make: '{make_a}' vs '{make_b}'")
        if model_a != model_b and model_a and model_b:
            result["diff_fields"].append(f"Model: '{model_a}' vs '{model_b}'")
        if serial_a and serial_b and serial_a != serial_b:
            result["diff_fields"].append(f"Serial: '{serial_a}' vs '{serial_b}'")
        if sw_a != sw_b and sw_a and sw_b:
            result["diff_fields"].append(f"Software: '{sw_a}' vs '{sw_b}'")

        # Date delta
        fmt = "%Y:%m:%d %H:%M:%S"
        date_a = str(tags_a.get("EXIF DateTimeOriginal", "")).strip()
        date_b = str(tags_b.get("EXIF DateTimeOriginal", "")).strip()
        if date_a and date_b:
            try:
                dt_a = datetime.strptime(date_a, fmt)
                dt_b = datetime.strptime(date_b, fmt)
                delta = abs((dt_b - dt_a).days)
                result["date_delta_days"] = delta
            except ValueError:
                pass

        # GPS distance
        gps_a = _extract_gps(path_a)
        gps_b = _extract_gps(path_b)
        if gps_a and gps_b:
            dist = _haversine(gps_a[0], gps_a[1], gps_b[0], gps_b[1])
            result["gps_distance_m"] = round(dist, 1)
            if dist < 50:
                result["gps_verdict"] = "Same location (<50m)"
            elif dist < 500:
                result["gps_verdict"] = f"Near each other ({dist:.0f}m apart)"
            elif dist < 5000:
                result["gps_verdict"] = f"Same area ({dist/1000:.1f}km apart)"
            else:
                result["gps_verdict"] = f"Different locations ({dist/1000:.1f}km apart)"

    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── Hash comparison ───────────────────────────────────────────────────────────

def _hash_comparison(path_a: str, path_b: str) -> dict:
    """Full hash comparison: SHA256 identity + pHash perceptual similarity."""
    sha_a = _file_sha256(path_a)
    sha_b = _file_sha256(path_b)
    identical = sha_a == sha_b

    phash_a = _compute_phash(path_a)
    phash_b = _compute_phash(path_b)

    result = {
        "identical_sha256": identical,
        "sha256_a": sha_a,
        "sha256_b": sha_b,
        "phash_a": phash_a,
        "phash_b": phash_b,
        "phash_distance": None,
        "similarity_pct": None,
        "verdict": None,
    }

    if phash_a and phash_b:
        dist, sim = _phash_similarity(phash_a, phash_b)
        result["phash_distance"]  = dist
        result["similarity_pct"]  = sim

        if identical:
            result["verdict"] = "Identical files"
        elif dist == 0:
            result["verdict"] = "Identical content (different encoding)"
        elif dist <= 5:
            result["verdict"] = "Near-duplicate (minor crop/resize/compression)"
        elif dist <= 12:
            result["verdict"] = "Similar (same source, edited)"
        elif dist <= 20:
            result["verdict"] = "Loosely similar"
        else:
            result["verdict"] = "Different images"
    elif identical:
        result["verdict"] = "Identical files"
    else:
        result["verdict"] = "Unknown (pHash unavailable)"

    return result


# ── Master compare ────────────────────────────────────────────────────────────

def compare_images(image_a: str, image_b: str) -> dict:
    """
    Full comparison between two images.

    Returns
    -------
    {
        hash_comparison: {identical_sha256, phash_distance, similarity_pct, verdict},
        face_match:      {faces_in_a, faces_in_b, matched_pairs[], overall_verdict},
        metadata_diff:   {same_device, same_serial, date_delta_days, gps_distance_m,
                          gps_verdict, diff_fields[]},
        ela_comparison:  {ela_score_a, ela_score_b, more_edited, delta},
        overall_verdict: str,
        flags:           list[str],
    }
    """
    if not os.path.exists(image_a):
        return {"error": f"File not found: {image_a}"}
    if not os.path.exists(image_b):
        return {"error": f"File not found: {image_b}"}

    print(f"[Compare] Hashing...")
    hash_cmp = _hash_comparison(image_a, image_b)

    print(f"[Compare] Comparing metadata...")
    meta_diff = _metadata_diff(image_a, image_b)

    print(f"[Compare] ELA analysis...")
    ela_a = _ela_score(image_a)
    ela_b = _ela_score(image_b)
    ela_delta = None
    more_edited = None
    if ela_a is not None and ela_b is not None:
        ela_delta = round(abs(ela_a - ela_b), 4)
        if ela_a > ela_b + 1.0:
            more_edited = "Image A"
        elif ela_b > ela_a + 1.0:
            more_edited = "Image B"
        else:
            more_edited = "Similar editing level"
    ela_cmp = {
        "ela_score_a": round(ela_a, 4) if ela_a is not None else None,
        "ela_score_b": round(ela_b, 4) if ela_b is not None else None,
        "delta":        ela_delta,
        "more_edited":  more_edited,
    }

    print(f"[Compare] Face matching...")
    face_cmp = _match_faces(image_a, image_b)

    # Build flags
    flags = []
    if hash_cmp.get("identical_sha256"):
        flags.append("✅ Files are byte-for-byte identical")
    elif hash_cmp.get("phash_distance", 99) <= 5:
        flags.append(f"🔁 Near-duplicate images (pHash dist {hash_cmp['phash_distance']})")
    elif hash_cmp.get("phash_distance", 99) <= 12:
        flags.append(f"🔍 Similar images — likely same source (pHash dist {hash_cmp['phash_distance']})")

    if meta_diff.get("same_device") is True:
        d = next((f for f in meta_diff["diff_fields"] if "Model" in f), None)
        model_str = d.split(":")[1].split("vs")[0].strip() if d else "same device"
        flags.append(f"📱 Both images from same device ({model_str})")
    elif meta_diff.get("same_device") is False and meta_diff.get("diff_fields"):
        flags.append(f"📱 Different devices: {'; '.join(meta_diff['diff_fields'][:2])}")

    if meta_diff.get("same_serial") is True:
        flags.append("🔩 Same camera serial number — definitively same physical device")
    elif meta_diff.get("same_serial") is False:
        flags.append("🔩 Different camera serial numbers — different devices")

    if meta_diff.get("date_delta_days") is not None:
        d = meta_diff["date_delta_days"]
        if d == 0:
            flags.append("📅 Taken within same second")
        elif d <= 1:
            flags.append(f"📅 Taken {d} day(s) apart")
        else:
            flags.append(f"📅 Taken {d} days apart")

    if meta_diff.get("gps_verdict"):
        flags.append(f"📍 GPS: {meta_diff['gps_verdict']}")

    if "Same person" in face_cmp.get("overall_verdict", ""):
        best_sim = max((p["cosine_similarity"] for p in face_cmp["matched_pairs"]), default=0)
        flags.append(f"👤 Same person in both images (face similarity {best_sim:.3f})")
    elif face_cmp.get("faces_in_a", 0) > 0 and face_cmp.get("faces_in_b", 0) > 0:
        flags.append("👤 Different people detected")

    if more_edited and more_edited not in ("Similar editing level",):
        flags.append(f"🖼️  {more_edited} shows higher ELA score (more editing/compression)")

    # Overall verdict
    if hash_cmp.get("identical_sha256"):
        overall = "Identical files"
    elif hash_cmp.get("phash_distance", 99) <= 5:
        overall = "Near-duplicate images"
    elif meta_diff.get("same_serial") is True:
        overall = "Same physical camera, different shots"
    elif "Same person" in face_cmp.get("overall_verdict", ""):
        overall = "Same subject, possibly different occasions"
    elif hash_cmp.get("phash_distance", 99) > 20:
        overall = "Unrelated images"
    else:
        overall = "Possibly related images — review flags"

    return {
        "stage": "image_comparison",
        "image_a": str(image_a),
        "image_b": str(image_b),
        "hash_comparison": hash_cmp,
        "face_match":      face_cmp,
        "metadata_diff":   meta_diff,
        "ela_comparison":  ela_cmp,
        "overall_verdict": overall,
        "flags": flags,
    }


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 3:
        print("Usage: python stage_compare.py <image_a> <image_b>")
        sys.exit(1)

    result = compare_images(sys.argv[1], sys.argv[2])

    print(f"\n=== Image Comparison ===")
    print(f"A: {result['image_a']}")
    print(f"B: {result['image_b']}")
    print(f"\nOverall: {result['overall_verdict']}")
    print(f"\nHash:  {result['hash_comparison']['verdict']}")
    if result['hash_comparison']['phash_distance'] is not None:
        print(f"  pHash distance: {result['hash_comparison']['phash_distance']} "
              f"({result['hash_comparison']['similarity_pct']}% similar)")
    print(f"\nFace:  {result['face_match']['overall_verdict']}")
    print(f"ELA:   A={result['ela_comparison']['ela_score_a']}, "
          f"B={result['ela_comparison']['ela_score_b']} "
          f"→ {result['ela_comparison']['more_edited']}")
    if result['metadata_diff']['gps_distance_m'] is not None:
        print(f"GPS:   {result['metadata_diff']['gps_verdict']}")
    print(f"\nFlags:")
    for f in result["flags"]:
        print(f"  {f}")
