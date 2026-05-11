"""Stage 16: Dark Web Mention Scan — search hashes/emails/phones via Ahmia clearnet proxy."""
import os
import re
import time
from typing import Any

try:
    import requests as _requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    from bs4 import BeautifulSoup as _BS
    BS4_OK = True
except ImportError:
    BS4_OK = False

_AHMIA_SEARCH = "https://ahmia.fi/search/?q={query}"
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def _ahmia_search(query: str, session) -> list[dict]:
    """Search Ahmia.fi (dark web search via clearnet) for a query term."""
    if not BS4_OK:
        return []
    try:
        url = _AHMIA_SEARCH.format(query=_requests.utils.quote(query))
        r = session.get(url, timeout=20)
        if r.status_code != 200:
            return []
        soup = _BS(r.text, "html.parser")
        results = []
        for li in soup.select("li.result")[:10]:
            title_el = li.select_one("h4")
            link_el = li.select_one("a[href]")
            desc_el = li.select_one("p")
            results.append({
                "title": title_el.get_text(strip=True) if title_el else "",
                "url": link_el["href"] if link_el else "",
                "description": desc_el.get_text(strip=True)[:200] if desc_el else "",
            })
        return results
    except Exception:
        return []


def _leakcheck_email(email: str, session) -> dict:
    """Check leakcheck.io public API (no key needed for basic check)."""
    try:
        r = session.get(f"https://leakcheck.io/api/public?check={email}", timeout=10)
        if r.status_code == 200:
            d = r.json()
            return {"found": d.get("found", False), "sources": d.get("sources", [])}
    except Exception:
        pass
    return {}


def analyze(image_path: str) -> dict[str, Any]:
    result: dict = {
        "stage": "darkweb",
        "queries": [],
        "mentions": [],
        "summary": {},
    }

    if not REQUESTS_OK:
        result["skipped"] = "requests not installed"
        return result

    sidecar = image_path + ".ocr.txt"
    raw_text = ""
    if os.path.exists(sidecar):
        with open(sidecar) as f:
            raw_text = f.read()

    # Also read hashes from stage0 sidecar if available
    hash_sidecar = image_path + ".hashes.txt"
    hashes = []
    if os.path.exists(hash_sidecar):
        with open(hash_sidecar) as f:
            hashes = [line.strip() for line in f if line.strip()]

    emails = list(set(_EMAIL_RE.findall(raw_text)))[:5]
    queries = emails[:3] + hashes[:2]  # limit total queries

    if not queries:
        result["skipped"] = "No identifiers to search"
        return result

    session = _requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 VisionOSINT/1.0"

    all_mentions = []
    for query in queries:
        mentions = _ahmia_search(query, session)
        result["queries"].append({"query": query, "mention_count": len(mentions)})
        all_mentions.extend(mentions)
        time.sleep(1)

    # LeakCheck for emails
    leak_results = []
    for email in emails[:3]:
        lr = _leakcheck_email(email, session)
        if lr:
            leak_results.append({"email": email, **lr})
        time.sleep(0.5)

    result["mentions"] = all_mentions
    result["leak_check"] = leak_results
    result["summary"] = {
        "queries_run": len(queries),
        "total_dark_web_mentions": len(all_mentions),
        "emails_in_leaks": len([l for l in leak_results if l.get("found")]),
    }
    return result
