"""
Stage 4 — Visual Content Analysis
Detects and extracts:
  - Faces (count, bounding boxes, attributes: age/gender/emotion via DeepFace)
  - Objects (via OpenCV DNN + YOLO or built-in Haar cascades)
  - OCR text (via pytesseract)
  - QR codes and barcodes (via pyzbar)
  - Dominant color palette
"""

import io
import os
import base64
import tempfile
from pathlib import Path

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import numpy as np
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

try:
    import shutil
    import pytesseract
    if os.name == "nt":
        candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        for c in candidates:
            if os.path.exists(c):
                pytesseract.pytesseract.tesseract_cmd = c
                break
    else:
        found = shutil.which("tesseract")
        if found:
            pytesseract.pytesseract.tesseract_cmd = found
    TESS_OK = True
except ImportError:
    TESS_OK = False

try:
    from pyzbar.pyzbar import decode as zbar_decode
    ZBAR_OK = True
except ImportError:
    ZBAR_OK = False

try:
    from deepface import DeepFace
    DEEPFACE_OK = True
except ImportError:
    DEEPFACE_OK = False

try:
    import onnxruntime as ort
    ORT_OK = True
except ImportError:
    ORT_OK = False

try:
    from langdetect import detect as _langdetect_detect, DetectorFactory
    DetectorFactory.seed = 0
    LANGDETECT_OK = True
except ImportError:
    LANGDETECT_OK = False

# YOLO model paths
_MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
_YOLO_FACE_MODEL = os.path.join(_MODELS_DIR, "yolov8n-face.onnx")
_YOLO_OBJ_MODEL  = os.path.join(_MODELS_DIR, "yolov8n.onnx")

# COCO class names (80 classes)
_COCO_CLASSES = [
    "person","bicycle","car","motorcycle","airplane","bus","train","truck","boat",
    "traffic light","fire hydrant","stop sign","parking meter","bench","bird","cat",
    "dog","horse","sheep","cow","elephant","bear","zebra","giraffe","backpack",
    "umbrella","handbag","tie","suitcase","frisbee","skis","snowboard","sports ball",
    "kite","baseball bat","baseball glove","skateboard","surfboard","tennis racket",
    "bottle","wine glass","cup","fork","knife","spoon","bowl","banana","apple",
    "sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","chair",
    "couch","potted plant","bed","dining table","toilet","tv","laptop","mouse",
    "remote","keyboard","cell phone","microwave","oven","toaster","sink","refrigerator",
    "book","clock","vase","scissors","teddy bear","hair drier","toothbrush",
]
_WEAPON_CLASSES = {"knife", "scissors"}
_VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle", "boat", "airplane", "train"}


# ── Face Detection ─────────────────────────────────────────────────────────────

def _detect_faces_cv2(image_path: str) -> list[dict]:
    """Use OpenCV Haar cascade for fast face detection (no internet needed)."""
    faces = []
    if not CV2_OK:
        return faces
    try:
        img = cv2.imread(image_path)
        if img is None:
            return faces
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)
        detections = cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        for i, (x, y, w, h) in enumerate(detections):
            faces.append({
                "id": i + 1,
                "bbox": [int(x), int(y), int(x + w), int(y + h)],
                "confidence": "Haar (qualitative)",
            })
    except Exception as e:
        faces.append({"error": str(e)})
    return faces


def _analyze_faces_deepface(image_path: str, face_bboxes: list) -> list[dict]:
    """Run DeepFace attribute analysis (age, gender, emotion, race) per face."""
    enriched = []
    if not DEEPFACE_OK or not face_bboxes:
        return face_bboxes  # return unchanged if deepface not available

    try:
        results = DeepFace.analyze(
            img_path=image_path,
            actions=["age", "gender", "emotion", "race"],
            enforce_detection=False,
            silent=True,
        )
        if not isinstance(results, list):
            results = [results]

        for i, face in enumerate(face_bboxes):
            enriched_face = dict(face)
            if i < len(results):
                r = results[i]
                enriched_face["age"]     = r.get("age")
                enriched_face["gender"]  = r.get("dominant_gender")
                enriched_face["emotion"] = r.get("dominant_emotion")
                enriched_face["race"]    = r.get("dominant_race")
            enriched.append(enriched_face)
    except Exception as e:
        for face in face_bboxes:
            enriched.append({**face, "deepface_error": str(e)})
    return enriched


def _crop_faces(image_path: str, face_bboxes: list) -> list[str]:
    """Crop face regions and return as base64 PNG strings (for report / Stage 7)."""
    crops = []
    if not PIL_OK or not face_bboxes:
        return crops
    try:
        img = Image.open(image_path).convert("RGB")
        for face in face_bboxes:
            bbox = face.get("bbox")
            if not bbox:
                continue
            x1, y1, x2, y2 = bbox
            # Add 20% padding
            pad_x = int((x2 - x1) * 0.2)
            pad_y = int((y2 - y1) * 0.2)
            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_y)
            x2 = min(img.width,  x2 + pad_x)
            y2 = min(img.height, y2 + pad_y)
            crop = img.crop((x1, y1, x2, y2))
            buf = io.BytesIO()
            crop.save(buf, format="PNG")
            crops.append(base64.b64encode(buf.getvalue()).decode())
    except Exception:
        pass
    return crops


# ── OCR Text Extraction ────────────────────────────────────────────────────────

def _extract_text(image_path: str) -> dict:
    result = {"text": None, "word_count": 0, "languages_hint": None, "verdict": "No text found"}
    if not TESS_OK:
        result["skipped"] = "pytesseract not installed (or Tesseract binary not found)"
        return result
    try:
        img = Image.open(image_path)
        # Run OCR in multiple PSM modes for best coverage
        text = pytesseract.image_to_string(img, config="--psm 3")
        text = text.strip()
        if text:
            words = text.split()
            result["text"] = text
            result["word_count"] = len(words)
            result["verdict"] = f"✅ {len(words)} words extracted"

            # Simple language detection based on character sets
            has_cyrillic = any('Ѐ' <= c <= 'ӿ' for c in text)
            has_arabic   = any('؀' <= c <= 'ۿ' for c in text)
            has_cjk      = any('一' <= c <= '鿿' for c in text)
            if has_cyrillic: result["languages_hint"] = "Cyrillic (Russian/Ukrainian/etc)"
            elif has_arabic: result["languages_hint"] = "Arabic/Persian"
            elif has_cjk:    result["languages_hint"] = "Chinese/Japanese/Korean"
            else:            result["languages_hint"] = "Latin script"
    except Exception as e:
        result["error"] = str(e)
    return result


# ── QR / Barcode Decoding ─────────────────────────────────────────────────────

def _decode_codes(image_path: str) -> dict:
    result = {"codes": [], "count": 0, "verdict": "No QR/barcode found"}
    if not ZBAR_OK:
        result["skipped"] = "pyzbar not installed"
        return result
    try:
        img = Image.open(image_path)
        decoded = zbar_decode(img)
        for item in decoded:
            result["codes"].append({
                "type": item.type,
                "data": item.data.decode("utf-8", errors="replace"),
                "rect": list(item.rect),
            })
        if result["codes"]:
            result["count"] = len(result["codes"])
            result["verdict"] = f"✅ {result['count']} code(s) decoded"
    except Exception as e:
        result["error"] = str(e)
    return result


# ── Dominant Color Palette ────────────────────────────────────────────────────

def _dominant_colors(image_path: str, n_colors: int = 6) -> dict:
    result = {"colors": [], "verdict": ""}
    if not PIL_OK:
        return result
    try:
        img = Image.open(image_path).convert("RGB")
        # Shrink for speed
        img.thumbnail((200, 200))
        # Quantize to n_colors
        quantized = img.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)
        palette = quantized.getpalette()
        if not palette:
            return result
        colors = []
        for i in range(n_colors):
            r, g, b = palette[i*3], palette[i*3+1], palette[i*3+2]
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            colors.append({"rgb": [r, g, b], "hex": hex_color})
        result["colors"] = colors
        result["verdict"] = f"{n_colors} dominant colors extracted"
    except Exception as e:
        result["error"] = str(e)
    return result


# ── Object Detection (OpenCV DNN / Haar) ─────────────────────────────────────

def _detect_objects(image_path: str) -> dict:
    """
    Lightweight object detection using OpenCV built-in classifiers.
    Falls back gracefully if no DNN model available.
    Detects: eyes, upper body, full body as basic scene context.
    """
    result = {"objects": [], "verdict": "Object detection limited (no YOLO model)"}
    if not CV2_OK:
        result["skipped"] = "OpenCV not installed"
        return result
    try:
        img = cv2.imread(image_path)
        if img is None:
            result["error"] = "Could not read image"
            return result
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        detectors = [
            ("Eye",        "haarcascade_eye.xml"),
            ("Upper Body", "haarcascade_upperbody.xml"),
            ("Full Body",  "haarcascade_fullbody.xml"),
            ("Profile Face", "haarcascade_profileface.xml"),
        ]

        found = []
        for label, xml in detectors:
            path = cv2.data.haarcascades + xml
            if not os.path.exists(path):
                continue
            cascade = cv2.CascadeClassifier(path)
            detections = cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4, minSize=(20, 20)
            )
            for (x, y, w, h) in detections:
                found.append({
                    "label": label,
                    "bbox": [int(x), int(y), int(x+w), int(y+h)],
                })

        result["objects"] = found
        if found:
            counts = {}
            for o in found:
                counts[o["label"]] = counts.get(o["label"], 0) + 1
            summary = ", ".join(f"{v}x {k}" for k, v in counts.items())
            result["verdict"] = f"Detected: {summary}"
        else:
            result["verdict"] = "No objects detected via Haar cascades"
    except Exception as e:
        result["error"] = str(e)
    return result


# ── YOLOv8 ONNX Face Detection ────────────────────────────────────────────────

def _yolo_preprocess(img_rgb, input_size=640):
    """Resize + normalize image for YOLOv8 ONNX input."""
    h, w = img_rgb.shape[:2]
    scale = input_size / max(h, w)
    nh, nw = int(h * scale), int(w * scale)
    resized = cv2.resize(img_rgb, (nw, nh))
    canvas = np.zeros((input_size, input_size, 3), dtype=np.float32)
    canvas[:nh, :nw] = resized
    canvas /= 255.0
    return canvas.transpose(2, 0, 1)[np.newaxis], scale, h, w


def _nms(boxes, scores, iou_threshold=0.45):
    """Simple non-maximum suppression."""
    if not boxes:
        return []
    boxes_arr = np.array(boxes)
    scores_arr = np.array(scores)
    order = scores_arr.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        if order.size == 1:
            break
        xx1 = np.maximum(boxes_arr[i, 0], boxes_arr[order[1:], 0])
        yy1 = np.maximum(boxes_arr[i, 1], boxes_arr[order[1:], 1])
        xx2 = np.minimum(boxes_arr[i, 2], boxes_arr[order[1:], 2])
        yy2 = np.minimum(boxes_arr[i, 3], boxes_arr[order[1:], 3])
        w = np.maximum(0, xx2 - xx1)
        h = np.maximum(0, yy2 - yy1)
        inter = w * h
        area_i = (boxes_arr[i, 2]-boxes_arr[i, 0]) * (boxes_arr[i, 3]-boxes_arr[i, 1])
        area_j = (boxes_arr[order[1:], 2]-boxes_arr[order[1:], 0]) * (boxes_arr[order[1:], 3]-boxes_arr[order[1:], 1])
        iou = inter / (area_i + area_j - inter + 1e-6)
        order = order[1:][iou < iou_threshold]
    return keep


def _detect_faces_onnx(image_path: str) -> list:
    """YOLOv8-face ONNX face detection. Falls back to Haar cascade if unavailable."""
    if not ORT_OK or not CV2_OK or not os.path.exists(_YOLO_FACE_MODEL):
        return _detect_faces_cv2(image_path)
    try:
        img_bgr = cv2.imread(image_path)
        if img_bgr is None:
            return _detect_faces_cv2(image_path)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        tensor, scale, orig_h, orig_w = _yolo_preprocess(img_rgb)

        sess = ort.InferenceSession(_YOLO_FACE_MODEL, providers=["CPUExecutionProvider"])
        input_name = sess.get_inputs()[0].name
        outputs = sess.run(None, {input_name: tensor})
        preds = outputs[0][0]  # [anchors, 20] for face model

        boxes, scores = [], []
        for pred in preds:
            conf = float(pred[4])
            if conf < 0.5:
                continue
            cx, cy, bw, bh = pred[0], pred[1], pred[2], pred[3]
            x1 = int((cx - bw / 2) / scale)
            y1 = int((cy - bh / 2) / scale)
            x2 = int((cx + bw / 2) / scale)
            y2 = int((cy + bh / 2) / scale)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(orig_w, x2), min(orig_h, y2)
            boxes.append([x1, y1, x2, y2])
            scores.append(conf)

        keep = _nms(boxes, scores)
        faces = []
        for i, idx in enumerate(keep):
            faces.append({
                "id": i + 1,
                "bbox": boxes[idx],
                "confidence": round(scores[idx], 3),
                "model": "YOLOv8-face",
            })
        return faces if faces else _detect_faces_cv2(image_path)
    except Exception:
        return _detect_faces_cv2(image_path)


# ── YOLOv8 ONNX Object Detection ─────────────────────────────────────────────

def _detect_objects_yolo(image_path: str) -> dict:
    """YOLOv8n ONNX 80-class COCO object detection. Falls back to Haar if unavailable."""
    if not ORT_OK or not CV2_OK or not os.path.exists(_YOLO_OBJ_MODEL):
        return _detect_objects(image_path)
    try:
        img_bgr = cv2.imread(image_path)
        if img_bgr is None:
            return _detect_objects(image_path)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        tensor, scale, orig_h, orig_w = _yolo_preprocess(img_rgb)

        sess = ort.InferenceSession(_YOLO_OBJ_MODEL, providers=["CPUExecutionProvider"])
        input_name = sess.get_inputs()[0].name
        outputs = sess.run(None, {input_name: tensor})
        preds = outputs[0][0]  # [84, anchors]
        preds = preds.T  # → [anchors, 84]

        boxes, scores, class_ids = [], [], []
        for pred in preds:
            class_scores = pred[4:]
            class_id = int(np.argmax(class_scores))
            conf = float(class_scores[class_id])
            if conf < 0.4:
                continue
            cx, cy, bw, bh = pred[0], pred[1], pred[2], pred[3]
            x1 = int((cx - bw / 2) / scale)
            y1 = int((cy - bh / 2) / scale)
            x2 = int((cx + bw / 2) / scale)
            y2 = int((cy + bh / 2) / scale)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(orig_w, x2), min(orig_h, y2)
            boxes.append([x1, y1, x2, y2])
            scores.append(conf)
            class_ids.append(class_id)

        keep = _nms(boxes, scores)
        objects = []
        detected_labels = set()
        for idx in keep:
            label = _COCO_CLASSES[class_ids[idx]] if class_ids[idx] < len(_COCO_CLASSES) else f"class_{class_ids[idx]}"
            objects.append({
                "label": label,
                "confidence": round(scores[idx], 3),
                "bbox": boxes[idx],
            })
            detected_labels.add(label)

        weapon_detected = bool(detected_labels & _WEAPON_CLASSES)
        vehicle_detected = bool(detected_labels & _VEHICLE_CLASSES)
        weapon_classes = list(detected_labels & _WEAPON_CLASSES)

        if objects:
            counts = {}
            for o in objects:
                counts[o["label"]] = counts.get(o["label"], 0) + 1
            verdict = "Detected: " + ", ".join(f"{v}x {k}" for k, v in counts.items())
        else:
            verdict = "No objects detected"

        return {
            "objects": objects,
            "verdict": verdict,
            "model": "YOLOv8n",
            "weapon_detected": weapon_detected,
            "weapon_classes": weapon_classes,
            "vehicle_detected": vehicle_detected,
        }
    except Exception:
        result = _detect_objects(image_path)
        result["weapon_detected"] = False
        result["weapon_classes"] = []
        result["vehicle_detected"] = False
        return result


# ── License Plate Detection ───────────────────────────────────────────────────

def _detect_license_plate(image_path: str) -> dict:
    """Detect and OCR license plates using contour analysis + Tesseract."""
    result = {"plates_found": False, "plates": [], "verdict": "No license plate detected"}
    if not CV2_OK or not TESS_OK or not PIL_OK:
        result["skipped"] = "OpenCV or Tesseract not available"
        return result
    try:
        import re
        img = cv2.imread(image_path)
        if img is None:
            return result
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        plate_candidates = []
        h_img, w_img = gray.shape
        for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:100]:
            x, y, w, h = cv2.boundingRect(cnt)
            if w < 60 or h < 15 or w > w_img * 0.8:
                continue
            aspect = w / h
            if 1.5 < aspect < 7.0:  # typical plate aspect ratio
                plate_candidates.append((x, y, w, h))

        # Deduplicate overlapping candidates
        seen = []
        for (x, y, w, h) in plate_candidates:
            overlap = False
            for (sx, sy, sw, sh) in seen:
                if abs(x - sx) < 20 and abs(y - sy) < 20:
                    overlap = True
                    break
            if not overlap:
                seen.append((x, y, w, h))

        plates = []
        for (x, y, w, h) in seen[:5]:
            # Pad slightly
            pad = 4
            crop = img[max(0, y-pad):y+h+pad, max(0, x-pad):x+w+pad]
            if crop.size == 0:
                continue
            crop_pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            crop_pil = crop_pil.resize((crop_pil.width * 3, crop_pil.height * 3), Image.LANCZOS)
            ocr_text = pytesseract.image_to_string(
                crop_pil, config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            ).strip()
            ocr_text = re.sub(r"[^A-Z0-9]", "", ocr_text.upper())
            if len(ocr_text) < 3:
                continue

            # Country pattern hints
            country_hint = "Unknown"
            if re.match(r'^[A-Z]{2}\d{2}[A-Z]{3}$', ocr_text):
                country_hint = "UK (new format)"
            elif re.match(r'^[A-Z]{1,3}\d{1,4}[A-Z]{0,3}$', ocr_text):
                country_hint = "UK (old format)"
            elif re.match(r'^\d{3}[A-Z]{3}$', ocr_text) or re.match(r'^[A-Z]{3}\d{4}$', ocr_text):
                country_hint = "US (possible)"
            elif re.match(r'^[A-Z]\d{3}[A-Z]{2}\d{2,3}$', ocr_text):
                country_hint = "Russia (possible)"

            plates.append({
                "bbox": [int(x), int(y), int(x+w), int(y+h)],
                "ocr_text": ocr_text,
                "country_hint": country_hint,
            })

        if plates:
            result["plates_found"] = True
            result["plates"] = plates
            result["verdict"] = f"✅ {len(plates)} license plate(s) detected: {', '.join(p['ocr_text'] for p in plates)}"
    except Exception as e:
        result["error"] = str(e)
    return result


# ── Document Type Detection ───────────────────────────────────────────────────

def _detect_document_type(image_path: str) -> dict:
    """Detect passports, ID cards, driver's licenses from aspect ratio + OCR."""
    result = {
        "document_detected": False,
        "document_type": None,
        "confidence": None,
        "mrz_lines": [],
        "flags": [],
    }
    if not PIL_OK or not TESS_OK:
        return result
    try:
        import re
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        aspect = w / h if h > 0 else 1.0

        doc_type = None
        confidence = "Low"

        # Aspect ratio heuristics
        if 0.65 < aspect < 0.75:
            doc_type = "Passport (booklet)"
            confidence = "Medium"
        elif 1.5 < aspect < 1.7:
            doc_type = "ID Card / Driver's License"
            confidence = "Medium"
        elif 1.7 < aspect < 1.9:
            doc_type = "Business Card"
            confidence = "Low"

        # OCR-based detection
        if TESS_OK:
            text = pytesseract.image_to_string(img, config="--psm 3").upper()
            mrz_pattern = re.compile(r'^[A-Z0-9<]{30,44}$', re.MULTILINE)
            mrz_lines = mrz_pattern.findall(text)
            if mrz_lines:
                result["mrz_lines"] = mrz_lines[:2]
                doc_type = "Passport (MRZ detected)"
                confidence = "High"
                result["flags"].append("🛂 Machine Readable Zone (MRZ) detected — passport or travel document")
            if re.search(r'DRIVER|LICENSE|PERMIS|FÜHRERSCHEIN', text):
                doc_type = "Driver's License"
                confidence = "High"
                result["flags"].append("🪪 Driver's license detected")
            if re.search(r'PASSPORT|PASSEPORT|REISEPASS', text):
                doc_type = "Passport"
                confidence = "High"
                result["flags"].append("🛂 Passport text detected")
            if re.search(r'NATIONAL ID|CARTE NATIONALE|PERSONALAUSWEIS', text):
                doc_type = "National ID Card"
                confidence = "High"
                result["flags"].append("🪪 National ID card detected")
            if re.search(r'VISA|ENTRY PERMIT', text):
                doc_type = "Visa"
                confidence = "High"
                result["flags"].append("✈️  Visa detected")

        if doc_type:
            result["document_detected"] = True
            result["document_type"] = doc_type
            result["confidence"] = confidence

    except Exception as e:
        result["error"] = str(e)
    return result


# ── Language Detection ────────────────────────────────────────────────────────

def _detect_language(text: str) -> dict:
    """Detect language of OCR text. Uses langdetect if available, else char heuristics."""
    result = {"language": None, "language_name": None, "confidence": None, "method": None}
    if not text or len(text.strip()) < 10:
        return result

    if LANGDETECT_OK:
        try:
            from langdetect import detect_langs
            langs = detect_langs(text)
            if langs:
                best = langs[0]
                lang_names = {
                    "en": "English", "ru": "Russian", "ar": "Arabic", "zh-cn": "Chinese (Simplified)",
                    "zh-tw": "Chinese (Traditional)", "ja": "Japanese", "ko": "Korean", "de": "German",
                    "fr": "French", "es": "Spanish", "pt": "Portuguese", "it": "Italian",
                    "nl": "Dutch", "pl": "Polish", "tr": "Turkish", "fa": "Persian/Farsi",
                    "uk": "Ukrainian", "he": "Hebrew", "hi": "Hindi", "th": "Thai",
                }
                result["language"] = best.lang
                result["language_name"] = lang_names.get(best.lang, best.lang.upper())
                result["confidence"] = round(best.prob, 3)
                result["method"] = "langdetect"
                return result
        except Exception:
            pass

    # Fallback: character range heuristics
    has_cyrillic = any('Ѐ' <= c <= 'ӿ' for c in text)
    has_arabic   = any('؀' <= c <= 'ۿ' for c in text)
    has_cjk      = any('一' <= c <= '鿿' for c in text)
    has_hangul   = any('가' <= c <= '힣' for c in text)
    has_kana     = any('぀' <= c <= 'ヿ' for c in text)
    has_thai     = any('฀' <= c <= '๿' for c in text)
    has_devanagari = any('ऀ' <= c <= 'ॿ' for c in text)

    if has_cyrillic:
        result["language"] = "ru"
        result["language_name"] = "Cyrillic (Russian/Ukrainian/etc)"
    elif has_arabic:
        result["language"] = "ar"
        result["language_name"] = "Arabic/Persian"
    elif has_hangul:
        result["language"] = "ko"
        result["language_name"] = "Korean"
    elif has_kana:
        result["language"] = "ja"
        result["language_name"] = "Japanese"
    elif has_cjk:
        result["language"] = "zh"
        result["language_name"] = "Chinese"
    elif has_thai:
        result["language"] = "th"
        result["language_name"] = "Thai"
    elif has_devanagari:
        result["language"] = "hi"
        result["language_name"] = "Hindi/Devanagari"
    else:
        result["language"] = "en"
        result["language_name"] = "Latin script (likely English)"
    result["method"] = "heuristic"
    return result


# ── Image Quality Metrics ─────────────────────────────────────────────────────

def _image_quality(image_path: str) -> dict:
    result = {}
    if not CV2_OK:
        return result
    try:
        img = cv2.imread(image_path)
        if img is None:
            return result
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Laplacian variance = sharpness
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        result["sharpness_score"] = round(laplacian_var, 2)
        result["sharpness_verdict"] = (
            "Sharp" if laplacian_var > 100 else
            "Moderate" if laplacian_var > 30 else "Blurry"
        )
        # Brightness
        brightness = float(np.mean(gray))
        result["brightness"] = round(brightness, 2)
        result["brightness_verdict"] = (
            "Overexposed" if brightness > 220 else
            "Dark" if brightness < 40 else "Normal"
        )
    except Exception as e:
        result["error"] = str(e)
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def analyze(image_path: str, run_deepface: bool = True) -> dict:
    """
    Full visual content analysis of image_path.
    run_deepface: set False to skip heavy DeepFace model (--stealth or beginner mode).
    """
    # Face detection — prefer ONNX YOLOv8-face, fall back to Haar
    faces_raw = _detect_faces_onnx(image_path)
    faces = _analyze_faces_deepface(image_path, faces_raw) if run_deepface else faces_raw
    face_crops_b64 = _crop_faces(image_path, faces)

    # OCR text + language detection
    text = _extract_text(image_path)
    if text.get("text"):
        lang = _detect_language(text["text"])
        text["language"] = lang.get("language")
        text["language_name"] = lang.get("language_name")
        text["language_confidence"] = lang.get("confidence")
        text["language_method"] = lang.get("method")

    # Other analysis
    codes        = _decode_codes(image_path)
    colors       = _dominant_colors(image_path)
    objects      = _detect_objects_yolo(image_path)
    quality      = _image_quality(image_path)
    license_plates = _detect_license_plate(image_path)
    document_type  = _detect_document_type(image_path)

    # Summary flags
    flags = []
    if faces:
        model_used = faces[0].get("model", "Haar")
        flags.append(f"👤 {len(faces)} face(s) detected ({model_used})")
    if text.get("text"):
        lang_name = text.get("language_name", "")
        flags.append(f"📝 Text found ({text['word_count']} words{', ' + lang_name if lang_name else ''})")
    if codes.get("codes"):
        flags.append(f"📱 {codes['count']} QR/barcode(s) decoded")
    if objects.get("objects"):
        flags.append(f"🔍 Objects: {objects['verdict']}")
    if objects.get("weapon_detected"):
        flags.append(f"⚠️  Weapon detected: {', '.join(objects['weapon_classes'])}")
    if license_plates.get("plates_found"):
        flags.append(license_plates["verdict"])
    for f in document_type.get("flags", []):
        flags.append(f)

    return {
        "stage": "content_analysis",
        "flags": flags,
        "faces": {
            "count": len(faces),
            "details": faces,
            "crops_b64": face_crops_b64,  # used by Stage 7
        },
        "ocr": text,
        "qr_barcodes": codes,
        "dominant_colors": colors,
        "objects": objects,
        "license_plates": license_plates,
        "document_type": document_type,
        "quality": quality,
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python stage4_content.py <image>")
        sys.exit(1)
    result = analyze(sys.argv[1])
    # Strip face crop b64 for terminal readability
    result["faces"]["crops_b64"] = [f"<base64 crop {i+1}>" for i in range(len(result["faces"]["crops_b64"]))]
    print(json.dumps(result, indent=2, default=str))
