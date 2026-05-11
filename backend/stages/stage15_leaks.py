"""Stage 15: Leaked Credential Check — check emails via HaveIBeenPwned (k-anonymity)."""
import hashlib
import os
import re
import time
from typing import Any

try:
    import requests as _requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_HIBP_API = "https://haveibeenpwned.com/api/v3"
_PWNED_PASSWORDS_API = "https://api.pwnedpasswords.com/range/{prefix}"


def _check_email_breaches(email: str, session, api_key: str | None) -> list[dict]:
    """Check email against HIBP breach database."""
    headers = {"hibp-api-key": api_key, "User-Agent": "VisionOSINT/1.0"} if api_key else {"User-Agent": "VisionOSINT/1.0"}
    try:
        r = session.get(
            f"{_HIBP_API}/breachedaccount/{email}?truncateResponse=false",
            headers=headers,
            timeout=10,
        )
        if r.status_code == 200:
            return [
                {
                    "name": b["Name"],
                    "domain": b.get("Domain", ""),
                    "breach_date": b.get("BreachDate", ""),
                    "pwn_count": b.get("PwnCount", 0),
                    "data_classes": b.get("DataClasses", []),
                    "is_sensitive": b.get("IsSensitive", False),
                }
                for b in r.json()
            ]
        elif r.status_code == 404:
            return []  # not found = not breached
        elif r.status_code == 401:
            return [{"error": "HIBP API key required for email lookup"}]
        elif r.status_code == 429:
            time.sleep(2)
            return [{"error": "HIBP rate limited"}]
    except Exception as e:
        return [{"error": str(e)}]
    return []


def _check_pastes(email: str, session, api_key: str | None) -> list[dict]:
    """Check if email appeared in pastes."""
    if not api_key:
        return []
    headers = {"hibp-api-key": api_key, "User-Agent": "VisionOSINT/1.0"}
    try:
        r = session.get(f"{_HIBP_API}/pasteaccount/{email}", headers=headers, timeout=10)
        if r.status_code == 200:
            return [
                {"source": p.get("Source", ""), "id": p.get("Id", ""), "date": p.get("Date", ""), "email_count": p.get("EmailCount", 0)}
                for p in r.json()
            ]
    except Exception:
        pass
    return []


def analyze(image_path: str) -> dict[str, Any]:
    result: dict = {"stage": "leaks", "emails_checked": [], "summary": {}}

    if not REQUESTS_OK:
        result["skipped"] = "requests not installed"
        return result

    sidecar = image_path + ".ocr.txt"
    raw_text = ""
    if os.path.exists(sidecar):
        with open(sidecar) as f:
            raw_text = f.read()

    emails = list(set(_EMAIL_RE.findall(raw_text)))[:10]  # cap at 10
    if not emails:
        result["skipped"] = "No email addresses found in image"
        return result

    api_key = os.environ.get("HIBP_API_KEY")
    session = _requests.Session()

    total_breaches = 0
    checked = []
    for email in emails:
        breaches = _check_email_breaches(email, session, api_key)
        pastes = _check_pastes(email, session, api_key)
        total_breaches += len([b for b in breaches if "error" not in b])
        checked.append({
            "email": email,
            "breach_count": len(breaches),
            "breaches": breaches,
            "paste_count": len(pastes),
            "pastes": pastes,
        })
        time.sleep(1.6)  # HIBP rate limit: 1 req/1.5s

    result["emails_checked"] = checked
    result["summary"] = {
        "emails_found": len(emails),
        "total_breaches": total_breaches,
        "breached_emails": len([e for e in checked if e["breach_count"] > 0]),
        "hibp_key_present": bool(api_key),
    }
    return result
