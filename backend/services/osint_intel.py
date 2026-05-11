import re
from collections import Counter
from urllib.parse import urlparse


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
HANDLE_RE = re.compile(r"(?<![\w@])@[A-Za-z0-9_]{3,32}\b")
COORD_RE = re.compile(r"(?<!\d)([-+]?\d{1,2}\.\d{3,})\s*,\s*([-+]?\d{1,3}\.\d{3,})(?!\d)")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
SOCIAL_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "youtube.com",
}
HIGH_TRUST_HINTS = {"edu", "gov", "mil"}
LOCATION_WORDS = {
    "street",
    "st.",
    "avenue",
    "ave",
    "road",
    "rd",
    "boulevard",
    "square",
    "station",
    "airport",
    "park",
    "bridge",
    "hotel",
    "cafe",
    "restaurant",
    "new york",
    "london",
    "paris",
    "tokyo",
    "seattle",
    "los angeles",
    "san francisco",
}


def domain_for(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).hostname or ""
        return host.lower().removeprefix("www.") or None
    except Exception:
        return None


def _unique(items: list[str], limit: int = 12) -> list[str]:
    seen = set()
    out = []
    for item in items:
        clean = item.strip().strip(".,;:)]}")
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            out.append(clean)
        if len(out) >= limit:
            break
    return out


def _match_strength(score: float, cluster_size: int) -> dict:
    if score >= 90:
        label = "Very strong"
    elif score >= 78:
        label = "Strong"
    elif score >= 60:
        label = "Possible"
    elif score >= 35:
        label = "Weak"
    else:
        label = "Speculative"
    return {
        "label": label,
        "score": round(score),
        "basis": f"Top visual score {round(score)} with {cluster_size} clustered hit(s)",
    }


def _source_credibility(domain: str | None, engines: list[str], cluster_size: int, url: str | None) -> dict:
    if not domain:
        return {"label": "Unknown", "score": 35, "basis": "No source domain was available"}
    suffix = domain.rsplit(".", 1)[-1]
    score = 45
    reasons = [f"Domain: {domain}"]
    if suffix in HIGH_TRUST_HINTS:
        score += 25
        reasons.append(f".{suffix} source")
    if cluster_size > 1:
        score += min(20, cluster_size * 4)
        reasons.append(f"{cluster_size} corroborating hits")
    if len(engines) > 1:
        score += min(18, len(engines) * 6)
        reasons.append(f"{len(engines)} engines")
    if url and any(marker in url.lower() for marker in ["archive", "original", "source", "map", "place"]):
        score += 8
        reasons.append("URL contains source/context hint")
    score = max(0, min(100, score))
    label = "Strong" if score >= 78 else "Good" if score >= 62 else "Mixed" if score >= 45 else "Low"
    return {"label": label, "score": score, "basis": "; ".join(reasons[:4])}


def extract_entities(text: str) -> dict:
    text = text or ""
    domains = re.findall(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", text, flags=re.I)
    social_links = []
    for match in re.findall(r"https?://[^\s<>'\"]+", text, flags=re.I):
        domain = domain_for(match)
        if domain and any(domain == social or domain.endswith(f".{social}") for social in SOCIAL_DOMAINS):
            social_links.append(match)
    return {
        "emails": _unique(EMAIL_RE.findall(text)),
        "handles": _unique(HANDLE_RE.findall(text)),
        "domains": _unique(domains),
        "phones": _unique(PHONE_RE.findall(text), limit=6),
        "social_links": _unique(social_links, limit=8),
    }


def extract_geo_clues(text: str) -> list[dict]:
    text = text or ""
    clues = []
    for lat, lon in COORD_RE.findall(text):
        clues.append({"type": "coordinates", "label": f"{lat}, {lon}", "confidence": 82, "basis": "Coordinate-like text"})
    lowered = text.lower()
    for word in sorted(LOCATION_WORDS, key=len, reverse=True):
        if word in lowered:
            clues.append({"type": "place_text", "label": word.title(), "confidence": 48, "basis": "Location-like keyword"})
    return clues[:10]


def analyze_browser_artifact(url: str, title: str | None = None, snippet: str | None = None) -> dict:
    combined = " ".join([url or "", title or "", snippet or ""])
    entities = extract_entities(combined)
    geo_clues = extract_geo_clues(combined)
    domain = domain_for(url)
    actions = ["Preserve screenshot or snippet with timestamp", "Compare final URL against original approved URL"]
    if entities["emails"] or entities["handles"] or entities["social_links"]:
        actions.append("Cross-reference extracted contact/profile clues inside the case")
    if geo_clues:
        actions.append("Verify location clues against image metadata, signage, and source context")
    if url and "archive" not in url.lower():
        actions.append("Capture an archived copy if the page is volatile")
    return {
        "domain": domain,
        "entities": entities,
        "geo_clues": geo_clues,
        "recommended_actions": actions[:5],
        "capture_label": "Source page artifact",
    }


def analyze_result_cluster(cluster: dict) -> dict:
    top = cluster.get("top_result") or {}
    items = cluster.get("items") or []
    engines = cluster.get("engines") or []
    cluster_size = int(cluster.get("cluster_size") or len(items) or 1)
    score = float(top.get("similarity_pct") or (cluster.get("rank_score") or 0) * 100 or 0)
    domain = top.get("source_domain") or domain_for(top.get("url"))
    combined = " ".join(
        [top.get("title") or "", top.get("url") or ""]
        + [f"{item.get('title') or ''} {item.get('url') or ''}" for item in items[:8]]
    )
    entities = extract_entities(combined)
    location_clues = extract_geo_clues(combined)
    domains = [domain_for(item.get("url")) for item in items if domain_for(item.get("url"))]
    domain_counts = Counter(domains)
    contradiction_hints = []
    if len(domain_counts) >= 4 and cluster_size >= 4:
        contradiction_hints.append("Many source domains repeat the image; verify which page is earliest or original")
    titles = [str(item.get("title") or "").lower() for item in items]
    if any("fake" in title or "hoax" in title for title in titles):
        contradiction_hints.append("At least one title suggests disputed authenticity")
    lane = "strong_match" if score >= 85 and cluster_size > 1 else "possible_match" if score >= 60 else "needs_review"
    if cluster.get("hidden"):
        lane = "rejected"
    elif cluster.get("saved"):
        lane = "saved"
    next_steps = [
        "Open the strongest source page and capture browser artifacts",
        "Check whether the source page predates reposts or mirrors",
        "Promote verified source context into case evidence",
    ]
    if location_clues:
        next_steps.insert(0, "Compare location clues against the Location Lab")
    if contradiction_hints:
        next_steps.insert(0, "Resolve contradiction hints before using this as evidence")
    return {
        "match_strength": _match_strength(score, cluster_size),
        "source_credibility": _source_credibility(domain, engines, cluster_size, top.get("url")),
        "corroboration_count": cluster_size,
        "engine_breakdown": [{"engine": engine, "label": engine.replace("Scraper", "")} for engine in engines],
        "location_clues": location_clues,
        "entities": entities,
        "contradiction_hints": contradiction_hints,
        "next_steps": next_steps[:6],
        "triage_lane": lane,
        "triage_lanes": ["strong_match", "possible_match", "needs_review", "rejected", "saved"],
        "provenance_summary": {
            "source_url": top.get("url"),
            "source_domain": domain,
            "cluster_size": cluster_size,
            "engines": engines,
        },
    }


def build_browser_followup_plan(items: list[dict], max_pages: int = 5, objective: str | None = None) -> dict:
    urls = []
    for item in items:
        url = item.get("url") if isinstance(item, dict) else str(item)
        if url and url not in urls:
            urls.append(url)
        if len(urls) >= max(1, min(max_pages, 10)):
            break
    return {
        "mode": "bounded_browser_assist",
        "objective": objective or "Inspect approved source pages, preserve artifacts, and extract cross-reference clues",
        "pages_to_visit": urls,
        "inspect_for": [
            "page title and final URL",
            "source context and publication clues",
            "emails, handles, domains, and social links",
            "coordinate or place-name clues",
            "contradictions against the selected result cluster",
        ],
        "artifacts_to_save": ["title", "final_url", "snippet", "screenshot_when_available", "extracted_clues"],
        "safety_note": "Browser Assist only visits approved URL targets and records an auditable run log.",
        "experimental_desktop_control": {
            "available": False,
            "label": "Future opt-in desktop-control hook",
            "warning": "Full computer/browser control is not enabled in this build.",
        },
    }
