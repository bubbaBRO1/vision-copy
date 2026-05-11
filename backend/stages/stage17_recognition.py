"""Stage 17: Vehicle & Brand Recognition — detect logos, vehicles, and plate regions."""
import os
import re
from typing import Any

try:
    import cv2 as _cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

try:
    from PIL import Image as _PIL
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import numpy as _np
    NP_OK = True
except ImportError:
    NP_OK = False

# Common license plate formats by country (regex → country)
_PLATE_PATTERNS = [
    (re.compile(r"^[A-Z]{1,3}\d{1,4}[A-Z]{0,3}$"), "USA/Generic"),
    (re.compile(r"^[A-Z]{2}\d{2}[A-Z]{3}$"), "UK"),
    (re.compile(r"^[A-Z]{2}-[A-Z]{1,2}\s?\d{1,4}$"), "Germany"),
    (re.compile(r"^\d{4}-[A-Z]{3}$"), "Spain"),
    (re.compile(r"^[A-Z]{3}-\d{4}$"), "Brazil"),
    (re.compile(r"^\d{3}-\d{4}$"), "Japan"),
    (re.compile(r"^[A-Z]{3}\d{4}$"), "Italy"),
    (re.compile(r"^\d{3}[A-Z]{3}\d{2}$"), "France"),
]

# Top-500 brand list subset for zero-shot (expanded at runtime via CLIP if available)
_BRAND_LIST = [
    "Nike", "Adidas", "Apple", "Google", "Samsung", "Microsoft", "Amazon", "Meta",
    "Tesla", "BMW", "Mercedes", "Audi", "Toyota", "Honda", "Ford", "Chevrolet",
    "Coca-Cola", "Pepsi", "McDonald's", "Starbucks", "Louis Vuitton", "Gucci",
    "Chanel", "Rolex", "Ferrari", "Lamborghini", "Porsche", "Intel", "NVIDIA",
    "YouTube", "Instagram", "Twitter", "TikTok", "Spotify", "Netflix", "Uber",
    "Airbnb", "PayPal", "Visa", "Mastercard", "Red Bull", "Monster Energy",
]


def _guess_plate_region(plate_text: str) -> str:
    plate_clean = plate_text.upper().strip().replace(" ", "").replace(".", "")
    for pattern, country in _PLATE_PATTERNS:
        if pattern.match(plate_clean):
            return country
    return "Unknown"


def _clip_brand_recognition(image_path: str) -> list[dict]:
    """Zero-shot brand detection via OpenCLIP."""
    try:
        import open_clip
        import torch
        model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai")
        tokenizer = open_clip.get_tokenizer("ViT-B-32")
        model.eval()

        img = preprocess(_PIL.open(image_path)).unsqueeze(0)
        texts = tokenizer([f"a logo of {b}" for b in _BRAND_LIST])
        with torch.no_grad():
            img_features = model.encode_image(img)
            txt_features = model.encode_text(texts)
            img_features /= img_features.norm(dim=-1, keepdim=True)
            txt_features /= txt_features.norm(dim=-1, keepdim=True)
            similarity = (100.0 * img_features @ txt_features.T).softmax(dim=-1)
            values, indices = similarity[0].topk(5)

        return [
            {"brand": _BRAND_LIST[idx], "confidence": round(val.item(), 4)}
            for val, idx in zip(values, indices)
            if val.item() > 0.05
        ]
    except Exception:
        return []


def _vehicle_classification(image_path: str) -> dict:
    """Basic vehicle type detection using aspect ratio + edge density heuristics."""
    if not CV2_OK or not NP_OK:
        return {}
    try:
        img = _cv2.imread(image_path)
        if img is None:
            return {}
        h, w = img.shape[:2]
        gray = _cv2.cvtColor(img, _cv2.COLOR_BGR2GRAY)
        edges = _cv2.Canny(gray, 50, 150)
        edge_density = _np.count_nonzero(edges) / (h * w)
        aspect = w / h
        # Very rough heuristics
        vehicle_type = "unknown"
        if 1.5 < aspect < 2.5 and edge_density > 0.05:
            vehicle_type = "car (likely)"
        elif aspect > 3.0:
            vehicle_type = "truck/bus (likely)"
        elif aspect < 1.0:
            vehicle_type = "motorcycle (possible)"
        return {"aspect_ratio": round(aspect, 2), "edge_density": round(edge_density, 4), "vehicle_type_guess": vehicle_type}
    except Exception:
        return {}


def analyze(image_path: str) -> dict[str, Any]:
    result: dict = {
        "stage": "recognition",
        "brands": [],
        "vehicle": {},
        "plate_regions": [],
        "summary": {},
    }

    # Read license plates from stage4 sidecar
    plates_sidecar = image_path + ".plates.txt"
    plates = []
    if os.path.exists(plates_sidecar):
        with open(plates_sidecar) as f:
            plates = [line.strip() for line in f if line.strip()]

    plate_regions = []
    for plate in plates:
        region = _guess_plate_region(plate)
        plate_regions.append({"plate": plate, "region_guess": region})

    result["plate_regions"] = plate_regions

    # Brand recognition
    if PIL_OK:
        result["brands"] = _clip_brand_recognition(image_path)

    # Vehicle classification
    result["vehicle"] = _vehicle_classification(image_path)

    result["summary"] = {
        "brands_detected": len(result["brands"]),
        "plates_analyzed": len(plates),
        "vehicle_detected": bool(result["vehicle"].get("vehicle_type_guess", "unknown") != "unknown"),
    }
    return result
