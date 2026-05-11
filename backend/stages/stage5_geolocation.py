"""
Stage 5 — AI Geolocation
Determines WHERE a photo was taken even without GPS EXIF data.

Methods:
  1. GeoSpy AI API — visual geolocation from architectural/environmental cues
  2. OCR cross-reference — extracts text clues (street signs, store names, license plates)
     and geocodes them via Nominatim (OpenStreetMap, free, no API key)
  3. Landmark heuristics — checks OCR text against known landmark/city databases
  4. Falls back gracefully if no APIs configured
"""

import os
import re
import json
import time
import base64
import math
import requests
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

try:
    import ephem
    EPHEM_OK = True
except ImportError:
    EPHEM_OK = False

try:
    import pvlib
    PVLIB_OK = True
except ImportError:
    PVLIB_OK = False

try:
    from timezonefinder import TimezoneFinder
    _TF = TimezoneFinder()
    TZF_OK = True
except ImportError:
    _TF = None
    TZF_OK = False

try:
    import overpy as _overpy
    OVERPY_OK = True
except ImportError:
    OVERPY_OK = False


# ── GeoSpy AI ─────────────────────────────────────────────────────────────────

def _geospy(image_path: str, api_key: str) -> dict:
    """
    Submit image to GeoSpy AI for visual geolocation.
    API key from: https://geospy.ai (free tier available).
    """
    result = {
        "method": "GeoSpy AI",
        "country": None, "city": None,
        "lat": None, "lon": None,
        "confidence": None,
        "description": None,
        "maps_link": None,
    }
    if not api_key:
        result["skipped"] = "No GeoSpy API key (set GEOSPY_API_KEY)"
        return result
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {"image": img_b64}
        resp = requests.post(
            "https://dev.geospy.ai/predict",
            headers=headers,
            json=payload,
            timeout=30,
        )
        data = resp.json()

        if resp.status_code == 200:
            result["country"]     = data.get("country")
            result["city"]        = data.get("city")
            result["lat"]         = data.get("coordinates", {}).get("latitude")
            result["lon"]         = data.get("coordinates", {}).get("longitude")
            result["confidence"]  = data.get("confidence")
            result["description"] = data.get("description")
            if result["lat"] and result["lon"]:
                result["maps_link"] = (
                    f"https://www.google.com/maps?q={result['lat']},{result['lon']}"
                )
        else:
            result["error"] = f"HTTP {resp.status_code}: {data}"
    except Exception as e:
        result["error"] = str(e)
    return result


# ── OCR-Based Geocoding ───────────────────────────────────────────────────────

# Regex patterns to extract location clues from OCR text
_PHONE_PATTERNS = [
    r'\+\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}',  # international phone
]
_POSTCODE_PATTERNS = [
    r'\b[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}\b',  # UK postcode
    r'\b\d{5}(?:-\d{4})?\b',                          # US ZIP
    r'\b\d{4,6}\b',                                   # Generic postal code
]
_COUNTRY_CODES = {
    "+1": "USA/Canada", "+44": "United Kingdom", "+49": "Germany",
    "+33": "France", "+81": "Japan", "+86": "China", "+7": "Russia",
    "+61": "Australia", "+55": "Brazil", "+91": "India",
    "+39": "Italy", "+34": "Spain", "+82": "South Korea",
    "+52": "Mexico", "+31": "Netherlands", "+46": "Sweden",
}


def _extract_location_clues(ocr_text: str) -> dict:
    """Parse OCR text for location-revealing patterns."""
    clues = {
        "phone_numbers": [],
        "postcodes": [],
        "country_hints": [],
        "raw_keywords": [],
    }
    if not ocr_text:
        return clues

    text = ocr_text.upper()

    # Phone numbers
    for pat in _PHONE_PATTERNS:
        matches = re.findall(pat, ocr_text, re.IGNORECASE)
        clues["phone_numbers"].extend(matches)
        for m in matches:
            for code, country in _COUNTRY_CODES.items():
                if m.startswith(code):
                    clues["country_hints"].append(country)

    # Postcodes
    for pat in _POSTCODE_PATTERNS:
        matches = re.findall(pat, ocr_text)
        clues["postcodes"].extend(matches)

    # Location keywords
    keywords = [
        "STREET", "AVENUE", "BOULEVARD", "PLAZA", "SQUARE",
        "STATION", "AIRPORT", "METRO", "SUBWAY", "DISTRICT",
        "TOKYO", "LONDON", "PARIS", "NEW YORK", "BERLIN", "ROME",
        "SYDNEY", "MOSCOW", "BEIJING", "DUBAI", "SINGAPORE",
        "RUE", "STRASSE", "AVENIDA", "CALLE", "VIA",  # foreign street words
        "EXIT", "FREEWAY", "HWY", "ROUTE",
    ]
    for kw in keywords:
        if kw in text:
            clues["raw_keywords"].append(kw.title())

    return clues


def _nominatim_geocode(query: str) -> dict | None:
    """Free OpenStreetMap geocoding — no API key needed."""
    try:
        headers = {"User-Agent": "ImageTrace-OSINT/2.0"}
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            headers=headers,
            timeout=10,
        )
        data = resp.json()
        if data:
            r = data[0]
            lat = float(r["lat"])
            lon = float(r["lon"])
            return {
                "display_name": r.get("display_name"),
                "lat": lat,
                "lon": lon,
                "maps_link": f"https://www.google.com/maps?q={lat},{lon}",
                "type": r.get("type"),
            }
    except Exception:
        pass
    return None


def _ocr_geolocation(ocr_text: str) -> dict:
    """Attempt to geolocate based on OCR-extracted text clues."""
    result = {
        "method": "OCR Cross-Reference",
        "clues": {},
        "geocoded": None,
        "country_hint": None,
        "verdict": "No location clues in text",
    }
    if not ocr_text:
        result["skipped"] = "No OCR text available"
        return result

    clues = _extract_location_clues(ocr_text)
    result["clues"] = clues

    # Country hint from phone number
    if clues["country_hints"]:
        result["country_hint"] = clues["country_hints"][0]
        result["verdict"] = f"📞 Phone number suggests: {result['country_hint']}"

    # Try to geocode specific keywords
    keywords = clues["raw_keywords"]
    postcodes = clues["postcodes"]

    geocoded = None
    if postcodes:
        time.sleep(1)  # Nominatim rate limit
        geocoded = _nominatim_geocode(postcodes[0])
    if not geocoded and keywords:
        query = " ".join(keywords[:3])
        time.sleep(1)
        geocoded = _nominatim_geocode(query)

    if geocoded:
        result["geocoded"] = geocoded
        result["verdict"] = (
            f"📍 OCR geocoded: {geocoded['display_name'][:80]}"
        )

    return result


# ── Landmark Hint Database ────────────────────────────────────────────────────

LANDMARK_HINTS = {
    # Famous structures / text that would appear near them
    "EIFFEL": ("Paris, France", 48.8584, 2.2945),
    "BIG BEN": ("London, UK", 51.5007, -0.1246),
    "TOWER BRIDGE": ("London, UK", 51.5055, -0.0754),
    "COLOSSEUM": ("Rome, Italy", 41.8902, 12.4922),
    "TIMES SQUARE": ("New York, USA", 40.7580, -73.9855),
    "CENTRAL PARK": ("New York, USA", 40.7851, -73.9683),
    "GOLDEN GATE": ("San Francisco, USA", 37.8199, -122.4783),
    "STATUE OF LIBERTY": ("New York, USA", 40.6892, -74.0445),
    "TOKYO TOWER": ("Tokyo, Japan", 35.6586, 139.7454),
    "SHIBUYA": ("Tokyo, Japan", 35.6580, 139.7016),
    "OPERA HOUSE": ("Sydney, Australia", -33.8568, 151.2153),
    "BURJ KHALIFA": ("Dubai, UAE", 25.1972, 55.2744),
    "KREMLIN": ("Moscow, Russia", 55.7520, 37.6175),
    "RED SQUARE": ("Moscow, Russia", 55.7539, 37.6208),
    "SAGRADA FAMILIA": ("Barcelona, Spain", 41.4036, 2.1744),
    "ACROPOLIS": ("Athens, Greece", 37.9715, 23.7267),
    "PARTHENON": ("Athens, Greece", 37.9715, 23.7267),
    "PYRAMIDS": ("Giza, Egypt", 29.9792, 31.1342),
    "TAJ MAHAL": ("Agra, India", 27.1751, 78.0421),
    "GREAT WALL": ("Beijing, China", 40.4319, 116.5704),
}


def _landmark_detection(ocr_text: str) -> dict:
    result = {"landmarks": [], "best_match": None}
    if not ocr_text:
        return result
    text_upper = ocr_text.upper()
    for keyword, (location, lat, lon) in LANDMARK_HINTS.items():
        if keyword in text_upper:
            result["landmarks"].append({
                "keyword": keyword,
                "location": location,
                "lat": lat,
                "lon": lon,
                "maps_link": f"https://www.google.com/maps?q={lat},{lon}",
            })
    if result["landmarks"]:
        result["best_match"] = result["landmarks"][0]
    return result


# ── Sun Angle Geolocation ─────────────────────────────────────────────────────

def _sun_angle_analysis(image_path: str, datetime_original: str = None) -> dict:
    """
    Estimate latitude band and time-of-day from shadow direction in image.
    Uses ephem for sun position calculations when DateTimeOriginal is available.
    """
    result = {
        "shadow_direction_deg": None,
        "estimated_latitude_band": None,
        "estimated_time_of_day": None,
        "sun_azimuth_estimate": None,
        "lat_candidates": [],
        "confidence": "Low",
        "verdict": "Sun angle analysis not performed",
        "skipped": None,
    }

    if not PIL_OK or not CV2_OK:
        result["skipped"] = "OpenCV/Pillow not available"
        return result

    try:
        import cv2 as _cv2
        img_bgr = _cv2.imread(image_path)
        if img_bgr is None:
            result["skipped"] = "Cannot read image"
            return result

        # Resize for speed
        h, w = img_bgr.shape[:2]
        if max(h, w) > 800:
            scale = 800 / max(h, w)
            img_bgr = _cv2.resize(img_bgr, (int(w * scale), int(h * scale)))

        # Detect shadow regions: very dark pixels (Value < 60 in HSV)
        hsv = _cv2.cvtColor(img_bgr, _cv2.COLOR_BGR2HSV)
        _, shadow_mask = _cv2.threshold(hsv[:, :, 2], 60, 255, _cv2.THRESH_BINARY_INV)
        # Remove tiny noise
        kernel = np.ones((5, 5), np.uint8)
        shadow_mask = _cv2.morphologyEx(shadow_mask, _cv2.MORPH_OPEN, kernel)

        contours, _ = _cv2.findContours(shadow_mask, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            result["skipped"] = "No shadows detected in image"
            return result

        # Find largest shadow contour
        largest = max(contours, key=_cv2.contourArea)
        if _cv2.contourArea(largest) < 500:
            result["skipped"] = "Shadow regions too small for analysis"
            return result

        # Fit ellipse to get shadow orientation angle
        if len(largest) < 5:
            result["skipped"] = "Insufficient shadow contour points"
            return result

        ellipse = _cv2.fitEllipse(largest)
        angle_deg = float(ellipse[2])  # 0-180 from horizontal
        # Convert to compass bearing (shadow points away from sun)
        shadow_bearing = (90 - angle_deg) % 360
        result["shadow_direction_deg"] = round(shadow_bearing, 1)

        # Estimate time-of-day from shadow length relative to contour
        x, y, ew, eh = _cv2.boundingRect(largest)
        shadow_length_ratio = max(ew, eh) / min(img_bgr.shape[:2])
        if shadow_length_ratio > 0.4:
            result["estimated_time_of_day"] = "Morning or Evening (long shadows)"
        elif shadow_length_ratio > 0.15:
            result["estimated_time_of_day"] = "Mid-morning or Mid-afternoon"
        else:
            result["estimated_time_of_day"] = "Near Midday (short shadows)"

        # Sun direction is ~180° opposite to shadow direction
        sun_azimuth = (shadow_bearing + 180) % 360
        result["sun_azimuth_estimate"] = round(sun_azimuth, 1)

        # Estimate latitude band from sun azimuth
        if 150 <= sun_azimuth <= 210:
            result["estimated_latitude_band"] = "Northern Hemisphere (sun in south)"
            result["lat_candidates"] = [20, 35, 45, 55]
        elif (sun_azimuth >= 330 or sun_azimuth <= 30):
            result["estimated_latitude_band"] = "Southern Hemisphere (sun in north)"
            result["lat_candidates"] = [-15, -25, -35]
        elif 60 <= sun_azimuth <= 120:
            result["estimated_latitude_band"] = "Morning shot (sun in east)"
            result["lat_candidates"] = []
        elif 240 <= sun_azimuth <= 300:
            result["estimated_latitude_band"] = "Afternoon shot (sun in west)"
            result["lat_candidates"] = []

        # Use ephem for precise latitude estimation if datetime available
        if EPHEM_OK and datetime_original:
            try:
                from datetime import datetime as dt
                dt_orig = dt.strptime(datetime_original, "%Y:%m:%d %H:%M:%S")
                ephem_date = ephem.Date(dt_orig)
                sun = ephem.Sun()
                best_lat = None
                best_diff = 999
                for lat in range(-60, 61, 5):
                    obs = ephem.Observer()
                    obs.lat = str(lat)
                    obs.lon = "0"
                    obs.date = ephem_date
                    sun.compute(obs)
                    sun_az = math.degrees(float(sun.az))
                    diff = abs(sun_az - sun_azimuth)
                    if diff > 180:
                        diff = 360 - diff
                    if diff < best_diff:
                        best_diff = diff
                        best_lat = lat
                if best_lat is not None and best_diff < 30:
                    result["lat_candidates"] = [best_lat]
                    result["confidence"] = "Medium"
                    result["estimated_latitude_band"] = f"~{best_lat}° latitude (ephem)"
            except Exception:
                pass

        result["confidence"] = "Medium" if result["lat_candidates"] else "Low"
        result["verdict"] = (
            f"☀️  Shadow bearing {shadow_bearing:.0f}°, sun at {sun_azimuth:.0f}°, "
            f"{result.get('estimated_latitude_band', 'unknown hemisphere')}, "
            f"{result.get('estimated_time_of_day', '')}"
        )
    except Exception as e:
        result["skipped"] = f"Sun angle analysis error: {e}"

    return result


# ── Vegetation / Climate Zone ─────────────────────────────────────────────────

def _vegetation_climate_zone(image_path: str, yolo_objects: list = None) -> dict:
    """
    Classify climate zone from vegetation/terrain colors visible in image.
    Uses dominant color palette analysis + YOLO object detection results.
    """
    result = {
        "climate_zone": None,
        "region_hints": [],
        "confidence": "Low",
        "verdict": "Climate zone indeterminate",
    }
    if not PIL_OK:
        return result

    try:
        img = Image.open(image_path).convert("RGB")
        img.thumbnail((200, 200))
        pixels = np.array(img).reshape(-1, 3).astype(float)

        # Compute average and dominant color channel ratios
        avg_r = float(pixels[:, 0].mean())
        avg_g = float(pixels[:, 1].mean())
        avg_b = float(pixels[:, 2].mean())
        avg_brightness = (avg_r + avg_g + avg_b) / 3

        # Color category percentages
        # Green-dominant pixels (vegetation)
        green_mask = (pixels[:, 1] > pixels[:, 0] * 1.1) & (pixels[:, 1] > pixels[:, 2] * 1.1)
        green_pct = float(green_mask.mean())

        # White/near-white pixels (snow/overcast)
        white_mask = (pixels.min(axis=1) > 180) & (pixels.max(axis=1) < 256)
        white_pct = float(white_mask.mean())

        # Sandy/ochre pixels (desert/arid)
        sandy_mask = (pixels[:, 0] > 150) & (pixels[:, 1] > 120) & (pixels[:, 1] < pixels[:, 0]) & (pixels[:, 2] < 120)
        sandy_pct = float(sandy_mask.mean())

        # Reddish rock (American Southwest / Australian Outback)
        red_rock_mask = (pixels[:, 0] > 140) & (pixels[:, 0] > pixels[:, 1] * 1.4) & (pixels[:, 0] > pixels[:, 2] * 1.4)
        red_rock_pct = float(red_rock_mask.mean())

        # Blue sky percentage
        blue_sky_mask = (pixels[:, 2] > 150) & (pixels[:, 2] > pixels[:, 0] * 1.2) & (pixels[:, 2] > pixels[:, 1] * 1.1)
        blue_pct = float(blue_sky_mask.mean())

        hints = []
        zone = None
        confidence = "Low"

        # Check for YOLO palm trees / snow from object results
        yolo_labels = set()
        if yolo_objects:
            for obj in yolo_objects:
                yolo_labels.add(obj.get("label", "").lower())

        if white_pct > 0.35:
            zone = "Arctic/Alpine"
            hints.append("High white coverage — snow or arctic environment")
            confidence = "Medium"
        elif red_rock_pct > 0.2:
            zone = "Arid (Red Rock)"
            hints.append("Red/orange rock formations → possibly American Southwest or Australian Outback")
            confidence = "Medium"
        elif sandy_pct > 0.3 and green_pct < 0.1:
            zone = "Desert/Arid"
            hints.append("Sandy/ochre dominant palette → desert environment (Middle East, Africa, SW USA)")
            confidence = "Medium"
        elif green_pct > 0.35 and avg_brightness > 100:
            if avg_g > 100 and avg_b > 80:
                zone = "Tropical/Subtropical"
                hints.append("Dense green + blue sky → tropical or subtropical")
                confidence = "Medium"
            else:
                zone = "Temperate"
                hints.append("Green vegetation → temperate region")
                confidence = "Low"
        elif green_pct > 0.15 and avg_g > avg_r * 0.9:
            zone = "Temperate"
            hints.append("Moderate green coverage → temperate")
            confidence = "Low"

        # Refine with YOLO objects
        if "boat" in yolo_labels or "surfboard" in yolo_labels:
            hints.append("Water recreation equipment → coastal region")
        if "umbrella" in yolo_labels and zone in ["Tropical/Subtropical", None]:
            hints.append("Umbrellas present → possibly tropical beach or rainy region")
        if "snowboard" in yolo_labels or "skis" in yolo_labels:
            zone = "Alpine/Winter"
            hints.append("Winter sports equipment → Alpine environment")
            confidence = "High"

        result["climate_zone"] = zone
        result["region_hints"] = hints
        result["confidence"] = confidence
        result["verdict"] = (
            f"🌿 Climate zone: {zone} — {'; '.join(hints[:2])}"
            if zone else "Climate zone indeterminate from color analysis"
        )
    except Exception as e:
        result["verdict"] = f"Vegetation analysis error: {e}"

    return result


# ── Architecture Style Hints ──────────────────────────────────────────────────

def _architecture_style_hint(image_path: str, ocr_text: str = "") -> dict:
    """
    Heuristic architecture style classification from building surface colors + OCR script.
    """
    result = {
        "style": None,
        "region_hint": None,
        "confidence": "Low",
        "verdict": "Architecture style indeterminate",
    }
    if not PIL_OK:
        return result

    try:
        img = Image.open(image_path).convert("RGB")
        img.thumbnail((300, 300))
        pixels = np.array(img).reshape(-1, 3).astype(float)

        avg_r = float(pixels[:, 0].mean())
        avg_g = float(pixels[:, 1].mean())
        avg_b = float(pixels[:, 2].mean())

        # Red brick: medium-high red, lower green, lower blue
        red_brick_mask = (
            (pixels[:, 0] > 120) & (pixels[:, 0] < 200) &
            (pixels[:, 0] > pixels[:, 1] * 1.3) &
            (pixels[:, 2] < 120)
        )
        red_brick_pct = float(red_brick_mask.mean())

        # White/cream stucco
        stucco_mask = (pixels.min(axis=1) > 160) & (pixels.max(axis=1) < 256)
        stucco_pct = float(stucco_mask.mean())

        # Grey concrete (Soviet-era, brutalist)
        grey_mask = (
            (np.abs(pixels[:, 0].astype(int) - pixels[:, 1].astype(int)) < 15) &
            (np.abs(pixels[:, 1].astype(int) - pixels[:, 2].astype(int)) < 15) &
            (pixels.mean(axis=1) > 80) &
            (pixels.mean(axis=1) < 180)
        )
        grey_pct = float(grey_mask.mean())

        # Terracotta/ochre walls (Mediterranean, Latin America)
        terra_mask = (
            (pixels[:, 0] > 150) & (pixels[:, 0] < 230) &
            (pixels[:, 1] > 80) & (pixels[:, 1] < 160) &
            (pixels[:, 2] < 100)
        )
        terra_pct = float(terra_mask.mean())

        # OCR script detection for region confirmation
        ocr_upper = (ocr_text or "").upper()
        has_cyrillic_ocr = any('Ѐ' <= c <= 'ӿ' for c in (ocr_text or ""))
        has_arabic_ocr = any('؀' <= c <= 'ۿ' for c in (ocr_text or ""))
        has_cjk_ocr = any('一' <= c <= '鿿' for c in (ocr_text or ""))

        style = None
        region_hint = None
        confidence = "Low"

        if red_brick_pct > 0.15:
            style = "Red Brick"
            region_hint = "UK / Ireland / NE USA / Northern Europe"
            confidence = "Medium"
        elif stucco_pct > 0.35 and terra_pct > 0.1:
            style = "Mediterranean Stucco"
            region_hint = "Mediterranean / Middle East / Southern Europe"
            confidence = "Medium"
        elif grey_pct > 0.4 and stucco_pct < 0.2:
            style = "Concrete / Brutalist"
            region_hint = "Soviet-era / Eastern Europe / East Asia"
            confidence = "Low"
        elif terra_pct > 0.2:
            style = "Terracotta / Ochre"
            region_hint = "Southern Europe / Latin America / North Africa"
            confidence = "Medium"

        # Override with OCR script clues
        if has_cyrillic_ocr:
            region_hint = "Russia / Eastern Europe / Central Asia (Cyrillic script confirmed)"
            confidence = "High"
        elif has_arabic_ocr:
            region_hint = "Middle East / North Africa / South Asia (Arabic script confirmed)"
            confidence = "High"
        elif has_cjk_ocr:
            region_hint = "East Asia — China / Japan / Korea (CJK script confirmed)"
            confidence = "High"

        # Check for specific English regional markers in OCR
        if re.search(r'\bLTD\b|\bPLC\b|\bLIMITED\b', ocr_upper):
            region_hint = (region_hint or "") + " | UK-style company suffix suggests UK/Commonwealth"
        if re.search(r'\bINC\b|\bLLC\b|\bCORP\b', ocr_upper):
            region_hint = (region_hint or "") + " | US-style company suffix suggests USA"
        if re.search(r'\bGMBH\b|\bAG\b|\bOHG\b', ocr_upper):
            region_hint = "Germany / German-speaking country (company suffix found)"
            confidence = "High"
        if re.search(r'\bSARL\b|\bSAS\b|\bSA\b', ocr_upper):
            region_hint = "France / French-speaking country (company suffix found)"
            confidence = "Medium"

        result["style"] = style
        result["region_hint"] = region_hint
        result["confidence"] = confidence
        result["verdict"] = (
            f"🏛️  Architecture: {style} → {region_hint}"
            if style and region_hint else
            (f"🏛️  Region hint from script: {region_hint}" if region_hint else
             "Architecture style indeterminate")
        )
    except Exception as e:
        result["verdict"] = f"Architecture analysis error: {e}"

    return result


# ── Deep OCR Geocoding ────────────────────────────────────────────────────────

def _deep_ocr_geocoding(ocr_text: str, license_plates: list = None) -> dict:
    """
    Advanced geocoding from OCR text + license plate country hints.
    Extracts TLDs, currency symbols, company suffixes, street terms, postcodes.
    """
    result = {
        "country_candidates": [],
        "best_country": None,
        "geocoded_results": [],
        "tld_hints": [],
        "currency_hints": [],
        "verdict": "No advanced geocoding signals found",
    }
    if not ocr_text and not license_plates:
        return result

    text = ocr_text or ""
    text_upper = text.upper()

    # TLD hints
    tld_country_map = {
        ".de": "Germany", ".fr": "France", ".co.uk": "United Kingdom", ".uk": "United Kingdom",
        ".ru": "Russia", ".cn": "China", ".jp": "Japan", ".au": "Australia",
        ".it": "Italy", ".es": "Spain", ".nl": "Netherlands", ".pl": "Poland",
        ".br": "Brazil", ".in": "India", ".ca": "Canada", ".mx": "Mexico",
        ".kr": "South Korea", ".se": "Sweden", ".no": "Norway", ".fi": "Finland",
        ".ch": "Switzerland", ".at": "Austria", ".be": "Belgium", ".pt": "Portugal",
        ".tr": "Turkey", ".sa": "Saudi Arabia", ".ae": "UAE", ".za": "South Africa",
        ".ua": "Ukraine", ".cz": "Czech Republic", ".ro": "Romania", ".hu": "Hungary",
    }
    for tld, country in tld_country_map.items():
        if tld in text.lower():
            result["tld_hints"].append(f"{tld} found → {country}")
            result["country_candidates"].append({"country": country, "source": f"TLD {tld}", "confidence": 0.6})

    # Currency symbols
    currency_map = {
        "£": "United Kingdom", "€": "Eurozone", "¥": "Japan/China",
        "₽": "Russia", "₹": "India", "₩": "South Korea", "฿": "Thailand",
        "₺": "Turkey", "R$": "Brazil", "C$": "Canada", "A$": "Australia",
        "CHF": "Switzerland", "kr": "Scandinavia",
    }
    for symbol, country in currency_map.items():
        if symbol in text:
            result["currency_hints"].append(f"'{symbol}' symbol → {country}")
            result["country_candidates"].append({"country": country, "source": f"Currency {symbol}", "confidence": 0.7})

    # Phone country codes
    phone_matches = re.findall(r'\+(\d{1,3})[\s\-]', text)
    phone_country_map = {
        "1": "USA/Canada", "44": "United Kingdom", "49": "Germany", "33": "France",
        "7": "Russia", "86": "China", "81": "Japan", "91": "India", "61": "Australia",
        "55": "Brazil", "52": "Mexico", "39": "Italy", "34": "Spain", "82": "South Korea",
        "31": "Netherlands", "46": "Sweden", "47": "Norway", "358": "Finland",
        "41": "Switzerland", "43": "Austria", "32": "Belgium", "351": "Portugal",
        "90": "Turkey", "966": "Saudi Arabia", "971": "UAE", "380": "Ukraine",
    }
    for code in phone_matches:
        country = phone_country_map.get(code)
        if country:
            result["country_candidates"].append({"country": country, "source": f"Phone +{code}", "confidence": 0.65})

    # License plate country hints
    if license_plates:
        for plate in license_plates:
            ch = plate.get("country_hint", "")
            if ch and ch != "Unknown":
                result["country_candidates"].append({"country": ch, "source": "License plate", "confidence": 0.5})

    # Postcode geocoding
    postcodes = []
    # UK postcode
    uk_pc = re.findall(r'\b[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}\b', text_upper)
    postcodes.extend([("UK", pc) for pc in uk_pc])
    # US ZIP
    us_zip = re.findall(r'\b\d{5}(?:-\d{4})?\b', text)
    postcodes.extend([("US", z) for z in us_zip])

    geocoded = []
    for origin, pc in postcodes[:3]:
        time.sleep(1)
        geo = _nominatim_geocode(pc)
        if geo:
            geocoded.append({**geo, "query": pc, "origin": origin})
            result["country_candidates"].append({
                "country": origin,
                "source": f"Postcode {pc}",
                "confidence": 0.75,
            })
    result["geocoded_results"] = geocoded

    # Aggregate country votes
    if result["country_candidates"]:
        country_votes = {}
        for c in result["country_candidates"]:
            key = c["country"]
            country_votes[key] = country_votes.get(key, 0) + c["confidence"]
        best = max(country_votes, key=country_votes.get)
        result["best_country"] = best
        result["verdict"] = (
            f"🌍 Best country estimate: {best} "
            f"(from {len(result['country_candidates'])} signal(s))"
        )

    return result


# ── Sun angle analysis v2 (pvlib) ────────────────────────────────────────────

def _sun_angle_analysis_v2(image_path: str, datetime_original: str = None) -> dict:
    """
    pvlib-based solar position matching for latitude estimation.
    More accurate than ephem (±0.01° vs ±0.1°). Falls back to ephem or basic.
    Uses same shadow detection as v1.
    """
    # Shadow detection (shared with v1)
    base = _sun_angle_analysis(image_path, datetime_original)

    if not PVLIB_OK:
        # pvlib not available — return v1 result as-is
        return base

    if base.get("skipped") or base.get("shadow_direction_deg") is None:
        return base

    observed_az = base.get("sun_azimuth_estimate")
    if observed_az is None:
        return base

    if not datetime_original:
        return base

    # Parse datetime string
    try:
        import pandas as pd
        # Try common EXIF formats
        for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = pd.Timestamp(datetime_original.replace(":", "-", 2)
                                  if fmt.startswith("%Y:%m") else datetime_original)
                break
            except Exception:
                try:
                    from datetime import datetime as _dt
                    dt_obj = _dt.strptime(datetime_original, fmt)
                    dt = pd.Timestamp(dt_obj)
                    break
                except Exception:
                    continue
        else:
            return base

        dt_utc = dt.tz_localize("UTC") if dt.tzinfo is None else dt.tz_convert("UTC")

        # Test latitudes -70 to +70 in 5° steps
        lat_candidates_pvlib: list[float] = []
        for lat in range(-70, 71, 5):
            try:
                sp = pvlib.solarposition.get_solarposition(
                    dt_utc, lat, 0.0, method="nrel_numpy"
                )
                pvlib_az = float(sp["azimuth"].iloc[0])
                pvlib_el = float(sp["apparent_elevation"].iloc[0])

                if pvlib_el < 2:  # Sun below horizon at this lat — skip
                    continue

                az_diff = abs(pvlib_az - observed_az)
                if az_diff > 180:
                    az_diff = 360 - az_diff

                if az_diff < 18:  # Within ±18° = plausible match
                    lat_candidates_pvlib.append(float(lat))
            except Exception:
                continue

        if lat_candidates_pvlib:
            base["lat_candidates_pvlib"] = lat_candidates_pvlib
            base["lat_candidates"] = lat_candidates_pvlib  # override v1
            base["confidence"] = "High" if len(lat_candidates_pvlib) <= 4 else "Medium"
            base["method"] = "pvlib"
            # Refined latitude band
            avg_lat = sum(lat_candidates_pvlib) / len(lat_candidates_pvlib)
            if abs(avg_lat) < 23.5:
                base["estimated_latitude_band"] = "Tropical"
            elif abs(avg_lat) < 35:
                base["estimated_latitude_band"] = "Subtropical"
            elif abs(avg_lat) < 55:
                base["estimated_latitude_band"] = "Temperate"
            else:
                base["estimated_latitude_band"] = "Polar"
            base["verdict"] = (
                f"☀️  pvlib: {len(lat_candidates_pvlib)} candidate latitude(s) "
                f"[{min(lat_candidates_pvlib)}°–{max(lat_candidates_pvlib)}°] "
                f"— {base['estimated_latitude_band']}"
            )
    except Exception:
        pass  # pvlib calc failed; return v1 result

    return base


# ── Overpass API: POI from GPS ────────────────────────────────────────────────

def _overpass_poi_query(lat: float, lon: float, radius: int = 300) -> dict:
    """
    Query OpenStreetMap Overpass API for POIs near GPS coordinates.
    Gives street-level location: street names, amenities, postcodes, city.
    No API key. Rate limit: ~1 req/s on public API.
    """
    result = {
        "street_names":  [],
        "named_places":  [],
        "city":          None,
        "postcode":      None,
        "country":       None,
        "neighbourhood": None,
        "osm_url":       f"https://www.openstreetmap.org/#map=17/{lat:.5f}/{lon:.5f}",
        "verdict":       None,
        "error":         None,
    }

    if not OVERPY_OK:
        # Fallback: Nominatim reverse geocode
        try:
            headers = {"User-Agent": "ImageTrace-OSINT/2.0"}
            resp = requests.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "json"},
                headers=headers,
                timeout=10,
            )
            data = resp.json()
            addr = data.get("address", {})
            result["city"]        = addr.get("city") or addr.get("town") or addr.get("village")
            result["postcode"]    = addr.get("postcode")
            result["country"]     = addr.get("country")
            result["neighbourhood"] = addr.get("suburb") or addr.get("neighbourhood")
            result["street_names"]  = [addr.get("road")] if addr.get("road") else []
            result["verdict"] = (
                f"📍 {data.get('display_name', 'Location resolved via Nominatim')}"
            )
        except Exception as e:
            result["error"] = f"Nominatim fallback failed: {e}"
        return result

    try:
        api = _overpy.API()
        query = f"""
[out:json][timeout:25];
(
  node(around:{radius},{lat},{lon});
  way(around:{radius},{lat},{lon});
);
out tags;
"""
        response = api.query(query)

        street_set:  set[str] = set()
        place_set:   set[str] = set()
        city:        str | None = None
        postcode:    str | None = None
        country:     str | None = None
        neighbourhood: str | None = None

        def _process_tags(tags: dict) -> None:
            nonlocal city, postcode, country, neighbourhood
            name = tags.get("name") or tags.get("ref")
            if name:
                hw = tags.get("highway")
                if hw and hw not in ("traffic_signals", "crossing", "turning_circle"):
                    street_set.add(name)
                elif not hw:
                    place_set.add(name)
            if tags.get("addr:city"):
                city = tags["addr:city"]
            if tags.get("addr:postcode"):
                postcode = tags["addr:postcode"]
            if tags.get("addr:country"):
                country = tags["addr:country"]
            if tags.get("addr:suburb") or tags.get("addr:neighbourhood"):
                neighbourhood = tags.get("addr:suburb") or tags.get("addr:neighbourhood")

        for node in response.nodes:
            _process_tags(node.tags)
        for way in response.ways:
            _process_tags(way.tags)

        result["street_names"]    = sorted(street_set)[:10]
        result["named_places"]    = sorted(place_set)[:15]
        result["city"]            = city
        result["postcode"]        = postcode
        result["country"]         = country
        result["neighbourhood"]   = neighbourhood

        # Build verdict
        desc_parts = list(filter(None, [
            neighbourhood, city, postcode, country,
        ]))
        n_features = len(street_set) + len(place_set)
        result["verdict"] = (
            f"📍 {', '.join(desc_parts) if desc_parts else 'Location found'} "
            f"({n_features} OSM feature(s) within {radius}m)"
        )

    except Exception as e:
        result["error"] = str(e)[:80]
        # Try Nominatim fallback
        try:
            headers = {"User-Agent": "ImageTrace-OSINT/2.0"}
            resp = requests.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "json"},
                headers=headers, timeout=10,
            )
            data = resp.json()
            addr = data.get("address", {})
            result["city"]     = addr.get("city") or addr.get("town") or addr.get("village")
            result["postcode"] = addr.get("postcode")
            result["country"]  = addr.get("country")
            result["verdict"]  = f"📍 {data.get('display_name', '')}"
        except Exception:
            pass

    return result


# ── Open-Meteo: historical weather corroboration ──────────────────────────────

def _weather_historical(lat: float, lon: float, date_str: str) -> dict:
    """
    Open-Meteo historical weather API (free, no API key required).
    Cross-reference weather conditions with what's visible in the image.
    Only runs if GPS + date are both available.
    """
    result = {
        "date":                 date_str,
        "max_temp_c":           None,
        "precipitation_mm":     None,
        "snowfall_cm":          None,
        "max_wind_kph":         None,
        "weather_summary":      None,
        "image_corroboration":  [],
        "skipped":              None,
        "error":                None,
    }

    if not date_str:
        result["skipped"] = "No date available"
        return result

    # Parse date — need YYYY-MM-DD
    try:
        from datetime import datetime
        for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt_obj = datetime.strptime(
                    date_str[:19].replace(":", "-", 2) if fmt.startswith("%Y:") else date_str[:19],
                    fmt
                )
                date_only = dt_obj.strftime("%Y-%m-%d")
                break
            except ValueError:
                continue
        else:
            result["skipped"] = "Could not parse date"
            return result
    except Exception:
        result["skipped"] = "Date parse error"
        return result

    try:
        resp = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude":   lat,
                "longitude":  lon,
                "start_date": date_only,
                "end_date":   date_only,
                "daily": ",".join([
                    "temperature_2m_max", "precipitation_sum",
                    "snowfall_sum", "windspeed_10m_max",
                ]),
                "timezone": "auto",
            },
            timeout=12,
        )
        data = resp.json()
        daily = data.get("daily", {})

        def _first(key: str):
            vals = daily.get(key, [])
            return vals[0] if vals else None

        result["max_temp_c"]       = _first("temperature_2m_max")
        result["precipitation_mm"] = _first("precipitation_sum")
        result["snowfall_cm"]      = _first("snowfall_sum")
        result["max_wind_kph"]     = _first("windspeed_10m_max")

        t   = result["max_temp_c"]
        pr  = result["precipitation_mm"]
        sn  = result["snowfall_cm"]
        wnd = result["max_wind_kph"]

        # Weather summary
        parts: list[str] = []
        if t is not None:
            parts.append(f"{t:.0f}°C")
        if pr is not None:
            parts.append(f"{pr:.1f}mm rain")
        if sn and sn > 0:
            parts.append(f"{sn:.1f}cm snow")
        if wnd is not None and wnd > 30:
            parts.append(f"winds {wnd:.0f}km/h")
        result["weather_summary"] = ", ".join(parts) if parts else "No data"

        # Corroboration hints
        if sn and sn > 0.5:
            result["image_corroboration"].append(
                f"❄️  Snowfall ({sn:.1f}cm) — expect white ground/trees in image"
            )
        if t is not None and t < 0:
            result["image_corroboration"].append(
                f"🥶 Sub-zero temperature ({t:.0f}°C) — expect winter clothing"
            )
        if t is not None and t > 35:
            result["image_corroboration"].append(
                f"🔥 Very hot ({t:.0f}°C) — expect summer/arid conditions"
            )
        if pr and pr > 10:
            result["image_corroboration"].append(
                f"🌧️  Heavy rain ({pr:.1f}mm) — expect wet surfaces/umbrellas"
            )
        if wnd and wnd > 50:
            result["image_corroboration"].append(
                f"💨 Strong winds ({wnd:.0f}km/h) — expect motion blur on foliage"
            )

    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── Mapillary: nearby street-level photos ─────────────────────────────────────

def _mapillary_nearby(lat: float, lon: float,
                      api_key: str = "", radius: int = 100) -> dict:
    """
    Mapillary v4 API: find street-level photos within radius meters of GPS coords.
    Free API key at mapillary.com/developer (250,000 req/month).
    Useful for visually confirming GPS location.
    """
    result = {
        "nearby_photos":    [],
        "street_view_count": 0,
        "coverage_verdict":  None,
        "skipped":           None,
        "error":             None,
    }

    api_key = api_key or os.environ.get("MAPILLARY_TOKEN", "")
    if not api_key:
        result["skipped"] = "No Mapillary API key (set MAPILLARY_TOKEN)"
        return result

    # Compute bounding box
    d = radius / 111320  # degrees
    bbox = f"{lon-d},{lat-d},{lon+d},{lat+d}"

    try:
        resp = requests.get(
            "https://graph.mapillary.com/images",
            params={
                "fields":       "id,thumb_256_url,compass_angle,captured_at,geometry",
                "bbox":         bbox,
                "limit":        5,
                "access_token": api_key,
            },
            timeout=10,
        )
        data = resp.json()

        photos = []
        for img in data.get("data", []):
            geom = img.get("geometry", {})
            img_lon, img_lat = geom.get("coordinates", [None, None])

            dist_m = None
            if img_lat and img_lon:
                from math import radians, cos, sin, sqrt, atan2
                R = 6_371_000
                phi1, phi2 = radians(lat), radians(float(img_lat))
                dphi = radians(float(img_lat) - lat)
                dlam = radians(float(img_lon) - lon)
                a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlam/2)**2
                dist_m = round(R * 2 * atan2(sqrt(a), sqrt(1-a)), 1)

            photos.append({
                "id":         img.get("id"),
                "thumb_url":  img.get("thumb_256_url"),
                "angle":      img.get("compass_angle"),
                "date":       img.get("captured_at"),
                "distance_m": dist_m,
            })

        result["nearby_photos"]     = photos
        result["street_view_count"] = len(photos)
        if photos:
            result["coverage_verdict"] = (
                f"✅ {len(photos)} Mapillary street-level photo(s) within {radius}m — "
                f"visual confirmation available"
            )
        else:
            result["coverage_verdict"] = (
                f"⚠️  No Mapillary street-level coverage within {radius}m"
            )

    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── Timezone from coordinates ─────────────────────────────────────────────────

def _timezone_from_coords(lat: float, lon: float) -> dict:
    """
    Offline timezone lookup from GPS (timezonefinder — 2MB data, no API).
    Corroborates region identified by other signals.
    """
    result = {
        "timezone":           None,
        "utc_offset":         None,
        "hemisphere":         "Northern" if lat >= 0 else "Southern",
        "approximate_region": None,
        "corroborates":       [],
        "error":              None,
    }

    if not TZF_OK:
        result["error"] = "timezonefinder not installed (pip install timezonefinder)"
        return result

    try:
        tz_str = _TF.timezone_at(lat=lat, lng=lon)
        if not tz_str:
            result["error"] = "No timezone found at these coordinates"
            return result

        result["timezone"] = tz_str

        # UTC offset
        try:
            import pytz
            from datetime import datetime
            tz = pytz.timezone(tz_str)
            offset = tz.utcoffset(datetime.utcnow())
            hours = offset.total_seconds() / 3600
            sign = "+" if hours >= 0 else ""
            result["utc_offset"] = f"UTC{sign}{hours:.1f}".replace(".0", "")
        except ImportError:
            pass
        except Exception:
            pass

        # Approximate region from timezone name
        tz_lower = tz_str.lower()
        region_map = {
            "america/new_york":    "Eastern United States",
            "america/chicago":     "Central United States",
            "america/denver":      "Mountain United States",
            "america/los_angeles": "Pacific United States",
            "america/toronto":     "Eastern Canada",
            "america/vancouver":   "Western Canada",
            "america/sao_paulo":   "Brazil",
            "america/mexico_city": "Mexico",
            "europe/london":       "United Kingdom / Ireland",
            "europe/paris":        "France / Central Europe",
            "europe/berlin":       "Germany / Central Europe",
            "europe/moscow":       "Russia (Moscow region)",
            "europe/madrid":       "Spain",
            "europe/rome":         "Italy",
            "asia/tokyo":          "Japan",
            "asia/shanghai":       "China",
            "asia/kolkata":        "India",
            "asia/dubai":          "UAE / Gulf region",
            "asia/singapore":      "Singapore / SE Asia",
            "asia/seoul":          "South Korea",
            "australia/sydney":    "Eastern Australia",
            "pacific/auckland":    "New Zealand",
        }
        for key, region in region_map.items():
            if key in tz_lower:
                result["approximate_region"] = region
                break
        if not result["approximate_region"]:
            # Derive from continent prefix
            continent = tz_str.split("/")[0]
            continent_map = {
                "America": "Americas",
                "Europe": "Europe",
                "Asia": "Asia",
                "Africa": "Africa",
                "Australia": "Australia/Oceania",
                "Pacific": "Pacific",
                "Atlantic": "Atlantic region",
                "Indian": "Indian Ocean region",
                "Arctic": "Arctic",
                "Antarctica": "Antarctica",
            }
            result["approximate_region"] = continent_map.get(continent, continent)

        # Corroboration hints
        result["corroborates"].append(
            f"Timezone {tz_str} → {result['approximate_region']} "
            f"({result['hemisphere']} hemisphere)"
        )

    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def geolocate(image_path: str, ocr_text: str = "", api_key: str = "",
              content_results: dict = None,
              gps_lat: float = None, gps_lon: float = None,
              mapillary_key: str = "",
              run_open_meteo: bool = True) -> dict:
    """
    Attempt to geolocate image using all available methods.

    Parameters
    ----------
    image_path      : path to image file
    ocr_text        : text extracted by Stage 4
    api_key         : GeoSpy API key (or GEOSPY_API_KEY env var)
    content_results : Stage 4 output dict (for license plates, YOLO objects)
    gps_lat/gps_lon : GPS from EXIF (pass from Stage 1 to avoid re-parsing)
    mapillary_key   : Mapillary API token (or MAPILLARY_TOKEN env var)
    run_open_meteo  : query Open-Meteo weather API when GPS+date available
    """
    api_key      = api_key      or os.environ.get("GEOSPY_API_KEY",    "")
    mapillary_key = mapillary_key or os.environ.get("MAPILLARY_TOKEN", "")

    # Extract helpers from content_results
    license_plates = []
    yolo_objects   = []
    dt_original    = None
    if content_results:
        plates_data = content_results.get("license_plates", {})
        if plates_data.get("plates"):
            license_plates = plates_data["plates"]
        objs = content_results.get("objects", {})
        if objs.get("objects"):
            yolo_objects = objs["objects"]
        # EXIF date may have been forwarded via content_results
        dt_original = content_results.get("datetime_original")

    # Try to pull date from EXIF directly if not provided
    if not dt_original:
        try:
            import piexif
            exif = piexif.load(image_path)
            raw = exif.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal, b"")
            if raw:
                dt_original = raw.decode("utf-8", errors="ignore")
        except Exception:
            pass

    # ── Core geolocation methods ──────────────────────────────────────────────
    geospy   = _geospy(image_path, api_key)
    ocr_geo  = _ocr_geolocation(ocr_text)
    landmark = _landmark_detection(ocr_text)

    # ── Enhanced visual analysis ──────────────────────────────────────────────
    sun_angle    = _sun_angle_analysis_v2(image_path, dt_original)
    vegetation   = _vegetation_climate_zone(image_path, yolo_objects)
    architecture = _architecture_style_hint(image_path, ocr_text)
    deep_ocr     = _deep_ocr_geocoding(ocr_text, license_plates)

    # ── GPS-powered precision (only if GPS available) ─────────────────────────
    overpass_poi  = {}
    weather       = {}
    mapillary     = {}
    timezone_info = {}

    best_lat = gps_lat or (geospy.get("lat") if geospy.get("lat") else None)
    best_lon = gps_lon or (geospy.get("lon") if geospy.get("lon") else None)

    if best_lat and best_lon:
        print(f"[Stage 5] Querying Overpass POI at ({best_lat:.4f}, {best_lon:.4f})...")
        overpass_poi = _overpass_poi_query(best_lat, best_lon, radius=300)
        time.sleep(1.1)  # Overpass rate limit

        if run_open_meteo and dt_original:
            print(f"[Stage 5] Fetching Open-Meteo historical weather...")
            weather = _weather_historical(best_lat, best_lon, dt_original)

        if mapillary_key:
            print(f"[Stage 5] Querying Mapillary nearby photos...")
            mapillary = _mapillary_nearby(best_lat, best_lon, mapillary_key)

        print(f"[Stage 5] Timezone lookup...")
        timezone_info = _timezone_from_coords(best_lat, best_lon)

    # ── Build signal list ─────────────────────────────────────────────────────
    best   = None
    source = None
    signals: list[str] = []

    # Priority: EXIF GPS (1.0) > GeoSpy (0.85) > Overpass (0.9 if GPS) > OCR (0.6)
    if gps_lat and gps_lon:
        best   = {"lat": gps_lat, "lon": gps_lon}
        source = "EXIF GPS"
        loc_str = f"{gps_lat:.4f}°, {gps_lon:.4f}°"
        if overpass_poi.get("city"):
            city_str = ", ".join(filter(None, [
                overpass_poi.get("neighbourhood"),
                overpass_poi.get("city"),
                overpass_poi.get("country"),
            ]))
            loc_str = city_str
        signals.append(f"GPS: {loc_str}")

    if geospy.get("lat"):
        if not best:
            best   = geospy
            source = "GeoSpy AI"
        signals.append(f"GeoSpy AI: {geospy.get('city','?')}")

    if landmark.get("best_match"):
        m = landmark["best_match"]
        if not best:
            best   = {"lat": m["lat"], "lon": m["lon"],
                      "city": m["location"], "maps_link": m["maps_link"]}
            source = f"Landmark: {m['keyword']}"
        signals.append(f"Landmark match: {m['keyword']}")

    if ocr_geo.get("geocoded"):
        g = ocr_geo["geocoded"]
        if not best:
            best   = {"lat": g["lat"], "lon": g["lon"],
                      "city": g["display_name"], "maps_link": g["maps_link"]}
            source = "OCR + Nominatim"
        signals.append(f"OCR geocoded: {g['display_name'][:40]}")

    if deep_ocr.get("best_country"):
        signals.append(f"OCR deep: {deep_ocr['best_country']}")
    if sun_angle.get("estimated_latitude_band") and not sun_angle.get("skipped"):
        signals.append(f"Sun angle: {sun_angle['estimated_latitude_band']}")
    if vegetation.get("climate_zone"):
        signals.append(f"Vegetation: {vegetation['climate_zone']}")
    if architecture.get("region_hint"):
        signals.append(f"Architecture: {architecture['region_hint'][:35]}")
    if overpass_poi.get("city"):
        signals.append(f"OSM: {overpass_poi['city']}")
    if timezone_info.get("approximate_region"):
        signals.append(f"Timezone: {timezone_info['approximate_region']}")

    # ── Overall verdict ───────────────────────────────────────────────────────
    overall_verdict = "❓ Could not determine location"
    if overpass_poi.get("verdict"):
        overall_verdict = overpass_poi["verdict"]
        if overpass_poi.get("street_names"):
            overall_verdict += f" | Streets: {', '.join(overpass_poi['street_names'][:3])}"
    elif best:
        loc = (best.get("city") or
               f"{best.get('lat','?'):.4f}°, {best.get('lon','?'):.4f}°"
               if isinstance(best.get("lat"), float) else "?")
        overall_verdict = f"📍 Location: {loc} (via {source})"
        if weather.get("weather_summary"):
            overall_verdict += f" | Weather: {weather['weather_summary']}"
    elif signals:
        overall_verdict = f"🔍 Location signals: {' | '.join(signals[:3])}"

    return {
        "stage":              "geolocation",
        "overall_verdict":    overall_verdict,
        "best_result":        best,
        "source":             source,
        "location_signals":   signals,
        # Core methods
        "geospy":             geospy,
        "ocr_geolocation":    ocr_geo,
        "landmark_detection": landmark,
        # v1 visual analysis
        "sun_angle":          sun_angle,
        "vegetation_zone":    vegetation,
        "architecture_hint":  architecture,
        "deep_ocr_geocoding": deep_ocr,
        # v2 precision methods
        "overpass_poi":       overpass_poi,
        "weather_corroboration": weather,
        "mapillary":          mapillary,
        "timezone":           timezone_info,
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python stage5_geolocation.py <image> [ocr_text]")
        sys.exit(1)
    ocr = sys.argv[2] if len(sys.argv) > 2 else ""
    print(json.dumps(geolocate(sys.argv[1], ocr_text=ocr), indent=2, default=str))
