"""Stage 13: Web Archiving — submit URLs found in image to Wayback Machine."""
import re
import time
from typing import Any

try:
    import requests as _requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_WB_SAVE = "https://web.archive.org/save/"
_WB_AVAIL = "https://archive.org/wayback/available?url={url}"


def _save_url(url: str, session) -> dict:
    try:
        r = session.get(f"{_WB_SAVE}{url}", timeout=30, allow_redirects=True)
        archived_url = r.headers.get("Content-Location") or r.url
        if "web.archive.org/web/" in archived_url:
            return {"url": url, "archived": archived_url, "status": "saved"}
        return {"url": url, "status": "queued"}
    except Exception as e:
        return {"url": url, "status": "error", "reason": str(e)}


def _check_existing(url: str, session) -> str | None:
    try:
        r = session.get(_WB_AVAIL.format(url=url), timeout=10)
        data = r.json()
        snap = data.get("archived_snapshots", {}).get("closest", {})
        if snap.get("available"):
            return snap.get("url")
    except Exception:
        pass
    return None


def analyze(image_path: str) -> dict[str, Any]:
    result: dict = {"stage": "archive", "urls_found": [], "archived": [], "already_archived": [], "errors": []}

    if not REQUESTS_OK:
        result["skipped"] = "requests not installed"
        return result

    # Extract URLs from image metadata or OCR results passed via side-channel file
    # Primary: look for a sidecar .txt file written by stage4
    import os
    sidecar = image_path + ".ocr.txt"
    raw_text = ""
    if os.path.exists(sidecar):
        with open(sidecar) as f:
            raw_text = f.read()

    urls = list(set(_URL_RE.findall(raw_text)))[:20]  # cap at 20
    result["urls_found"] = urls

    if not urls:
        result["skipped"] = "No URLs found in image content"
        return result

    session = _requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 VisionOSINT/1.0"

    for url in urls:
        # Check if already archived first
        existing = _check_existing(url, session)
        if existing:
            result["already_archived"].append({"url": url, "archived": existing})
        else:
            res = _save_url(url, session)
            if res.get("status") == "error":
                result["errors"].append(res)
            else:
                result["archived"].append(res)
        time.sleep(0.5)  # be polite to archive.org

    result["summary"] = {
        "urls_processed": len(urls),
        "newly_archived": len(result["archived"]),
        "already_archived": len(result["already_archived"]),
        "errors": len(result["errors"]),
    }
    return result
