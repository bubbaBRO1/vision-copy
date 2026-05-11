"""
Stage 11 — IP & Domain Intelligence
=====================================
Deep intelligence on domains and IPs discovered by earlier stages.

Data sources (all free-tier or no key):
  - crt.sh          — Certificate Transparency: all subdomains ever issued
  - Wayback Machine — Historical snapshots: first/last seen, snapshot count
  - ipinfo.io       — IP geolocation + ASN + org (no key for basic)
  - ip-api.com      — IP → city/ISP/lat-lon (no key, 45 req/min)
  - AbuseIPDB       — IP abuse confidence score (free key, 1000/day)
  - Shodan          — Open ports, services, OS, known CVEs (free key, 100/month)
  - VirusTotal      — URL/domain/IP/hash reputation (free key, 500/day)
  - Hunter.io       — Domain email finder (free key, 25 searches/month)
  - URLScan.io      — URL screenshot + tech stack (free key, 5000/month)

API keys: set in environment or .env file:
  SHODAN_API_KEY, VIRUSTOTAL_API_KEY, ABUSEIPDB_API_KEY,
  HUNTER_API_KEY, URLSCAN_API_KEY

Usage:
    from stages.stage11_domain_intel import domain_intel_all
    all_results["domain_intel"] = domain_intel_all(all_results)
"""

import os
import re
import time
import json
import socket
import hashlib
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

HEADERS = {
    "User-Agent": "ImageTrace-OSINT/2.0",
    "Accept":     "application/json",
}


# ── Certificate Transparency (crt.sh) ────────────────────────────────────────

def crt_sh_lookup(domain: str) -> dict:
    """
    Certificate Transparency logs via crt.sh — free, no key.
    Returns all subdomains ever issued a TLS cert for this domain.
    """
    result = {
        "subdomains":         [],
        "cert_count":         0,
        "earliest_cert_date": None,
        "latest_cert_date":   None,
        "wildcard_cert":      False,
        "flags":              [],
        "error":              None,
    }

    # Strip scheme / path
    domain = re.sub(r"^https?://", "", domain).split("/")[0].split(":")[0]
    if not domain:
        result["error"] = "Invalid domain"
        return result

    try:
        resp = requests.get(
            "https://crt.sh/",
            params={"q": f"%.{domain}", "output": "json"},
            headers=HEADERS,
            timeout=20,
        )
        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}"
            return result

        data = resp.json()
        result["cert_count"] = len(data)

        subdomains: set[str] = set()
        dates: list[str] = []

        for entry in data:
            names = entry.get("name_value", "")
            for name in names.split("\n"):
                name = name.strip().lower()
                if name and not name.startswith("*"):
                    subdomains.add(name)
                elif name.startswith("*"):
                    result["wildcard_cert"] = True

            date = entry.get("not_before", "")
            if date:
                dates.append(date[:10])

        result["subdomains"] = sorted(subdomains)[:50]  # cap output

        if dates:
            dates.sort()
            result["earliest_cert_date"] = dates[0]
            result["latest_cert_date"]   = dates[-1]

        if result["wildcard_cert"]:
            result["flags"].append("🌐 Wildcard certificate — large org or CDN")
        if len(subdomains) > 20:
            result["flags"].append(
                f"🏢 Large digital footprint: {len(subdomains)} subdomains found"
            )

    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── Wayback Machine ───────────────────────────────────────────────────────────

def wayback_lookup(url: str) -> dict:
    """
    Wayback Machine: first/last seen, snapshot count, status history.
    No API key required.
    """
    result = {
        "first_seen":        None,
        "last_seen":         None,
        "snapshot_count":    0,
        "oldest_url":        None,
        "is_archived":       False,
        "status_history":    [],
        "flags":             [],
        "error":             None,
    }

    try:
        # Availability API
        avail_resp = requests.get(
            "https://archive.org/wayback/available",
            params={"url": url},
            headers=HEADERS,
            timeout=10,
        )
        avail_data = avail_resp.json()
        closest = avail_data.get("archived_snapshots", {}).get("closest", {})
        if closest.get("available"):
            result["is_archived"]  = True
            result["oldest_url"]   = closest.get("url")
            result["last_seen"]    = closest.get("timestamp", "")[:8]  # YYYYMMDD

        # CDX API for full history
        time.sleep(0.5)
        cdx_resp = requests.get(
            "http://web.archive.org/cdx/search/cdx",
            params={
                "url":    url,
                "output": "json",
                "limit":  50,
                "fl":     "timestamp,statuscode",
            },
            headers=HEADERS,
            timeout=15,
        )
        cdx_data = cdx_resp.json()
        if cdx_data and len(cdx_data) > 1:
            rows = cdx_data[1:]  # skip header
            result["snapshot_count"] = len(rows)
            timestamps = [r[0] for r in rows if r[0]]
            if timestamps:
                result["first_seen"] = timestamps[0][:8]
                result["last_seen"]  = timestamps[-1][:8]
            # Status history
            statuses = [r[1] for r in rows if len(r) > 1]
            from collections import Counter
            result["status_history"] = [
                f"HTTP {code}: {cnt} snapshots"
                for code, cnt in Counter(statuses).most_common(5)
            ]

        if result["snapshot_count"] > 100:
            result["flags"].append(
                f"📚 High archive activity: {result['snapshot_count']} snapshots"
            )
        if result["first_seen"]:
            year = result["first_seen"][:4]
            result["flags"].append(f"📅 Domain first archived: {year}")

    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── ipinfo.io — IP geolocation + ASN ─────────────────────────────────────────

def ipinfo_lookup(ip: str) -> dict:
    """
    ipinfo.io: free (50k/month), no key for basic.
    Returns city, region, country, org (ASN+name), hostname, timezone.
    """
    result = {
        "ip":        ip,
        "city":      None,
        "region":    None,
        "country":   None,
        "org":       None,
        "asn":       None,
        "isp":       None,
        "hostname":  None,
        "timezone":  None,
        "lat":       None,
        "lon":       None,
        "is_vpn_or_hosting": False,
        "error":     None,
    }

    _VPN_ORGS = {
        "mullvad", "nordvpn", "expressvpn", "protonvpn", "privateinternetaccess",
        "torguard", "surfshark", "ipvanish", "cyberghost", "hidemyass",
    }
    _HOSTING_ORGS = {
        "amazon", "amazonaws", "google", "microsoft", "cloudflare",
        "digitalocean", "linode", "vultr", "hetzner", "ovh",
        "hosting", "datacenter", "server", "vps",
    }

    try:
        resp = requests.get(
            f"https://ipinfo.io/{ip}/json",
            headers={**HEADERS, "Accept": "application/json"},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            result["city"]     = data.get("city")
            result["region"]   = data.get("region")
            result["country"]  = data.get("country")
            result["org"]      = data.get("org")  # "AS12345 ISP Name"
            result["hostname"] = data.get("hostname")
            result["timezone"] = data.get("timezone")

            loc = data.get("loc", "")
            if "," in loc:
                parts = loc.split(",")
                result["lat"] = float(parts[0])
                result["lon"] = float(parts[1])

            org_lower = (result["org"] or "").lower()
            # ASN
            asn_match = re.search(r"AS(\d+)", result["org"] or "")
            if asn_match:
                result["asn"] = f"AS{asn_match.group(1)}"
            isp_part = re.sub(r"^AS\d+\s*", "", result["org"] or "").strip()
            result["isp"] = isp_part if isp_part else None

            result["is_vpn_or_hosting"] = any(
                k in org_lower for k in _VPN_ORGS | _HOSTING_ORGS
            )
        else:
            result["error"] = f"HTTP {resp.status_code}"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── ip-api.com — free, no key ─────────────────────────────────────────────────

def ip_api_lookup(ip: str) -> dict:
    """
    ip-api.com: completely free, no API key, 45 req/min.
    Returns city, ISP, lat/lon, org, mobile flag, proxy flag.
    """
    result = {
        "ip":       ip,
        "city":     None,
        "country":  None,
        "isp":      None,
        "org":      None,
        "lat":      None,
        "lon":      None,
        "mobile":   None,
        "proxy":    None,
        "hosting":  None,
        "error":    None,
    }
    try:
        resp = requests.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,message,country,city,isp,org,"
                              "lat,lon,mobile,proxy,hosting"},
            headers={"User-Agent": "ImageTrace-OSINT"},
            timeout=8,
        )
        data = resp.json()
        if data.get("status") == "success":
            result["city"]    = data.get("city")
            result["country"] = data.get("country")
            result["isp"]     = data.get("isp")
            result["org"]     = data.get("org")
            result["lat"]     = data.get("lat")
            result["lon"]     = data.get("lon")
            result["mobile"]  = data.get("mobile")
            result["proxy"]   = data.get("proxy")
            result["hosting"] = data.get("hosting")
        else:
            result["error"] = data.get("message", "Unknown error")
    except Exception as e:
        result["error"] = str(e)[:80]
    return result


# ── AbuseIPDB ─────────────────────────────────────────────────────────────────

def abuseipdb_check(ip: str, api_key: str = "") -> dict:
    """
    AbuseIPDB: IP abuse confidence score (free: 1000/day, key required).
    Free signup: https://www.abuseipdb.com/register
    """
    result = {
        "abuse_confidence_score": None,
        "total_reports":          None,
        "last_reported":          None,
        "country":                None,
        "isp":                    None,
        "usage_type":             None,
        "is_tor":                 False,
        "is_whitelisted":         False,
        "flags":                  [],
        "error":                  None,
    }

    api_key = api_key or os.environ.get("ABUSEIPDB_API_KEY", "")
    if not api_key:
        result["error"] = "No ABUSEIPDB_API_KEY — skipped"
        return result

    try:
        resp = requests.get(
            "https://api.abuseipdb.com/api/v2/check",
            params={"ipAddress": ip, "maxAgeInDays": 90},
            headers={**HEADERS, "Key": api_key},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            result["abuse_confidence_score"] = data.get("abuseConfidenceScore")
            result["total_reports"]           = data.get("totalReports")
            result["last_reported"]           = data.get("lastReportedAt")
            result["country"]                 = data.get("countryCode")
            result["isp"]                     = data.get("isp")
            result["usage_type"]              = data.get("usageType")
            result["is_tor"]                  = data.get("isTor", False)
            result["is_whitelisted"]          = data.get("isWhitelisted", False)

            score = result["abuse_confidence_score"] or 0
            if score > 75:
                result["flags"].append(
                    f"🔴 High abuse confidence ({score}%) — likely malicious"
                )
            elif score > 25:
                result["flags"].append(
                    f"🟡 Moderate abuse score ({score}%)"
                )
            if result["is_tor"]:
                result["flags"].append("🧅 TOR exit node — anonymity tool")
            if result["usage_type"] in ("VPN", "Hosting/Data Center"):
                result["flags"].append(
                    f"🔒 Usage type: {result['usage_type']}"
                )
        else:
            result["error"] = f"HTTP {resp.status_code}"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── Shodan ────────────────────────────────────────────────────────────────────

def shodan_host(ip: str, api_key: str = "") -> dict:
    """
    Shodan host intel (free: 100 queries/month, no scanning).
    Free API key: https://shodan.io
    """
    result = {
        "open_ports":   [],
        "services":     [],
        "os":           None,
        "isp":          None,
        "org":          None,
        "country":      None,
        "hostnames":    [],
        "vulns":        [],
        "last_update":  None,
        "flags":        [],
        "error":        None,
    }

    api_key = api_key or os.environ.get("SHODAN_API_KEY", "")
    if not api_key:
        result["error"] = "No SHODAN_API_KEY — skipped"
        return result

    try:
        resp = requests.get(
            f"https://api.shodan.io/shodan/host/{ip}",
            params={"key": api_key},
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            result["open_ports"]  = data.get("ports", [])
            result["os"]          = data.get("os")
            result["isp"]         = data.get("isp")
            result["org"]         = data.get("org")
            result["country"]     = data.get("country_name")
            result["hostnames"]   = data.get("hostnames", [])[:5]
            result["last_update"] = data.get("last_update", "")[:10]
            result["vulns"]       = list(data.get("vulns", {}).keys())[:10]

            # Services
            for item in data.get("data", [])[:10]:
                svc = {
                    "port":    item.get("port"),
                    "product": item.get("product"),
                    "version": item.get("version"),
                    "banner":  (item.get("data") or "")[:100],
                }
                result["services"].append(svc)

            # Flags
            if 22 in result["open_ports"]:
                result["flags"].append("🔑 Port 22 (SSH) open")
            if 3389 in result["open_ports"]:
                result["flags"].append("🖥️  Port 3389 (RDP) open — remote desktop exposed")
            if 5900 in result["open_ports"] or 5901 in result["open_ports"]:
                result["flags"].append("🖥️  VNC port open — remote desktop exposed")
            if result["vulns"]:
                result["flags"].append(
                    f"⚠️  Known CVE(s): {', '.join(result['vulns'][:3])}"
                )
            if result["os"]:
                result["flags"].append(f"💻 OS: {result['os']}")
        elif resp.status_code == 404:
            result["error"] = "Host not found in Shodan"
        else:
            result["error"] = f"HTTP {resp.status_code}"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── VirusTotal ────────────────────────────────────────────────────────────────

def virustotal_check(ioc: str, ioc_type: str = "domain",
                     api_key: str = "") -> dict:
    """
    VirusTotal reputation check (free: 500/day, 4/min).
    ioc_type: "domain" | "ip_address" | "url" | "file" (hash)
    Free API key: https://virustotal.com
    """
    result = {
        "malicious_count":   0,
        "suspicious_count":  0,
        "harmless_count":    0,
        "total_engines":     0,
        "reputation_score":  None,
        "categories":        [],
        "tags":              [],
        "last_analysis_date": None,
        "verdict":           "Unknown",
        "flags":             [],
        "error":             None,
    }

    api_key = api_key or os.environ.get("VIRUSTOTAL_API_KEY", "")
    if not api_key:
        result["error"] = "No VIRUSTOTAL_API_KEY — skipped"
        return result

    try:
        import urllib.parse
        if ioc_type == "url":
            encoded = urllib.parse.b64encode(ioc.encode()).decode().rstrip("=")
            endpoint = f"https://www.virustotal.com/api/v3/urls/{encoded}"
        elif ioc_type == "ip_address":
            endpoint = f"https://www.virustotal.com/api/v3/ip_addresses/{ioc}"
        elif ioc_type == "file":
            endpoint = f"https://www.virustotal.com/api/v3/files/{ioc}"
        else:  # domain
            endpoint = f"https://www.virustotal.com/api/v3/domains/{ioc}"

        resp = requests.get(
            endpoint,
            headers={**HEADERS, "x-apikey": api_key},
            timeout=15,
        )
        if resp.status_code == 200:
            attrs = resp.json().get("data", {}).get("attributes", {})
            stats = attrs.get("last_analysis_stats", {})
            result["malicious_count"]   = stats.get("malicious", 0)
            result["suspicious_count"]  = stats.get("suspicious", 0)
            result["harmless_count"]    = stats.get("harmless", 0)
            result["total_engines"]     = sum(stats.values())
            result["reputation_score"]  = attrs.get("reputation")
            result["categories"]        = list(
                attrs.get("categories", {}).values()
            )[:5]
            result["tags"]              = attrs.get("tags", [])[:10]
            result["last_analysis_date"] = attrs.get("last_analysis_date")

            m = result["malicious_count"]
            if m > 5:
                result["verdict"] = f"🔴 Malicious ({m} engines)"
                result["flags"].append(
                    f"🦠 Flagged malicious by {m}/{result['total_engines']} AV engines"
                )
            elif m > 1:
                result["verdict"] = f"🟡 Suspicious ({m} engines)"
                result["flags"].append(
                    f"⚠️  Flagged by {m} AV engines"
                )
            else:
                result["verdict"] = "✅ Clean"
        elif resp.status_code == 404:
            result["verdict"] = "Not found in VirusTotal"
        else:
            result["error"] = f"HTTP {resp.status_code}"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── Hunter.io ─────────────────────────────────────────────────────────────────

def hunter_domain_search(domain: str, api_key: str = "") -> dict:
    """
    Hunter.io domain email finder (free: 25 searches/month).
    Free API key: https://hunter.io/users/sign_up
    """
    result = {
        "emails":         [],
        "organization":   None,
        "email_pattern":  None,
        "employee_count": None,
        "twitter":        None,
        "linkedin":       None,
        "error":          None,
    }

    api_key = api_key or os.environ.get("HUNTER_API_KEY", "")
    if not api_key:
        result["error"] = "No HUNTER_API_KEY — skipped"
        return result

    domain = re.sub(r"^https?://", "", domain).split("/")[0]
    try:
        resp = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": api_key, "limit": 10},
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            result["organization"]   = data.get("organization")
            result["email_pattern"]  = data.get("pattern")
            result["employee_count"] = data.get("employee_count")
            result["twitter"]        = data.get("twitter")
            result["linkedin"]       = data.get("linkedin")
            result["emails"] = [
                {
                    "email":      e.get("value"),
                    "type":       e.get("type"),
                    "confidence": e.get("confidence"),
                    "first_name": e.get("first_name"),
                    "last_name":  e.get("last_name"),
                    "position":   e.get("position"),
                }
                for e in data.get("emails", [])
            ]
        else:
            result["error"] = f"HTTP {resp.status_code}"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── URLScan.io ────────────────────────────────────────────────────────────────

def urlscan_submit(url: str, api_key: str = "", max_wait: int = 30) -> dict:
    """
    URLScan.io: URL screenshot + DOM + technology stack (free: 5000/month).
    Free API key: https://urlscan.io/user/signup
    """
    result = {
        "screenshot_url":  None,
        "dom_url":         None,
        "technologies":    [],
        "ips":             [],
        "page_title":      None,
        "effective_url":   None,
        "asn":             None,
        "country":         None,
        "malicious_score": None,
        "scan_id":         None,
        "result_url":      None,
        "error":           None,
    }

    api_key = api_key or os.environ.get("URLSCAN_API_KEY", "")
    if not api_key:
        result["error"] = "No URLSCAN_API_KEY — skipped"
        return result

    try:
        # Submit scan
        submit_resp = requests.post(
            "https://urlscan.io/api/v1/scan/",
            headers={**HEADERS, "API-Key": api_key, "Content-Type": "application/json"},
            json={"url": url, "visibility": "private"},
            timeout=10,
        )
        if submit_resp.status_code not in (200, 201):
            result["error"] = f"Submit HTTP {submit_resp.status_code}"
            return result

        scan_id = submit_resp.json().get("uuid")
        result["scan_id"]    = scan_id
        result["result_url"] = f"https://urlscan.io/result/{scan_id}/"

        # Poll for result
        for _ in range(max_wait // 5):
            time.sleep(5)
            res_resp = requests.get(
                f"https://urlscan.io/api/v1/result/{scan_id}/",
                headers={**HEADERS, "API-Key": api_key},
                timeout=10,
            )
            if res_resp.status_code == 200:
                data = res_resp.json()
                page = data.get("page", {})
                result["page_title"]    = page.get("title")
                result["effective_url"] = page.get("url")
                result["asn"]           = page.get("asn")
                result["country"]       = page.get("country")
                result["screenshot_url"] = (
                    f"https://urlscan.io/screenshots/{scan_id}.png"
                )
                result["dom_url"]       = (
                    f"https://urlscan.io/dom/{scan_id}/"
                )
                # Technology stack
                result["technologies"] = [
                    t.get("name") for t in data.get("meta", {}).get("processors", {})
                    .get("wappa", {}).get("data", [])
                    if t.get("name")
                ][:10]
                # IPs
                result["ips"] = list(set(
                    r.get("response", {}).get("remoteIPAddress", "")
                    for r in data.get("data", {}).get("requests", [])
                    if r.get("response", {}).get("remoteIPAddress")
                ))[:5]
                # Verdicts
                verdicts = data.get("verdicts", {}).get("overall", {})
                result["malicious_score"] = verdicts.get("score")
                break
            elif res_resp.status_code == 404:
                pass  # Still processing
            else:
                result["error"] = f"Result HTTP {res_resp.status_code}"
                break

    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── Resolve domain → IPs ──────────────────────────────────────────────────────

def _resolve_ips(domain: str) -> list[str]:
    """Resolve domain to IP addresses."""
    try:
        return list(set(socket.gethostbyname_ex(domain)[2]))
    except Exception:
        return []


# ── Master function ───────────────────────────────────────────────────────────

def domain_intel_all(results: dict,
                     shodan_key: str = "",
                     vt_key: str = "",
                     abuseipdb_key: str = "",
                     hunter_key: str = "",
                     urlscan_key: str = "",
                     run_urlscan: bool = False) -> dict:
    """
    Collect all domains+IPs from previous stages → run full intelligence.

    Sources:
    - Stage 10 web intel: whois_results keys (domains)
    - Stage 9 social: registered_domains
    - Stage 6 reverse search: result domains
    - Metadata: IPTC source/credit URLs

    Parameters
    ----------
    results      : all_results dict
    *_key        : API keys (falls back to env vars)
    run_urlscan  : submit top 3 URLs to URLScan (takes ~30s each)
    """
    output = {
        "stage":      "domain_intel",
        "per_domain": {},
        "per_ip":     {},
        "flags":      [],
        "summary": {
            "domains_analyzed": 0,
            "ips_analyzed":     0,
            "total_subdomains": 0,
            "malicious_found":  False,
            "abuse_ips":        [],
            "hunter_emails":    [],
        },
    }

    # ── Collect domains ───────────────────────────────────────────────────────
    domains: list[str] = []

    # Stage 10 web intel domains
    web_intel = results.get("web_intel", {})
    for d in web_intel.get("whois_results", {}).keys():
        if d not in domains:
            domains.append(d)

    # Stage 9 registered domains
    social = results.get("social", {})
    for entry in social.get("registered_domains", []):
        d = entry.get("domain", "").split(".")[0]  # strip TLD — re-add below
        full = entry.get("domain", "")
        if full and full not in domains:
            domains.append(full)

    # Stage 6 reverse search result domains
    rev = results.get("reverse_search", {})
    for r in rev.get("results", []):
        url = r.get("url", "")
        if url:
            parsed = urlparse(url)
            d = parsed.netloc.replace("www.", "")
            if d and d not in domains:
                domains.append(d)

    # Metadata IPTC/XMP URLs
    meta = results.get("metadata", {})
    for source_key in ("credit", "source"):
        url = meta.get("iptc", {}).get(source_key, "")
        if url and url.startswith("http"):
            d = urlparse(url).netloc.replace("www.", "")
            if d and d not in domains:
                domains.append(d)

    # Limit to top 15 domains
    domains = domains[:15]
    output["summary"]["domains_analyzed"] = len(domains)

    # ── Process each domain ───────────────────────────────────────────────────
    for domain in domains:
        print(f"[Stage 11] Analyzing domain: {domain}")
        domain_data: dict = {}

        # crt.sh (no key, no rate limit beyond courtesy)
        print(f"  crt.sh...")
        domain_data["crt"] = crt_sh_lookup(domain)
        time.sleep(0.5)

        # Wayback
        print(f"  Wayback...")
        domain_data["wayback"] = wayback_lookup(f"https://{domain}")
        time.sleep(0.5)

        # VirusTotal domain check
        print(f"  VirusTotal...")
        domain_data["virustotal"] = virustotal_check(
            domain, ioc_type="domain",
            api_key=vt_key or os.environ.get("VIRUSTOTAL_API_KEY", "")
        )
        time.sleep(0.25)

        # Hunter.io email search
        print(f"  Hunter.io...")
        domain_data["hunter"] = hunter_domain_search(
            domain,
            api_key=hunter_key or os.environ.get("HUNTER_API_KEY", "")
        )

        output["per_domain"][domain] = domain_data

        # Accumulate subdomains count
        output["summary"]["total_subdomains"] += len(
            domain_data["crt"].get("subdomains", [])
        )

        # Hunter emails
        for e in domain_data["hunter"].get("emails", []):
            if e.get("email"):
                output["summary"]["hunter_emails"].append(e["email"])

        # Malicious flag
        if domain_data["virustotal"].get("malicious_count", 0) > 2:
            output["summary"]["malicious_found"] = True

        # Resolve IPs for this domain
        ips = _resolve_ips(domain)
        for ip in ips[:3]:
            if ip not in output["per_ip"]:
                output["per_ip"][ip] = {}
            output["per_ip"][ip].setdefault("domains", []).append(domain)

    # ── Process IPs ───────────────────────────────────────────────────────────
    all_ips = list(output["per_ip"].keys())[:10]
    output["summary"]["ips_analyzed"] = len(all_ips)

    for ip in all_ips:
        print(f"[Stage 11] Analyzing IP: {ip}")
        ip_data = output["per_ip"].get(ip, {})

        # ipinfo (no key)
        ip_data["ipinfo"] = ipinfo_lookup(ip)
        time.sleep(0.1)

        # ip-api (no key, free)
        ip_data["ip_api"] = ip_api_lookup(ip)
        time.sleep(0.1)

        # AbuseIPDB
        ip_data["abuseipdb"] = abuseipdb_check(
            ip,
            api_key=abuseipdb_key or os.environ.get("ABUSEIPDB_API_KEY", "")
        )
        time.sleep(0.1)

        # Shodan
        ip_data["shodan"] = shodan_host(
            ip,
            api_key=shodan_key or os.environ.get("SHODAN_API_KEY", "")
        )
        time.sleep(0.1)

        # VirusTotal IP
        ip_data["virustotal"] = virustotal_check(
            ip, ioc_type="ip_address",
            api_key=vt_key or os.environ.get("VIRUSTOTAL_API_KEY", "")
        )
        time.sleep(0.25)

        output["per_ip"][ip] = ip_data

        # Track abusive IPs
        abuse_score = ip_data["abuseipdb"].get("abuse_confidence_score") or 0
        if abuse_score > 25:
            output["summary"]["abuse_ips"].append(
                {"ip": ip, "score": abuse_score}
            )

    # ── URLScan (optional, slow) ──────────────────────────────────────────────
    if run_urlscan:
        urls_to_scan: list[str] = []
        for r in rev.get("results", [])[:3]:
            u = r.get("url", "")
            if u:
                urls_to_scan.append(u)

        uk = urlscan_key or os.environ.get("URLSCAN_API_KEY", "")
        for url in urls_to_scan[:3]:
            domain = urlparse(url).netloc.replace("www.", "")
            print(f"[Stage 11] URLScan: {url[:60]}...")
            scan = urlscan_submit(url, api_key=uk)
            if domain in output["per_domain"]:
                output["per_domain"][domain]["urlscan"] = scan

    # ── Build flags ───────────────────────────────────────────────────────────
    for domain, data in output["per_domain"].items():
        crt  = data.get("crt",  {})
        way  = data.get("wayback", {})
        vt   = data.get("virustotal", {})
        hunt = data.get("hunter", {})

        if crt.get("subdomains") and len(crt["subdomains"]) > 20:
            output["flags"].append(
                f"🌐 '{domain}': {len(crt['subdomains'])} subdomains in cert logs"
            )
        if way.get("first_seen"):
            output["flags"].append(
                f"📅 '{domain}' first archived: {way['first_seen'][:4]}"
            )
        if vt.get("malicious_count", 0) > 2:
            output["flags"].append(
                f"🦠 '{domain}' flagged malicious by "
                f"{vt['malicious_count']} VT engines"
            )
        if hunt.get("emails"):
            output["flags"].append(
                f"📧 Hunter.io found {len(hunt['emails'])} email(s) for '{domain}'"
            )
        if hunt.get("email_pattern"):
            output["flags"].append(
                f"✉️  Email pattern at '{domain}': {hunt['email_pattern']}"
            )

    for ip, data in output["per_ip"].items():
        abuse = data.get("abuseipdb", {})
        shodan = data.get("shodan", {})
        ipinfo = data.get("ipinfo", {})

        score = abuse.get("abuse_confidence_score") or 0
        if score > 50:
            output["flags"].append(f"🔴 IP {ip} abuse score: {score}%")
        if shodan.get("vulns"):
            output["flags"].append(
                f"⚠️  IP {ip} has known CVEs: {', '.join(shodan['vulns'][:2])}"
            )
        if ipinfo.get("is_vpn_or_hosting"):
            output["flags"].append(
                f"🕵️  IP {ip} resolves to VPN/hosting: {ipinfo.get('org')}"
            )
        if shodan.get("open_ports"):
            risky = [p for p in shodan["open_ports"] if p in (22, 3389, 5900, 23)]
            if risky:
                output["flags"].append(
                    f"🔑 IP {ip} risky ports open: {risky}"
                )

    return output


if __name__ == "__main__":
    import sys
    import json as _json

    if len(sys.argv) < 3:
        print("Usage:")
        print("  python stage11_domain_intel.py crt <domain>")
        print("  python stage11_domain_intel.py wayback <url>")
        print("  python stage11_domain_intel.py ip <ip>")
        print("  python stage11_domain_intel.py vt <domain_or_ip>")
        sys.exit(1)

    cmd = sys.argv[1]
    arg = sys.argv[2]

    if cmd == "crt":
        result = crt_sh_lookup(arg)
    elif cmd == "wayback":
        result = wayback_lookup(arg)
    elif cmd == "ip":
        result = {
            "ipinfo":    ipinfo_lookup(arg),
            "ip_api":    ip_api_lookup(arg),
            "abuseipdb": abuseipdb_check(arg),
            "shodan":    shodan_host(arg),
        }
    elif cmd == "vt":
        result = virustotal_check(arg)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

    print(_json.dumps(result, indent=2, default=str))
