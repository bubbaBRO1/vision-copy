"""
Stage 6 — Multi-Engine Reverse Image Search
Simultaneously queries 5 reverse image search engines and aggregates results.

Engines:
  1. TinEye       — official API (150 free searches/month)
  2. Google Images — Selenium automation
  3. Yandex Images — Selenium automation (best for faces)
  4. Bing Visual Search — Selenium automation
  5. ImgOps       — aggregator page (Selenium, quick multi-engine check)

Results are deduplicated and ranked by domain uniqueness.
"""

import os
import time
import base64
import hashlib
import tempfile
import requests
from pathlib import Path
from urllib.parse import quote_plus, urlparse

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


# ── Browser setup ─────────────────────────────────────────────────────────────

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


# ── TinEye (Official API) ─────────────────────────────────────────────────────

def _tineye(image_path: str, api_key: str) -> dict:
    result = {"engine": "TinEye", "matches": [], "total": 0, "error": None}
    if not api_key:
        result["skipped"] = "No TinEye API key (set TINEYE_API_KEY)"
        return result
    try:
        with open(image_path, "rb") as f:
            files = {"image": (Path(image_path).name, f, "image/jpeg")}
            resp = requests.post(
                "https://api.tineye.com/rest/search/",
                files=files,
                params={"api_key": api_key},
                timeout=30,
            )
        data = resp.json()
        if data.get("code") == 200:
            result["total"] = data.get("results", {}).get("total_results", 0)
            for match in data.get("results", {}).get("matches", [])[:10]:
                result["matches"].append({
                    "url": match.get("image_url"),
                    "domain": match.get("domain"),
                    "title": match.get("title"),
                    "score": match.get("score"),
                    "width": match.get("width"),
                    "height": match.get("height"),
                })
        else:
            result["error"] = str(data)
    except Exception as e:
        result["error"] = str(e)
    return result


# ── Google Reverse Image Search (Selenium) ─────────────────────────────────────

def _google(driver: "webdriver.Chrome", image_path: str) -> dict:
    result = {"engine": "Google", "matches": [], "total": 0}
    try:
        # Navigate to Google Images upload
        driver.get("https://images.google.com")
        time.sleep(1)

        # Click camera icon
        try:
            camera_btn = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[aria-label='Search by image']"))
            )
            camera_btn.click()
        except Exception:
            # Try alternate selector
            driver.get("https://images.google.com/?hl=en")
            time.sleep(1)
            btns = driver.find_elements(By.CSS_SELECTOR, "div[jsname='R5mgy']")
            if btns:
                btns[0].click()

        time.sleep(1)

        # Upload image
        try:
            upload_tab = driver.find_element(By.XPATH, "//*[contains(text(),'upload')]")
            upload_tab.click()
            time.sleep(0.5)
        except Exception:
            pass

        file_input = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        )
        file_input.send_keys(str(Path(image_path).resolve()))
        time.sleep(4)

        # Scrape result links
        links = driver.find_elements(By.CSS_SELECTOR, "a[href*='http']")
        seen = set()
        for link in links[:30]:
            href = link.get_attribute("href") or ""
            if "google" in href or not href.startswith("http"):
                continue
            domain = urlparse(href).netloc
            if domain not in seen:
                seen.add(domain)
                title = link.text.strip() or domain
                result["matches"].append({"url": href, "domain": domain, "title": title[:80]})

        result["total"] = len(result["matches"])
    except Exception as e:
        result["error"] = str(e)
    return result


# ── Yandex Reverse Image Search (Selenium) ────────────────────────────────────

def _yandex(driver: "webdriver.Chrome", image_path: str) -> dict:
    result = {"engine": "Yandex", "matches": [], "total": 0}
    try:
        driver.get("https://yandex.com/images/")
        time.sleep(1)

        # Click camera icon
        camera = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".input__cbir-button, [aria-label='Search by image']"))
        )
        camera.click()
        time.sleep(0.5)

        # Upload file
        file_input = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        )
        file_input.send_keys(str(Path(image_path).resolve()))
        time.sleep(5)

        # Collect results
        items = driver.find_elements(By.CSS_SELECTOR, ".serp-item__title a, .MMOrganicSnippet a")
        seen = set()
        for item in items[:20]:
            href = item.get_attribute("href") or ""
            if not href.startswith("http"):
                continue
            domain = urlparse(href).netloc
            if "yandex" in domain:
                continue
            if domain not in seen:
                seen.add(domain)
                result["matches"].append({
                    "url": href,
                    "domain": domain,
                    "title": item.text.strip()[:80] or domain,
                })

        result["total"] = len(result["matches"])
    except Exception as e:
        result["error"] = str(e)
    return result


# ── Bing Visual Search (Selenium) ─────────────────────────────────────────────

def _bing(driver: "webdriver.Chrome", image_path: str) -> dict:
    result = {"engine": "Bing", "matches": [], "total": 0}
    try:
        driver.get("https://www.bing.com/visualsearch")
        time.sleep(1)

        file_input = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        )
        file_input.send_keys(str(Path(image_path).resolve()))
        time.sleep(5)

        items = driver.find_elements(By.CSS_SELECTOR, "a.richcard_a, a[href*='http']")
        seen = set()
        for item in items[:20]:
            href = item.get_attribute("href") or ""
            if not href.startswith("http") or "bing" in href or "microsoft" in href:
                continue
            domain = urlparse(href).netloc
            if domain not in seen:
                seen.add(domain)
                result["matches"].append({
                    "url": href,
                    "domain": domain,
                    "title": item.text.strip()[:80] or domain,
                })
        result["total"] = len(result["matches"])
    except Exception as e:
        result["error"] = str(e)
    return result


# ── ImgOps Quick Check (no Selenium needed for basic check) ──────────────────

def _imgops(image_path: str) -> dict:
    """
    ImgOps generates a URL that opens multi-engine search on click.
    We generate the direct search links for each engine.
    """
    result = {"engine": "ImgOps", "search_links": [], "note": "Manual visit links"}
    try:
        with open(image_path, "rb") as f:
            img_hash = hashlib.md5(f.read()).hexdigest()

        fname = Path(image_path).name
        result["search_links"] = [
            f"https://imgops.com/{quote_plus(fname)}",
            f"https://images.google.com/searchbyimage/upload",
            f"https://yandex.com/images/",
            f"https://www.bing.com/visualsearch",
            f"https://tineye.com/",
        ]
        result["note"] = "ImgOps aggregates multiple engines — visit the link above to check all at once"
    except Exception as e:
        result["error"] = str(e)
    return result


# ── Result Aggregation ────────────────────────────────────────────────────────

def _aggregate(results: list[dict]) -> list[dict]:
    """Combine all matches, deduplicate by domain, rank by frequency."""
    seen_domains = {}
    all_matches = []
    for r in results:
        engine = r.get("engine", "?")
        for m in r.get("matches", []):
            domain = m.get("domain", "")
            if domain in seen_domains:
                seen_domains[domain]["engines"].append(engine)
            else:
                entry = {**m, "engines": [engine]}
                seen_domains[domain] = entry
                all_matches.append(entry)

    # Sort: matches found by multiple engines first
    all_matches.sort(key=lambda x: len(x["engines"]), reverse=True)
    return all_matches


# ── Main ──────────────────────────────────────────────────────────────────────

def search(image_path: str, headless: bool = True, tineye_key: str = "",
           skip_selenium: bool = False) -> dict:
    """
    Run multi-engine reverse image search.
    skip_selenium: True = only use TinEye API + ImgOps (--stealth mode or no Chrome)
    """
    tineye_key = tineye_key or os.environ.get("TINEYE_API_KEY", "")

    engine_results = []

    # TinEye API (no browser needed)
    tineye = _tineye(image_path, tineye_key)
    engine_results.append(tineye)

    # ImgOps links (always)
    imgops = _imgops(image_path)
    engine_results.append(imgops)

    if not skip_selenium:
        if not SELENIUM_OK:
            engine_results.append({
                "engine": "Selenium engines",
                "skipped": "selenium not installed — run: pip install selenium webdriver-manager",
            })
        else:
            driver = None
            try:
                driver = _make_driver(headless=headless)
                google = _google(driver, image_path)
                engine_results.append(google)
                time.sleep(1)
                yandex = _yandex(driver, image_path)
                engine_results.append(yandex)
                time.sleep(1)
                bing = _bing(driver, image_path)
                engine_results.append(bing)
            except Exception as e:
                engine_results.append({"engine": "Selenium", "error": str(e)})
            finally:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass

    aggregated = _aggregate(engine_results)
    total_unique = len(aggregated)

    verdict = "❌ No matches found"
    if total_unique >= 10:
        verdict = f"🔴 HIGH EXPOSURE — image found in {total_unique} locations"
    elif total_unique >= 3:
        verdict = f"🟡 Moderate exposure — {total_unique} unique domains"
    elif total_unique > 0:
        verdict = f"🟢 Low exposure — {total_unique} match(es)"

    return {
        "stage": "reverse_image_search",
        "verdict": verdict,
        "total_unique_domains": total_unique,
        "aggregated_matches": aggregated[:25],  # top 25
        "engine_results": engine_results,
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python stage6_reverse_search.py <image>")
        sys.exit(1)
    print(json.dumps(search(sys.argv[1]), indent=2, default=str))
