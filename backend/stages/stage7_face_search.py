"""
Stage 7 — Facial Recognition Search
If faces were detected in Stage 4, submits cropped face images to:
  1. PimEyes    — 3.5B image index (Selenium)
  2. FaceCheck.ID — 763M images incl. mugshots/criminal DBs (Selenium)
  3. Yandex Images — face-optimized reverse search (Selenium)

OPSEC WARNING: This stage sends biometric face data to external services.
The tool always warns the user before submitting and requires --confirm-face-search.
"""

import os
import io
import base64
import time
import tempfile
from pathlib import Path
from urllib.parse import urlparse

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_OK = True
except ImportError:
    SELENIUM_OK = False


# ── Driver ────────────────────────────────────────────────────────────────────

def _make_driver(headless: bool = True) -> "webdriver.Chrome":
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


# ── Face crop helper ──────────────────────────────────────────────────────────

def _save_face_crop(crop_b64: str, index: int) -> str | None:
    """Save a base64 face crop to a temp file. Returns path."""
    if not crop_b64:
        return None
    try:
        data = base64.b64decode(crop_b64)
        tmp = tempfile.NamedTemporaryFile(
            suffix=f"_face{index}.png", delete=False
        )
        tmp.write(data)
        tmp.close()
        return tmp.name
    except Exception:
        return None


# ── PimEyes ───────────────────────────────────────────────────────────────────

def _pimeyes(driver: "webdriver.Chrome", face_path: str) -> dict:
    """
    Upload face crop to PimEyes and collect result thumbnails + source URLs.
    Free tier returns thumbnails but blurs URLs — we collect what we can.
    """
    result = {"engine": "PimEyes", "matches": [], "total": 0, "note": ""}
    try:
        driver.get("https://pimeyes.com/en")
        time.sleep(2)

        # Handle cookie banner if present
        try:
            accept = driver.find_element(By.XPATH, "//*[contains(text(),'Accept')]")
            accept.click()
            time.sleep(0.5)
        except Exception:
            pass

        # Upload button
        upload_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "label[for='file'], input[type='file'], .upload-button"))
        )
        file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
        file_input.send_keys(str(Path(face_path).resolve()))
        time.sleep(6)

        # Search button
        try:
            search_btn = driver.find_element(By.CSS_SELECTOR, ".search-button, button[type='submit']")
            search_btn.click()
            time.sleep(6)
        except Exception:
            pass

        # Collect result items
        items = driver.find_elements(By.CSS_SELECTOR, ".result-item, .face-result, article")
        for item in items[:15]:
            try:
                link_el = item.find_element(By.TAG_NAME, "a")
                href = link_el.get_attribute("href") or ""
                img_el = item.find_element(By.TAG_NAME, "img")
                src = img_el.get_attribute("src") or ""
                if href or src:
                    result["matches"].append({
                        "url": href or "blurred (free tier)",
                        "thumbnail": src,
                        "domain": urlparse(href).netloc if href else "hidden",
                    })
            except Exception:
                pass

        result["total"] = len(result["matches"])
        result["note"] = "Free tier: URLs may be blurred. Upgrade at pimeyes.com for full results."

    except Exception as e:
        result["error"] = str(e)
    return result


# ── FaceCheck.ID ──────────────────────────────────────────────────────────────

def _facecheck(driver: "webdriver.Chrome", face_path: str) -> dict:
    """
    Upload to FaceCheck.ID which indexes 763M+ images including mugshot/criminal DBs.
    """
    result = {"engine": "FaceCheck.ID", "matches": [], "total": 0}
    try:
        driver.get("https://facecheck.id")
        time.sleep(2)

        # Accept cookies
        try:
            accept = driver.find_element(By.XPATH, "//*[contains(text(),'Accept')]")
            accept.click()
            time.sleep(0.5)
        except Exception:
            pass

        # Upload
        file_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        )
        file_input.send_keys(str(Path(face_path).resolve()))
        time.sleep(3)

        # Search
        try:
            search_btn = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'], .search-btn"))
            )
            search_btn.click()
            time.sleep(8)
        except Exception:
            pass

        # Scrape results
        items = driver.find_elements(By.CSS_SELECTOR, ".result, .match, article, .card")
        for item in items[:15]:
            try:
                links = item.find_elements(By.TAG_NAME, "a")
                imgs  = item.find_elements(By.TAG_NAME, "img")
                href = links[0].get_attribute("href") if links else ""
                src  = imgs[0].get_attribute("src") if imgs else ""
                score_el = item.find_elements(By.CSS_SELECTOR, ".score, .confidence, .similarity")
                score = score_el[0].text if score_el else ""
                result["matches"].append({
                    "url": href or "requires account",
                    "thumbnail": src,
                    "similarity": score,
                    "domain": urlparse(href).netloc if href else "unknown",
                })
            except Exception:
                pass

        result["total"] = len(result["matches"])

    except Exception as e:
        result["error"] = str(e)
    return result


# ── Yandex Face Search ────────────────────────────────────────────────────────

def _yandex_face(driver: "webdriver.Chrome", face_path: str) -> dict:
    """Yandex Images has the strongest free face recognition of any search engine."""
    result = {"engine": "Yandex (Face)", "matches": [], "total": 0}
    try:
        driver.get("https://yandex.com/images/")
        time.sleep(1)

        # Camera button
        camera = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".input__cbir-button, [data-type='cbir-button']"))
        )
        camera.click()
        time.sleep(0.5)

        # Upload
        file_input = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        )
        file_input.send_keys(str(Path(face_path).resolve()))
        time.sleep(6)

        # People found section
        try:
            people_section = driver.find_elements(By.CSS_SELECTOR, ".cbir-section__title")
            for section in people_section:
                if "people" in section.text.lower() or "similar" in section.text.lower():
                    parent = section.find_element(By.XPATH, "./..")
                    links = parent.find_elements(By.TAG_NAME, "a")
                    for link in links[:10]:
                        href = link.get_attribute("href") or ""
                        if href.startswith("http") and "yandex" not in href:
                            result["matches"].append({
                                "url": href,
                                "domain": urlparse(href).netloc,
                                "title": link.text.strip()[:80] or href,
                            })
        except Exception:
            pass

        # Fallback: any result links
        if not result["matches"]:
            items = driver.find_elements(By.CSS_SELECTOR, ".serp-item__title a, .MMOrganicSnippet a")
            for item in items[:15]:
                href = item.get_attribute("href") or ""
                if href.startswith("http") and "yandex" not in href:
                    result["matches"].append({
                        "url": href,
                        "domain": urlparse(href).netloc,
                        "title": item.text.strip()[:80],
                    })

        result["total"] = len(result["matches"])

    except Exception as e:
        result["error"] = str(e)
    return result


# ── Local FaceDB search ───────────────────────────────────────────────────────

def _search_local_db(image_path: str, face_crops_b64: list[str]) -> dict:
    """Search the local face database. Runs offline, no external requests."""
    result = {"matches": [], "db_stats": {}, "backend": None}
    try:
        from facedb import FaceDB, BACKEND, extract_embeddings
        result["backend"] = BACKEND
        if BACKEND is None:
            result["skipped"] = "No face recognition backend installed (install insightface, deepface, or face_recognition)"
            return result

        db = FaceDB()
        stats = db.stats()
        result["db_stats"] = {
            "total_faces": stats.get("total_faces", 0),
            "known_people": len(stats.get("known_people", [])),
        }

        if stats.get("total_faces", 0) == 0:
            result["skipped"] = "Local face database is empty"
            db.close()
            return result

        # Try searching by the full image first
        matches = db.search(image_path, top_k=10, min_similarity=0.40)

        # If no matches from image, try face crops
        if not matches and face_crops_b64:
            for crop_b64 in face_crops_b64[:2]:
                try:
                    crop_data = base64.b64decode(crop_b64)
                    tmp = tempfile.NamedTemporaryFile(suffix="_crop.jpg", delete=False)
                    tmp.write(crop_data); tmp.close()
                    embeddings = extract_embeddings(tmp.name)
                    for emb_data in embeddings:
                        crop_matches = db.search_embedding(emb_data["embedding"], top_k=5)
                        matches.extend(crop_matches)
                    try:
                        os.unlink(tmp.name)
                    except Exception:
                        pass
                except Exception:
                    pass

        result["matches"] = [
            {
                "label": m.get("label") or "Unknown",
                "similarity_pct": m.get("similarity_pct", 0),
                "confidence_label": m.get("confidence_label", ""),
                "image": Path(m.get("image_path", "")).name,
            }
            for m in matches[:10]
        ]
        db.close()
    except Exception as e:
        result["error"] = str(e)
    return result


# ── face_recognition local comparison ────────────────────────────────────────

def _local_face_encoding(image_path: str) -> dict:
    """
    Extract face encoding using face_recognition library.
    This encoding can be used to compare against a local database.
    """
    result = {"encoding": None, "face_count": 0}
    try:
        import face_recognition
        import numpy as np
        img = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(img)
        result["face_count"] = len(encodings)
        if encodings:
            # Store as list for JSON serialization
            result["encoding"] = encodings[0].tolist()
    except ImportError:
        result["skipped"] = "face_recognition not installed"
    except Exception as e:
        result["error"] = str(e)
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def search(
    image_path: str,
    face_crops_b64: list[str],
    confirmed: bool = False,
    headless: bool = True,
) -> dict:
    """
    Run face recognition search across PimEyes, FaceCheck.ID, and Yandex.

    Parameters
    ----------
    image_path    : original image (for Yandex fallback)
    face_crops_b64: list of base64 face crop strings from Stage 4
    confirmed     : must be True to actually submit to external face DBs
    headless      : run browser in headless mode
    """
    result = {
        "stage": "face_search",
        "face_count": len(face_crops_b64),
        "opsec_warning": (
            "This stage submits biometric face data to third-party services. "
            "Pass confirmed=True to proceed."
        ),
        "confirmed": confirmed,
        "per_face": [],
        "local_encoding": {},
        "local_db_results": {},
    }

    # Always do local encoding (no internet)
    result["local_encoding"] = _local_face_encoding(image_path)

    # Always check local FaceDB (no internet required)
    result["local_db_results"] = _search_local_db(image_path, face_crops_b64)

    if not confirmed:
        result["skipped"] = "Face search skipped — use --confirm-face-search to enable"
        return result

    if not SELENIUM_OK:
        result["error"] = "selenium not installed — run: pip install selenium webdriver-manager"
        return result

    if not face_crops_b64:
        result["skipped"] = "No faces detected in Stage 4"
        return result

    # Use first face crop (most prominent face)
    face_path = _save_face_crop(face_crops_b64[0], 0)
    if not face_path:
        result["error"] = "Failed to save face crop to temp file"
        return result

    driver = None
    face_results = {}
    try:
        driver = _make_driver(headless=headless)

        pimeyes = _pimeyes(driver, face_path)
        face_results["pimeyes"] = pimeyes
        time.sleep(2)

        facecheck = _facecheck(driver, face_path)
        face_results["facecheck"] = facecheck
        time.sleep(2)

        yandex = _yandex_face(driver, face_path)
        face_results["yandex"] = yandex

    except Exception as e:
        face_results["driver_error"] = str(e)
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        # Clean up temp file
        try:
            os.unlink(face_path)
        except Exception:
            pass

    # Aggregate all matches
    all_matches = []
    for engine_name, er in face_results.items():
        if isinstance(er, dict):
            for m in er.get("matches", []):
                all_matches.append({**m, "engine": engine_name})

    total = len(all_matches)
    verdict = "❌ No face matches found across databases"
    if total >= 5:
        verdict = f"🔴 HIGH — {total} potential face match(es) found"
    elif total > 0:
        verdict = f"🟡 {total} potential face match(es) found — review manually"

    result["per_face"] = [{
        "face_index": 0,
        "results": face_results,
        "aggregated_matches": all_matches,
        "verdict": verdict,
    }]

    return result


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python stage7_face_search.py <image>")
        print("  Note: requires --confirm-face-search to submit to external databases")
        sys.exit(1)
    r = search(sys.argv[1], face_crops_b64=[], confirmed=False)
    print(json.dumps(r, indent=2, default=str))
