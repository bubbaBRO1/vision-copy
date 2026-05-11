"""Registry of all /command handlers for VISION-AI chat."""
import asyncio
import json
from typing import Callable, Optional, AsyncGenerator
import httpx


COMMAND_REGISTRY: dict[str, dict] = {}


def command(name: str, description: str, usage: str = ""):
    def decorator(fn: Callable):
        COMMAND_REGISTRY[name] = {"fn": fn, "description": description, "usage": usage or name}
        return fn
    return decorator


# ── SEARCH & RESEARCH ────────────────────────────────────────────────────────

@command("/search", "Search DuckDuckGo and return summarized results", "/search [query]")
async def cmd_search(args: str, **ctx) -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://api.duckduckgo.com/",
            params={"q": args, "format": "json", "no_html": 1, "skip_disambig": 1},
        )
        data = r.json()
        results = []
        if data.get("AbstractText"):
            results.append(f"**Summary:** {data['AbstractText']}\n**Source:** {data.get('AbstractURL', '')}")
        for topic in data.get("RelatedTopics", [])[:5]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(f"- {topic['Text']} [{topic.get('FirstURL', '')}]")
        return "\n".join(results) if results else f"No results for: {args}"


@command("/wiki", "Wikipedia summary and key facts", "/wiki [topic]")
async def cmd_wiki(args: str, **ctx) -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "titles": args, "prop": "extracts", "exintro": 1, "explaintext": 1, "format": "json"},
        )
        pages = r.json().get("query", {}).get("pages", {})
        for page in pages.values():
            extract = page.get("extract", "")
            if extract:
                return f"**{page['title']}**\n\n{extract[:2000]}"
    return f"No Wikipedia article found for: {args}"


@command("/news", "Latest news via RSS aggregation", "/news [topic]")
async def cmd_news(args: str, **ctx) -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"https://news.google.com/rss/search?q={args}&hl=en-US&gl=US&ceid=US:en",
        )
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.text)
        items = root.findall(".//item")[:8]
        if not items:
            return f"No news found for: {args}"
        lines = [f"**Latest news: {args}**\n"]
        for item in items:
            title = item.findtext("title", "").replace("<![CDATA[", "").replace("]]>", "")
            link = item.findtext("link", "")
            pub = item.findtext("pubDate", "")[:16]
            lines.append(f"- [{title}]({link}) — {pub}")
        return "\n".join(lines)


# ── OSINT ─────────────────────────────────────────────────────────────────────

@command("/whois", "Full WHOIS lookup", "/whois [domain]")
async def cmd_whois(args: str, **ctx) -> str:
    try:
        import whois
        w = whois.whois(args.strip())
        fields = {
            "Domain": w.domain_name,
            "Registrar": w.registrar,
            "Created": str(w.creation_date)[:25] if w.creation_date else None,
            "Expires": str(w.expiration_date)[:25] if w.expiration_date else None,
            "Updated": str(w.updated_date)[:25] if w.updated_date else None,
            "Name Servers": ", ".join(w.name_servers or [])[:100],
            "Status": str(w.status)[:100] if w.status else None,
            "Emails": ", ".join(w.emails or []) if w.emails else None,
            "Country": w.country,
            "Org": w.org,
        }
        lines = [f"**WHOIS: {args}**\n"]
        for k, v in fields.items():
            if v:
                lines.append(f"- **{k}:** {v}")
        return "\n".join(lines)
    except Exception as e:
        return f"WHOIS failed: {e}"


@command("/dns", "DNS records lookup", "/dns [domain]")
async def cmd_dns(args: str, **ctx) -> str:
    try:
        import dns.resolver
        domain = args.strip()
        record_types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]
        lines = [f"**DNS: {domain}**\n"]
        for rtype in record_types:
            try:
                answers = dns.resolver.resolve(domain, rtype, raise_on_no_answer=False)
                if answers:
                    vals = [str(r) for r in answers][:5]
                    lines.append(f"**{rtype}:** {', '.join(vals)}")
            except Exception:
                pass
        return "\n".join(lines) if len(lines) > 1 else f"No DNS records found for: {domain}"
    except Exception as e:
        return f"DNS lookup failed: {e}"


@command("/iplookup", "IP geolocation + ASN info", "/iplookup [ip]")
async def cmd_iplookup(args: str, **ctx) -> str:
    async with httpx.AsyncClient(timeout=8) as client:
        r = await client.get(f"http://ip-api.com/json/{args.strip()}?fields=66846719")
        data = r.json()
        if data.get("status") != "success":
            return f"Failed to look up IP: {args}"
        lines = [f"**IP Intel: {args}**\n"]
        for k in ["query", "country", "regionName", "city", "zip", "isp", "org", "as", "asname", "lat", "lon", "timezone", "mobile", "proxy", "hosting"]:
            if data.get(k) is not None:
                lines.append(f"- **{k}:** {data[k]}")
        return "\n".join(lines)


@command("/headers", "HTTP headers + server fingerprinting", "/headers [url]")
async def cmd_headers(args: str, **ctx) -> str:
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        r = await client.head(args.strip(), headers={"User-Agent": "Mozilla/5.0"})
        lines = [f"**HTTP Headers: {args}**\n", f"Status: `{r.status_code}`\n"]
        for k, v in sorted(r.headers.items()):
            lines.append(f"- **{k}:** `{v}`")
        return "\n".join(lines)


@command("/subdomains", "Subdomain enumeration via crt.sh", "/subdomains [domain]")
async def cmd_subdomains(args: str, **ctx) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"https://crt.sh/?q=%.{args.strip()}&output=json")
        domains = list({entry.get("name_value", "").strip() for entry in r.json() if entry.get("name_value")})
        domains = sorted(d for d in domains if "\n" not in d)[:50]
        return f"**Subdomains for {args}** ({len(domains)} found):\n\n" + "\n".join(f"- `{d}`" for d in domains)


@command("/shodan", "Shodan InternetDB free lookup", "/shodan [ip]")
async def cmd_shodan(args: str, **ctx) -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"https://internetdb.shodan.io/{args.strip()}")
        if r.status_code == 404:
            return f"No Shodan data for {args}"
        data = r.json()
        lines = [f"**Shodan: {args}**\n"]
        if data.get("ports"):
            lines.append(f"- **Open ports:** {', '.join(map(str, data['ports']))}")
        if data.get("cpes"):
            lines.append(f"- **CPEs:** {', '.join(data['cpes'][:5])}")
        if data.get("tags"):
            lines.append(f"- **Tags:** {', '.join(data['tags'])}")
        if data.get("vulns"):
            lines.append(f"- **Vulns:** {', '.join(data['vulns'][:10])}")
        if data.get("hostnames"):
            lines.append(f"- **Hostnames:** {', '.join(data['hostnames'][:5])}")
        return "\n".join(lines)


@command("/wayback", "Check Internet Archive for historical versions", "/wayback [url]")
async def cmd_wayback(args: str, **ctx) -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"http://archive.org/wayback/available?url={args.strip()}"
        )
        data = r.json()
        snap = data.get("archived_snapshots", {}).get("closest", {})
        if snap.get("available"):
            return f"**Wayback Machine: {args}**\n\n- **Snapshot:** {snap['url']}\n- **Timestamp:** {snap['timestamp']}\n- **Status:** {snap['status']}"
        return f"No archived snapshots found for: {args}"


@command("/exif", "Dump EXIF of current image", "/exif")
async def cmd_exif(args: str, search_results: Optional[dict] = None, **ctx) -> str:
    if not search_results:
        return "No image in current session. Upload an image first."
    exif = search_results.get("EXIF & Metadata", {})
    if not exif:
        return "No EXIF data found for current image."
    lines = ["**EXIF Data:**\n"]
    for k, v in exif.items():
        if v and k != "raw":
            lines.append(f"- **{k}:** {v}")
    return "\n".join(lines)


@command("/hash", "Hash current image", "/hash [md5|sha256|phash]")
async def cmd_hash(args: str, search_results: Optional[dict] = None, **ctx) -> str:
    if not search_results:
        return "No image loaded."
    hashes = search_results.get("Hashing & NSFW", {})
    lines = ["**Image Hashes:**\n"]
    for algo in ["md5", "sha256", "phash", "dhash", "whash"]:
        if hashes.get(algo):
            lines.append(f"- **{algo.upper()}:** `{hashes[algo]}`")
    return "\n".join(lines) if len(lines) > 1 else "No hash data available."


@command("/ela", "Run Error Level Analysis description", "/ela")
async def cmd_ela(args: str, search_results: Optional[dict] = None, **ctx) -> str:
    if not search_results:
        return "No image loaded."
    forensics = search_results.get("Forensics (ELA)", {})
    ela = forensics.get("ela", {}) if forensics else {}
    if not ela:
        return "ELA not yet run. Use the Forensics panel in the UI."
    return f"**ELA Analysis:**\n- Manipulation probability: **{ela.get('manipulation_probability', 0):.1%}**\n- {ela.get('verdict', 'Unknown')}"


@command("/geoguess", "AI geolocation estimate of current image", "/geoguess")
async def cmd_geoguess(args: str, search_results: Optional[dict] = None, **ctx) -> str:
    if not search_results:
        return "No image loaded."
    geo = search_results.get("Geolocation", {})
    if not geo:
        return "Geolocation not yet run."
    primary = geo.get("primary", {})
    if not primary:
        return "No geolocation result available."
    lat = primary.get("lat")
    lon = primary.get("lon")
    confidence = geo.get("confidence", 0)
    address = primary.get("address", "Unknown")
    return f"**Geolocation Estimate:**\n- **Location:** {address}\n- **Coordinates:** {lat}, {lon}\n- **Confidence:** {confidence}%"


@command("/faces", "Face detection summary", "/faces")
async def cmd_faces(args: str, search_results: Optional[dict] = None, **ctx) -> str:
    if not search_results:
        return "No image loaded."
    content = search_results.get("Face & Object Detection", {})
    faces = content.get("faces", []) if content else []
    if not faces:
        return "No faces detected in current image."
    lines = [f"**{len(faces)} face(s) detected:**\n"]
    for i, face in enumerate(faces):
        attrs = face.get("attributes", {})
        lines.append(f"**Face {i+1}:** Age ~{attrs.get('age', '?')}, {attrs.get('gender', '?')}, emotion: {attrs.get('emotion', '?')}")
    return "\n".join(lines)


@command("/translate", "Translate text", "/translate [text]")
async def cmd_translate(args: str, **ctx) -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://libretranslate.com/translate",
            json={"q": args, "source": "auto", "target": "en"},
            headers={"Content-Type": "application/json"},
        )
        if r.status_code == 200:
            data = r.json()
            return f"**Translation:**\n- **Detected language:** {data.get('detectedLanguage', {}).get('language', 'unknown')}\n- **Result:** {data.get('translatedText', '')}"
        # Fallback: just ask the AI
        return f"Translation service unavailable. Text: {args}"


@command("/summarize", "Fetch and summarize a webpage", "/summarize [url]")
async def cmd_summarize(args: str, **ctx) -> str:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(args.strip(), headers={"User-Agent": "Mozilla/5.0"})
        from readabilipy import simple_json_from_html_string
        result = simple_json_from_html_string(r.text, use_readability=True)
        text = (result.get("plain_text") or "")[:3000]
        if not text:
            return "Could not extract content from that URL."
        from .ollama_client import generate_one_shot
        summary = await generate_one_shot(f"Summarize this article in 3-5 bullet points:\n\n{text}")
        return f"**Summary of {args}:**\n\n{summary}"
    except Exception as e:
        return f"Failed to fetch/summarize: {e}"


@command("/model", "Switch AI model", "/model [name]")
async def cmd_model(args: str, **ctx) -> str:
    from .ollama_client import list_models
    available = await list_models()
    if not args.strip():
        return "**Available models:**\n" + "\n".join(f"- `{m}`" for m in available)
    return f"Model set to `{args.strip()}` for this conversation."


@command("/dossier", "Generate AI intelligence dossier from current search results", "/dossier")
async def cmd_dossier(args: str, search_results: Optional[dict] = None, **ctx) -> str:
    if not search_results:
        return "No search results loaded. Upload an image first."
    try:
        from ai.dossier import generate_dossier
        data = await asyncio.to_thread(generate_dossier, search_results, ctx.get("filename", "image"))
        dossier = data.get("dossier", "")
        score = data.get("intel_score")
        header = f"**Intel Score:** {score}/100\n\n" if score else ""
        return f"{header}{dossier}"
    except Exception as e:
        return f"Dossier generation failed: {e}"


@command("/blockchain", "Look up a crypto wallet address", "/blockchain <address>")
async def cmd_blockchain(args: str, **ctx) -> str:
    addr = args.strip()
    if not addr:
        return "Usage: `/blockchain <wallet_address>`"
    async with httpx.AsyncClient(timeout=15) as client:
        # Bitcoin
        if addr.startswith(("1", "3", "bc1")):
            try:
                r = await client.get(f"https://blockchain.info/rawaddr/{addr}?limit=0")
                if r.status_code == 200:
                    d = r.json()
                    bal = d.get("final_balance", 0) / 1e8
                    return f"**Bitcoin** `{addr}`\nBalance: **{bal:.8f} BTC**\nTransactions: {d.get('n_tx', 0)}\nTotal received: {d.get('total_received', 0)/1e8:.8f} BTC"
            except Exception as e:
                return f"Lookup error: {e}"
        # Ethereum
        elif addr.startswith("0x") and len(addr) == 42:
            try:
                r = await client.get(f"https://api.etherscan.io/api?module=account&action=balance&address={addr}&tag=latest")
                if r.status_code == 200:
                    d = r.json()
                    if d.get("status") == "1":
                        bal = int(d["result"]) / 1e18
                        return f"**Ethereum** `{addr}`\nBalance: **{bal:.6f} ETH**"
            except Exception as e:
                return f"Lookup error: {e}"
        return f"Address format not recognized. Supported: Bitcoin, Ethereum.\nAddress: `{addr}`"


@command("/pwned", "Check email for data breaches via HaveIBeenPwned", "/pwned <email>")
async def cmd_pwned(args: str, **ctx) -> str:
    import os, hashlib
    email = args.strip().lower()
    if not email or "@" not in email:
        return "Usage: `/pwned <email>`"
    api_key = os.environ.get("HIBP_API_KEY", "")
    headers = {"User-Agent": "VisionOSINT/1.0"}
    if api_key:
        headers["hibp-api-key"] = api_key
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}?truncateResponse=false",
                headers=headers,
            )
            if r.status_code == 404:
                return f"**Good news!** `{email}` not found in any known breaches."
            elif r.status_code == 401:
                return "HIBP API key required for this lookup. Set `HIBP_API_KEY` env var."
            elif r.status_code == 200:
                breaches = r.json()
                lines = [f"**{len(breaches)} breach(es)** found for `{email}`:\n"]
                for b in breaches[:10]:
                    lines.append(f"- **{b['Name']}** ({b.get('BreachDate', '?')}) — {', '.join(b.get('DataClasses', [])[:4])}")
                if len(breaches) > 10:
                    lines.append(f"... and {len(breaches) - 10} more")
                return "\n".join(lines)
        except Exception as e:
            return f"HIBP lookup failed: {e}"
    return "Unexpected error"


@command("/archive", "Submit URL to Wayback Machine", "/archive <url>")
async def cmd_archive(args: str, **ctx) -> str:
    url = args.strip()
    if not url.startswith("http"):
        return "Usage: `/archive <url>` — URL must start with http(s)://"
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            r = await client.get(f"https://web.archive.org/save/{url}")
            location = r.headers.get("Content-Location") or r.headers.get("Location", "")
            if "web.archive.org/web/" in (location or r.url.path):
                archived = location or str(r.url)
                return f"Archived: {archived}"
            return f"Submitted to Wayback Machine. Check: https://web.archive.org/web/*/{url}"
        except Exception as e:
            return f"Archive failed: {e}"


@command("/timeline", "Build chronological timeline from all metadata timestamps", "/timeline")
async def cmd_timeline(args: str, search_results: Optional[dict] = None, **ctx) -> str:
    if not search_results:
        return "No search results loaded."
    events = []
    # EXIF timestamps
    meta = search_results.get("EXIF & Metadata", {})
    for key in ("DateTimeOriginal", "DateTime", "DateTimeDigitized", "CreateDate", "ModifyDate"):
        val = meta.get(key) or meta.get("exif", {}).get(key)
        if val:
            events.append((str(val), f"📷 EXIF `{key}`: {val}"))
    # Breach dates
    leaks = search_results.get("Leaked Credentials", {})
    for email_data in leaks.get("emails_checked", []):
        for breach in email_data.get("breaches", []):
            if breach.get("breach_date"):
                events.append((breach["breach_date"], f"🔓 Breach: **{breach['name']}** ({email_data['email']})"))
    # Archive dates
    archive = search_results.get("Web Archiving", {})
    for item in archive.get("archived", []) + archive.get("already_archived", []):
        if "archived" in item:
            events.append(("archived", f"🗄️ Archived: {item.get('url', '')}"))
    if not events:
        return "No timestamps found in search results."
    events.sort(key=lambda x: x[0])
    lines = ["**Timeline of Events:**\n"]
    for _, label in events:
        lines.append(f"- {label}")
    return "\n".join(lines)


@command("/compare", "Compare current search to another by ID", "/compare <search_id>")
async def cmd_compare(args: str, search_results: Optional[dict] = None, db=None, **ctx) -> str:
    search_id = args.strip()
    if not search_id:
        return "Usage: `/compare <search_id>`"
    if not search_results:
        return "No current search results loaded."
    # Fetch other search from DB
    if db is None:
        return "Database context not available in this session."
    try:
        from models.search import Search
        import uuid
        other = await db.get(Search, uuid.UUID(search_id))
        if not other or not other.results_json:
            return f"Search `{search_id}` not found or has no results."
        other_results = other.results_json
        lines = [f"**Comparing current image vs `{other.filename}`:**\n"]
        # Hash comparison
        h1 = search_results.get("Hashing & NSFW", {})
        h2 = other_results.get("Hashing & NSFW", {})
        if h1.get("phash") and h2.get("phash"):
            ph1, ph2 = h1["phash"], h2["phash"]
            # Hamming distance approximation
            diff = bin(int(ph1, 16) ^ int(ph2, 16)).count("1") if ph1 and ph2 else None
            if diff is not None:
                match_pct = max(0, 100 - diff * 1.5625)
                lines.append(f"- **Perceptual hash similarity:** {match_pct:.0f}% (hamming={diff})")
        # GPS comparison
        g1 = search_results.get("EXIF & Metadata", {}).get("gps", {})
        g2 = other_results.get("EXIF & Metadata", {}).get("gps", {})
        if g1.get("latitude") and g2.get("latitude"):
            lines.append(f"- **GPS (current):** {g1['latitude']:.4f}, {g1['longitude']:.4f}")
            lines.append(f"- **GPS (other):** {g2['latitude']:.4f}, {g2['longitude']:.4f}")
        lines.append(f"\nFull comparison: use stage_compare for detailed face + hash + metadata matching.")
        return "\n".join(lines)
    except Exception as e:
        return f"Compare failed: {e}"


@command("/help", "Show all commands or detail on one", "/help [command?]")
async def cmd_help(args: str, **ctx) -> str:
    if args.strip():
        cmd = args.strip()
        if cmd in COMMAND_REGISTRY:
            info = COMMAND_REGISTRY[cmd]
            return f"**{cmd}**\n{info['description']}\nUsage: `{info['usage']}`"
        return f"Unknown command: {cmd}"
    lines = ["**VISION-AI Slash Commands:**\n"]
    for name, info in sorted(COMMAND_REGISTRY.items()):
        lines.append(f"- `{name}` — {info['description']}")
    return "\n".join(lines)


async def handle_slash_command(
    text: str,
    search_results: Optional[dict] = None,
    **ctx,
) -> Optional[str]:
    """Returns command output string or None if not a slash command."""
    text = text.strip()
    if not text.startswith("/"):
        return None

    parts = text.split(None, 1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd not in COMMAND_REGISTRY:
        return f"Unknown command: `{cmd}`. Use `/help` to see all commands."

    try:
        return await COMMAND_REGISTRY[cmd]["fn"](args, search_results=search_results, **ctx)
    except Exception as e:
        return f"Command failed: {e}"
