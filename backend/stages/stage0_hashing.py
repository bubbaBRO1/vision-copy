"""Stage 0 — Image Hashing & NSFW Detection

Computes cryptographic + perceptual fingerprints and NSFW scoring.
All heavy deps (imagehash, nudenet) are guarded with try/except.
"""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout


def hash_image(image_path: str) -> dict:
    """
    Returns cryptographic + perceptual hashes and NSFW analysis.

    Keys: md5, sha256, phash, dhash, whash, phash_int, nsfw, flags
    """
    result = {
        "stage": "hashing",
        "md5": None,
        "sha256": None,
        "phash": None,
        "dhash": None,
        "whash": None,
        "phash_int": None,
        "nsfw": {"score": None, "verdict": "Unknown", "skipped": None},
        "flags": [],
        "error": None,
    }

    if not os.path.exists(image_path):
        result["error"] = f"File not found: {image_path}"
        return result

    # ── Cryptographic hashes ──────────────────────────────────────────────────
    try:
        md5 = hashlib.md5()
        sha256 = hashlib.sha256()
        with open(image_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                md5.update(chunk)
                sha256.update(chunk)
        result["md5"] = md5.hexdigest()
        result["sha256"] = sha256.hexdigest()
    except Exception as e:
        result["error"] = f"Hash error: {e}"

    # ── Perceptual hashes ─────────────────────────────────────────────────────
    try:
        import imagehash
        from PIL import Image

        img = Image.open(image_path).convert("RGB")
        ph = imagehash.phash(img)
        dh = imagehash.dhash(img)
        wh = imagehash.average_hash(img)

        result["phash"] = str(ph)
        result["dhash"] = str(dh)
        result["whash"] = str(wh)
        result["phash_int"] = int(str(ph), 16)
    except ImportError:
        result["flags"].append("imagehash not installed — perceptual hashes skipped")
    except Exception as e:
        result["flags"].append(f"Perceptual hash error: {e}")

    # ── NSFW detection (NudeNet, ONNX-based) ─────────────────────────────────
    def _run_nudenet():
        from nudenet import NudeDetector
        detector = NudeDetector()
        detections = detector.detect(image_path)
        if not detections:
            return 0.0, []
        score = max((d.get("score", 0) for d in detections), default=0.0)
        labels = [d.get("class", "") for d in detections if d.get("score", 0) > 0.5]
        return score, labels

    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_run_nudenet)
            try:
                nsfw_score, nsfw_labels = future.result(timeout=20)
                verdict = "NSFW" if nsfw_score > 0.6 else ("Borderline" if nsfw_score > 0.35 else "SFW")
                result["nsfw"] = {
                    "score": round(nsfw_score, 3),
                    "verdict": verdict,
                    "labels": nsfw_labels,
                    "skipped": None,
                }
                if nsfw_score > 0.6:
                    result["flags"].append(f"🔞 NSFW content detected (score: {nsfw_score:.2f})")
            except FuturesTimeout:
                result["nsfw"]["skipped"] = "Timeout (>20s) — likely first-run model download"
    except ImportError:
        result["nsfw"]["skipped"] = "nudenet not installed"
    except Exception as e:
        result["nsfw"]["skipped"] = f"NudeNet error: {e}"

    return result


def compare_hashes(hash_a: dict, hash_b: dict) -> dict:
    """
    Compare two hash_image() results.

    Returns: identical_sha256, phash_distance, similarity_pct, verdict
    """
    result = {
        "identical_sha256": False,
        "phash_distance": None,
        "similarity_pct": None,
        "verdict": "Unknown",
        "flags": [],
    }

    sha_a = hash_a.get("sha256")
    sha_b = hash_b.get("sha256")
    if sha_a and sha_b:
        result["identical_sha256"] = sha_a == sha_b
        if result["identical_sha256"]:
            result["verdict"] = "Identical (byte-for-byte)"
            result["similarity_pct"] = 100.0
            return result

    phash_a = hash_a.get("phash")
    phash_b = hash_b.get("phash")
    if phash_a and phash_b:
        try:
            import imagehash
            h_a = imagehash.hex_to_hash(phash_a)
            h_b = imagehash.hex_to_hash(phash_b)
            dist = h_a - h_b
            result["phash_distance"] = dist
            # pHash is 64 bits — max distance 64
            result["similarity_pct"] = round((1 - dist / 64) * 100, 1)
            if dist < 1:
                result["verdict"] = "Identical"
            elif dist < 10:
                result["verdict"] = "Near-duplicate"
                result["flags"].append(f"Near-duplicate images (pHash distance: {dist})")
            elif dist < 20:
                result["verdict"] = "Similar"
            else:
                result["verdict"] = "Different"
        except ImportError:
            result["verdict"] = "Cannot compare — imagehash not installed"
        except Exception as e:
            result["verdict"] = f"Comparison error: {e}"
    else:
        result["verdict"] = "Cannot compare — perceptual hashes unavailable"

    return result


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python stage0_hashing.py <image> [image2]")
        sys.exit(1)

    r = hash_image(sys.argv[1])
    if len(sys.argv) >= 3:
        r2 = hash_image(sys.argv[2])
        cmp = compare_hashes(r, r2)
        print(json.dumps({"image1": r, "image2": r2, "comparison": cmp}, indent=2))
    else:
        print(json.dumps(r, indent=2))
