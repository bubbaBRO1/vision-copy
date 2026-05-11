"""
POI Profile Builder
===================
Aggregates all identity signals from across the pipeline into per-person
Person of Interest (POI) dossiers.

Runs after Stage 9 (social). Consumes all_results dict.

Usage:
    from stages.poi_profile import build_poi_profiles
    all_results["poi_profiles"] = build_poi_profiles(all_results)
"""

import re
from typing import Any


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_anchors(results: dict) -> list[dict]:
    """
    Collect all identity anchors (name / username / email / face label)
    from every stage. Each anchor becomes a seed for a POI profile.
    """
    anchors = []

    # Stage 1: EXIF / XMP / IPTC author
    meta = results.get("metadata", {})
    exif_artist = meta.get("gps_info", {})  # may not have artist here
    # Check top-level metadata fields
    for key in ("artist", "copyright", "author"):
        val = str(meta.get(key, "")).strip()
        if val and len(val) > 2:
            anchors.append({"type": "name", "value": val, "source": f"EXIF {key}"})

    xmp = meta.get("xmp", {})
    if xmp.get("creator"):
        anchors.append({"type": "name", "value": xmp["creator"], "source": "XMP creator"})
    if xmp.get("credit"):
        anchors.append({"type": "name", "value": xmp["credit"], "source": "XMP credit"})

    iptc = meta.get("iptc", {})
    if iptc.get("author"):
        anchors.append({"type": "name", "value": iptc["author"], "source": "IPTC author"})

    # Stage 9: username
    social = results.get("social", {})
    if social.get("username"):
        anchors.append({
            "type": "username",
            "value": social["username"],
            "source": "Stage 9 input",
        })

    # Stage 9: GitHub name / email
    github = social.get("github", {})
    if github.get("profile", {}).get("name"):
        anchors.append({
            "type": "name",
            "value": github["profile"]["name"],
            "source": "GitHub profile name",
        })
    for email in github.get("emails_found", []):
        anchors.append({"type": "email", "value": email, "source": "GitHub commit email"})

    # Stage 9: emails checked
    for email in social.get("emails_checked", []):
        anchors.append({"type": "email", "value": email, "source": "Stage 9 email"})

    # Stage 9: Gravatar display name
    gravatar = social.get("gravatar", {})
    if gravatar.get("profile", {}).get("display_name"):
        anchors.append({
            "type": "name",
            "value": gravatar["profile"]["display_name"],
            "source": "Gravatar display name",
        })

    # Stage 7: face search results (named face labels)
    face_search = results.get("face_search", {})
    for match in face_search.get("matches", []):
        label = match.get("label") or match.get("name")
        if label:
            anchors.append({"type": "face", "value": label, "source": "Stage 7 face search"})

    # FaceDB: known faces matched
    facedb = results.get("face_recognition", {})
    for match in facedb.get("matches", []):
        label = match.get("label") or match.get("name")
        if label:
            anchors.append({"type": "face", "value": label, "source": "FaceDB match"})

    # Stage 4: document MRZ (name on passport/ID)
    content = results.get("content_analysis", {})
    doc = content.get("document_type", {})
    for mrz_line in doc.get("mrz_lines", []):
        # Try to extract name from MRZ line 2: surname<<given<names
        # MRZ P type line 2: surname<<given<<< ...
        clean = mrz_line.replace("<", " ").strip()
        if len(clean) > 5:
            anchors.append({"type": "name", "value": clean, "source": "Document MRZ"})

    # Deduplicate anchors by (type, value)
    seen = set()
    unique = []
    for a in anchors:
        key = (a["type"], a["value"].lower().strip())
        if key not in seen:
            seen.add(key)
            unique.append(a)

    return unique


def _collect_locations(results: dict) -> list[dict]:
    """Gather all location signals from the pipeline."""
    locations = []

    geo = results.get("geolocation", {})

    # GPS from EXIF
    meta = results.get("metadata", {})
    gps = meta.get("gps_info", {})
    if gps.get("latitude") and gps.get("longitude"):
        locations.append({
            "source": "EXIF GPS",
            "lat": gps["latitude"],
            "lon": gps["longitude"],
            "description": gps.get("gps_address") or f"{gps['latitude']:.4f}°, {gps['longitude']:.4f}°",
            "confidence": 1.0,
        })

    # GeoSpy AI
    geospy = geo.get("geospy", {})
    if geospy.get("latitude") and geospy.get("longitude"):
        locations.append({
            "source": "GeoSpy AI",
            "lat": geospy["latitude"],
            "lon": geospy["longitude"],
            "description": geospy.get("location") or "GeoSpy estimate",
            "confidence": 0.85,
        })

    # IPTC city/state/country
    iptc = meta.get("iptc", {})
    iptc_loc = ", ".join(
        filter(None, [iptc.get("city"), iptc.get("state"), iptc.get("country")])
    )
    if iptc_loc:
        locations.append({
            "source": "IPTC location",
            "lat": None,
            "lon": None,
            "description": iptc_loc,
            "confidence": 0.7,
        })

    # Deep OCR geocoding
    ocr_geo = geo.get("deep_ocr_geocoding", {})
    if ocr_geo.get("best_country"):
        locations.append({
            "source": "OCR geocoding",
            "lat": None,
            "lon": None,
            "description": ocr_geo["best_country"],
            "confidence": 0.6,
        })

    # Overpass POI (if v2 stage ran)
    overpass = geo.get("overpass_poi", {})
    if overpass.get("city") or overpass.get("street_names"):
        desc = ", ".join(filter(None, [
            overpass.get("city"),
            overpass.get("neighbourhood"),
            overpass.get("country"),
        ]))
        locations.append({
            "source": "Overpass OSM",
            "lat": None,
            "lon": None,
            "description": desc or "OSM POI match",
            "confidence": 0.9,
        })

    # Phone intel region
    social = results.get("social", {})
    phone_intel = social.get("phone_intel", {})
    if phone_intel.get("country"):
        locations.append({
            "source": "Phone number region",
            "lat": None,
            "lon": None,
            "description": phone_intel["country"],
            "confidence": 0.45,
        })

    return locations


def _collect_social_accounts(results: dict) -> list[dict]:
    """All confirmed social platform accounts from Stage 9."""
    social = results.get("social", {})
    accounts = []
    for entry in social.get("found_platforms", []):
        if entry.get("found"):
            accounts.append({
                "platform": entry["platform"],
                "url":      entry["url"],
                "category": entry.get("category", ""),
                "source":   entry.get("source", "direct"),
            })
    # Add holehe results
    holehe = social.get("holehe", {})
    for site in holehe.get("sites_found", []):
        accounts.append({
            "platform": site,
            "url":      "",
            "category": "email-verified",
            "source":   "holehe",
        })
    return accounts


def _collect_online_appearances(results: dict) -> list[dict]:
    """URLs where this person/image appears online (Stage 6 + Stage 7)."""
    appearances = []

    rev = results.get("reverse_search", {})
    for r in rev.get("results", []):
        appearances.append({
            "url":    r.get("url", ""),
            "engine": r.get("engine", ""),
            "title":  r.get("title", ""),
        })

    face_search = results.get("face_search", {})
    for m in face_search.get("matches", []):
        appearances.append({
            "url":    m.get("url", ""),
            "engine": "face_search",
            "title":  m.get("title") or m.get("label", ""),
        })

    return appearances


def _collect_face_crops(results: dict) -> list[str]:
    """Base64 face crop images from Stage 4 content analysis."""
    content = results.get("content_analysis", {})
    crops = []
    for face in content.get("faces", []):
        if face.get("crop_b64"):
            crops.append(face["crop_b64"])
    return crops


def _risk_score(profile: dict) -> int:
    """Compute risk/exposure score 0-100 for a POI profile."""
    score = 0

    # Digital footprint
    n_platforms = len(profile.get("social_accounts", []))
    if n_platforms > 50:
        score += 35
    elif n_platforms > 20:
        score += 25
    elif n_platforms > 10:
        score += 15
    elif n_platforms > 0:
        score += 8

    # HIBP breaches
    social = profile.get("_raw_social", {})
    breach_count = sum(
        len(v.get("breaches", []))
        for v in social.get("breach_data", {}).values()
    )
    score += min(30, breach_count * 8)

    # GPS location found
    has_gps = any(
        loc["source"] == "EXIF GPS"
        for loc in profile.get("locations", [])
    )
    if has_gps:
        score += 20

    # Face found online
    if profile.get("online_appearances"):
        score += 15

    # Registered domains
    if profile.get("domains"):
        score += 10

    # GitHub email exposed
    has_github_email = bool(social.get("github", {}).get("emails_found"))
    if has_github_email:
        score += 12

    # Phone number known
    if profile.get("phones"):
        score += 8

    return min(100, score)


def _profile_summary(profile: dict) -> str:
    """One-line human-readable summary of a POI profile."""
    parts = []

    if profile.get("names"):
        parts.append(profile["names"][0])
    elif profile.get("usernames"):
        parts.append(f"@{profile['usernames'][0]}")
    elif profile.get("emails"):
        parts.append(profile["emails"][0])

    n = len(profile.get("social_accounts", []))
    if n > 0:
        parts.append(f"active on {n} platforms")

    locs = [l for l in profile.get("locations", []) if l.get("description")]
    if locs:
        best = max(locs, key=lambda x: x["confidence"])
        parts.append(f"location: {best['description']}")

    breach_count = sum(
        len(v.get("breaches", []))
        for v in profile.get("_raw_social", {}).get("breach_data", {}).values()
    )
    if breach_count:
        parts.append(f"{breach_count} HIBP breach(es)")

    if profile.get("domains"):
        parts.append(f"owns {len(profile['domains'])} domain(s)")

    return " — ".join(parts) if parts else "No identity signals found"


def _merge_profiles(profiles: list[dict]) -> list[dict]:
    """
    Deduplicate profiles that share usernames, emails, or names.
    Merge their signals into a single unified profile.
    """
    if not profiles:
        return profiles

    merged: list[dict] = []

    def _overlaps(a: dict, b: dict) -> bool:
        # Share any username
        if set(a.get("usernames", [])) & set(b.get("usernames", [])):
            return True
        # Share any email
        if set(a.get("emails", [])) & set(b.get("emails", [])):
            return True
        # Share any name (case-insensitive)
        names_a = {n.lower() for n in a.get("names", [])}
        names_b = {n.lower() for n in b.get("names", [])}
        if names_a & names_b:
            return True
        return False

    def _merge_two(a: dict, b: dict) -> dict:
        """Merge profile b into profile a."""
        for key in ("names", "usernames", "emails", "phones", "domains",
                    "social_accounts", "online_appearances", "face_crops_b64",
                    "locations", "flags"):
            combined = a.get(key, []) + b.get(key, [])
            # Deduplicate
            seen_vals: set = set()
            unique_vals = []
            for item in combined:
                key_val = str(item).lower() if isinstance(item, str) else str(item)
                if key_val not in seen_vals:
                    seen_vals.add(key_val)
                    unique_vals.append(item)
            a[key] = unique_vals
        # Merge anchor info
        a["anchor_sources"] = list(
            set(a.get("anchor_sources", [a.get("anchor")]) +
                b.get("anchor_sources", [b.get("anchor")]))
        )
        # Take max risk
        a["risk_score"] = max(a.get("risk_score", 0), b.get("risk_score", 0))
        return a

    for profile in profiles:
        matched_idx = None
        for i, existing in enumerate(merged):
            if _overlaps(existing, profile):
                matched_idx = i
                break
        if matched_idx is not None:
            merged[matched_idx] = _merge_two(merged[matched_idx], profile)
        else:
            merged.append(dict(profile))

    # Re-number IDs
    for i, p in enumerate(merged):
        p["id"] = i + 1

    return merged


# ── Main builder ──────────────────────────────────────────────────────────────

def build_poi_profiles(results: dict) -> dict:
    """
    Aggregate all identity signals per individual into POI dossiers.

    Parameters
    ----------
    results : dict
        all_results dict from imagetrace.py (output of all previous stages).

    Returns
    -------
    {
        "stage": "poi_profiles",
        "profiles": [...],
        "total_profiles": int,
        "highest_risk": int,
    }
    """
    anchors = _extract_anchors(results)

    if not anchors:
        return {
            "stage": "poi_profiles",
            "profiles": [],
            "total_profiles": 0,
            "highest_risk": 0,
            "flags": ["⚠️  No identity anchors found in image pipeline"],
        }

    # Build one raw profile per anchor (will merge duplicates later)
    social    = results.get("social", {})
    content   = results.get("content_analysis", {})
    all_locs  = _collect_locations(results)
    all_social_accs = _collect_social_accounts(results)
    all_appearances = _collect_online_appearances(results)
    all_crops       = _collect_face_crops(results)

    profiles: list[dict] = []

    for anchor in anchors:
        anchor_val  = anchor["value"]
        anchor_type = anchor["type"]

        # Collect names / usernames / emails relevant to this anchor
        names:     list[str] = []
        usernames: list[str] = []
        emails:    list[str] = []
        phones:    list[str] = []

        if anchor_type == "name":
            names.append(anchor_val)
        elif anchor_type == "username":
            usernames.append(anchor_val)
        elif anchor_type == "email":
            emails.append(anchor_val)
            # Try to derive username from email local part
            local = anchor_val.split("@")[0]
            if local and local not in usernames:
                usernames.append(local)

        # Pull all emails from GitHub + breach data
        for em in social.get("emails_checked", []):
            if em and em not in emails:
                emails.append(em)
        for em in social.get("github", {}).get("emails_found", []):
            if em and em not in emails:
                emails.append(em)

        # Phone
        if social.get("phone_intel", {}).get("international_format"):
            phones.append(social["phone_intel"]["international_format"])

        # Username from social search
        if social.get("username") and social["username"] not in usernames:
            usernames.append(social["username"])

        # GitHub name
        gh_name = social.get("github", {}).get("profile", {}).get("name")
        if gh_name and gh_name not in names:
            names.append(gh_name)

        # Domains
        domains = [d["domain"] for d in social.get("registered_domains", [])]

        # GitHub profile link
        gh_profile: dict = {}
        if social.get("github", {}).get("exists"):
            gh = social["github"]
            gh_profile = {
                "username":   gh.get("profile", {}).get("login") or social.get("username"),
                "name":       gh.get("profile", {}).get("name"),
                "bio":        gh.get("profile", {}).get("bio"),
                "company":    gh.get("profile", {}).get("company"),
                "location":   gh.get("profile", {}).get("location"),
                "email":      gh.get("profile", {}).get("email"),
                "twitter":    gh.get("profile", {}).get("twitter"),
                "followers":  gh.get("profile", {}).get("followers"),
                "repos":      [r.get("name") for r in gh.get("repos", [])[:5]],
                "url": f"https://github.com/{social.get('username', '')}",
            }

        # Breaches
        breaches: list[dict] = []
        for em, hibp in social.get("breach_data", {}).items():
            for breach in hibp.get("breaches", []):
                breach_entry = dict(breach)
                breach_entry["email"] = em
                breaches.append(breach_entry)

        # Flags
        flags: list[str] = []
        if len(all_social_accs) > 50:
            flags.append(f"🔴 Extreme digital footprint: {len(all_social_accs)} platforms")
        elif len(all_social_accs) > 20:
            flags.append(f"🟠 High digital footprint: {len(all_social_accs)} platforms")
        if breaches:
            flags.append(f"🚨 {len(breaches)} HIBP breach(es) found")
        if any(l["source"] == "EXIF GPS" for l in all_locs):
            flags.append("📍 Precise GPS location embedded in image")
        if all_appearances:
            flags.append(f"🌐 Image/face found online ({len(all_appearances)} appearances)")
        if domains:
            flags.append(f"🔗 Registered domain(s): {', '.join(domains)}")
        if emails:
            flags.append(f"📧 {len(emails)} email address(es) identified")
        if social.get("gravatar", {}).get("has_gravatar"):
            flags.append("🖼️  Gravatar profile found")
        if social.get("holehe", {}).get("sites_count", 0) > 0:
            n = social["holehe"]["sites_count"]
            flags.append(f"📨 Email active on {n} site(s) (holehe)")

        profile = {
            "id":               len(profiles) + 1,
            "anchor":           f"{anchor_type.title()}: {anchor_val}",
            "anchor_type":      anchor_type,
            "anchor_source":    anchor["source"],
            "anchor_sources":   [anchor["source"]],
            "names":            names,
            "usernames":        usernames,
            "emails":           emails,
            "phones":           phones,
            "domains":          domains,
            "locations":        all_locs,
            "social_accounts":  all_social_accs,
            "online_appearances": all_appearances,
            "face_crops_b64":   all_crops,
            "github":           gh_profile,
            "breaches":         breaches,
            "flags":            flags,
            "risk_score":       0,  # computed below
            "summary":          "",
            # Internal: raw social for risk scoring
            "_raw_social":      social,
        }

        profile["risk_score"] = _risk_score(profile)
        profile["summary"]    = _profile_summary(profile)

        profiles.append(profile)

    # Merge duplicate profiles
    profiles = _merge_profiles(profiles)

    # Remove internal _raw_social key from output
    for p in profiles:
        p.pop("_raw_social", None)

    highest_risk = max((p["risk_score"] for p in profiles), default=0)

    return {
        "stage":          "poi_profiles",
        "profiles":       profiles,
        "total_profiles": len(profiles),
        "highest_risk":   highest_risk,
        "anchor_count":   len(anchors),
    }
