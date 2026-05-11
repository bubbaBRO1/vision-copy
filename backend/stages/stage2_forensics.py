"""
Stage 2 — Image Forensics
Detects: image manipulation (ELA), copy-paste cloning, noise anomalies,
AI-generated images, and deepfakes (via Sightengine + Reality Defender APIs).
"""

import io
import os
import math
import base64
import requests
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageEnhance, ImageFilter
    import numpy as np
    PIL_OK = True
except ImportError:
    PIL_OK = False


# ── ELA (Error Level Analysis) ────────────────────────────────────────────────

def _ela(image_path: str, quality: int = 90) -> dict:
    """
    Re-save image at given quality, diff original vs re-saved.
    High-difference regions indicate possible editing.
    Returns: ela_score (0-100), ela_image_b64, high_error_regions %
    """
    result = {"ela_score": 0, "ela_max_diff": 0, "high_error_pct": 0.0,
              "ela_image_b64": None, "verdict": "Clean"}
    if not PIL_OK:
        result["error"] = "Pillow not installed"
        return result
    try:
        original = Image.open(image_path).convert("RGB")

        # Re-save at reduced quality
        buf = io.BytesIO()
        original.save(buf, format="JPEG", quality=quality)
        buf.seek(0)
        resaved = Image.open(buf).convert("RGB")

        # Pixel difference
        diff = ImageChops.difference(original, resaved)
        arr = np.array(diff).astype(float)

        # Amplify for visibility
        scale = 10
        ela_arr = np.clip(arr * scale, 0, 255).astype(np.uint8)
        ela_img = Image.fromarray(ela_arr)

        # Stats
        max_diff = float(arr.max())
        mean_diff = float(arr.mean())
        # Pixels where any channel > 20 after scaling = suspicious
        suspicious_mask = np.any(arr > 20, axis=2)
        high_error_pct = round(float(suspicious_mask.mean()) * 100, 2)

        # Score 0-100
        ela_score = min(100, int(mean_diff * 5 + high_error_pct * 2))

        # Encode ELA image as base64 for report embedding
        buf2 = io.BytesIO()
        ela_img.save(buf2, format="PNG")
        ela_b64 = base64.b64encode(buf2.getvalue()).decode()

        result["ela_score"] = ela_score
        result["ela_max_diff"] = round(max_diff, 2)
        result["high_error_pct"] = high_error_pct
        result["ela_image_b64"] = ela_b64

        if ela_score >= 60:
            result["verdict"] = "Likely Manipulated"
        elif ela_score >= 30:
            result["verdict"] = "Possibly Edited"
        else:
            result["verdict"] = "Likely Authentic"

    except Exception as e:
        result["error"] = str(e)
    return result


# ── Clone / Copy-Paste Detection ──────────────────────────────────────────────

def _clone_detection(image_path: str, block_size: int = 16, threshold: float = 0.98) -> dict:
    """
    Detect copy-pasted (cloned) regions by comparing image blocks.
    Uses normalized cross-correlation on grayscale blocks.
    """
    result = {"clone_detected": False, "clone_count": 0,
              "clone_regions": [], "verdict": "No cloning detected"}
    if not PIL_OK:
        result["error"] = "Pillow/numpy not installed"
        return result
    try:
        img = Image.open(image_path).convert("L")  # grayscale
        arr = np.array(img, dtype=float)
        h, w = arr.shape

        if h * w > 4_000_000:
            # Resize to keep speed reasonable on large images
            scale = math.sqrt(4_000_000 / (h * w))
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            arr = np.array(img, dtype=float)
            h, w = arr.shape

        blocks = {}
        matches = []

        step = block_size
        for y in range(0, h - block_size, step):
            for x in range(0, w - block_size, step):
                block = arr[y:y+block_size, x:x+block_size]
                norm = np.linalg.norm(block)
                if norm == 0:
                    continue
                key = round(float((block / norm).sum()), 4)
                if key in blocks:
                    by, bx = blocks[key]
                    # Verify actual pixel similarity
                    prev_block = arr[by:by+block_size, bx:bx+block_size]
                    prev_norm = np.linalg.norm(prev_block)
                    if prev_norm > 0:
                        corr = float(np.dot(block.flatten(), prev_block.flatten()) /
                                     (norm * prev_norm))
                        if corr >= threshold:
                            matches.append({
                                "region_a": [int(bx), int(by), int(bx+block_size), int(by+block_size)],
                                "region_b": [int(x), int(y), int(x+block_size), int(y+block_size)],
                                "similarity": round(corr, 4),
                            })
                else:
                    blocks[key] = (y, x)

        if matches:
            result["clone_detected"] = True
            result["clone_count"] = len(matches)
            result["clone_regions"] = matches[:10]  # top 10
            result["verdict"] = f"⚠️  {len(matches)} cloned region(s) detected"

    except Exception as e:
        result["error"] = str(e)
    return result


# ── Noise Analysis ────────────────────────────────────────────────────────────

def _noise_analysis(image_path: str) -> dict:
    """
    Compute per-region noise variance. Inconsistent noise across regions
    suggests splicing (pasting from a different image).
    """
    result = {"noise_score": 0, "verdict": "Consistent noise", "regions": []}
    if not PIL_OK:
        result["error"] = "Pillow/numpy not installed"
        return result
    try:
        img = Image.open(image_path).convert("L")
        arr = np.array(img, dtype=float)
        h, w = arr.shape
        tile = 64
        variances = []
        for y in range(0, h - tile, tile):
            for x in range(0, w - tile, tile):
                region = arr[y:y+tile, x:x+tile]
                variances.append(float(region.var()))

        if not variances:
            return result

        mean_var = float(np.mean(variances))
        std_var  = float(np.std(variances))
        cv = std_var / mean_var if mean_var > 0 else 0

        # High coefficient of variation = inconsistent noise = suspicious
        noise_score = min(100, int(cv * 100))
        result["noise_score"] = noise_score
        result["mean_variance"] = round(mean_var, 2)
        result["std_variance"] = round(std_var, 2)
        result["coefficient_of_variation"] = round(cv, 4)

        if noise_score >= 50:
            result["verdict"] = "⚠️  Inconsistent noise — possible splice/composite"
        elif noise_score >= 25:
            result["verdict"] = "Slightly inconsistent noise"
        else:
            result["verdict"] = "Consistent noise (natural)"

    except Exception as e:
        result["error"] = str(e)
    return result


# ── AI / Deepfake Detection (Sightengine API) ─────────────────────────────────

def _sightengine_check(image_path: str, api_user: str, api_secret: str) -> dict:
    """
    Calls Sightengine API to detect AI-generated images and deepfakes.
    Free tier: 2,000 API calls/month.
    """
    result = {"ai_generated": None, "deepfake": None, "raw": {}}
    if not api_user or not api_secret:
        result["skipped"] = "No Sightengine API credentials provided (set SIGHTENGINE_USER and SIGHTENGINE_SECRET)"
        return result
    try:
        with open(image_path, "rb") as f:
            files = {"media": f}
            params = {
                "models": "deepfake,genai",
                "api_user": api_user,
                "api_secret": api_secret,
            }
            resp = requests.post(
                "https://api.sightengine.com/1.0/check.json",
                files=files, data=params, timeout=20
            )
        data = resp.json()
        result["raw"] = data
        if data.get("status") == "success":
            result["ai_generated"] = data.get("type", {}).get("ai_generated")
            result["deepfake"]     = data.get("deepfake", {}).get("score")
    except Exception as e:
        result["error"] = str(e)
    return result


# ── JPEG Ghost Detection ─────────────────────────────────────────────────────

def _jpeg_ghost(image_path: str, qualities: list = None) -> dict:
    """
    Re-encode at multiple JPEG qualities and detect anomalous error curves.
    Regions that were previously re-saved show unusually low error at the quality
    they were saved at (the 'ghost' quality) — a U-shaped error vs quality curve.
    """
    result = {
        "ghost_detected": False,
        "suspected_original_quality": None,
        "ghost_block_count": 0,
        "ghost_pct": 0.0,
        "quality_errors": {},
        "verdict": "No JPEG ghost detected",
        "skipped": None,
    }
    if not PIL_OK:
        result["skipped"] = "Pillow/numpy not installed"
        return result

    try:
        img = Image.open(image_path)
        if img.format != "JPEG":
            result["skipped"] = f"Not a JPEG (format: {img.format})"
            return result
    except Exception as e:
        result["skipped"] = f"Cannot open image: {e}"
        return result

    if qualities is None:
        qualities = [50, 60, 70, 75, 80, 85, 90, 95]

    try:
        # Resize to max 800px on longest side for speed
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > 800:
            scale = 800 / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        original_arr = np.array(img, dtype=float)
        block = 16
        bh = original_arr.shape[0] // block
        bw = original_arr.shape[1] // block
        if bh == 0 or bw == 0:
            result["skipped"] = "Image too small for ghost analysis"
            return result

        # Per-block mean error at each quality
        block_errors = {}
        for q in qualities:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=q)
            buf.seek(0)
            reenc = np.array(Image.open(buf).convert("RGB"), dtype=float)
            diff = np.abs(original_arr - reenc)
            errors = []
            for by in range(bh):
                for bx in range(bw):
                    region = diff[by*block:(by+1)*block, bx*block:(bx+1)*block]
                    errors.append(float(region.mean()))
            block_errors[q] = errors
            result["quality_errors"][q] = round(float(np.mean(errors)), 4)

        # Find quality where the most blocks have unusually low error
        # relative to adjacent quality levels
        ghost_counts = {}
        for i, q in enumerate(qualities[1:-1], 1):
            q_prev = qualities[i - 1]
            q_next = qualities[i + 1]
            ghost_blocks = 0
            for j in range(bh * bw):
                e_prev = block_errors[q_prev][j]
                e_curr = block_errors[q][j]
                e_next = block_errors[q_next][j]
                # Ghost: current error notably lower than both neighbours (U-dip)
                if e_curr < e_prev * 0.7 and e_curr < e_next * 0.7 and e_curr < 5.0:
                    ghost_blocks += 1
            ghost_counts[q] = ghost_blocks

        if ghost_counts:
            best_q = max(ghost_counts, key=ghost_counts.get)
            best_count = ghost_counts[best_q]
            total_blocks = bh * bw
            ghost_pct = round(best_count / total_blocks * 100, 2) if total_blocks > 0 else 0

            if ghost_pct > 5:
                result["ghost_detected"] = True
                result["suspected_original_quality"] = best_q
                result["ghost_block_count"] = best_count
                result["ghost_pct"] = ghost_pct
                result["verdict"] = (
                    f"⚠️  JPEG ghost at quality {best_q} "
                    f"({ghost_pct:.1f}% of blocks) — image may have been re-saved"
                )

    except Exception as e:
        result["skipped"] = f"Ghost analysis error: {e}"

    return result


# ── Metadata Consistency Check ────────────────────────────────────────────────

def _metadata_consistency(image_path: str, metadata: dict) -> dict:
    """
    Cross-reference Stage 1 metadata vs actual file properties.
    Looks for signs of post-processing, editing, or metadata tampering.
    """
    result = {
        "consistent": True,
        "issues": [],
        "flags": [],
        "resolution_ratio": None,
    }
    if not metadata:
        return result

    from datetime import datetime as dt
    scan_time = dt.now()

    exif = metadata.get("exif", {})
    file_info = metadata.get("file", {})
    resolution_check = metadata.get("resolution_check", {})
    device = metadata.get("device", {})

    # Resolution mismatch from Stage 1
    if resolution_check and not resolution_check.get("consistent", True):
        result["consistent"] = False
        result["issues"].append(resolution_check.get("flag", "Resolution mismatch"))
        result["flags"].append("🚩 Resolution metadata mismatch")

    # File size anomaly: < 50KB for an image stated as > 5 Megapixels
    size_bytes = file_info.get("size_bytes", 0)
    mp = exif.get("megapixels", 0) or 0
    if size_bytes < 50_000 and mp > 5:
        result["consistent"] = False
        ratio = round(size_bytes / max(mp, 1) / 1000, 1)
        result["resolution_ratio"] = ratio
        result["issues"].append(
            f"Suspiciously small file ({size_bytes/1000:.0f}KB) for {mp}MP image — "
            f"possible thumbnail or downscaled export"
        )
        result["flags"].append("🚩 File size vs resolution anomaly")

    # DateTimeOriginal checks
    dt_orig_str = exif.get("datetime_original")
    if dt_orig_str:
        try:
            dt_orig = dt.strptime(dt_orig_str, "%Y:%m:%d %H:%M:%S")
            if dt_orig > scan_time:
                result["consistent"] = False
                result["issues"].append(f"DateTimeOriginal is in the FUTURE: {dt_orig_str}")
                result["flags"].append("🚨 Timestamp in future — clock error or tampering")
            elif dt_orig.year < 1990:
                result["issues"].append(f"DateTimeOriginal very old: {dt_orig_str} — verify device clock")
                result["flags"].append("⚠️  Very old timestamp (pre-1990)")
        except ValueError:
            pass

    # Editor software + GPS still present is suspicious (editors usually strip GPS)
    software = (device.get("software") or "").lower()
    gps = metadata.get("gps", {})
    gps_present = gps.get("latitude") is not None
    if gps_present and any(s in software for s in ["photoshop", "lightroom", "gimp", "affinity"]):
        result["issues"].append(
            f"Editing software '{software}' found but GPS still present — "
            f"GPS usually stripped by editors, possible manual re-injection"
        )
        result["flags"].append("⚠️  GPS retained despite editor software")

    if result["issues"]:
        result["consistent"] = False

    return result


# ── Overall manipulation score ─────────────────────────────────────────────────

def _score(ela: dict, clone: dict, noise: dict, ai: dict,
           ghost: dict = None, meta_consistency: dict = None) -> tuple[int, str]:
    score = 0
    reasons = []

    ela_s = ela.get("ela_score", 0)
    if ela_s >= 60:
        score += 40; reasons.append("High ELA error level")
    elif ela_s >= 30:
        score += 20; reasons.append("Moderate ELA error level")

    if clone.get("clone_detected"):
        score += 30; reasons.append(f"{clone['clone_count']} cloned regions")

    noise_s = noise.get("noise_score", 0)
    if noise_s >= 50:
        score += 20; reasons.append("Inconsistent noise (splice)")
    elif noise_s >= 25:
        score += 10

    ai_gen = ai.get("ai_generated")
    if ai_gen is not None and ai_gen > 0.7:
        score += 30; reasons.append(f"AI-generated ({ai_gen:.0%})")

    deepfake = ai.get("deepfake")
    if deepfake is not None and deepfake > 0.7:
        score += 30; reasons.append(f"Deepfake ({deepfake:.0%})")

    # JPEG ghost
    if ghost and ghost.get("ghost_detected"):
        ghost_pct = ghost.get("ghost_pct", 0)
        if ghost_pct > 10:
            score += 25; reasons.append(f"JPEG ghost at quality {ghost.get('suspected_original_quality')} ({ghost_pct:.0f}%)")
        else:
            score += 10; reasons.append(f"Minor JPEG ghost ({ghost_pct:.0f}%)")

    # Metadata consistency issues
    if meta_consistency and not meta_consistency.get("consistent", True):
        issues = meta_consistency.get("issues", [])
        if issues:
            score += 15; reasons.append(f"Metadata inconsistency: {issues[0][:60]}")

    score = min(100, score)

    if score >= 70:
        verdict = "🚨 HIGHLY SUSPICIOUS — likely manipulated/synthetic"
    elif score >= 40:
        verdict = "⚠️  POSSIBLY EDITED — some anomalies found"
    elif score >= 15:
        verdict = "🟡 MINOR ANOMALIES — probably authentic"
    else:
        verdict = "✅ LIKELY AUTHENTIC"

    return score, verdict + (f" | Reasons: {', '.join(reasons)}" if reasons else "")


# ── Main ──────────────────────────────────────────────────────────────────────

def analyze(image_path: str, api_user: str = "", api_secret: str = "",
            metadata: dict = None) -> dict:
    """
    Run full forensic analysis on image_path.
    api_user / api_secret: Sightengine credentials (optional).
    metadata: Stage 1 results for consistency cross-check (optional).
    """
    api_user   = api_user   or os.environ.get("SIGHTENGINE_USER", "")
    api_secret = api_secret or os.environ.get("SIGHTENGINE_SECRET", "")

    ela    = _ela(image_path)
    clone  = _clone_detection(image_path)
    noise  = _noise_analysis(image_path)
    ai     = _sightengine_check(image_path, api_user, api_secret)
    ghost  = _jpeg_ghost(image_path)
    meta_c = _metadata_consistency(image_path, metadata)

    manip_score, manip_verdict = _score(ela, clone, noise, ai, ghost, meta_c)

    flags = []
    if ghost.get("ghost_detected"):
        flags.append(ghost["verdict"])
    for f in meta_c.get("flags", []):
        flags.append(f)

    return {
        "stage": "forensics",
        "manipulation_score": manip_score,
        "manipulation_verdict": manip_verdict,
        "ela": ela,
        "clone_detection": clone,
        "noise_analysis": noise,
        "ai_detection": ai,
        "jpeg_ghost": ghost,
        "metadata_consistency": meta_c,
        "flags": flags,
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python stage2_forensics.py <image>")
        sys.exit(1)
    result = analyze(sys.argv[1])
    # Don't dump b64 ela image to terminal
    result["ela"]["ela_image_b64"] = "<base64 omitted>"
    print(json.dumps(result, indent=2, default=str))
