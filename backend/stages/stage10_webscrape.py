"""
Stage 10 — Web Intelligence Scraper
=====================================
Takes URLs discovered in earlier stages (reverse search, social profiles,
IPTC credit links) and extracts deep intelligence from each:

  - Clean article text, author, publish date (trafilatura)
  - Contact info: emails, phone numbers, addresses, social handles
  - Domain WHOIS: registrar, dates, registrant org/email
  - DNS records: hosting provider, email provider, site ownership proofs
  - Google dorking for additional mentions
  - URLScan.io: screenshot, tech stack, linked assets

Runs after Stage 9 social. Results feed POI profiles + Intel score.

Usage:
    from stages.stage10_webscrape import scrape_all
    all_results["web_intel"] = scrape_all(all_results)
"""

import os
import re
import time
import socket
import hashlib
from pathlib import Path
from urllib.parse import urlparse, quote
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Patterns for contact extraction
_EMAIL_RE    = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.I)
_PHONE_RE    = re.compile(r"""
    (?:
        (?:\+\d{1,3}[\s\-.]?)?          # optional country code
        (?:\(\d{1,4}\)[\s\-.]?)?        # optional area code in parens
        \d{2,4}[\s\-.]?                 # first group
        \d{2,4}[\s\-.]?                 # second group
        \d{2,4}                         # third group
    )
""", re.VERBOSE)
_SOCIAL_RE   = re.compile(
    r"(?:twitter\.com|x\.com)/([A-Za-z0-9_]{1,50})|"
    r"instagram\.com/([A-Za-z0-9_.]{1,50})|"
    r"facebook\.com/([A-Za-z0-9.]{1,50})|"
    r"linkedin\.com/in/([A-Za-z0-9\-]{1,100})|"
    r"github\.com/([A-Za-z0-9\-]{1,100})|"
    r"youtube\.com/@([A-Za-z0-9_\-]{1,100})|"
    r"tiktok\.com/@([A-Za-z0-9_.]{1,100})",
    re.I
)

# Known VPN/hosting ASN keywords
_VPN_KEYWORDS = {
    "mullvad", "nordvpn", "expressvpn", "protonvpn", "privateinternetaccess",
    "torguard", "surfshark", "ipvanish", "cyberghost",
}
_HOSTING_MAP = {
    "amazonaws": "AWS", "googleusercontent": "Google Cloud",
    "cloudflare": "Cloudflare", "fastly": "Fastly",
    "akamai": "Akamai", "github.io": "GitHub Pages",
    "vercel": "Vercel", "netlify": "Netlify",
    "heroku": "Heroku", "digitalocean": "DigitalOcean",
    "vultr": "Vultr", "linode": "Linode",
    "ovh": "OVH", "hetzner": "Hetzner",
    "azure": "Azure", "oracle": "Oracle Cloud",
}
_EMAIL_PROVIDERS = {
    "google": "Google Workspace",
    "aspmx.l.google": "Google Workspace",
    "outlook": "Microsoft 365",
    "office365": "Microsoft 365",
    "protonmail": "ProtonMail",
    "tutanota": "Tutanota",
    "zoho": "Zoho Mail",
    "mxroute": "MXroute",
    "mailgun": "Mailgun",
    "sendgrid": "SendGrid",
    "amazonses": "Amazon SES",
}


# ── Single URL scrape ─────────────────────────────────────────────────────────

def scrape_url(url: str, timeout: int = 15) -> dict:
    """
    Extract intelligence from a single URL.
    Uses trafilatura for clean content; falls back to BeautifulSoup.
    """
    result = {
        "url":           url,
        "title":         None,
        "author":        None,
        "publish_date":  None,
        "text":          None,
        "outbound_links": [],
        "images":        [],
        "og_data":       {},
        "meta_tags":     {},
        "status_code":   None,
        "error":         None,
    }

    try:
        # Attempt trafilatura first
        try:
            import trafilatura
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                meta = trafilatura.extract_metadata(downloaded)
                if meta:
                    result["title"]        = meta.title
                    result["author"]       = meta.author
                    result["publish_date"] = str(meta.date) if meta.date else None

                text = trafilatura.extract(
                    downloaded,
                    include_links=True,
                    include_images=True,
                    include_comments=False,
                    no_fallback=False,
                )
                result["text"] = text
                result["status_code"] = 200
                return result
        except ImportError:
            pass

        # Fallback: requests + manual parse
        resp = requests.get(url, headers=HEADERS, timeout=timeout,
                            allow_redirects=True)
        result["status_code"] = resp.status_code
        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}"
            return result

        html = resp.text

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # Title
            title_tag = soup.find("title")
            result["title"] = title_tag.get_text(strip=True) if title_tag else None

            # Author
            author_meta = (
                soup.find("meta", attrs={"name": re.compile(r"author", re.I)}) or
                soup.find("meta", attrs={"property": "article:author"})
            )
            if author_meta:
                result["author"] = author_meta.get("content")

            # Date
            date_meta = (
                soup.find("meta", attrs={"property": "article:published_time"}) or
                soup.find("meta", attrs={"name": re.compile(r"date", re.I)}) or
                soup.find("time")
            )
            if date_meta:
                result["publish_date"] = (
                    date_meta.get("content") or
                    date_meta.get("datetime") or
                    date_meta.get_text(strip=True)
                )

            # OG tags
            for tag in soup.find_all("meta", attrs={"property": re.compile(r"^og:")}):
                key = tag.get("property", "")[3:]
                result["og_data"][key] = tag.get("content", "")

            # Links
            for a in soup.find_all("a", href=True)[:100]:
                href = a["href"].strip()
                if href.startswith("http"):
                    result["outbound_links"].append(href)

            # Images
            for img in soup.find_all("img", src=True)[:20]:
                src = img.get("src", "")
                if src.startswith("http"):
                    result["images"].append(src)

            # Text
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            result["text"] = soup.get_text(separator=" ", strip=True)[:5000]

        except ImportError:
            # No BeautifulSoup — extract raw text
            result["text"] = re.sub(r"<[^>]+>", " ", html)[:3000]

    except requests.exceptions.Timeout:
        result["error"] = "timeout"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── Contact info extraction ───────────────────────────────────────────────────

def extract_contact_info(text: str, source_url: str = "") -> dict:
    """
    Extract emails, phones, social handles, addresses from text.
    """
    if not text:
        return {"emails": [], "phones": [], "social_handles": {}, "addresses": []}

    # Emails
    emails = list(set(
        e for e in _EMAIL_RE.findall(text)
        if not e.endswith((".png", ".jpg", ".gif", ".svg"))  # skip image filenames
        and "noreply" not in e.lower()
        and "example" not in e.lower()
    ))

    # Phones — validate with phonenumbers if available
    raw_phones = _PHONE_RE.findall(text)
    valid_phones: list[str] = []
    try:
        import phonenumbers
        seen: set = set()
        for p in raw_phones:
            p = p.strip()
            if len(p) < 7:
                continue
            for region in (None, "US", "GB"):
                try:
                    pn = phonenumbers.parse(p, region)
                    if phonenumbers.is_valid_number(pn):
                        fmt = phonenumbers.format_number(
                            pn, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                        if fmt not in seen:
                            seen.add(fmt)
                            valid_phones.append(fmt)
                        break
                except Exception:
                    pass
    except ImportError:
        # Basic dedup without validation
        seen_raw: set = set()
        for p in raw_phones:
            p = re.sub(r"\s+", "", p.strip())
            if len(p) >= 7 and p not in seen_raw:
                seen_raw.add(p)
                valid_phones.append(p)

    # Social handles
    handles: dict[str, list[str]] = {}
    platform_map = {
        0: "twitter", 1: "instagram", 2: "facebook",
        3: "linkedin", 4: "github", 5: "youtube", 6: "tiktok",
    }
    for match in _SOCIAL_RE.finditer(text):
        for i, group in enumerate(match.groups()):
            if group:
                platform = platform_map.get(i, "unknown")
                handles.setdefault(platform, [])
                if group not in handles[platform]:
                    handles[platform].append(group)

    # Addresses — heuristic: lines with number + street word + city/state
    address_re = re.compile(
        r"\b\d{1,5}\s+[A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|"
        r"Boulevard|Blvd|Lane|Ln|Drive|Dr|Way|Court|Ct|Place|Pl)\b.*",
        re.I
    )
    addresses = address_re.findall(text)[:5]

    return {
        "emails":         emails,
        "phones":         valid_phones,
        "social_handles": handles,
        "addresses":      addresses,
    }


# ── WHOIS lookup ──────────────────────────────────────────────────────────────

def whois_lookup(domain: str) -> dict:
    """
    WHOIS data for a domain. Uses python-whois library.
    """
    result = {
        "registrar":         None,
        "creation_date":     None,
        "expiry_date":       None,
        "updated_date":      None,
        "registrant_name":   None,
        "registrant_email":  None,
        "registrant_org":    None,
        "name_servers":      [],
        "status":            [],
        "privacy_protected": False,
        "age_days":          None,
        "error":             None,
    }

    # Strip scheme/path from domain
    domain = re.sub(r"^https?://", "", domain).split("/")[0].split(":")[0]
    if not domain:
        result["error"] = "Invalid domain"
        return result

    try:
        import whois
        w = whois.whois(domain)

        def _first(val):
            if isinstance(val, list):
                return val[0] if val else None
            return val

        def _str_date(val):
            if val is None:
                return None
            first = _first(val)
            if first is None:
                return None
            return str(first)[:10]

        result["registrar"]      = str(w.registrar or "").strip() or None
        result["creation_date"]  = _str_date(w.creation_date)
        result["expiry_date"]    = _str_date(w.expiration_date)
        result["updated_date"]   = _str_date(w.updated_date)
        result["name_servers"]   = [
            str(ns).lower() for ns in (w.name_servers or [])
        ][:5]
        result["status"] = (
            [w.status] if isinstance(w.status, str) else list(w.status or [])
        )[:3]

        # Registrant info (often redacted)
        registrant_email = str(w.emails or "").strip()
        if "@" in registrant_email:
            result["registrant_email"] = registrant_email.split()[0]
        result["registrant_org"]  = str(w.org or "").strip() or None
        result["registrant_name"] = str(w.name or "").strip() or None

        # Privacy check
        privacy_keywords = {"privacy", "protect", "proxy", "whoisguard",
                            "redacted", "domain admin"}
        combined = " ".join(filter(None, [
            result["registrant_email"] or "",
            result["registrant_name"] or "",
            result["registrant_org"] or "",
        ])).lower()
        result["privacy_protected"] = any(k in combined for k in privacy_keywords)

        # Domain age
        if result["creation_date"]:
            try:
                from datetime import datetime
                created = datetime.strptime(result["creation_date"], "%Y-%m-%d")
                age = (datetime.utcnow() - created).days
                result["age_days"] = age
            except Exception:
                pass

    except ImportError:
        result["error"] = "python-whois not installed (pip install python-whois)"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── DNS intelligence ──────────────────────────────────────────────────────────

def dns_intel(domain: str) -> dict:
    """
    DNS records: A, MX, TXT, NS.
    Infers: hosting provider, email provider, site ownership tokens.
    """
    result = {
        "a_records":            [],
        "mx_records":           [],
        "txt_records":          [],
        "ns_records":           [],
        "hosting_hint":         None,
        "email_provider":       None,
        "site_ownership_proofs": [],
        "is_vpn_or_proxy":      False,
        "error":                None,
    }

    domain = re.sub(r"^https?://", "", domain).split("/")[0].split(":")[0]
    if not domain:
        result["error"] = "Invalid domain"
        return result

    try:
        import dns.resolver

        # A records
        try:
            answers = dns.resolver.resolve(domain, "A")
            result["a_records"] = [str(r) for r in answers]
        except Exception:
            pass

        # MX records
        try:
            answers = dns.resolver.resolve(domain, "MX")
            result["mx_records"] = sorted(
                [str(r.exchange).rstrip(".").lower() for r in answers]
            )
        except Exception:
            pass

        # TXT records
        try:
            answers = dns.resolver.resolve(domain, "TXT")
            for r in answers:
                txt = str(r).strip('"').strip()
                result["txt_records"].append(txt)
                # Site ownership proofs
                if any(k in txt.lower() for k in (
                    "google-site-verification", "facebook-domain-verification",
                    "github-", "stripe-verification", "atlassian-domain-verification",
                )):
                    result["site_ownership_proofs"].append(txt[:80])
        except Exception:
            pass

        # NS records
        try:
            answers = dns.resolver.resolve(domain, "NS")
            result["ns_records"] = [str(r).rstrip(".").lower() for r in answers][:4]
        except Exception:
            pass

        # Hosting hint from A record reverse DNS or NS records
        all_host_text = " ".join(
            result["a_records"] + result["ns_records"]
        ).lower()
        for key, name in _HOSTING_MAP.items():
            if key in all_host_text:
                result["hosting_hint"] = name
                break

        # VPN check
        if any(k in all_host_text for k in _VPN_KEYWORDS):
            result["is_vpn_or_proxy"] = True

        # Email provider from MX
        mx_text = " ".join(result["mx_records"]).lower()
        for key, name in _EMAIL_PROVIDERS.items():
            if key in mx_text:
                result["email_provider"] = name
                break

    except ImportError:
        # Fallback: use socket for basic A lookup
        try:
            ips = socket.gethostbyname_ex(domain)[2]
            result["a_records"] = ips
        except Exception:
            pass
        result["error"] = "dnspython not installed — partial results only"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── Google dorking ────────────────────────────────────────────────────────────

def google_dork(query: str, num_results: int = 10, sleep_s: float = 2.0) -> list[dict]:
    """
    Google search results for a dork query (no API key needed).
    Uses googlesearch-python library. Rate-limited by sleep_s.
    """
    results: list[dict] = []
    try:
        from googlesearch import search
        for url in search(query, num_results=num_results, sleep_interval=sleep_s):
            results.append({"url": url, "query": query})
        time.sleep(sleep_s)
    except ImportError:
        results.append({"error": "googlesearch-python not installed", "query": query})
    except Exception as e:
        results.append({"error": str(e)[:80], "query": query})
    return results


# ── URL collection from pipeline ─────────────────────────────────────────────

def _collect_urls(results: dict) -> list[str]:
    """Gather all interesting URLs from all previous stages."""
    urls: list[str] = []

    # Stage 6: reverse search results
    rev = results.get("reverse_search", {})
    for r in rev.get("results", []):
        u = r.get("url", "")
        if u and u.startswith("http"):
            urls.append(u)

    # Stage 7: face search matches
    face_search = results.get("face_search", {})
    for m in face_search.get("matches", []):
        u = m.get("url", "")
        if u and u.startswith("http"):
            urls.append(u)

    # Stage 9: social profile URLs (found platforms — actual profile pages, not homepages)
    social = results.get("social", {})
    for platform in social.get("found_platforms", []):
        u = platform.get("url", "")
        # Skip homepage-only URLs (too short, no meaningful path)
        parsed = urlparse(u)
        if u and u.startswith("http") and len(parsed.path.strip("/")) > 1:
            urls.append(u)

    # Stage 1: IPTC credit / source URL
    meta = results.get("metadata", {})
    iptc = meta.get("iptc", {})
    for key in ("credit", "source"):
        val = iptc.get(key, "")
        if val and val.startswith("http"):
            urls.append(val)

    # XMP source
    xmp = meta.get("xmp", {})
    if xmp.get("raw_xmp"):
        found = re.findall(r"https?://[^\s\"<>]+", xmp["raw_xmp"])
        urls.extend(found[:5])

    # Deduplicate preserving order
    seen: set = set()
    unique: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    # Filter: skip known social platform homepages (no useful content to scrape)
    _skip_patterns = {
        "twitter.com", "x.com", "instagram.com", "facebook.com",
        "tiktok.com", "youtube.com", "linkedin.com", "reddit.com",
        "discord.com", "t.me",
    }
    def _should_skip(u: str) -> bool:
        parsed = urlparse(u)
        host = parsed.netloc.lower().replace("www.", "")
        # Skip if just the homepage of a major social platform
        if host in _skip_patterns and len(parsed.path.strip("/")) < 3:
            return True
        return False

    return [u for u in unique if not _should_skip(u)][:50]  # cap at 50 URLs


def _extract_domains(urls: list[str]) -> list[str]:
    """Get unique domains from a list of URLs."""
    domains: list[str] = []
    seen: set = set()
    for url in urls:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        if domain and domain not in seen:
            seen.add(domain)
            domains.append(domain)
    return domains


# ── Master scrape function ────────────────────────────────────────────────────

def scrape_all(results: dict,
               max_scrape_workers: int = 10,
               run_google_dorks: bool = False) -> dict:
    """
    Collect all URLs from pipeline → scrape concurrently → WHOIS + DNS on domains.

    Parameters
    ----------
    results            : all_results dict from imagetrace.py
    max_scrape_workers : concurrent HTTP threads for URL scraping
    run_google_dorks   : run Google dorks for username/email (adds 10-30s; rate-limited)
    """
    output = {
        "stage":                "web_intel",
        "urls_scraped":         [],
        "scraped":              [],
        "whois_results":        {},
        "dns_results":          {},
        "all_emails":           [],
        "all_phones":           [],
        "social_handles_found": {},
        "addresses_found":      [],
        "google_dork_results":  [],
        "owner_verified_domains": [],
        "flags":                [],
    }

    # Collect URLs
    urls_to_scrape = _collect_urls(results)
    output["urls_scraped"] = urls_to_scrape

    if not urls_to_scrape:
        output["flags"].append("⚠️  No URLs found to scrape")

    # Scrape concurrently
    print(f"[Stage 10] Scraping {len(urls_to_scrape)} URLs...")
    scraped_pages: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_scrape_workers) as executor:
        futures = {
            executor.submit(scrape_url, url, 15): url
            for url in urls_to_scrape
        }
        for future in as_completed(futures):
            try:
                page = future.result()
                scraped_pages.append(page)
            except Exception:
                pass

    output["scraped"] = scraped_pages

    # Extract contact info from all scraped text
    all_emails: list[str] = []
    all_phones: list[str] = []
    all_handles: dict[str, list[str]] = {}
    all_addresses: list[str] = []

    for page in scraped_pages:
        text = page.get("text") or ""
        contact = extract_contact_info(text, page["url"])
        all_emails.extend(contact["emails"])
        all_phones.extend(contact["phones"])
        for platform, handles in contact["social_handles"].items():
            all_handles.setdefault(platform, [])
            for h in handles:
                if h not in all_handles[platform]:
                    all_handles[platform].append(h)
        all_addresses.extend(contact["addresses"])

        # Also scan outbound links for social handles
        for link in page.get("outbound_links", []):
            link_contact = extract_contact_info(link)
            for platform, handles in link_contact["social_handles"].items():
                all_handles.setdefault(platform, [])
                for h in handles:
                    if h not in all_handles[platform]:
                        all_handles[platform].append(h)

    # Deduplicate
    output["all_emails"]           = list(set(all_emails))
    output["all_phones"]           = list(set(all_phones))
    output["social_handles_found"] = all_handles
    output["addresses_found"]      = list(set(all_addresses))

    # WHOIS + DNS on unique domains
    domains = _extract_domains(urls_to_scrape)
    print(f"[Stage 10] WHOIS + DNS for {len(domains)} domains...")
    for domain in domains[:20]:  # cap at 20 domains
        print(f"  {domain}...")
        output["whois_results"][domain] = whois_lookup(domain)
        output["dns_results"][domain]   = dns_intel(domain)
        time.sleep(0.3)  # light rate limiting

    # Google dorks (optional)
    social = results.get("social", {})
    username = social.get("username", "")
    emails_known = output["all_emails"] + social.get("emails_checked", [])

    if run_google_dorks:
        print(f"[Stage 10] Running Google dorks...")
        dork_queries: list[str] = []
        if username:
            dork_queries.append(f'site:pastebin.com "{username}"')
            dork_queries.append(f'"{username}" -site:twitter.com -site:instagram.com')
        for em in emails_known[:2]:
            dork_queries.append(f'"{em}"')

        dork_results: list[dict] = []
        for q in dork_queries[:4]:  # max 4 dork queries (rate limiting)
            dork_results.extend(google_dork(q, num_results=5, sleep_s=3.0))
        output["google_dork_results"] = dork_results

    # Detect cross-confirmed emails (scraped page contains email from Stage 9)
    stage9_emails = set(social.get("emails_checked", []))
    stage9_github_emails = set(
        social.get("github", {}).get("emails_found", [])
    )
    all_known_emails = stage9_emails | stage9_github_emails
    confirmed_on_web = [e for e in output["all_emails"] if e in all_known_emails]

    # Site ownership proofs from DNS TXT
    verified_domains: list[str] = []
    for domain, dns in output["dns_results"].items():
        if dns.get("site_ownership_proofs"):
            verified_domains.append(domain)
    output["owner_verified_domains"] = verified_domains

    # Build flags
    if confirmed_on_web:
        output["flags"].append(
            f"📧 Email cross-confirmed on web: {', '.join(confirmed_on_web)}"
        )
    if output["all_emails"]:
        new_emails = [e for e in output["all_emails"] if e not in all_known_emails]
        if new_emails:
            output["flags"].append(
                f"📬 {len(new_emails)} new email(s) found on scraped pages"
            )
    if output["all_phones"]:
        output["flags"].append(
            f"📞 {len(output['all_phones'])} phone number(s) found on scraped pages"
        )
    if output["social_handles_found"]:
        total_handles = sum(len(v) for v in output["social_handles_found"].values())
        output["flags"].append(
            f"👤 {total_handles} social handle(s) found across scraped pages"
        )
    for domain, w in output["whois_results"].items():
        if w.get("age_days") is not None and w["age_days"] < 365:
            output["flags"].append(
                f"🆕 Domain '{domain}' registered <1 year ago "
                f"({w['age_days']} days) — possible fake identity"
            )
        if not w.get("privacy_protected") and w.get("registrant_email"):
            output["flags"].append(
                f"✉️  WHOIS registrant email for '{domain}': {w['registrant_email']}"
            )
        if w.get("privacy_protected"):
            output["flags"].append(
                f"🔒 '{domain}' WHOIS privacy protection enabled"
            )
    for domain, dns in output["dns_results"].items():
        if dns.get("site_ownership_proofs"):
            output["flags"].append(
                f"✅ '{domain}' site ownership verified "
                f"(Google/Facebook/GitHub TXT record)"
            )
        if dns.get("email_provider") in ("ProtonMail", "Tutanota"):
            output["flags"].append(
                f"🔒 '{domain}' uses privacy email provider "
                f"({dns['email_provider']})"
            )
        if dns.get("is_vpn_or_proxy"):
            output["flags"].append(
                f"🕵️  '{domain}' resolves to VPN/proxy infrastructure"
            )
    if output["addresses_found"]:
        output["flags"].append(
            f"🏠 Physical address(es) found: {output['addresses_found'][0]}"
        )

    return output


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python stage10_webscrape.py <url>")
        print("       python stage10_webscrape.py --whois <domain>")
        print("       python stage10_webscrape.py --dns <domain>")
        sys.exit(1)

    mode = sys.argv[1]
    if mode == "--whois":
        domain = sys.argv[2] if len(sys.argv) > 2 else input("Domain: ").strip()
        result = whois_lookup(domain)
        print(json.dumps(result, indent=2, default=str))
    elif mode == "--dns":
        domain = sys.argv[2] if len(sys.argv) > 2 else input("Domain: ").strip()
        result = dns_intel(domain)
        print(json.dumps(result, indent=2, default=str))
    else:
        url = mode
        result = scrape_url(url)
        print(f"Title:   {result['title']}")
        print(f"Author:  {result['author']}")
        print(f"Date:    {result['publish_date']}")
        print(f"Text:    {(result['text'] or '')[:500]}...")
        contact = extract_contact_info(result.get("text") or "")
        print(f"\nEmails:  {contact['emails']}")
        print(f"Phones:  {contact['phones']}")
        print(f"Handles: {contact['social_handles']}")
