"""
Dashboard — PimEyes-Style HTML Intelligence Report
===================================================
Generates a full self-contained HTML file with:
  - Live Intel Score gauge
  - Image preview + ELA overlay side-by-side
  - Face crops with similarity scores (PimEyes-style grid)
  - Interactive tabs per stage
  - Color-coded verdict badges
  - Clickable source URLs
  - Platform presence heatmap (Stage 9)
  - Geolocation map embed
  - Exportable to PDF via browser print
"""

import os
import json
import base64
import datetime
from pathlib import Path
from typing import Optional


# ── Embed image as base64 ─────────────────────────────────────────────────────

def _img_b64(path: str, max_dim: int = 600) -> str:
    try:
        from PIL import Image
        import io
        img = Image.open(path)
        img.thumbnail((max_dim, max_dim))
        buf = io.BytesIO()
        fmt = img.format or "JPEG"
        img.save(buf, format=fmt)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def _mime(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif",
            "webp": "webp", "bmp": "bmp"}.get(ext.lstrip("."), "jpeg")


# ── Score color ────────────────────────────────────────────────────────────────

def _score_color(score: int) -> str:
    if score >= 70: return "#ef4444"
    if score >= 40: return "#f59e0b"
    return "#22c55e"


def _verdict_badge(verdict: str) -> str:
    v = verdict or ""
    if any(x in v for x in ["🚨", "HIGH", "SUSPICIOUS", "Manipulated", "LIKELY"]):
        cls = "badge-red"
    elif any(x in v for x in ["⚠️", "POSSIBLE", "Possibly", "Moderate"]):
        cls = "badge-yellow"
    elif any(x in v for x in ["✅", "Clean", "Authentic", "No "]):
        cls = "badge-green"
    else:
        cls = "badge-gray"
    clean = v.replace("🚨","").replace("⚠️","").replace("✅","").replace("🟡","").replace("🔴","").strip()
    return f'<span class="badge {cls}">{clean[:60]}</span>'


# ── Main HTML builder ──────────────────────────────────────────────────────────

def _build_timeline_section(results: dict) -> str:
    """Collect all dates from all stages, render chronological timeline."""
    events = []
    meta = results.get("metadata", {})
    exif = meta.get("exif", {})
    ts_scan = results.get("_meta", {}).get("scan_ts", "")

    def _add(label: str, dt_str: str, color: str = "#38bdf8"):
        if dt_str and dt_str != "—" and dt_str != "None":
            events.append({"label": label, "dt": str(dt_str), "color": color})

    _add("📷 Date Taken (EXIF)",     exif.get("datetime_original", ""), "#22c55e")
    _add("🖥️  Date Digitized",        exif.get("datetime_digitized", ""), "#38bdf8")
    _add("✏️  Date Modified",         exif.get("datetime_modified", ""),  "#f59e0b")
    xmp = meta.get("xmp", {})
    _add("📄 XMP Create Date",        xmp.get("create_date", ""),  "#a78bfa")
    _add("📄 XMP Modify Date",        xmp.get("modify_date", ""),  "#f59e0b")
    _add("🔍 Scan Time",              ts_scan, "#94a3b8")

    if not events:
        return '<div class="card"><p style="color:var(--muted)">No date/time information found.</p></div>'

    events.sort(key=lambda x: x["dt"])
    dots = "".join(
        f'<div class="tl-item"><div class="tl-dot" style="background:{e["color"]}"></div>'
        f'<div class="tl-body"><div class="tl-label">{e["label"]}</div>'
        f'<div class="tl-dt">{e["dt"]}</div></div></div>'
        for e in events
    )
    return f'<div class="card"><div class="card-title">Event Timeline</div><div class="timeline">{dots}</div></div>'


def _build_poi_section(results: dict) -> str:
    """Render POI profile cards."""
    poi = results.get("poi_profiles", {})
    if not poi or poi.get("skipped"):
        return '<div class="card"><p style="color:var(--muted)">POI profiles not available. Run full pipeline to generate dossiers.</p></div>'

    profiles = poi.get("profiles", [])
    if not profiles:
        return '<div class="card"><p style="color:var(--muted)">No identity anchors found — no POI profiles to display.</p></div>'

    cards = []
    for p in profiles:
        risk = p.get("risk_score", 0)
        risk_color = "#ef4444" if risk >= 70 else ("#f59e0b" if risk >= 40 else "#22c55e")
        anchor = p.get("anchor", "Unknown")
        summary = p.get("summary", "")
        platforms = p.get("social_accounts", [])
        platform_pills = "".join(
            f'<a href="{acc.get("url","#")}" target="_blank" class="platform-pill">{acc.get("platform","?")}</a>'
            for acc in platforms[:20]
        )
        breach_count = len(p.get("breaches", []))
        emails = ", ".join(p.get("emails", [])[:3]) or "—"
        locations = p.get("locations", [])
        loc_str = "; ".join(l.get("description", "") for l in locations[:2]) or "—"
        flags_html = "".join(f'<div class="flag-item">{f}</div>' for f in p.get("flags", [])[:6])

        cards.append(f"""
        <div class="card" style="margin-bottom:16px;border-left:4px solid {risk_color}">
          <div style="display:flex;align-items:flex-start;gap:20px;margin-bottom:12px">
            <div style="text-align:center;min-width:60px">
              <div style="font-size:36px;font-weight:900;color:{risk_color}">{risk}</div>
              <div style="font-size:10px;color:var(--muted)">Risk Score</div>
            </div>
            <div style="flex:1">
              <div style="font-size:15px;font-weight:700;margin-bottom:4px">{anchor}</div>
              <div style="font-size:12px;color:var(--muted)">{summary}</div>
            </div>
          </div>
          <div class="info-grid" style="margin-bottom:12px">
            <div class="info-item"><span class="ik">Emails</span><span style="font-size:11px">{emails}</span></div>
            <div class="info-item"><span class="ik">HIBP Breaches</span>
              <span style="color:{'#ef4444' if breach_count else 'var(--muted)'}">{breach_count}</span></div>
            <div class="info-item" style="grid-column:span 2"><span class="ik">Locations</span>
              <span style="font-size:11px">{loc_str}</span></div>
          </div>
          {f'<div class="platform-pills" style="margin-bottom:10px">{platform_pills}</div>' if platform_pills else ''}
          {flags_html}
        </div>""")

    return "".join(cards)


def _build_ai_section(results: dict) -> str:
    """Render AI analysis: DeepFace demographics, CLIP country hints, OCR engine."""
    ai = results.get("ai_analysis", {})
    if not ai or ai.get("skipped"):
        msg = ai.get("skipped", "AI analysis not run") if ai else "AI analysis not run"
        return f'<div class="card"><p style="color:var(--muted)">{msg}</p></div>'

    html_parts = []

    # CLIP country hints
    clip = ai.get("openclip", {})
    if clip and not clip.get("skipped"):
        top_c = clip.get("top_country_hints", [])
        bars  = "".join(
            f'<div style="margin-bottom:6px"><div style="display:flex;justify-content:space-between;font-size:12px">'
            f'<span>{c["country"]}</span><span style="color:var(--muted)">{c["confidence"]:.1%}</span></div>'
            f'<div style="background:var(--surface2);border-radius:99px;height:6px;overflow:hidden">'
            f'<div style="height:100%;background:#38bdf8;width:{min(c["confidence"]*100/top_c[0]["confidence"],100):.0f}%"></div></div></div>'
            for c in top_c
        )
        scene = clip.get("scene_type", "")
        html_parts.append(f"""
        <div class="card" style="margin-bottom:16px">
          <div class="card-title">🌍 CLIP Zero-Shot Country Hints</div>
          <div style="margin-bottom:8px;font-size:12px;color:var(--muted)">Model: {clip.get("model","ViT-B-32")} &nbsp;|&nbsp; Scene: <strong>{scene}</strong></div>
          {bars}
        </div>""")

    # DeepFace demographics
    deepface = ai.get("deepface", [])
    if deepface and not (len(deepface) == 1 and deepface[0].get("skipped")):
        rows = ""
        for fd in deepface:
            if fd.get("skipped"):
                rows += f'<tr><td>Face {fd.get("face_id",0)}</td><td colspan="4" style="color:var(--muted)">{fd["skipped"]}</td></tr>'
                continue
            rows += (f'<tr><td>Face {fd["face_id"]}</td>'
                     f'<td>~{fd.get("age","?")}y</td>'
                     f'<td>{fd.get("gender","?")}</td>'
                     f'<td>{fd.get("dominant_emotion","?")}</td>'
                     f'<td>{fd.get("dominant_race","?")}</td></tr>')
        html_parts.append(f"""
        <div class="card" style="margin-bottom:16px">
          <div class="card-title">👤 DeepFace Demographics</div>
          <table class="data-table">
            <thead><tr><th>Face</th><th>Age</th><th>Gender</th><th>Emotion</th><th>Demographic</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>""")

    # Clothing analysis
    clothing = ai.get("clothing", {})
    if clothing and not clothing.get("skipped"):
        persons = clothing.get("persons", [])
        c_html = ""
        for p in persons[:6]:
            colors = p.get("dominant_colors", [])
            swatches = "".join(
                f'<span title="{c["color_name"]} {c["pct"]}%" style="display:inline-block;width:16px;height:16px;'
                f'border-radius:3px;background:hsl({c["hsv"][0]*2:.0f},{c["hsv"][1]/255*100:.0f}%,{c["hsv"][2]/255*50:.0f}%);'
                f'margin:1px;vertical-align:middle"></span>'
                for c in colors[:4]
            )
            uniform_span = ('<br><span style="color:#ef4444;font-size:11px">' + p.get("uniform_type","") + '</span>') if p.get("uniform_detected") else ""
            c_html += (f'<div style="padding:8px;background:var(--surface2);border-radius:6px;margin-bottom:6px">'
                       f'<strong>Person {p["person_id"]}</strong> — {p.get("clothing_type_hint","?")} {swatches}'
                       f'{uniform_span}'
                       f'</div>')
        html_parts.append(f"""
        <div class="card" style="margin-bottom:16px">
          <div class="card-title">👔 Clothing Analysis</div>
          {c_html or '<p style="color:var(--muted)">No clothing analysis available.</p>'}
        </div>""")

    # OCR result from AI stage
    ocr = ai.get("ocr", {})
    if ocr and not ocr.get("skipped") and ocr.get("text"):
        html_parts.append(f"""
        <div class="card" style="margin-bottom:16px">
          <div class="card-title">📝 Enhanced OCR ({ocr.get("engine","?")})</div>
          <pre style="white-space:pre-wrap;font-size:12px;max-height:200px;overflow-y:auto">{ocr["text"][:2000]}</pre>
        </div>""")

    # AI Flags
    ai_flags = ai.get("flags", [])
    if ai_flags:
        flag_html = "".join(f'<div class="flag-item">{f}</div>' for f in ai_flags)
        html_parts.append(f'<div class="card"><div class="card-title">🚩 AI Flags</div>{flag_html}</div>')

    return "".join(html_parts) if html_parts else '<div class="card"><p style="color:var(--muted)">No AI analysis results.</p></div>'


def _build_domain_intel_section(results: dict) -> str:
    """Render domain + IP intel cards."""
    di = results.get("domain_intel", {})
    if not di or di.get("skipped"):
        msg = di.get("skipped", "Domain intel not run") if di else "Domain intel not run"
        return f'<div class="card"><p style="color:var(--muted)">{msg}</p></div>'

    html_parts = []

    # Per-domain cards
    per_domain = di.get("per_domain", {})
    for domain, info in list(per_domain.items())[:8]:
        crt   = info.get("crt", {})
        wb    = info.get("wayback", {})
        vt    = info.get("virustotal", {})
        hunter = info.get("hunter", {})

        vt_color = "#ef4444" if vt.get("malicious_count", 0) > 2 else "#22c55e"
        vt_badge = (f'<span style="color:{vt_color};font-weight:700">'
                    f'VT: {vt.get("malicious_count",0)} malicious</span>' if not vt.get("skipped") else "")

        html_parts.append(f"""
        <div class="card" style="margin-bottom:12px">
          <div class="card-title">🌐 {domain} {vt_badge}</div>
          <div class="info-grid">
            <div class="info-item"><span class="ik">Subdomains (crt.sh)</span>
              <span>{crt.get("cert_count", 0)} certs · {len(crt.get("subdomains",[]))} subdomains</span></div>
            <div class="info-item"><span class="ik">Wayback</span>
              <span>{wb.get("snapshot_count",0)} snapshots · First: {wb.get("first_seen","—")}</span></div>
            <div class="info-item"><span class="ik">Hunter.io Emails</span>
              <span>{len(hunter.get("emails",[]))} email(s) found</span></div>
            <div class="info-item"><span class="ik">Pattern</span>
              <span>{hunter.get("pattern","—")}</span></div>
          </div>
          {("".join(f'<div style="font-size:11px;padding:3px 8px;background:#fee2e2;color:#991b1b;border-radius:4px;display:inline-block;margin:2px">'
             f'{e.get("value","?")} ({e.get("type","?")})</div>' for e in hunter.get("emails",[])[:5]))
           if hunter.get("emails") else ""}
        </div>""")

    # Per-IP cards
    per_ip = di.get("per_ip", {})
    for ip, info in list(per_ip.items())[:5]:
        ipinfo   = info.get("ipinfo", {})
        ip_api   = info.get("ip_api", {})
        abuse    = info.get("abuseipdb", {})
        shodan   = info.get("shodan", {})

        abuse_score = abuse.get("abuse_confidence_score", 0)
        abuse_color = "#ef4444" if abuse_score > 25 else "#22c55e"

        ports = ", ".join(str(p) for p in shodan.get("open_ports", [])[:8])
        vulns = ", ".join(shodan.get("vulns", [])[:3])

        html_parts.append(f"""
        <div class="card" style="margin-bottom:12px">
          <div class="card-title">🔌 {ip}</div>
          <div class="info-grid">
            <div class="info-item"><span class="ik">Location</span>
              <span>{ipinfo.get("city","—")}, {ipinfo.get("country","—")}</span></div>
            <div class="info-item"><span class="ik">ISP / Org</span>
              <span>{ipinfo.get("org","—")[:40]}</span></div>
            <div class="info-item"><span class="ik">AbuseIPDB</span>
              <span style="color:{abuse_color};font-weight:600">{abuse_score}% abuse confidence</span></div>
            <div class="info-item"><span class="ik">Open Ports (Shodan)</span>
              <span>{ports or "—"}</span></div>
          </div>
          {f'<div style="color:#ef4444;font-size:12px;margin-top:6px">⚠️ CVEs: {vulns}</div>' if vulns else ""}
        </div>""")

    # Flags
    flags = di.get("flags", [])
    if flags:
        flag_html = "".join(f'<div class="flag-item">{f}</div>' for f in flags)
        html_parts.append(f'<div class="card"><div class="card-title">🚩 Flags</div>{flag_html}</div>')

    return "".join(html_parts) if html_parts else '<div class="card"><p style="color:var(--muted)">No domain/IP intelligence collected.</p></div>'


def _build_web_intel_section(results: dict) -> str:
    """Render web scrape results, WHOIS, DNS, extracted contacts."""
    wi = results.get("web_intel", {})
    if not wi or wi.get("skipped"):
        msg = wi.get("skipped", "Web intel not run") if wi else "Web intel not run"
        return f'<div class="card"><p style="color:var(--muted)">{msg}</p></div>'

    html_parts = []

    # Summary card
    emails   = wi.get("all_emails", [])
    phones   = wi.get("all_phones", [])
    scraped  = wi.get("scraped", [])
    html_parts.append(f"""
    <div class="card" style="margin-bottom:16px">
      <div class="card-title">🕸️  Web Intel Summary</div>
      <div class="info-grid">
        <div class="info-item"><span class="ik">URLs Scraped</span><span>{len(scraped)}</span></div>
        <div class="info-item"><span class="ik">Emails Found</span>
          <span style="color:{'#ef4444' if emails else 'var(--muted)'}">
            {', '.join(emails[:4]) or '—'}</span></div>
        <div class="info-item"><span class="ik">Phones Found</span>
          <span>{', '.join(phones[:3]) or '—'}</span></div>
        <div class="info-item"><span class="ik">WHOIS Domains</span>
          <span>{len(wi.get("whois_results",{}))}</span></div>
      </div>
    </div>""")

    # Scraped URL cards (top 5)
    for s in scraped[:5]:
        url   = s.get("url", "")
        title = s.get("title", "") or ""
        author = s.get("author", "")
        text_preview = (s.get("text", "") or "")[:300]
        html_parts.append(f"""
        <div class="card" style="margin-bottom:10px">
          <div style="font-weight:700;margin-bottom:4px">
            <a href="{url}" target="_blank" class="link">{title or url[:60]}</a>
          </div>
          {f'<div style="font-size:11px;color:var(--muted);margin-bottom:6px">Author: {author}</div>' if author else ''}
          <pre style="white-space:pre-wrap;font-size:11px;color:var(--muted);max-height:100px;overflow-y:auto">{text_preview}</pre>
        </div>""")

    # WHOIS summary
    whois_results = wi.get("whois_results", {})
    if whois_results:
        rows = ""
        for domain, w in list(whois_results.items())[:5]:
            priv = "🔒 Private" if w.get("privacy_protected") else w.get("registrant_email", "—")
            age  = f'{w.get("age_days","?")}d old' if w.get("age_days") else "—"
            rows += f'<tr><td>{domain}</td><td>{w.get("registrar","—")}</td><td>{w.get("creation_date","—")}</td><td>{age}</td><td>{priv}</td></tr>'
        html_parts.append(f"""
        <div class="card" style="margin-bottom:16px">
          <div class="card-title">🔍 WHOIS Data</div>
          <table class="data-table">
            <thead><tr><th>Domain</th><th>Registrar</th><th>Created</th><th>Age</th><th>Registrant</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>""")

    # Flags
    flags = wi.get("flags", [])
    if flags:
        flag_html = "".join(f'<div class="flag-item">{f}</div>' for f in flags)
        html_parts.append(f'<div class="card"><div class="card-title">🚩 Flags</div>{flag_html}</div>')

    return "".join(html_parts)


def _build_phone_intel_section(results: dict) -> str:
    """Render phone intel from social stage."""
    social  = results.get("social", {}) or {}
    phone_i = social.get("phone_intel", {})
    pfoga   = social.get("phoneinfoga", {})

    if not phone_i and not pfoga:
        return '<div class="card"><p style="color:var(--muted)">Phone intel not available — provide a phone number via TRACK_PHONE env var.</p></div>'

    html_parts = []
    if phone_i and not phone_i.get("skipped"):
        pi_rows = ""
        for k, v in [("Valid", phone_i.get("valid","")), ("Country", phone_i.get("country","")),
                     ("Region", phone_i.get("region","")), ("Type", phone_i.get("number_type","")),
                     ("Carrier", phone_i.get("carrier","")),
                     ("Intl. format", phone_i.get("international_format","")),
                     ("National format", phone_i.get("national_format",""))]:
            if v:
                pi_rows += f"<tr><td class='key'>{k}</td><td>{v}</td></tr>"
        html_parts.append(f"""
        <div class="card" style="margin-bottom:16px">
          <div class="card-title">📞 Phone Number Intelligence</div>
          <table class="data-table"><tbody>{pi_rows}</tbody></table>
        </div>""")

    if pfoga and not pfoga.get("skipped") and pfoga.get("carrier"):
        html_parts.append(f"""
        <div class="card">
          <div class="card-title">🔎 PhoneInfoga Scan</div>
          <div class="info-grid">
            <div class="info-item"><span class="ik">Carrier</span><span>{pfoga.get("carrier","—")}</span></div>
            <div class="info-item"><span class="ik">Line Type</span><span>{pfoga.get("line_type","—")}</span></div>
            <div class="info-item"><span class="ik">Country</span><span>{pfoga.get("country","—")}</span></div>
            <div class="info-item"><span class="ik">Valid</span><span>{pfoga.get("valid","—")}</span></div>
          </div>
        </div>""")

    return "".join(html_parts) if html_parts else '<div class="card"><p style="color:var(--muted)">No phone data.</p></div>'


def generate_html(results: dict, image_path: str) -> str:
    meta       = results.get("metadata", {})
    forensics  = results.get("forensics", {})
    stego      = results.get("steganography", {})
    content    = results.get("content_analysis", {})
    geo        = results.get("geolocation", {})
    rev        = results.get("reverse_image_search", {})
    face_s     = results.get("face_search", {})
    social     = results.get("social", {}) or results.get("social_search", {}) or {}
    facedb_r   = results.get("facedb", {}) or results.get("facedb_search", {}) or {}
    hashing    = results.get("hashing", {})

    intel_score = results.get("intel_score", 0)
    highlights  = results.get("highlights", [])
    ts          = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    image_name  = Path(image_path).name
    score_color = _score_color(intel_score)

    # Embed original image
    img_b64 = _img_b64(image_path)
    img_mime = _mime(image_path)

    # ELA image
    ela_b64 = forensics.get("ela", {}).get("ela_image_b64", "")

    # Face crops
    face_crops = content.get("faces", {}).get("crops_b64", [])
    face_details = content.get("faces", {}).get("details", [])

    # FaceDB matches
    facedb_matches = facedb_r.get("matches", []) if isinstance(facedb_r, dict) else []

    # GPS
    gps = meta.get("gps", {})
    maps_link = gps.get("maps_link", "")
    lat = gps.get("latitude")
    lon = gps.get("longitude")

    # Best geo
    best_geo = geo.get("best_result") or {}
    geo_lat = best_geo.get("lat") or lat
    geo_lon = best_geo.get("lon") or lon
    geo_maps = best_geo.get("maps_link") or maps_link

    # Social platforms
    found_platforms = social.get("found_platforms", [])

    # Reverse image matches
    rev_matches = rev.get("aggregated_matches", [])

    # Pre-extract nested dicts so they can be used inside f-strings without {{}} issues
    ela_d         = forensics.get("ela", {}) or {}
    clone_d       = forensics.get("clone_detection", {}) or {}
    noise_d       = forensics.get("noise_analysis", {}) or {}
    ai_d          = forensics.get("ai_detection", {}) or {}
    lsb_d         = stego.get("lsb", {}) or {}
    dct_d         = stego.get("dct", {}) or {}
    palette_d     = stego.get("palette", {}) or {}
    embedded_d    = stego.get("embedded_file", {}) or {}
    ocr_d         = content.get("ocr", {}) or {}
    quality_d     = content.get("quality", {}) or {}
    lsb_channels  = lsb_d.get("channels", {}) or {}

    # ── HTML ──────────────────────────────────────────────────────────────────

    face_crops_html = ""
    if face_crops:
        cards = []
        for i, crop in enumerate(face_crops[:12]):
            detail = face_details[i] if i < len(face_details) else {}
            age    = detail.get("age", "")
            gender = detail.get("gender", "")
            emotion = detail.get("emotion", "")
            attr = " · ".join(filter(None, [
                f"{age}y" if age else "",
                gender or "",
                emotion or "",
            ]))
            cards.append(f"""
            <div class="face-card">
              <img src="data:image/png;base64,{crop}" alt="Face {i+1}" />
              <div class="face-label">Face {i+1}</div>
              {f'<div class="face-attr">{attr}</div>' if attr else ""}
            </div>""")
        face_crops_html = '<div class="face-grid">' + "".join(cards) + "</div>"

    facedb_html = ""
    if facedb_matches:
        rows = []
        for m in facedb_matches[:20]:
            sim   = m.get("similarity_pct", 0)
            label = m.get("label") or "Unknown"
            fname = Path(m.get("image_path", "")).name
            conf  = m.get("confidence_label", "")
            color = "#ef4444" if sim >= 70 else ("#f59e0b" if sim >= 55 else "#94a3b8")
            rows.append(f"""
            <tr>
              <td><span style="color:{color};font-weight:700">{sim:.1f}%</span></td>
              <td>{conf}</td>
              <td>{label}</td>
              <td title="{m.get('image_path','')}">{fname}</td>
            </tr>""")
        facedb_html = f"""
        <table class="data-table">
          <thead><tr><th>Similarity</th><th>Confidence</th><th>Label</th><th>Source</th></tr></thead>
          <tbody>{"".join(rows)}</tbody>
        </table>"""

    platform_html = ""
    if found_platforms:
        categories = {}
        for p in found_platforms:
            cat = p.get("category", "other")
            categories.setdefault(cat, []).append(p)
        cat_icons = {
            "social": "👥", "dev": "💻", "gaming": "🎮",
            "creative": "🎨", "forum": "💬", "commerce": "🛒",
            "crypto": "₿", "professional": "💼", "paste": "📋", "dating": "💘",
        }
        sections = []
        for cat, platforms in sorted(categories.items()):
            icon = cat_icons.get(cat, "🌐")
            pills = "".join(
                f'<a href="{p["url"]}" target="_blank" class="platform-pill">{p["platform"]}</a>'
                for p in platforms
            )
            sections.append(f'<div class="platform-cat"><span class="cat-label">{icon} {cat.title()}</span><div class="platform-pills">{pills}</div></div>')
        platform_html = "".join(sections)

    rev_html = ""
    if rev_matches:
        rows = []
        for m in rev_matches[:20]:
            engines = ", ".join(m.get("engines", []))
            title   = (m.get("title") or m.get("domain", ""))[:60]
            url     = m.get("url", "")
            domain  = m.get("domain", "")
            rows.append(f"""
            <tr>
              <td><a href="{url}" target="_blank" class="link">{domain}</a></td>
              <td><span class="engine-tag">{engines}</span></td>
              <td>{title}</td>
            </tr>""")
        rev_html = f"""
        <table class="data-table">
          <thead><tr><th>Domain</th><th>Engine(s)</th><th>Title</th></tr></thead>
          <tbody>{"".join(rows)}</tbody>
        </table>"""

    # EXIF table
    exif = meta.get("exif", {})
    device = meta.get("device", {})
    exif_rows = ""
    exif_fields = [
        ("Camera", f"{device.get('make','')} {device.get('model','')}".strip() or "—"),
        ("Device type", device.get("type", "—")),
        ("Serial #", device.get("serial_number") or "—"),
        ("Software", device.get("software") or "—"),
        ("Date taken", exif.get("datetime_original") or "—"),
        ("ISO", exif.get("iso") or "—"),
        ("Aperture", exif.get("aperture") or "—"),
        ("Shutter", exif.get("shutter_speed") or "—"),
        ("Focal length", exif.get("focal_length") or "—"),
        ("Flash", exif.get("flash") or "—"),
        ("GPS Lat", str(gps.get("latitude", "—"))),
        ("GPS Lon", str(gps.get("longitude", "—"))),
        ("Altitude", f"{gps.get('altitude_m', '—')} m"),
        ("Artist", exif.get("artist") or "—"),
        ("Copyright", exif.get("copyright") or "—"),
    ]
    for k, v in exif_fields:
        highlight = ' style="background:#fef9c3"' if v != "—" and k in ("GPS Lat", "GPS Lon", "Serial #") else ""
        exif_rows += f"<tr{highlight}><td class='key'>{k}</td><td>{v}</td></tr>"

    flag_items = "".join(f'<li class="flag-item">{f}</li>' for f in meta.get("flags", []))

    highlights_html = "".join(f'<li class="hl-item">{h}</li>' for h in highlights)

    # Map embed (OpenStreetMap iframe — free, no key)
    map_html = ""
    if geo_lat and geo_lon:
        map_html = f"""
        <div class="map-wrap">
          <iframe
            src="https://www.openstreetmap.org/export/embed.html?bbox={geo_lon-0.01},{geo_lat-0.01},{geo_lon+0.01},{geo_lat+0.01}&layer=mapnik&marker={geo_lat},{geo_lon}"
            style="width:100%;height:280px;border:0;border-radius:8px">
          </iframe>
          <div class="map-link">
            <a href="{geo_maps}" target="_blank" class="link">Open in Google Maps ↗</a>
          </div>
        </div>"""

    # Social risk score
    social_risk = social.get("risk_score", 0) if social else 0
    social_risk_color = _score_color(social_risk)

    # Breach rows
    breach_html = ""
    breach_data = social.get("breach_data", {}) if social else {}
    for email, hibp in breach_data.items():
        for breach in hibp.get("breaches", [])[:10]:
            data_classes = ", ".join(breach.get("data_classes", [])[:5])
            breach_html += f"""
            <tr>
              <td>{email}</td>
              <td><strong>{breach.get('name')}</strong></td>
              <td>{breach.get('date','—')}</td>
              <td>{breach.get('pwn_count',0):,}</td>
              <td>{data_classes}</td>
            </tr>"""

    github = social.get("github", {}) if social else {}
    github_profile = github.get("profile", {}) if github else {}
    github_html = ""
    if github.get("exists"):
        emails_str = ", ".join(github.get("emails_found", [])) or "—"
        repos = github.get("repos", [])
        repos_html = "".join(
            f'<tr><td><a href="{r["url"]}" target="_blank" class="link">{r["name"]}</a></td>'
            f'<td>⭐ {r["stars"]}</td><td>{r["language"] or "—"}</td>'
            f'<td>{(r["description"] or "")[:60]}</td></tr>'
            for r in repos[:5]
        )
        github_html = f"""
        <div class="info-grid">
          <div class="info-item"><span class="ik">Name</span><span>{github_profile.get('name','—')}</span></div>
          <div class="info-item"><span class="ik">Bio</span><span>{github_profile.get('bio','—')}</span></div>
          <div class="info-item"><span class="ik">Company</span><span>{github_profile.get('company','—')}</span></div>
          <div class="info-item"><span class="ik">Location</span><span>{github_profile.get('location','—')}</span></div>
          <div class="info-item"><span class="ik">Twitter</span><span>{('@' + github_profile.get('twitter','')) if github_profile.get('twitter') else '—'}</span></div>
          <div class="info-item"><span class="ik">Emails leaked</span><span style="color:#ef4444;font-weight:600">{emails_str}</span></div>
          <div class="info-item"><span class="ik">Followers</span><span>{github_profile.get('followers','—')}</span></div>
          <div class="info-item"><span class="ik">Public repos</span><span>{github_profile.get('public_repos','—')}</span></div>
        </div>
        {'<h4 style="margin-top:16px">Top Repositories</h4><table class="data-table"><thead><tr><th>Repo</th><th>Stars</th><th>Language</th><th>Description</th></tr></thead><tbody>' + repos_html + '</tbody></table>' if repos_html else ''}
        """

    # Pre-compute sections that need backslashes (not allowed inside f-string expressions in Python <3.12)
    mapillary_photos_html = ""
    mapillary_data = geo.get("mapillary", {})
    if mapillary_data and not mapillary_data.get("skipped") and mapillary_data.get("nearby_photos"):
        photo_divs = []
        for p in mapillary_data["nearby_photos"][:5]:
            thumb = p.get("thumb_url", "")
            date  = str(p.get("date", ""))[:10]
            photo_divs.append(
                f'<div style="text-align:center">'
                f'<img src="{thumb}" style="width:120px;height:90px;object-fit:cover;border-radius:6px" />'
                f'<div style="font-size:10px;color:var(--muted);margin-top:4px">{date}</div>'
                f'</div>'
            )
        mapillary_photos_html = f"""
        <div class="card">
          <div class="card-title">📸 Mapillary Street-Level Photos</div>
          <div style="display:flex;flex-wrap:wrap;gap:8px">{"".join(photo_divs)}</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>ImageTrace — {image_name}</title>
<style>
:root {{
  --bg: #0f172a; --surface: #1e293b; --surface2: #334155;
  --text: #f1f5f9; --muted: #94a3b8; --accent: #38bdf8;
  --red: #ef4444; --yellow: #f59e0b; --green: #22c55e;
  --border: #334155; --radius: 10px;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); font-size: 14px; }}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

/* Layout */
.container {{ max-width: 1280px; margin: 0 auto; padding: 24px 20px; }}
.header {{ display:flex; align-items:center; gap:16px; margin-bottom:28px; border-bottom:1px solid var(--border); padding-bottom:20px; }}
.logo {{ font-size:28px; font-weight:800; color:var(--accent); letter-spacing:-1px; }}
.header-meta {{ flex:1; }}
.header-meta h1 {{ font-size:18px; font-weight:600; }}
.header-meta small {{ color:var(--muted); font-size:12px; }}
.grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
.grid-3 {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; }}
@media(max-width:900px) {{ .grid-2,.grid-3 {{ grid-template-columns:1fr; }} }}

/* Cards */
.card {{ background: var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:20px; }}
.card-title {{ font-size:13px; font-weight:700; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; margin-bottom:14px; }}

/* Score gauge */
.score-wrap {{ text-align:center; padding:8px; }}
.score-num {{ font-size:64px; font-weight:900; line-height:1; color:{score_color}; }}
.score-label {{ font-size:12px; color:var(--muted); margin-top:4px; }}
.score-bar {{ background:var(--surface2); border-radius:99px; height:10px; margin:12px 0 6px; overflow:hidden; }}
.score-fill {{ height:100%; border-radius:99px; background:{score_color}; width:{intel_score}%; transition:width .8s ease; }}

/* Badges */
.badge {{ display:inline-block; padding:3px 10px; border-radius:99px; font-size:11px; font-weight:600; margin:2px; }}
.badge-red    {{ background:#fee2e2; color:#991b1b; }}
.badge-yellow {{ background:#fef3c7; color:#92400e; }}
.badge-green  {{ background:#dcfce7; color:#166534; }}
.badge-gray   {{ background:var(--surface2); color:var(--muted); }}

/* Image preview */
.img-pair {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
.img-pair img {{ width:100%; border-radius:8px; object-fit:contain; max-height:320px; background:#000; }}
.img-cap {{ text-align:center; font-size:11px; color:var(--muted); margin-top:6px; }}

/* Face grid */
.face-grid {{ display:flex; flex-wrap:wrap; gap:12px; margin-top:12px; }}
.face-card {{ background:var(--surface2); border-radius:8px; padding:8px; text-align:center; width:120px; }}
.face-card img {{ width:100px; height:100px; object-fit:cover; border-radius:6px; display:block; margin:0 auto; }}
.face-label {{ font-size:11px; color:var(--muted); margin-top:6px; }}
.face-attr {{ font-size:10px; color:var(--accent); margin-top:2px; }}

/* Tables */
.data-table {{ width:100%; border-collapse:collapse; font-size:13px; margin-top:8px; }}
.data-table th {{ background:var(--surface2); padding:9px 12px; text-align:left; font-size:11px; color:var(--muted); text-transform:uppercase; }}
.data-table td {{ padding:9px 12px; border-top:1px solid var(--border); vertical-align:top; word-break:break-word; }}
.data-table tr:hover td {{ background:var(--surface2); }}
.key {{ color:var(--muted); font-size:12px; width:130px; }}

/* Tabs */
.tabs {{ display:flex; gap:4px; margin-bottom:20px; flex-wrap:wrap; }}
.tab {{ padding:8px 18px; border-radius:8px; cursor:pointer; font-size:13px; font-weight:600;
         background:var(--surface); border:1px solid var(--border); color:var(--muted); }}
.tab.active {{ background:var(--accent); color:#0f172a; border-color:var(--accent); }}
.tab-content {{ display:none; }}
.tab-content.active {{ display:block; }}

/* Platforms */
.platform-cat {{ margin-bottom:14px; }}
.cat-label {{ font-size:12px; font-weight:700; color:var(--muted); text-transform:uppercase; display:block; margin-bottom:8px; }}
.platform-pills {{ display:flex; flex-wrap:wrap; gap:6px; }}
.platform-pill {{ background:var(--surface2); border:1px solid var(--border); padding:4px 12px;
                  border-radius:99px; font-size:12px; color:var(--text);
                  transition:background .15s; }}
.platform-pill:hover {{ background:var(--accent); color:#0f172a; border-color:var(--accent); text-decoration:none; }}

/* Highlights */
.hl-list {{ list-style:none; }}
.hl-item {{ padding:7px 0; border-bottom:1px solid var(--border); font-size:13px; }}
.hl-item:last-child {{ border-bottom:none; }}

/* Flags */
.flag-list {{ list-style:none; }}
.flag-item {{ padding:6px 10px; border-radius:6px; background:var(--surface2); margin-bottom:6px; font-size:13px; }}

/* Info grid */
.info-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; }}
.info-item {{ display:flex; flex-direction:column; padding:8px; background:var(--surface2); border-radius:6px; }}
.ik {{ font-size:10px; color:var(--muted); text-transform:uppercase; margin-bottom:2px; }}

/* Engine tags */
.engine-tag {{ font-size:10px; background:var(--surface2); padding:2px 8px; border-radius:99px; color:var(--muted); }}

/* Map */
.map-wrap {{ border-radius:8px; overflow:hidden; margin-top:12px; }}
.map-link {{ text-align:right; margin-top:6px; font-size:12px; }}

/* Timeline */
.timeline {{ padding:8px 0; }}
.tl-item {{ display:flex; align-items:flex-start; gap:12px; padding:8px 0; border-bottom:1px solid var(--border); }}
.tl-item:last-child {{ border-bottom:none; }}
.tl-dot {{ width:12px; height:12px; border-radius:50%; flex-shrink:0; margin-top:3px; }}
.tl-label {{ font-size:13px; font-weight:600; }}
.tl-dt {{ font-size:12px; color:var(--muted); }}

/* Hash fingerprints */
.hash-row {{ display:flex; gap:8px; align-items:baseline; padding:5px 0; border-bottom:1px solid var(--border); font-size:12px; }}
.hash-key {{ color:var(--muted); width:80px; flex-shrink:0; font-size:11px; text-transform:uppercase; }}
.hash-val {{ font-family:monospace; word-break:break-all; color:var(--accent); }}

/* Print */
@media print {{
  body {{ background:#fff; color:#000; }}
  .card {{ border:1px solid #ccc; }}
  .tab-content {{ display:block !important; }}
  .tabs {{ display:none; }}
}}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
<div class="header">
  <div class="logo">ImageTrace</div>
  <div class="header-meta">
    <h1>Intelligence Report — {image_name}</h1>
    <small>Generated {ts} &nbsp;·&nbsp; v2.2 &nbsp;·&nbsp; 15-Stage Pipeline</small>
  </div>
  <button onclick="window.print()" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px;">🖨 Export PDF</button>
</div>

<!-- Top row: score + image + highlights -->
<div class="grid-3" style="margin-bottom:16px">
  <div class="card score-wrap">
    <div class="card-title">Intel Score</div>
    <div class="score-num">{intel_score}</div>
    <div class="score-bar"><div class="score-fill"></div></div>
    <div class="score-label">/ 100 intelligence value</div>
  </div>
  <div class="card" style="grid-column:span 2">
    <div class="card-title">Key Findings</div>
    <ul class="hl-list">{highlights_html or '<li class="hl-item" style="color:var(--muted)">No significant findings</li>'}</ul>
  </div>
</div>

<!-- Image preview -->
<div class="card" style="margin-bottom:16px">
  <div class="card-title">Image Preview</div>
  <div class="img-pair">
    <div>
      {'<img src="data:image/' + img_mime + ';base64,' + img_b64 + '" alt="Original"/>' if img_b64 else '<div style="height:200px;display:flex;align-items:center;justify-content:center;color:var(--muted)">Preview unavailable</div>'}
      <div class="img-cap">Original</div>
    </div>
    <div>
      {'<img src="data:image/png;base64,' + ela_b64 + '" alt="ELA"/>' if ela_b64 else '<div style="height:200px;display:flex;align-items:center;justify-content:center;color:var(--muted)">ELA not available</div>'}
      <div class="img-cap">Error Level Analysis (bright = edited regions)</div>
    </div>
  </div>
</div>

<!-- Face crops -->
{f'<div class="card" style="margin-bottom:16px"><div class="card-title">Detected Faces ({len(face_crops)})</div>{face_crops_html}</div>' if face_crops else ''}

<!-- Tabs -->
<div class="tabs">
  <div class="tab active" onclick="showTab('meta')">📋 Metadata</div>
  <div class="tab" onclick="showTab('forensics')">🔬 Forensics</div>
  <div class="tab" onclick="showTab('stego')">🔐 Steganography</div>
  <div class="tab" onclick="showTab('content')">👁 Content</div>
  <div class="tab" onclick="showTab('ai')">🤖 AI Analysis</div>
  <div class="tab" onclick="showTab('geo')">🌍 Geolocation</div>
  <div class="tab" onclick="showTab('reverse')">🔎 Reverse Search</div>
  <div class="tab" onclick="showTab('facedb')">🧬 FaceDB</div>
  <div class="tab" onclick="showTab('social')">👥 Social</div>
  <div class="tab" onclick="showTab('poi')">🕵️ POI Profiles</div>
  <div class="tab" onclick="showTab('webscrape')">🕸️ Web Intel</div>
  <div class="tab" onclick="showTab('domain')">🔒 Domain Intel</div>
  <div class="tab" onclick="showTab('phone')">📞 Phone Intel</div>
  <div class="tab" onclick="showTab('timeline')">⏱ Timeline</div>
</div>

<!-- Tab: Metadata -->
<div id="tab-meta" class="tab-content active">
  <div class="grid-2">
    <div class="card">
      <div class="card-title">EXIF & Device Info</div>
      <table class="data-table"><tbody>{exif_rows}</tbody></table>
    </div>
    <div class="card">
      <div class="card-title">Flags &amp; Warnings</div>
      {'<ul class="flag-list">' + flag_items + '</ul>' if flag_items else '<p style="color:var(--muted)">No flags detected.</p>'}
    </div>
  </div>
  <div class="card" style="margin-top:16px">
    <div class="card-title">🔑 Hash Fingerprints</div>
    <div class="hash-row"><span class="hash-key">MD5</span><span class="hash-val">{hashing.get("md5","—")}</span></div>
    <div class="hash-row"><span class="hash-key">SHA-256</span><span class="hash-val">{hashing.get("sha256","—")}</span></div>
    <div class="hash-row"><span class="hash-key">pHash</span><span class="hash-val">{hashing.get("phash","—")}</span></div>
    <div class="hash-row"><span class="hash-key">dHash</span><span class="hash-val">{hashing.get("dhash","—")}</span></div>
    <div class="hash-row"><span class="hash-key">NSFW</span>
      <span class="hash-val" style="color:{'#ef4444' if hashing.get('nsfw',{}).get('score',0)>0.6 else 'var(--muted)'}">
        {hashing.get("nsfw",{}).get("verdict","—")}
        {(' · score: ' + str(round(hashing.get("nsfw",{}).get("score",0),3))) if hashing.get("nsfw",{}).get("score") else ''}
      </span>
    </div>
  </div>
</div>

<!-- Tab: Forensics -->
<div id="tab-forensics" class="tab-content">
  <div class="card">
    <div class="card-title">Manipulation Analysis</div>
    <div style="margin-bottom:16px">
      <strong>Verdict:</strong> {_verdict_badge(forensics.get('manipulation_verdict','—'))}
      &nbsp;&nbsp;
      <strong>Score:</strong> <span style="font-size:20px;font-weight:800;color:{_score_color(forensics.get('manipulation_score',0))}">{forensics.get('manipulation_score',0)}/100</span>
    </div>
    <table class="data-table">
      <thead><tr><th>Check</th><th>Result</th><th>Details</th></tr></thead>
      <tbody>
        <tr><td>Error Level Analysis (ELA)</td>
            <td>{_verdict_badge(ela_d.get('verdict','—'))}</td>
            <td>Score: {ela_d.get('ela_score',0)}/100 · High-error regions: {ela_d.get('high_error_pct',0):.1f}%</td></tr>
        <tr><td>Clone Detection</td>
            <td>{_verdict_badge(clone_d.get('verdict','—'))}</td>
            <td>{clone_d.get('clone_count',0)} region(s) detected</td></tr>
        <tr><td>Noise Analysis</td>
            <td>{_verdict_badge(noise_d.get('verdict','—'))}</td>
            <td>Score: {noise_d.get('noise_score',0)}/100</td></tr>
        <tr><td>AI/Deepfake Detection</td>
            <td>{_verdict_badge('checked' if not ai_d.get('skipped') else 'Skipped')}</td>
            <td>{ai_d.get('skipped', 'AI gen: ' + str(ai_d.get('ai_generated','—')))}</td></tr>
      </tbody>
    </table>
  </div>
</div>

<!-- Tab: Steganography -->
<div id="tab-stego" class="tab-content">
  <div class="card">
    <div class="card-title">Steganography Scan</div>
    <div style="margin-bottom:16px">
      <strong>Overall:</strong> {_verdict_badge(stego.get('overall','—'))}
    </div>
    <table class="data-table">
      <thead><tr><th>Method</th><th>Result</th><th>Details</th></tr></thead>
      <tbody>
        <tr><td>LSB Analysis</td><td>{_verdict_badge(lsb_d.get('verdict','—'))}</td>
            <td>{'Channels: ' + ', '.join(str(k) + ': entropy=' + str(v.get('entropy','?')) for k,v in lsb_channels.items()) if lsb_channels else '—'}</td></tr>
        <tr><td>DCT (JPEG)</td><td>{_verdict_badge(dct_d.get('verdict','—'))}</td>
            <td>{'Applicable' if dct_d.get('applicable') else 'Not a JPEG'}</td></tr>
        <tr><td>Palette Analysis</td><td>{_verdict_badge(palette_d.get('verdict','—'))}</td>
            <td>Near-duplicate pairs: {palette_d.get('near_duplicate_pairs',0)}</td></tr>
        <tr><td>Embedded File Scan</td><td>{_verdict_badge(embedded_d.get('verdict','—'))}</td>
            <td>Appended bytes: {embedded_d.get('appended_bytes',0)}</td></tr>
      </tbody>
    </table>
    {'<div style="margin-top:12px;padding:10px;background:var(--surface2);border-radius:6px;font-family:monospace;font-size:12px"><strong>Hidden text preview:</strong><br>' + stego.get("lsb",{}).get("hidden_text_preview","") + '</div>' if stego.get("lsb",{}).get("hidden_text_preview") else ''}
  </div>
</div>

<!-- Tab: Content -->
<div id="tab-content" class="tab-content">
  <div class="grid-2">
    <div class="card">
      <div class="card-title">OCR — Extracted Text</div>
      {'<pre style="white-space:pre-wrap;font-size:12px;color:var(--text);max-height:300px;overflow-y:auto">' + (content.get("ocr",{}).get("text","") or "No text found") + '</pre>' if True else ''}
      <div style="margin-top:8px;color:var(--muted);font-size:12px">{content.get('ocr',{}).get('word_count',0)} words · {content.get('ocr',{}).get('languages_hint','—')}</div>
    </div>
    <div class="card">
      <div class="card-title">QR / Barcodes</div>
      {''.join(f'<div style="padding:8px;background:var(--surface2);border-radius:6px;margin-bottom:8px"><strong>{c.get("type")}</strong><br><code style="font-size:12px">{c.get("data","")}</code></div>' for c in content.get("qr_barcodes",{}).get("codes",[])) or '<p style="color:var(--muted)">None detected</p>'}
    </div>
  </div>
  <div class="card" style="margin-top:16px">
    <div class="card-title">Image Quality</div>
    <div class="info-grid">
      <div class="info-item"><span class="ik">Sharpness</span><span>{content.get('quality',{}).get('sharpness_verdict','—')} ({content.get('quality',{}).get('sharpness_score','—')})</span></div>
      <div class="info-item"><span class="ik">Brightness</span><span>{content.get('quality',{}).get('brightness_verdict','—')} ({content.get('quality',{}).get('brightness','—')})</span></div>
    </div>
  </div>
</div>

<!-- Tab: AI Analysis -->
<div id="tab-ai" class="tab-content">
  {_build_ai_section(results)}
</div>

<!-- Tab: Geolocation -->
<div id="tab-geo" class="tab-content">
  <div class="card" style="margin-bottom:16px">
    <div class="card-title">Geolocation</div>
    <div style="margin-bottom:16px"><strong>{geo.get('overall_verdict','—')}</strong></div>
    <div class="info-grid" style="margin-bottom:16px">
      <div class="info-item"><span class="ik">Source</span><span>{geo.get('source','—')}</span></div>
      <div class="info-item"><span class="ik">Country</span><span>{best_geo.get('country','—')}</span></div>
      <div class="info-item"><span class="ik">City</span><span>{(best_geo.get('city') or '—')[:60]}</span></div>
      <div class="info-item"><span class="ik">Coordinates</span><span>{geo_lat or '—'}, {geo_lon or '—'}</span></div>
      <div class="info-item"><span class="ik">Sun Angle</span>
        <span>{geo.get('sun_angle_v2',{}).get('estimated_latitude_band') or geo.get('sun_angle',{}).get('estimated_latitude_band') or '—'}</span></div>
      <div class="info-item"><span class="ik">Time of Day</span>
        <span>{geo.get('sun_angle_v2',{}).get('estimated_time_of_day') or geo.get('sun_angle',{}).get('estimated_time_of_day') or '—'}</span></div>
      <div class="info-item"><span class="ik">Climate Zone</span>
        <span>{geo.get('vegetation_zone',{}).get('climate_zone','—')}</span></div>
      <div class="info-item"><span class="ik">Architecture</span>
        <span>{geo.get('architecture_hint',{}).get('region_hint','—')}</span></div>
      <div class="info-item"><span class="ik">Timezone</span>
        <span>{geo.get('timezone',{}).get('timezone','—')} ({geo.get('timezone',{}).get('utc_offset','—')})</span></div>
      <div class="info-item"><span class="ik">Hemisphere</span>
        <span>{geo.get('timezone',{}).get('hemisphere','—')}</span></div>
    </div>
    {map_html}
  </div>
  {f'''<div class="card" style="margin-bottom:16px">
    <div class="card-title">📍 Overpass OSM POI ({geo.get("overpass_poi",{}).get("verdict","—")})</div>
    <div class="info-grid">
      <div class="info-item"><span class="ik">City</span><span>{geo.get("overpass_poi",{}).get("city","—")}</span></div>
      <div class="info-item"><span class="ik">Postcode</span><span>{geo.get("overpass_poi",{}).get("postcode","—")}</span></div>
      <div class="info-item"><span class="ik">Country</span><span>{geo.get("overpass_poi",{}).get("country","—")}</span></div>
      <div class="info-item"><span class="ik">Neighbourhood</span><span>{geo.get("overpass_poi",{}).get("neighbourhood","—")}</span></div>
    </div>
    <div style="margin-top:8px;font-size:12px;color:var(--muted)">Nearby: {", ".join(geo.get("overpass_poi",{}).get("street_names",[])[:5]) or "—"}</div>
    {f'<div style="margin-top:6px"><a href="{geo["overpass_poi"]["osm_url"]}" target="_blank" class="link">Open in OpenStreetMap ↗</a></div>' if geo.get("overpass_poi",{}).get("osm_url") else ""}
  </div>''' if geo.get("overpass_poi") and not geo.get("overpass_poi",{}).get("skipped") else ""}
  {f'''<div class="card" style="margin-bottom:16px">
    <div class="card-title">🌦️  Weather Corroboration ({geo.get("weather_corroboration",{}).get("date","—")})</div>
    <div class="info-grid">
      <div class="info-item"><span class="ik">Max Temp</span><span>{geo.get("weather_corroboration",{}).get("max_temp_c","—")}°C</span></div>
      <div class="info-item"><span class="ik">Precipitation</span><span>{geo.get("weather_corroboration",{}).get("precipitation_mm","—")}mm</span></div>
      <div class="info-item"><span class="ik">Snowfall</span><span>{geo.get("weather_corroboration",{}).get("snowfall_cm","—")}cm</span></div>
      <div class="info-item"><span class="ik">Summary</span><span>{geo.get("weather_corroboration",{}).get("weather_summary","—")}</span></div>
    </div>
    {"".join(f'<div class="flag-item">{c}</div>' for c in geo.get("weather_corroboration",{}).get("image_corroboration",[]))}
  </div>''' if geo.get("weather_corroboration") and not geo.get("weather_corroboration",{}).get("skipped") else ""}
  {mapillary_photos_html}
</div>

<!-- Tab: Reverse Search -->
<div id="tab-reverse" class="tab-content">
  <div class="card">
    <div class="card-title">Reverse Image Search Results</div>
    <div style="margin-bottom:16px">
      {_verdict_badge(rev.get('verdict','—'))}
      <span style="margin-left:12px;color:var(--muted);font-size:12px">{rev.get('total_unique_domains',0)} unique domains found</span>
    </div>
    {rev_html or '<p style="color:var(--muted)">No matches found or search skipped.</p>'}
  </div>
</div>

<!-- Tab: FaceDB -->
<div id="tab-facedb" class="tab-content">
  <div class="card">
    <div class="card-title">Local Face Database Matches</div>
    {facedb_html or '<p style="color:var(--muted)">No local face database results. Run: <code>python facedb.py index ./your_photos/</code> first.</p>'}
    <div style="margin-top:16px;padding:12px;background:var(--surface2);border-radius:8px;font-size:12px;color:var(--muted)">
      💡 <strong>Tip:</strong> Build your local face database with <code>python stages/facedb.py index ./photos/ --label "Person Name"</code>
      then re-run ImageTrace to get similarity matches.
    </div>
  </div>
</div>

<!-- Tab: Social -->
<div id="tab-social" class="tab-content">
  {f'''
  <div class="card" style="margin-bottom:16px">
    <div class="card-title">Social Footprint — {social.get("username","—")}</div>
    <div style="display:flex;gap:24px;margin-bottom:16px;flex-wrap:wrap">
      <div><span style="font-size:36px;font-weight:900;color:{social_risk_color}">{social_risk}</span><div style="font-size:11px;color:var(--muted)">Risk Score / 100</div></div>
      <div style="flex:1">
        <div style="margin-bottom:8px"><strong>{social.get("summary",{}).get("platforms_found",0)}</strong> of <strong>{social.get("summary",{}).get("platforms_checked",0)}</strong> platforms active</div>
        {''.join(f'<div class="flag-item">{f}</div>' for f in social.get("flags",[]))}
      </div>
    </div>
    {platform_html or '<p style="color:var(--muted)">No platforms found.</p>'}
  </div>
  {f'<div class="card" style="margin-bottom:16px"><div class="card-title">GitHub Intelligence</div>{github_html}</div>' if github_html else ''}
  {f'<div class="card" style="margin-bottom:16px"><div class="card-title">🚨 Breach Data (HaveIBeenPwned)</div><table class="data-table"><thead><tr><th>Email</th><th>Breach</th><th>Date</th><th>Pwned</th><th>Data leaked</th></tr></thead><tbody>{breach_html}</tbody></table></div>' if breach_html else ''}
  ''' if social else '<div class="card"><p style="color:var(--muted)">Social search not run. Provide a username to enable.</p></div>'}
</div>

<!-- Tab: POI Profiles -->
<div id="tab-poi" class="tab-content">
  {_build_poi_section(results)}
</div>

<!-- Tab: Web Intel -->
<div id="tab-webscrape" class="tab-content">
  {_build_web_intel_section(results)}
</div>

<!-- Tab: Domain Intel -->
<div id="tab-domain" class="tab-content">
  {_build_domain_intel_section(results)}
</div>

<!-- Tab: Phone Intel -->
<div id="tab-phone" class="tab-content">
  {_build_phone_intel_section(results)}
</div>

<!-- Tab: Timeline -->
<div id="tab-timeline" class="tab-content">
  {_build_timeline_section(results)}
</div>

</div><!-- /container -->

<script>
function showTab(name) {{
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  event.currentTarget.classList.add('active');
}}
</script>
</body>
</html>"""

    return html


def save_dashboard(results: dict, image_path: str, output_dir: str = ".") -> str:
    """Generate and save the HTML dashboard. Returns the file path."""
    stem = Path(image_path).stem
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out  = Path(output_dir) / f"dashboard_{stem}_{ts}.html"
    out.parent.mkdir(parents=True, exist_ok=True)

    html = generate_html(results, image_path)
    out.write_text(html, encoding="utf-8")
    return str(out)
