"""
Stage 8 — Intelligence Report Generation
Compiles all stage results into:
  1. Rich terminal output (tables, panels, color-coded verdicts)
  2. Markdown report file (report_<name>_<timestamp>.md)
  3. JSON export (machine-readable)
  4. Discord / Telegram / email webhook alerts (optional)
  5. Overall INTEL SCORE (0-100)
"""

import os
import json
import time
import datetime
import requests
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.text import Text
    from rich import box
    from rich.rule import Rule
    from rich.columns import Columns
    from rich.style import Style
    RICH_OK = True
except ImportError:
    RICH_OK = False

console = Console() if RICH_OK else None


# ── Small helpers ─────────────────────────────────────────────────────────────

def _fmt_ai(ai: dict) -> str:
    """Format AI/deepfake detection result without backslashes in f-string."""
    if not ai:
        return "—"
    if "skipped" in ai:
        return str(ai["skipped"])
    ai_gen   = ai.get("ai_generated", "?")
    deepfake = ai.get("deepfake", "?")
    return f"AI={ai_gen} | Deepfake={deepfake}"


# ── Intel Score ───────────────────────────────────────────────────────────────

def _compute_intel_score(results: dict) -> tuple[int, list[str], dict]:
    """
    Weighted 5-category Intel Score (0-100).
    Returns: (score, highlights, breakdown)
    Categories: Identity (25), Location (25), Authenticity (20), Exposure (20), Content (10)
    """
    highlights = []
    breakdown = {
        "identity":      {"score": 0, "max": 25, "factors": []},
        "location":      {"score": 0, "max": 25, "factors": []},
        "authenticity":  {"score": 0, "max": 20, "factors": []},
        "exposure":      {"score": 0, "max": 20, "factors": []},
        "content":       {"score": 0, "max": 10, "factors": []},
    }

    meta     = results.get("metadata", {})
    forensics = results.get("forensics", {})
    stego    = results.get("steganography", {})
    content  = results.get("content_analysis", {})
    geo      = results.get("geolocation", {})
    reverse  = results.get("reverse_image_search", {})
    face_s   = results.get("face_search", {})
    social   = results.get("social", {})
    poi      = results.get("poi_profiles", {})

    # ── IDENTITY (max 25) ──────────────────────────────────────────────────────
    ident = breakdown["identity"]
    if meta.get("gps", {}).get("latitude"):
        ident["score"] += 15
        ident["factors"].append("GPS coordinates")
        highlights.append("📍 GPS coordinates extracted")

    if meta.get("device", {}).get("serial_number"):
        ident["score"] += 5
        ident["factors"].append("Device serial number")
        highlights.append(f"🔑 Device serial: {meta['device']['serial_number']}")

    xmp_creator = meta.get("xmp", {}).get("creator") or meta.get("iptc", {}).get("author")
    if xmp_creator:
        ident["score"] += 5
        ident["factors"].append(f"Author metadata: {xmp_creator}")
        highlights.append(f"👤 Author: {xmp_creator}")

    face_matches_total = sum(
        len(f.get("aggregated_matches", []))
        for f in face_s.get("per_face", [])
    )
    if face_matches_total > 0:
        ident["score"] = min(25, ident["score"] + 10)
        ident["factors"].append(f"{face_matches_total} face match(es) online")
        highlights.append(f"🔍 {face_matches_total} face match(es) in online databases")

    # ── LOCATION (max 25) ─────────────────────────────────────────────────────
    loc = breakdown["location"]
    if meta.get("gps", {}).get("latitude"):
        loc["score"] += 15
        loc["factors"].append("GPS in EXIF")

    geospy_lat = geo.get("geospy", {}).get("lat")
    if geospy_lat and not meta.get("gps", {}).get("latitude"):
        loc["score"] += 10
        loc["factors"].append("GeoSpy AI visual geolocation")
        highlights.append(f"🌍 GeoSpy: {geo['geospy'].get('city', '?')}")

    sun_angle = geo.get("sun_angle", {})
    if sun_angle.get("estimated_latitude_band") and not sun_angle.get("skipped"):
        loc["score"] = min(25, loc["score"] + 5)
        loc["factors"].append(f"Sun angle: {sun_angle['estimated_latitude_band']}")

    if geo.get("ocr_geolocation", {}).get("geocoded") or geo.get("deep_ocr_geocoding", {}).get("best_country"):
        loc["score"] = min(25, loc["score"] + 5)
        loc["factors"].append("OCR/text geocoding signal")

    # ── AUTHENTICITY (max 20) ─────────────────────────────────────────────────
    auth = breakdown["authenticity"]
    manip = forensics.get("manipulation_score", 0)
    if manip >= 60:
        auth["score"] += 20
        auth["factors"].append(f"Image manipulated ({manip}/100)")
        highlights.append(f"🚨 Image manipulated (score: {manip}/100)")
    elif manip >= 30:
        auth["score"] += 10
        auth["factors"].append(f"Possible editing ({manip}/100)")
        highlights.append(f"⚠️  Possible editing (score: {manip}/100)")

    if forensics.get("jpeg_ghost", {}).get("ghost_detected"):
        ghost_pct = forensics["jpeg_ghost"].get("ghost_pct", 0)
        if ghost_pct > 10:
            auth["score"] = min(20, auth["score"] + 10)
            auth["factors"].append(f"JPEG ghost at q{forensics['jpeg_ghost'].get('suspected_original_quality')}")
            highlights.append(f"👻 JPEG ghost: {ghost_pct:.0f}% of blocks re-saved")

    if not forensics.get("metadata_consistency", {}).get("consistent", True):
        auth["score"] = min(20, auth["score"] + 5)
        auth["factors"].append("Metadata inconsistency")

    if stego.get("suspicious"):
        auth["score"] = min(20, auth["score"] + 15)
        methods = stego.get("methods_triggered", [])
        auth["factors"].append(f"Steganography: {', '.join(methods)}")
        highlights.append(f"🔐 Hidden data detected: {', '.join(methods)}")

    # ── EXPOSURE (max 20) ─────────────────────────────────────────────────────
    exp = breakdown["exposure"]
    unique = reverse.get("total_unique_domains", 0)
    if unique >= 10:
        exp["score"] += 15
        exp["factors"].append(f"Found on {unique} domains (high exposure)")
        highlights.append(f"🔴 Image found on {unique} domains")
    elif unique > 0:
        exp["score"] += 8
        exp["factors"].append(f"Found on {unique} domain(s)")
        highlights.append(f"🟡 Image found on {unique} domain(s)")

    social_found = len(social.get("found", [])) if social else 0
    if social_found > 0:
        exp["score"] = min(20, exp["score"] + 5)
        exp["factors"].append(f"{social_found} social platforms found")
        if social_found >= 10:
            highlights.append(f"🌐 Found on {social_found} social platforms")

    breaches = social.get("hibp_breaches", []) if social else []
    if breaches:
        exp["score"] = min(20, exp["score"] + min(5, len(breaches)))
        exp["factors"].append(f"{len(breaches)} HIBP breach(es)")
        highlights.append(f"⚠️  {len(breaches)} data breach(es) found")

    # ── CONTENT (max 10) ──────────────────────────────────────────────────────
    cont = breakdown["content"]
    face_count = content.get("faces", {}).get("count", 0)
    if face_count > 0:
        cont["score"] += 5
        cont["factors"].append(f"{face_count} face(s)")

    if content.get("ocr", {}).get("text"):
        cont["score"] += 3
        cont["factors"].append(f"OCR text ({content['ocr'].get('word_count', 0)} words)")
        if not any("📝" in h for h in highlights):
            highlights.append(f"📝 Text extracted ({content['ocr'].get('word_count', 0)} words)")

    qr_count = content.get("qr_barcodes", {}).get("count", 0)
    if qr_count > 0:
        cont["score"] = min(10, cont["score"] + 5)
        cont["factors"].append(f"{qr_count} QR/barcode(s)")
        highlights.append(f"📱 QR/barcode decoded")

    if content.get("objects", {}).get("weapon_detected"):
        cont["score"] = min(10, cont["score"] + 5)
        cont["factors"].append("Weapon detected")
        highlights.append(f"⚠️  Weapon in image")

    if content.get("document_type", {}).get("document_detected"):
        cont["score"] = min(10, cont["score"] + 5)
        cont["factors"].append(f"Document: {content['document_type'].get('document_type')}")
        highlights.append(f"🪪 Document detected: {content['document_type'].get('document_type')}")

    # ── Total ──────────────────────────────────────────────────────────────────
    total = sum(min(v["score"], v["max"]) for v in breakdown.values())
    total = min(100, total)

    # Compute confidence + data richness
    filled_stages = sum(1 for k in ["metadata", "forensics", "content_analysis",
                                     "geolocation", "steganography", "social"]
                        if results.get(k))
    breakdown["confidence"] = "High" if total >= 60 else ("Medium" if total >= 30 else "Low")
    breakdown["data_richness"] = f"{filled_stages}/6 stages ran"

    return total, highlights, breakdown


# ── Rich Terminal Output ──────────────────────────────────────────────────────

def _color_score(score: int) -> str:
    if score >= 70: return "red"
    if score >= 40: return "yellow"
    return "green"


def _verdict_emoji(v: str) -> str:
    v = v or ""
    if "🚨" in v or "HIGH" in v or "HIGHLY" in v: return "🚨"
    if "⚠️" in v or "POSSIBLE" in v or "Possibly" in v: return "⚠️ "
    if "✅" in v or "Clean" in v or "Authentic" in v: return "✅"
    return "ℹ️ "


def print_terminal_report(results: dict, intel_score: int, highlights: list[str]):
    if not RICH_OK:
        print(json.dumps(results, indent=2, default=str))
        return

    c = Console()
    image_name = results.get("metadata", {}).get("file", {}).get("name", "Unknown")

    c.print()
    c.print(Rule(f"[bold cyan]🔍 ImageTrace 2.0 — Intelligence Report[/bold cyan]"))
    c.print(f"[dim]Image:[/dim] [bold]{image_name}[/bold]   "
            f"[dim]Scan time:[/dim] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.print()

    # Intel score panel
    color = _color_score(intel_score)
    score_bar = "█" * (intel_score // 5) + "░" * (20 - intel_score // 5)
    c.print(Panel(
        f"[{color} bold]{score_bar}  {intel_score}/100[/{color} bold]\n\n" +
        "\n".join(f"  {h}" for h in highlights),
        title="[bold white]INTEL SCORE[/bold white]",
        border_style=color,
        padding=(1, 2),
    ))
    c.print()

    # ── Stage 1: Metadata ───────────────────────────────────────────────────
    meta = results.get("metadata", {})
    t = Table(title="Stage 1 — Metadata", box=box.SIMPLE_HEAVY, show_header=True)
    t.add_column("Field", style="cyan", width=22)
    t.add_column("Value", style="white")

    exif = meta.get("exif", {})
    device = meta.get("device", {})
    gps = meta.get("gps", {})
    file_info = meta.get("file", {})

    t.add_row("File size", f"{file_info.get('size_bytes', 0):,} bytes")
    t.add_row("Dimensions", f"{exif.get('width_px', '?')} × {exif.get('height_px', '?')} px")
    t.add_row("Megapixels", str(exif.get("megapixels", "?")))
    t.add_row("Device", f"{device.get('make', '?')} {device.get('model', '')}")
    t.add_row("Device type", device.get("type", "?"))
    t.add_row("Software", device.get("software") or "—")
    t.add_row("Date taken", exif.get("datetime_original") or "—")
    t.add_row("ISO", exif.get("iso") or "—")
    t.add_row("Aperture", exif.get("aperture") or "—")
    t.add_row("Shutter speed", exif.get("shutter_speed") or "—")
    t.add_row("Lens", device.get("lens") or "—")

    if gps.get("latitude"):
        t.add_row("[green]GPS Latitude[/green]", str(gps["latitude"]))
        t.add_row("[green]GPS Longitude[/green]", str(gps["longitude"]))
        t.add_row("[green]GPS Altitude[/green]", f"{gps.get('altitude_m', '?')} m")
        t.add_row("[green bold]Maps Link[/green bold]", gps.get("maps_link", "—"))
    else:
        t.add_row("GPS", "[dim]None in EXIF[/dim]")

    for flag in meta.get("flags", []):
        t.add_row("[yellow]FLAG[/yellow]", flag)

    c.print(t)

    # ── Stage 2: Forensics ──────────────────────────────────────────────────
    forensics = results.get("forensics", {})
    manip = forensics.get("manipulation_score", 0)
    manip_color = _color_score(manip)
    c.print(Panel(
        f"[{manip_color} bold]{forensics.get('manipulation_verdict', '—')}[/{manip_color} bold]\n\n"
        f"  ELA Score:      {forensics.get('ela', {}).get('ela_score', 0)}/100  "
        f"({forensics.get('ela', {}).get('verdict', '—')})\n"
        f"  Clone Detection:{' ⚠️  ' + str(forensics.get('clone_detection', {}).get('clone_count', 0)) + ' regions' if forensics.get('clone_detection', {}).get('clone_detected') else ' ✅ None'}\n"
        f"  Noise Analysis: {forensics.get('noise_analysis', {}).get('verdict', '—')}\n"
        f"  AI/Deepfake:    {_fmt_ai(forensics.get('ai_detection', {}))}",
        title="Stage 2 — Forensics",
        border_style=manip_color,
    ))
    c.print()

    # ── Stage 3: Steganography ──────────────────────────────────────────────
    stego = results.get("steganography", {})
    stego_color = "red" if stego.get("suspicious") else "green"
    c.print(Panel(
        f"[{stego_color} bold]{stego.get('overall', '—')}[/{stego_color} bold]\n\n"
        f"  LSB:           {stego.get('lsb', {}).get('verdict', '—')}\n"
        f"  DCT:           {stego.get('dct', {}).get('verdict', '—')}\n"
        f"  Palette:       {stego.get('palette', {}).get('verdict', '—')}\n"
        f"  Embedded Files:{' ' + stego.get('embedded_file', {}).get('verdict', '—')}",
        title="Stage 3 — Steganography",
        border_style=stego_color,
    ))
    c.print()

    # ── Stage 4: Content ────────────────────────────────────────────────────
    content = results.get("content_analysis", {})
    c.print(Panel(
        f"  Faces detected:  {content.get('faces', {}).get('count', 0)}\n"
        f"  OCR text:        {content.get('ocr', {}).get('verdict', '—')}\n"
        f"  QR/Barcodes:     {content.get('qr_barcodes', {}).get('verdict', '—')}\n"
        f"  Objects:         {content.get('objects', {}).get('verdict', '—')}\n"
        f"  Image quality:   {content.get('quality', {}).get('sharpness_verdict', '—')} | "
        f"Brightness: {content.get('quality', {}).get('brightness_verdict', '—')}",
        title="Stage 4 — Content Analysis",
        border_style="cyan",
    ))

    # Show OCR text if found
    ocr_text = content.get("ocr", {}).get("text", "")
    if ocr_text:
        c.print(Panel(
            ocr_text[:500] + ("..." if len(ocr_text) > 500 else ""),
            title="[cyan]Extracted Text (OCR)[/cyan]",
            border_style="dim",
        ))
    c.print()

    # ── Stage 5: Geolocation ────────────────────────────────────────────────
    geo = results.get("geolocation", {})
    geo_color = "green" if geo.get("best_result") else "dim"
    best = geo.get("best_result") or {}
    c.print(Panel(
        f"[{geo_color} bold]{geo.get('overall_verdict', '—')}[/{geo_color} bold]\n\n"
        f"  Source:   {geo.get('source', '—')}\n"
        f"  Country:  {best.get('country', '—')}\n"
        f"  City:     {best.get('city', '—')}\n"
        f"  Maps:     {best.get('maps_link', '—')}",
        title="Stage 5 — Geolocation",
        border_style=geo_color,
    ))
    c.print()

    # ── Stage 6: Reverse Image Search ───────────────────────────────────────
    reverse = results.get("reverse_image_search", {})
    matches = reverse.get("aggregated_matches", [])
    if matches:
        t2 = Table(title="Stage 6 — Reverse Image Search Matches", box=box.SIMPLE)
        t2.add_column("Domain", style="cyan", width=30)
        t2.add_column("Engines", style="yellow", width=20)
        t2.add_column("Title", style="white")
        for m in matches[:10]:
            t2.add_row(
                m.get("domain", "?"),
                ", ".join(m.get("engines", [])),
                (m.get("title") or "")[:60],
            )
        c.print(t2)
    else:
        c.print(Panel("No matches found", title="Stage 6 — Reverse Image Search", border_style="dim"))
    c.print()

    # ── Stage 7: Face Search ────────────────────────────────────────────────
    face_search = results.get("face_search", {})
    if not face_search.get("confirmed"):
        c.print(Panel(
            "[yellow]Face search not performed.[/yellow]\n"
            "Run with [bold]--confirm-face-search[/bold] to submit faces to PimEyes, FaceCheck.ID, and Yandex.",
            title="Stage 7 — Face Recognition Search",
            border_style="yellow",
        ))
    else:
        for pf in face_search.get("per_face", []):
            c.print(Panel(
                f"[bold]{pf.get('verdict', '—')}[/bold]\n\n"
                + "\n".join(
                    f"  [{m.get('engine', '?')}] {m.get('domain', m.get('url', '?'))[:60]}"
                    for m in pf.get("aggregated_matches", [])[:8]
                ),
                title=f"Stage 7 — Face #{pf.get('face_index', 0) + 1} Search Results",
                border_style="magenta",
            ))
    c.print()

    c.print(Rule("[dim]End of Report[/dim]"))
    c.print()


# ── Markdown Report ───────────────────────────────────────────────────────────

def _to_md(results: dict, intel_score: int, highlights: list[str]) -> str:
    meta = results.get("metadata", {})
    forensics = results.get("forensics", {})
    stego = results.get("steganography", {})
    content = results.get("content_analysis", {})
    geo = results.get("geolocation", {})
    reverse = results.get("reverse_image_search", {})
    face_search = results.get("face_search", {})

    file_name = meta.get("file", {}).get("name", "Unknown")
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    gps = meta.get("gps", {})
    device = meta.get("device", {})
    exif = meta.get("exif", {})
    best_geo = geo.get("best_result") or {}
    matches = reverse.get("aggregated_matches", [])

    score_bar = "█" * (intel_score // 5) + "░" * (20 - intel_score // 5)

    lines = [
        f"# 🔍 ImageTrace 2.0 — Intelligence Report",
        f"",
        f"**Image:** `{file_name}`  ",
        f"**Scan date:** {ts}  ",
        f"**Intel Score:** `{score_bar}` **{intel_score}/100**",
        f"",
        f"---",
        f"",
        f"## 🎯 Key Findings",
        "",
        *[f"- {h}" for h in highlights],
        "",
        f"---",
        "",
        f"## Stage 1 — Metadata",
        "",
        f"| Field | Value |",
        f"|---|---|",
        f"| File size | {meta.get('file', {}).get('size_bytes', 0):,} bytes |",
        f"| Dimensions | {exif.get('width_px', '?')} × {exif.get('height_px', '?')} px |",
        f"| Device | {device.get('make', '?')} {device.get('model', '')} |",
        f"| Device type | {device.get('type', '?')} |",
        f"| Software | {device.get('software') or '—'} |",
        f"| Date taken | {exif.get('datetime_original') or '—'} |",
        f"| ISO | {exif.get('iso') or '—'} |",
        f"| Aperture | {exif.get('aperture') or '—'} |",
        f"| Shutter | {exif.get('shutter_speed') or '—'} |",
        f"| GPS Latitude | {gps.get('latitude', '—')} |",
        f"| GPS Longitude | {gps.get('longitude', '—')} |",
        f"| GPS Altitude | {gps.get('altitude_m', '—')} m |",
        f"| Maps link | {gps.get('maps_link') or '—'} |",
        "",
    ]

    if meta.get("flags"):
        lines += ["**Flags:**", ""] + [f"- {f}" for f in meta["flags"]] + [""]

    lines += [
        f"---",
        f"",
        f"## Stage 2 — Forensics",
        f"",
        f"**Verdict:** {forensics.get('manipulation_verdict', '—')}  ",
        f"**Manipulation Score:** {forensics.get('manipulation_score', 0)}/100",
        f"",
        f"| Check | Result |",
        f"|---|---|",
        f"| ELA | {forensics.get('ela', {}).get('verdict', '—')} (score: {forensics.get('ela', {}).get('ela_score', 0)}) |",
        f"| Clone Detection | {forensics.get('clone_detection', {}).get('verdict', '—')} |",
        f"| Noise Analysis | {forensics.get('noise_analysis', {}).get('verdict', '—')} |",
        f"| AI/Deepfake | {forensics.get('ai_detection', {}).get('skipped', '—') if 'skipped' in forensics.get('ai_detection', {}) else 'checked'} |",
        "",
        f"---",
        f"",
        f"## Stage 3 — Steganography",
        f"",
        f"**Overall:** {stego.get('overall', '—')}",
        f"",
        f"| Method | Result |",
        f"|---|---|",
        f"| LSB | {stego.get('lsb', {}).get('verdict', '—')} |",
        f"| DCT | {stego.get('dct', {}).get('verdict', '—')} |",
        f"| Palette | {stego.get('palette', {}).get('verdict', '—')} |",
        f"| Embedded File | {stego.get('embedded_file', {}).get('verdict', '—')} |",
        "",
        f"---",
        f"",
        f"## Stage 4 — Content Analysis",
        f"",
        f"- **Faces:** {content.get('faces', {}).get('count', 0)} detected",
        f"- **OCR:** {content.get('ocr', {}).get('verdict', '—')}",
        f"- **QR/Barcodes:** {content.get('qr_barcodes', {}).get('verdict', '—')}",
        f"- **Objects:** {content.get('objects', {}).get('verdict', '—')}",
        f"- **Sharpness:** {content.get('quality', {}).get('sharpness_verdict', '—')}",
        f"- **Brightness:** {content.get('quality', {}).get('brightness_verdict', '—')}",
        "",
    ]

    ocr_text = content.get("ocr", {}).get("text", "")
    if ocr_text:
        lines += [
            f"### Extracted Text",
            f"",
            f"```",
            ocr_text[:1000],
            f"```",
            "",
        ]

    qr_codes = content.get("qr_barcodes", {}).get("codes", [])
    if qr_codes:
        lines += ["### QR/Barcode Data", ""]
        for code in qr_codes:
            lines.append(f"- **{code.get('type')}:** `{code.get('data', '')}`")
        lines.append("")

    lines += [
        f"---",
        f"",
        f"## Stage 5 — Geolocation",
        f"",
        f"**{geo.get('overall_verdict', '—')}**",
        f"",
        f"| Field | Value |",
        f"|---|---|",
        f"| Source | {geo.get('source', '—')} |",
        f"| Country | {best_geo.get('country', '—')} |",
        f"| City | {best_geo.get('city', '—')} |",
        f"| Coordinates | {best_geo.get('lat', '—')}, {best_geo.get('lon', '—')} |",
        f"| Maps | {best_geo.get('maps_link', '—')} |",
        "",
        f"---",
        f"",
        f"## Stage 6 — Reverse Image Search",
        f"",
        f"**{reverse.get('verdict', '—')}**  ",
        f"**Unique domains:** {reverse.get('total_unique_domains', 0)}",
        "",
    ]

    if matches:
        lines += [
            "| Domain | Engines | Title |",
            "|---|---|---|",
        ]
        for m in matches[:15]:
            lines.append(
                f"| {m.get('domain', '?')} | {', '.join(m.get('engines', []))} | "
                f"{(m.get('title') or '')[:60]} |"
            )
        lines.append("")

    lines += [
        f"---",
        f"",
        f"## Stage 7 — Face Recognition Search",
        f"",
    ]

    if not face_search.get("confirmed"):
        lines.append("*Face search not performed. Run with `--confirm-face-search` to enable.*")
    else:
        for pf in face_search.get("per_face", []):
            lines += [
                f"**Face #{pf.get('face_index', 0) + 1}:** {pf.get('verdict', '—')}",
                "",
            ]
            for m in pf.get("aggregated_matches", [])[:10]:
                lines.append(
                    f"- [{m.get('engine', '?')}] `{m.get('domain', m.get('url', '?'))[:60]}`"
                )

    lines += [
        "",
        f"---",
        f"",
        f"*Generated by ImageTrace 2.0 — Autonomous Reverse Image OSINT*",
        f"*Scan completed: {ts}*",
        "",
    ]

    return "\n".join(lines)


# ── Discord Webhook ───────────────────────────────────────────────────────────

def _discord_alert(webhook_url: str, image_name: str, intel_score: int, highlights: list[str]):
    if not webhook_url:
        return
    color = 0xFF0000 if intel_score >= 70 else (0xFFAA00 if intel_score >= 40 else 0x00AA00)
    payload = {
        "embeds": [{
            "title": f"🔍 ImageTrace Report — {image_name}",
            "color": color,
            "fields": [
                {"name": "Intel Score", "value": f"**{intel_score}/100**", "inline": True},
                {"name": "Key Findings", "value": "\n".join(highlights[:8]) or "None", "inline": False},
            ],
            "footer": {"text": "ImageTrace 2.0 — Autonomous OSINT"},
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }]
    }
    try:
        requests.post(webhook_url, json=payload, timeout=10)
    except Exception:
        pass


# ── Telegram Webhook ──────────────────────────────────────────────────────────

def _telegram_alert(bot_token: str, chat_id: str, image_name: str,
                    intel_score: int, highlights: list[str]):
    if not bot_token or not chat_id:
        return
    score_bar = "█" * (intel_score // 10) + "░" * (10 - intel_score // 10)
    msg = (
        f"🔍 *ImageTrace Report*\n"
        f"Image: `{image_name}`\n"
        f"Score: `{score_bar}` *{intel_score}/100*\n\n"
        + "\n".join(highlights[:6])
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────

def _export_pdf_weasyprint(html_path: str, output_dir: str) -> str | None:
    """Export HTML dashboard to PDF via WeasyPrint (optional dep)."""
    try:
        from weasyprint import HTML
        pdf_path = str(Path(output_dir) / (Path(html_path).stem + ".pdf"))
        HTML(filename=html_path).write_pdf(pdf_path)
        return pdf_path
    except ImportError:
        return None
    except Exception:
        return None


def generate(
    results: dict,
    output_dir: str = ".",
    save_report: bool = True,
    save_json: bool = True,
    export_pdf: bool = False,
    discord_webhook: str = "",
    telegram_token: str = "",
    telegram_chat: str = "",
) -> dict:
    """
    Generate all report formats from combined stage results dict.
    Returns paths of written files.
    """
    discord_webhook  = discord_webhook  or os.environ.get("DISCORD_WEBHOOK", "")
    telegram_token   = telegram_token   or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat    = telegram_chat    or os.environ.get("TELEGRAM_CHAT_ID", "")

    intel_score, highlights, breakdown = _compute_intel_score(results)
    results["intel_score"] = intel_score
    results["highlights"] = highlights
    results["score_breakdown"] = breakdown

    image_name = results.get("metadata", {}).get("file", {}).get("name", "unknown")
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(image_name).stem

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    written = {}

    # Terminal output
    print_terminal_report(results, intel_score, highlights)

    # Markdown report
    if save_report:
        md_path = output_dir / f"report_{stem}_{ts}.md"
        md_content = _to_md(results, intel_score, highlights)
        md_path.write_text(md_content, encoding="utf-8")
        written["markdown"] = str(md_path)
        if RICH_OK:
            console.print(f"[green]✅ Report saved:[/green] {md_path}")

    # JSON export
    if save_json:
        json_path = output_dir / f"report_{stem}_{ts}.json"
        safe_results = json.loads(json.dumps(results, default=str))
        # Remove large b64 blobs from JSON export
        try:
            safe_results["forensics"]["ela"]["ela_image_b64"] = "<base64 omitted>"
        except Exception:
            pass
        try:
            safe_results["content_analysis"]["faces"]["crops_b64"] = []
        except Exception:
            pass
        json_path.write_text(json.dumps(safe_results, indent=2), encoding="utf-8")
        written["json"] = str(json_path)
        if RICH_OK:
            console.print(f"[green]✅ JSON saved:  [/green] {json_path}")

    # Webhooks
    if discord_webhook:
        _discord_alert(discord_webhook, image_name, intel_score, highlights)
        written["discord"] = "alert sent"
    if telegram_token and telegram_chat:
        _telegram_alert(telegram_token, telegram_chat, image_name, intel_score, highlights)
        written["telegram"] = "alert sent"

    # PDF export (requires weasyprint + dashboard HTML)
    if export_pdf and written.get("dashboard"):
        pdf_path = _export_pdf_weasyprint(written["dashboard"], str(output_dir))
        if pdf_path:
            written["pdf"] = pdf_path
            if RICH_OK:
                console.print(f"[green]✅ PDF saved:    [/green] {pdf_path}")
        else:
            if RICH_OK:
                console.print("[yellow]⚠️  PDF export skipped — install weasyprint: pip install weasyprint[/yellow]")

    return {"intel_score": intel_score, "highlights": highlights, "breakdown": breakdown, "files": written}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python stage8_report.py <results.json>")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        data = json.load(f)
    generate(data)
