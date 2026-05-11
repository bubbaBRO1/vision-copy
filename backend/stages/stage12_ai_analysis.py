"""
Stage 12 — Advanced AI Content Analysis
DeepFace demographics, OpenCLIP zero-shot scene/country, PaddleOCR, EasyOCR, clothing analysis.
All guarded with try/except ImportError — pipeline runs fine without any of these.
"""

from __future__ import annotations
import os
import io
import sys
import json
import time
import warnings
import traceback
from pathlib import Path
from typing import Optional

import numpy as np

# ── Optional heavy imports ──────────────────────────────────────────────────
try:
    from PIL import Image as PILImage
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

try:
    from deepface import DeepFace
    DEEPFACE_OK = True
except ImportError:
    DEEPFACE_OK = False

try:
    import open_clip
    import torch
    CLIP_OK = True
except ImportError:
    CLIP_OK = False

try:
    from paddleocr import PaddleOCR
    PADDLE_OK = True
except ImportError:
    PADDLE_OK = False

try:
    import easyocr
    EASYOCR_OK = True
except ImportError:
    EASYOCR_OK = False


# ── Country list for CLIP zero-shot ─────────────────────────────────────────
_COUNTRIES = [
    "United States", "United Kingdom", "France", "Germany", "Russia",
    "China", "Japan", "South Korea", "India", "Brazil", "Australia",
    "Canada", "Mexico", "Spain", "Italy", "Turkey", "Saudi Arabia",
    "Nigeria", "South Africa", "Egypt", "Iran", "Pakistan", "Indonesia",
    "Thailand", "Vietnam", "Philippines", "Ukraine", "Poland", "Netherlands",
    "Sweden", "Norway", "Denmark", "Finland", "Switzerland", "Austria",
    "Belgium", "Portugal", "Greece", "Czech Republic", "Hungary",
    "Romania", "Bulgaria", "Serbia", "Croatia", "Israel", "UAE",
    "Kazakhstan", "Argentina", "Chile", "Colombia", "Peru",
    "Morocco", "Algeria", "Kenya", "Ethiopia", "Ghana",
    "New Zealand", "Singapore", "Malaysia", "Bangladesh",
]

_SCENE_TYPES = [
    "indoor office", "indoor home living room", "indoor kitchen",
    "indoor bedroom", "indoor shopping mall", "indoor warehouse",
    "outdoor city street", "outdoor market", "outdoor park",
    "outdoor rural farmland", "outdoor mountain landscape",
    "outdoor beach", "outdoor desert", "outdoor forest",
    "outdoor airport tarmac", "outdoor train station",
    "outdoor construction site", "outdoor military base",
    "outdoor protest or crowd", "outdoor stadium",
    "indoor restaurant", "indoor hospital", "indoor school classroom",
    "outdoor suburban neighbourhood", "outdoor port or harbour",
]

# ── Clothing / uniform heuristics ───────────────────────────────────────────
_UNIFORM_HINTS = {
    # (r, g, b) dominant-ish → label
    # We work from HSV ranges for robustness
}

_CAMO_HSV_RANGE = {
    "lower": np.array([25, 20, 20]),
    "upper": np.array([90, 130, 130]),
}

# Colour bucket → season / type label
_COLOR_SEASON = {
    "white":  "Light/summer or snow environment",
    "black":  "Formal / tactical",
    "navy":   "Military / police / formal",
    "khaki":  "Military / outdoor",
    "orange": "High-vis / safety worker",
    "yellow": "High-vis / safety worker",
    "gray":   "Urban / casual",
    "green":  "Military / outdoor / rural",
    "red":    "Casual / sports",
    "blue":   "Casual / work",
    "brown":  "Outdoor / camouflage",
    "beige":  "Desert / arid environment",
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. DeepFace demographics
# ─────────────────────────────────────────────────────────────────────────────

def deepface_analyze(image_path: str, face_bboxes: list | None = None) -> list[dict]:
    """
    Per-face age, gender, dominant emotion, dominant race.
    Uses face_bboxes from Stage 4 to crop each face; falls back to full image.
    Returns list of per-face dicts.
    """
    if not DEEPFACE_OK:
        return [{"skipped": "deepface not installed — pip install deepface"}]
    if not PIL_OK:
        return [{"skipped": "Pillow required for face crop"}]

    results = []
    try:
        img = PILImage.open(image_path).convert("RGB")
        img_np = np.array(img)

        def _analyze_region(region_img_np: np.ndarray, face_id: int) -> dict:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    # Suppress TF/DeepFace verbose logs
                    old_stdout, old_stderr = sys.stdout, sys.stderr
                    sys.stdout = io.StringIO()
                    sys.stderr = io.StringIO()
                    try:
                        analysis = DeepFace.analyze(
                            img_path=region_img_np,
                            actions=["age", "gender", "emotion", "race"],
                            enforce_detection=False,
                            silent=True,
                        )
                    finally:
                        sys.stdout = old_stdout
                        sys.stderr = old_stderr

                if isinstance(analysis, list):
                    analysis = analysis[0]

                return {
                    "face_id": face_id,
                    "age": int(analysis.get("age", 0)),
                    "gender": analysis.get("dominant_gender", analysis.get("gender", "Unknown")),
                    "gender_confidence": round(
                        max(analysis.get("gender", {}).values()) if isinstance(analysis.get("gender"), dict) else 0.0, 3
                    ),
                    "dominant_emotion": analysis.get("dominant_emotion", "neutral"),
                    "emotion_scores": {
                        k: round(v, 3)
                        for k, v in analysis.get("emotion", {}).items()
                    },
                    "dominant_race": analysis.get("dominant_race", "Unknown"),
                    "race_scores": {
                        k: round(v, 3)
                        for k, v in analysis.get("race", {}).items()
                    },
                    "skipped": None,
                }
            except Exception as e:
                return {"face_id": face_id, "error": str(e), "skipped": "DeepFace analysis failed"}

        if face_bboxes:
            for i, bbox in enumerate(face_bboxes):
                try:
                    x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
                    # Expand bbox 20% for better DeepFace accuracy
                    h, w = img_np.shape[:2]
                    pad_x = max(0, int((x2 - x1) * 0.2))
                    pad_y = max(0, int((y2 - y1) * 0.2))
                    x1c = max(0, x1 - pad_x)
                    y1c = max(0, y1 - pad_y)
                    x2c = min(w, x2 + pad_x)
                    y2c = min(h, y2 + pad_y)
                    crop = img_np[y1c:y2c, x1c:x2c]
                    if crop.size == 0:
                        continue
                    results.append(_analyze_region(crop, i))
                except Exception as e:
                    results.append({"face_id": i, "error": str(e)})
        else:
            # Analyze full image — DeepFace will auto-detect faces
            results.append(_analyze_region(img_np, 0))

    except Exception as e:
        return [{"skipped": f"DeepFace error: {e}"}]

    return results if results else [{"skipped": "No faces analyzed"}]


# ─────────────────────────────────────────────────────────────────────────────
# 2. OpenCLIP zero-shot scene + country classification
# ─────────────────────────────────────────────────────────────────────────────

_clip_model_cache: dict = {}

def openclip_scene_classify(image_path: str) -> dict:
    """
    Zero-shot CLIP classification for country hint + scene type.
    Model: ViT-B-32 (open_clip). ~350MB first download, cached afterwards.
    """
    if not CLIP_OK:
        return {"skipped": "open-clip-torch not installed — pip install open-clip-torch"}
    if not PIL_OK:
        return {"skipped": "Pillow required"}

    try:
        global _clip_model_cache
        if not _clip_model_cache:
            model, _, preprocess = open_clip.create_model_and_transforms(
                "ViT-B-32", pretrained="openai"
            )
            model.eval()
            tokenizer = open_clip.get_tokenizer("ViT-B-32")
            _clip_model_cache = {
                "model": model,
                "preprocess": preprocess,
                "tokenizer": tokenizer,
            }

        model = _clip_model_cache["model"]
        preprocess = _clip_model_cache["preprocess"]
        tokenizer = _clip_model_cache["tokenizer"]

        img = PILImage.open(image_path).convert("RGB")
        image_tensor = preprocess(img).unsqueeze(0)

        # Country classification
        country_prompts = [f"a photo taken in {c}" for c in _COUNTRIES]
        country_tokens = tokenizer(country_prompts)

        # Scene classification
        scene_prompts = [f"a photo of {s}" for s in _SCENE_TYPES]
        scene_tokens = tokenizer(scene_prompts)

        with torch.no_grad():
            image_features = model.encode_image(image_tensor)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

            country_text_features = model.encode_text(country_tokens)
            country_text_features = country_text_features / country_text_features.norm(dim=-1, keepdim=True)

            scene_text_features = model.encode_text(scene_tokens)
            scene_text_features = scene_text_features / scene_text_features.norm(dim=-1, keepdim=True)

            country_sims = (image_features @ country_text_features.T).softmax(dim=-1).squeeze().tolist()
            scene_sims = (image_features @ scene_text_features.T).softmax(dim=-1).squeeze().tolist()

        # Top 3 countries
        country_ranked = sorted(zip(_COUNTRIES, country_sims), key=lambda x: x[1], reverse=True)
        top_countries = [
            {"country": c, "confidence": round(s, 4)}
            for c, s in country_ranked[:3]
        ]

        # Top scene
        scene_ranked = sorted(zip(_SCENE_TYPES, scene_sims), key=lambda x: x[1], reverse=True)
        top_scene = scene_ranked[0]

        return {
            "top_country_hints": top_countries,
            "scene_type": top_scene[0],
            "scene_confidence": round(top_scene[1], 4),
            "all_scene_top3": [
                {"scene": s, "confidence": round(c, 4)}
                for s, c in scene_ranked[:3]
            ],
            "model": "ViT-B-32 (OpenCLIP)",
            "skipped": None,
        }

    except Exception as e:
        return {"skipped": f"OpenCLIP error: {e}", "traceback": traceback.format_exc()}


# ─────────────────────────────────────────────────────────────────────────────
# 3. PaddleOCR + EasyOCR fallback
# ─────────────────────────────────────────────────────────────────────────────

_paddle_instance: dict = {}

def paddleocr_extract(image_path: str) -> dict:
    """
    PaddleOCR — significantly better than Tesseract for non-Latin scripts,
    curved text, low-quality images.
    """
    if not PADDLE_OK:
        return {"skipped": "paddleocr not installed — pip install paddleocr"}

    try:
        global _paddle_instance
        if not _paddle_instance:
            _paddle_instance["ocr"] = PaddleOCR(
                use_angle_cls=True, lang="en", show_log=False, use_gpu=False
            )

        ocr = _paddle_instance["ocr"]
        result = ocr.ocr(image_path, cls=True)

        lines = []
        full_text_parts = []

        if result and result[0]:
            for line in result[0]:
                if line and len(line) >= 2:
                    bbox_pts = line[0]   # 4 corner points
                    text_conf = line[1]  # (text, confidence)
                    if text_conf:
                        text, conf = text_conf[0], text_conf[1]
                        lines.append({
                            "text": text,
                            "confidence": round(float(conf), 3),
                            "bbox": bbox_pts,
                        })
                        full_text_parts.append(text)

        full_text = " ".join(full_text_parts)
        high_conf = " ".join(l["text"] for l in lines if l["confidence"] > 0.9)

        # Language detection hint
        language_hint = None
        try:
            from langdetect import detect
            if len(full_text.strip()) > 10:
                language_hint = detect(full_text)
        except Exception:
            pass

        return {
            "text": full_text,
            "lines": lines,
            "language_hint": language_hint,
            "high_confidence_text": high_conf,
            "engine": "paddleocr",
            "skipped": None,
        }

    except Exception as e:
        return {"skipped": f"PaddleOCR error: {e}"}


_easyocr_readers: dict = {}

def easyocr_extract(image_path: str, languages: list | None = None) -> dict:
    """
    EasyOCR — 80+ language support, no compilation needed.
    Used as fallback after PaddleOCR.
    """
    if not EASYOCR_OK:
        return {"skipped": "easyocr not installed — pip install easyocr"}

    if languages is None:
        languages = ["en"]

    lang_key = ",".join(sorted(languages))

    try:
        global _easyocr_readers
        if lang_key not in _easyocr_readers:
            _easyocr_readers[lang_key] = easyocr.Reader(languages, verbose=False)

        reader = _easyocr_readers[lang_key]

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = reader.readtext(image_path)

        lines = []
        full_text_parts = []

        for bbox, text, conf in result:
            lines.append({
                "text": text,
                "confidence": round(float(conf), 3),
                "bbox": bbox,
            })
            if conf > 0.3:
                full_text_parts.append(text)

        full_text = " ".join(full_text_parts)

        return {
            "text": full_text,
            "lines": lines,
            "language_hint": None,
            "high_confidence_text": " ".join(l["text"] for l in lines if l["confidence"] > 0.8),
            "engine": "easyocr",
            "skipped": None,
        }

    except Exception as e:
        return {"skipped": f"EasyOCR error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 4. Clothing / appearance analysis
# ─────────────────────────────────────────────────────────────────────────────

def _dominant_colors_hsv(roi: np.ndarray, k: int = 3) -> list[dict]:
    """K-means on HSV pixels → dominant color buckets."""
    if not CV2_OK:
        return []
    try:
        small = cv2.resize(roi, (64, 64))
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        pixels = hsv.reshape(-1, 3).astype(np.float32)

        _, labels, centers = cv2.kmeans(
            pixels, k,
            None,
            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5),
            5,
            cv2.KMEANS_PP_CENTERS,
        )

        counts = np.bincount(labels.flatten())
        total = counts.sum()

        results = []
        for idx in np.argsort(-counts):
            h, s, v = centers[idx]
            pct = round(float(counts[idx]) / total * 100, 1)
            color_name = _hsv_to_name(h, s, v)
            results.append({
                "color_name": color_name,
                "hsv": [round(float(h), 1), round(float(s), 1), round(float(v), 1)],
                "pct": pct,
            })
        return results
    except Exception:
        return []


def _hsv_to_name(h: float, s: float, v: float) -> str:
    """Map HSV to human-readable color name."""
    if v < 40:
        return "black"
    if s < 30:
        if v > 200:
            return "white"
        return "gray"
    # Hue ranges (0-180 in OpenCV)
    if h < 10 or h >= 170:
        return "red"
    if h < 25:
        return "orange"
    if h < 35:
        return "yellow"
    if h < 85:
        if s < 60:
            return "khaki"
        return "green"
    if h < 100:
        return "cyan"
    if h < 125:
        return "blue"
    if h < 145:
        return "navy"
    if h < 160:
        return "purple"
    return "pink"


def _is_camo(roi: np.ndarray) -> bool:
    """Check if ROI contains camouflage pattern (multi-tone earthy colors)."""
    if not CV2_OK or roi.size == 0:
        return False
    try:
        small = cv2.resize(roi, (64, 64))
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        # Earthy tones: greens + browns + tans
        masks = [
            cv2.inRange(hsv, np.array([15, 30, 30]), np.array([45, 150, 180])),   # tan/khaki
            cv2.inRange(hsv, np.array([35, 30, 20]), np.array([80, 180, 130])),   # olive green
            cv2.inRange(hsv, np.array([5, 50, 30]), np.array([20, 200, 150])),    # brown
        ]
        coverage = sum(m.sum() / 255 for m in masks) / (64 * 64)
        # Camo: multiple earthy colors each covering 10-50% of region
        if coverage > 0.4:
            earthy_count = sum(1 for m in masks if m.sum() / 255 > (64 * 64 * 0.08))
            return earthy_count >= 2
        return False
    except Exception:
        return False


def _is_highvis(dominant_colors: list[dict]) -> bool:
    """Check for high-visibility (orange/yellow dominant)."""
    for c in dominant_colors[:2]:
        if c["color_name"] in ("orange", "yellow") and c["pct"] > 25:
            return True
    return False


def clothing_analysis(image_path: str, face_bboxes: list | None = None) -> dict:
    """
    Clothing / appearance analysis from dominant colors below face bboxes.
    Returns per-person clothing type hints and uniform detection.
    """
    if not CV2_OK:
        return {"skipped": "opencv-python required"}
    if not PIL_OK:
        return {"skipped": "Pillow required"}

    try:
        img_bgr = cv2.imread(image_path)
        if img_bgr is None:
            return {"skipped": "Could not read image"}

        h, w = img_bgr.shape[:2]
        persons = []

        def _analyze_torso(person_id: int, x1: int, y1: int, x2: int, y2: int) -> dict:
            face_h = y2 - y1
            # Torso: from bottom of face → 3× face height down
            torso_y1 = y2
            torso_y2 = min(h, y2 + face_h * 3)
            torso_x1 = max(0, x1 - int(face_h * 0.5))
            torso_x2 = min(w, x2 + int(face_h * 0.5))

            torso = img_bgr[torso_y1:torso_y2, torso_x1:torso_x2]
            if torso.size == 0:
                return {"person_id": person_id, "skipped": "No torso region"}

            colors = _dominant_colors_hsv(torso, k=4)
            camo = _is_camo(torso)
            highvis = _is_highvis(colors)

            # Determine clothing type hint
            uniform_detected = False
            uniform_type = None
            clothing_type = "Casual"
            seasonal_hint = None

            if camo:
                uniform_detected = True
                uniform_type = "Camouflage (military/hunting)"
                clothing_type = "Military/tactical"
            elif highvis:
                uniform_detected = True
                uniform_type = "High-visibility vest"
                clothing_type = "Safety/construction worker"

            # Seasonal hint from dominant color
            top_color = colors[0]["color_name"] if colors else None
            if top_color == "white":
                seasonal_hint = "Light/summer or snow environment"
            elif top_color in ("khaki", "beige", "brown"):
                seasonal_hint = "Outdoor/arid — desert, safari"
            elif top_color in ("navy", "black"):
                seasonal_hint = "Formal or tactical"

            # Color-based uniform detection
            if not uniform_detected and colors:
                top2 = [c["color_name"] for c in colors[:2]]
                if set(top2) <= {"navy", "black"} and max(c["pct"] for c in colors[:2]) > 50:
                    uniform_detected = True
                    uniform_type = "Dark formal/tactical"

            return {
                "person_id": person_id,
                "dominant_colors": colors[:4],
                "clothing_type_hint": clothing_type,
                "uniform_detected": uniform_detected,
                "uniform_type": uniform_type,
                "seasonal_hint": seasonal_hint,
                "camo_detected": camo,
                "highvis_detected": highvis,
                "torso_bbox": [torso_x1, torso_y1, torso_x2, torso_y2],
            }

        if face_bboxes:
            for i, bbox in enumerate(face_bboxes):
                try:
                    x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
                    persons.append(_analyze_torso(i, x1, y1, x2, y2))
                except Exception as e:
                    persons.append({"person_id": i, "error": str(e)})
        else:
            # No face bboxes — analyze full lower 2/3 of image
            third_y = h // 3
            roi = img_bgr[third_y:, :]
            colors = _dominant_colors_hsv(roi, k=4)
            camo = _is_camo(roi)
            highvis = _is_highvis(colors)
            persons.append({
                "person_id": 0,
                "dominant_colors": colors[:4],
                "clothing_type_hint": "Unknown (no face bbox)",
                "uniform_detected": camo or highvis,
                "uniform_type": "Camouflage" if camo else ("High-vis" if highvis else None),
                "seasonal_hint": None,
                "camo_detected": camo,
                "highvis_detected": highvis,
                "torso_bbox": [0, third_y, w, h],
            })

        flags = []
        for p in persons:
            if p.get("camo_detected"):
                flags.append(f"🪖 Person {p['person_id']}: camouflage detected — military/hunting")
            if p.get("highvis_detected"):
                flags.append(f"🦺 Person {p['person_id']}: high-visibility clothing — safety/construction")

        return {
            "persons": persons,
            "person_count": len(persons),
            "flags": flags,
            "skipped": None,
        }

    except Exception as e:
        return {"skipped": f"Clothing analysis error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# 5. Best-available OCR selector
# ─────────────────────────────────────────────────────────────────────────────

def best_ocr(image_path: str) -> dict:
    """
    Try OCR engines in priority order: PaddleOCR → EasyOCR → Tesseract.
    Returns first successful result with non-empty text.
    """
    # 1. PaddleOCR
    if PADDLE_OK:
        result = paddleocr_extract(image_path)
        if not result.get("skipped") and result.get("text", "").strip():
            return result

    # 2. EasyOCR (multi-language: en + Chinese simplified + Arabic + Russian + Japanese)
    if EASYOCR_OK:
        result = easyocr_extract(image_path, languages=["en", "ch_sim", "ar", "ru", "ja", "ko"])
        if not result.get("skipped") and result.get("text", "").strip():
            return result

    # 3. Tesseract fallback
    try:
        import pytesseract
        text = pytesseract.image_to_string(PILImage.open(image_path))
        return {
            "text": text.strip(),
            "lines": [{"text": l, "confidence": 0.5, "bbox": None} for l in text.splitlines() if l.strip()],
            "language_hint": None,
            "high_confidence_text": text.strip(),
            "engine": "tesseract",
            "skipped": None,
        }
    except Exception:
        pass

    return {"text": "", "lines": [], "engine": "none", "skipped": "No OCR engine available"}


# ─────────────────────────────────────────────────────────────────────────────
# 6. Master function
# ─────────────────────────────────────────────────────────────────────────────

def analyze_ai(image_path: str, results: dict | None = None) -> dict:
    """
    Run all AI analysis: DeepFace demographics, OpenCLIP scene/country,
    best-available OCR, clothing analysis.
    Returns aggregated dict with all results + cross-stage signals.
    """
    if results is None:
        results = {}

    t0 = time.time()

    # Extract face bboxes from Stage 4 if available
    # content_analysis["faces"] is a dict: {count, details:[{bbox,...}], crops_b64:[...]}
    face_bboxes = []
    content = results.get("content_analysis", {})
    faces_data = content.get("faces", {})
    if isinstance(faces_data, dict):
        for face in faces_data.get("details", []):
            bbox = face.get("bbox")
            if bbox:
                face_bboxes.append(bbox)
    elif isinstance(faces_data, list):
        for face in faces_data:
            if isinstance(face, dict):
                bbox = face.get("bbox")
                if bbox:
                    face_bboxes.append(bbox)

    output = {
        "stage": "ai_analysis",
        "deepface": [],
        "openclip": {},
        "ocr": {},
        "clothing": {},
        "flags": [],
        "location_signals": [],  # fed back into Stage 5
        "elapsed_s": 0.0,
    }

    # DeepFace
    output["deepface"] = deepface_analyze(image_path, face_bboxes if face_bboxes else None)
    for fd in output["deepface"]:
        if not fd.get("skipped"):
            age = fd.get("age", 0)
            gender = fd.get("gender", "")
            emotion = fd.get("dominant_emotion", "")
            race = fd.get("dominant_race", "")
            if emotion in ("angry", "fear", "sad"):
                output["flags"].append(f"😟 Face {fd['face_id']}: dominant emotion = {emotion}")
            if age and gender:
                output["flags"].append(f"👤 Face {fd['face_id']}: estimated {gender}, ~{age}y")

    # OpenCLIP
    output["openclip"] = openclip_scene_classify(image_path)
    if not output["openclip"].get("skipped"):
        top_countries = output["openclip"].get("top_country_hints", [])
        for ch in top_countries:
            output["location_signals"].append({
                "source": "OpenCLIP",
                "type": "country_hint",
                "value": ch["country"],
                "confidence": round(ch["confidence"] * 0.45, 4),  # CLIP confidence scaled to 0.45 max
            })
        if top_countries:
            output["flags"].append(
                f"🌍 CLIP country hint: {top_countries[0]['country']} "
                f"({top_countries[0]['confidence']:.1%})"
            )
        scene = output["openclip"].get("scene_type", "")
        if scene:
            output["flags"].append(f"🏞️ Scene: {scene}")

    # OCR (best available)
    output["ocr"] = best_ocr(image_path)
    if output["ocr"].get("text"):
        engine = output["ocr"].get("engine", "unknown")
        line_count = len(output["ocr"].get("lines", []))
        output["flags"].append(f"📝 OCR ({engine}): {line_count} text lines extracted")

    # Clothing analysis
    output["clothing"] = clothing_analysis(image_path, face_bboxes if face_bboxes else None)
    output["flags"].extend(output["clothing"].get("flags", []))

    output["elapsed_s"] = round(time.time() - t0, 2)
    return output


# ─────────────────────────────────────────────────────────────────────────────
# CLI test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, json

    if len(sys.argv) < 2:
        print("Usage: python stage12_ai_analysis.py <image_path>")
        sys.exit(1)

    path = sys.argv[1]
    print(f"[AI Analysis] Running on: {path}")
    print(f"  DeepFace: {'✅' if DEEPFACE_OK else '❌ (pip install deepface)'}")
    print(f"  OpenCLIP: {'✅' if CLIP_OK else '❌ (pip install open-clip-torch)'}")
    print(f"  PaddleOCR: {'✅' if PADDLE_OK else '❌ (pip install paddleocr)'}")
    print(f"  EasyOCR:  {'✅' if EASYOCR_OK else '❌ (pip install easyocr)'}")
    print()

    result = analyze_ai(path)
    print(json.dumps(result, indent=2, default=str))
