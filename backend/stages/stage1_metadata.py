"""
Stage 1 — Metadata Extraction
Extracts full EXIF, GPS, device fingerprint, and hidden metadata from an image.
"""

import base64
import io
import os
import struct
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

try:
    import exifread
    EXIFREAD_OK = True
except ImportError:
    EXIFREAD_OK = False

try:
    import piexif
    PIEXIF_OK = True
except ImportError:
    PIEXIF_OK = False

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import iptcinfo3
    IPTCINFO_OK = True
except ImportError:
    IPTCINFO_OK = False


# ── GPS helpers ───────────────────────────────────────────────────────────────

def _to_decimal(dms_tag, ref_tag) -> float | None:
    """Convert DMS EXIF tag to decimal degrees."""
    try:
        vals = dms_tag.values
        d = float(vals[0].num) / float(vals[0].den)
        m = float(vals[1].num) / float(vals[1].den)
        s = float(vals[2].num) / float(vals[2].den)
        decimal = d + m / 60 + s / 3600
        if ref_tag and str(ref_tag.values) in ("S", "W"):
            decimal = -decimal
        return round(decimal, 6)
    except Exception:
        return None


def _parse_gps(tags: dict) -> dict:
    lat = _to_decimal(
        tags.get("GPS GPSLatitude"),
        tags.get("GPS GPSLatitudeRef"),
    )
    lon = _to_decimal(
        tags.get("GPS GPSLongitude"),
        tags.get("GPS GPSLongitudeRef"),
    )
    alt_tag = tags.get("GPS GPSAltitude")
    alt = None
    if alt_tag:
        try:
            v = alt_tag.values[0]
            alt = round(float(v.num) / float(v.den), 2)
            if tags.get("GPS GPSAltitudeRef") and tags["GPS GPSAltitudeRef"].values[0] == 1:
                alt = -alt
        except Exception:
            pass

    speed_tag = tags.get("GPS GPSSpeed")
    speed = None
    if speed_tag:
        try:
            v = speed_tag.values[0]
            speed = round(float(v.num) / float(v.den), 2)
        except Exception:
            pass

    result = {
        "latitude": lat,
        "longitude": lon,
        "altitude_m": alt,
        "speed": speed,
        "maps_link": (
            f"https://www.google.com/maps?q={lat},{lon}"
            if lat is not None and lon is not None
            else None
        ),
    }
    return result


# ── Device fingerprint ─────────────────────────────────────────────────────────

def _device_type(make: str, model: str) -> str:
    make_l = (make or "").lower()
    model_l = (model or "").lower()
    phones = ["iphone", "samsung", "pixel", "huawei", "xiaomi", "oppo",
              "oneplus", "motorola", "nokia", "sony xperia", "lg"]
    dslr_brands = ["canon", "nikon", "fujifilm", "pentax", "olympus",
                   "panasonic", "leica", "hasselblad", "phase one"]
    if any(p in make_l or p in model_l for p in phones):
        return "Smartphone"
    if any(b in make_l for b in dslr_brands):
        return "Camera (DSLR/Mirrorless)"
    if "gopro" in make_l or "gopro" in model_l:
        return "Action Camera"
    if "drone" in model_l or "mavic" in model_l or "phantom" in model_l:
        return "Drone"
    if make or model:
        return "Unknown Device"
    return "No Device Info"


# ── File-level stealth checks ──────────────────────────────────────────────────

def _check_appended_data(path: str) -> dict:
    """Check if extra data is appended after the image EOF marker."""
    result = {"appended_bytes": 0, "suspicious": False}
    try:
        with open(path, "rb") as f:
            data = f.read()
        # JPEG ends with FF D9
        if data[:2] == b'\xff\xd8':
            eof_idx = data.rfind(b'\xff\xd9')
            if eof_idx != -1 and eof_idx + 2 < len(data):
                extra = len(data) - (eof_idx + 2)
                result["appended_bytes"] = extra
                result["suspicious"] = extra > 0
        # PNG ends with IEND chunk (8 bytes after marker)
        elif data[:8] == b'\x89PNG\r\n\x1a\n':
            iend = data.rfind(b'IEND')
            if iend != -1:
                extra = len(data) - (iend + 8)
                result["appended_bytes"] = max(0, extra)
                result["suspicious"] = extra > 0
    except Exception:
        pass
    return result


# ── XMP extraction ────────────────────────────────────────────────────────────

def _extract_xmp(image_path: str) -> dict:
    """Parse XMP metadata embedded in image file."""
    result = {
        "creator": None, "creator_tool": None, "create_date": None,
        "modify_date": None, "credit": None, "description": None,
        "rights": None, "raw_xmp": None,
    }
    if not PIL_OK:
        return result
    try:
        with Image.open(image_path) as img:
            xmp_bytes = img.info.get("xmp")
        if not xmp_bytes:
            return result

        xmp_str = xmp_bytes.decode("utf-8", errors="replace") if isinstance(xmp_bytes, bytes) else xmp_bytes
        result["raw_xmp"] = xmp_str[:2000]

        # Strip XMP packet wrapper if present
        start = xmp_str.find("<")
        if start > 0:
            xmp_str = xmp_str[start:]

        ns = {
            "dc": "http://purl.org/dc/elements/1.1/",
            "xmp": "http://ns.adobe.com/xap/1.0/",
            "photoshop": "http://ns.adobe.com/photoshop/1.0/",
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        }
        root = ET.fromstring(xmp_str)

        def _find_text(tag_path):
            try:
                el = root.find(".//" + tag_path, ns)
                if el is not None:
                    # Value might be direct text or inside rdf:Alt/rdf:Seq/rdf:li
                    if el.text and el.text.strip():
                        return el.text.strip()
                    li = el.find(".//rdf:li", ns)
                    if li is not None and li.text:
                        return li.text.strip()
            except Exception:
                pass
            return None

        result["creator"] = _find_text("dc:creator") or _find_text("xmp:creator")
        result["creator_tool"] = _find_text("xmp:CreatorTool")
        result["create_date"] = _find_text("xmp:CreateDate")
        result["modify_date"] = _find_text("xmp:ModifyDate")
        result["credit"] = _find_text("photoshop:Credit")
        result["description"] = _find_text("dc:description")
        result["rights"] = _find_text("dc:rights") or _find_text("xmp:Rights")
    except Exception:
        pass
    return result


# ── IPTC extraction ────────────────────────────────────────────────────────────

def _extract_iptc(image_path: str) -> dict:
    """Extract IPTC metadata (news wire standard, used by agencies/photojournalists)."""
    result = {
        "author": None, "caption": None, "credit": None,
        "keywords": [], "city": None, "state": None,
        "country": None, "headline": None, "source": None,
    }
    if not IPTCINFO_OK:
        return result
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            info = iptcinfo3.IPTCInfo(image_path, force=True)

        def _val(key):
            v = info.data.get(key)
            if v is None:
                return None
            if isinstance(v, list):
                return v[0].decode("utf-8", errors="replace") if v else None
            return v.decode("utf-8", errors="replace") if isinstance(v, bytes) else str(v)

        def _list(key):
            v = info.data.get(key)
            if not v:
                return []
            if isinstance(v, list):
                return [x.decode("utf-8", errors="replace") if isinstance(x, bytes) else str(x) for x in v]
            return [v.decode("utf-8", errors="replace") if isinstance(v, bytes) else str(v)]

        result["author"] = _val(80)       # By-line
        result["caption"] = _val(120)     # Caption/Abstract
        result["credit"] = _val(110)      # Credit
        result["keywords"] = _list(25)    # Keywords
        result["city"] = _val(90)         # City
        result["state"] = _val(95)        # Province/State
        result["country"] = _val(101)     # Country Name
        result["headline"] = _val(105)    # Headline
        result["source"] = _val(115)      # Source
    except Exception:
        pass
    return result


# ── ICC profile extraction ─────────────────────────────────────────────────────

def _extract_icc_profile(image_path: str) -> dict:
    """Parse ICC color profile header for device/workflow hints."""
    result = {
        "profile_name": None, "device_class": None,
        "color_space": None, "rendering_intent": None, "osint_hint": None,
    }
    if not PIL_OK:
        return result
    try:
        with Image.open(image_path) as img:
            icc_bytes = img.info.get("icc_profile")
        if not icc_bytes or len(icc_bytes) < 128:
            return result

        # ICC profile header layout (bytes 0-127)
        profile_size = struct.unpack(">I", icc_bytes[0:4])[0]
        device_class_raw = icc_bytes[12:16].decode("ascii", errors="replace").strip()
        color_space_raw = icc_bytes[16:20].decode("ascii", errors="replace").strip()
        rendering_intent_raw = struct.unpack(">I", icc_bytes[64:68])[0]

        class_map = {"scnr": "Scanner", "mntr": "Display", "prtr": "Printer",
                     "link": "DeviceLink", "spac": "ColorSpace", "abst": "Abstract", "nmcl": "Named"}
        ri_map = {0: "Perceptual", 1: "Relative Colorimetric", 2: "Saturation", 3: "Absolute Colorimetric"}

        result["device_class"] = class_map.get(device_class_raw, device_class_raw)
        result["color_space"] = color_space_raw
        result["rendering_intent"] = ri_map.get(rendering_intent_raw, str(rendering_intent_raw))

        # Try to get profile description tag (tag signature "desc" at offset 128+)
        try:
            tag_count = struct.unpack(">I", icc_bytes[128:132])[0]
            for i in range(min(tag_count, 50)):
                offset = 132 + i * 12
                sig = icc_bytes[offset:offset+4].decode("ascii", errors="replace")
                tag_offset = struct.unpack(">I", icc_bytes[offset+4:offset+8])[0]
                tag_size = struct.unpack(">I", icc_bytes[offset+8:offset+12])[0]
                if sig == "desc" and tag_size > 12:
                    raw = icc_bytes[tag_offset:tag_offset+tag_size]
                    type_sig = raw[0:4].decode("ascii", errors="replace")
                    if type_sig == "desc":
                        name_len = struct.unpack(">I", raw[8:12])[0]
                        name = raw[12:12+name_len].decode("ascii", errors="replace").rstrip("\x00")
                        result["profile_name"] = name
                    elif type_sig == "mluc":
                        name = raw[28:].decode("utf-16-be", errors="replace").rstrip("\x00")
                        result["profile_name"] = name[:64]
                    break
        except Exception:
            pass

        # OSINT hint from profile name
        name = (result["profile_name"] or "").lower()
        if "display p3" in name or "dci-p3" in name:
            result["osint_hint"] = "Display P3 → likely Apple device (iPhone/Mac)"
        elif "adobe rgb" in name:
            result["osint_hint"] = "Adobe RGB → professional photography workflow"
        elif "srgb" in name or "s-rgb" in name:
            result["osint_hint"] = "sRGB → standard consumer device"
        elif "prophoto" in name:
            result["osint_hint"] = "ProPhoto RGB → high-end professional post-processing"
        elif "bt.2020" in name or "bt2020" in name:
            result["osint_hint"] = "BT.2020 → HDR content, modern high-end device"
        elif "cmyk" in color_space_raw.lower():
            result["osint_hint"] = "CMYK color space → prepared for print publication"
    except Exception:
        pass
    return result


# ── Thumbnail extraction ───────────────────────────────────────────────────────

def _extract_thumbnail(image_path: str) -> dict:
    """Extract embedded EXIF thumbnail and check for forensic discrepancies."""
    result = {
        "has_thumbnail": False, "thumbnail_b64": None,
        "thumbnail_size": None, "thumbnail_differs": False, "forensic_flag": None,
    }
    if not PIEXIF_OK or not PIL_OK:
        return result
    try:
        exif_dict = piexif.load(image_path)
        thumb_bytes = exif_dict.get("thumbnail")
        if not thumb_bytes:
            return result

        result["has_thumbnail"] = True
        result["thumbnail_b64"] = base64.b64encode(thumb_bytes).decode()

        # Open thumbnail to get dimensions
        thumb_img = Image.open(io.BytesIO(thumb_bytes))
        t_w, t_h = thumb_img.size
        result["thumbnail_size"] = [t_w, t_h]

        # Compare aspect ratio with main image
        with Image.open(image_path) as main_img:
            m_w, m_h = main_img.size

        if m_w > 0 and t_w > 0:
            main_ratio = m_w / m_h
            thumb_ratio = t_w / t_h
            diff_pct = abs(main_ratio - thumb_ratio) / main_ratio * 100
            if diff_pct > 5:
                result["thumbnail_differs"] = True
                result["forensic_flag"] = (
                    f"⚠️  Thumbnail aspect ratio differs from main image by {diff_pct:.1f}% "
                    f"— image may have been cropped after capture"
                )
    except Exception:
        pass
    return result


# ── Resolution consistency check ──────────────────────────────────────────────

def _check_resolution_consistency(exif: dict, actual_w: int, actual_h: int) -> dict:
    """Compare EXIF-stated dimensions vs actual PIL-measured dimensions."""
    result = {
        "consistent": True, "exif_stated_w": None, "exif_stated_h": None,
        "actual_w": actual_w, "actual_h": actual_h, "flag": None,
    }
    try:
        stated_w = exif.get("PixelXDimension") or exif.get("width_px")
        stated_h = exif.get("PixelYDimension") or exif.get("height_px")
        if stated_w and stated_h and actual_w and actual_h:
            result["exif_stated_w"] = int(stated_w)
            result["exif_stated_h"] = int(stated_h)
            diff_w = abs(actual_w - int(stated_w)) / max(actual_w, 1) * 100
            diff_h = abs(actual_h - int(stated_h)) / max(actual_h, 1) * 100
            if diff_w > 20 or diff_h > 20:
                result["consistent"] = False
                result["flag"] = (
                    f"⚠️  EXIF states {stated_w}×{stated_h}px but actual is {actual_w}×{actual_h}px "
                    f"— resized without updating EXIF"
                )
    except Exception:
        pass
    return result


# ── Main extraction ────────────────────────────────────────────────────────────

def extract(image_path: str) -> dict:
    """
    Extract all metadata from image_path.
    Returns a structured dict with all findings.
    """
    path = Path(image_path)
    result = {
        "stage": "metadata",
        "file": {
            "name": path.name,
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "extension": path.suffix.lower(),
            "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat()
                        if path.exists() else None,
        },
        "exif": {},
        "gps": {},
        "device": {},
        "xmp": {},
        "iptc": {},
        "icc_profile": {},
        "thumbnail": {},
        "resolution_check": {},
        "flags": [],
        "warnings": [],
        "raw_tags": {},
    }

    if not path.exists():
        result["warnings"].append("File not found.")
        return result

    # ── PIL basic info ──────────────────────────────────────────────────────
    if PIL_OK:
        try:
            with Image.open(image_path) as img:
                result["exif"]["image_format"] = img.format
                result["exif"]["image_mode"] = img.mode
                result["exif"]["width_px"] = img.width
                result["exif"]["height_px"] = img.height
                result["exif"]["megapixels"] = round(
                    img.width * img.height / 1_000_000, 2
                )
        except Exception as e:
            result["warnings"].append(f"PIL open failed: {e}")

    # ── exifread full tag dump ──────────────────────────────────────────────
    if EXIFREAD_OK:
        try:
            with open(image_path, "rb") as f:
                tags = exifread.process_file(f, details=True)

            # Store human-readable raw tags
            result["raw_tags"] = {k: str(v) for k, v in tags.items()}

            # Camera / device
            make  = str(tags.get("Image Make",  "")).strip()
            model = str(tags.get("Image Model", "")).strip()
            software = str(tags.get("Image Software", "")).strip()
            lens = str(tags.get("EXIF LensModel", tags.get("MakerNote LensModel", ""))).strip()
            serial = str(tags.get("MakerNote SerialNumber",
                                  tags.get("EXIF BodySerialNumber", ""))).strip()

            result["device"] = {
                "make": make or None,
                "model": model or None,
                "serial_number": serial or None,
                "lens": lens or None,
                "software": software or None,
                "type": _device_type(make, model),
            }

            # Timestamps
            dt_orig = str(tags.get("EXIF DateTimeOriginal", "")).strip()
            dt_dig  = str(tags.get("EXIF DateTimeDigitized", "")).strip()
            dt_mod  = str(tags.get("Image DateTime", "")).strip()
            result["exif"]["datetime_original"]  = dt_orig  or None
            result["exif"]["datetime_digitized"] = dt_dig   or None
            result["exif"]["datetime_modified"]  = dt_mod   or None

            # Camera settings
            result["exif"]["iso"]           = str(tags.get("EXIF ISOSpeedRatings", "")).strip() or None
            result["exif"]["aperture"]      = str(tags.get("EXIF FNumber", "")).strip() or None
            result["exif"]["shutter_speed"] = str(tags.get("EXIF ExposureTime", "")).strip() or None
            result["exif"]["focal_length"]  = str(tags.get("EXIF FocalLength", "")).strip() or None
            result["exif"]["flash"]         = str(tags.get("EXIF Flash", "")).strip() or None
            result["exif"]["white_balance"] = str(tags.get("EXIF WhiteBalance", "")).strip() or None
            result["exif"]["exposure_mode"] = str(tags.get("EXIF ExposureMode", "")).strip() or None
            result["exif"]["metering_mode"] = str(tags.get("EXIF MeteringMode", "")).strip() or None

            # Copyright / author
            result["exif"]["artist"]    = str(tags.get("Image Artist", "")).strip() or None
            result["exif"]["copyright"] = str(tags.get("Image Copyright", "")).strip() or None
            result["exif"]["user_comment"] = str(tags.get("EXIF UserComment", "")).strip() or None

            # GPS
            if any(k.startswith("GPS") for k in tags):
                result["gps"] = _parse_gps(tags)
                if result["gps"]["maps_link"]:
                    result["flags"].append("📍 GPS coordinates found")
            else:
                result["gps"] = {"note": "No GPS data in EXIF"}

            # Edit detection
            if software and any(s in software.lower() for s in
                                ["photoshop", "lightroom", "gimp", "affinity",
                                 "snapseed", "facetune", "vsco"]):
                result["flags"].append(
                    f"⚠️  Editing software detected: {software}"
                )

        except Exception as e:
            result["warnings"].append(f"exifread failed: {e}")
    else:
        result["warnings"].append("exifread not installed — limited metadata extraction.")

    # ── Metadata stripped check ─────────────────────────────────────────────
    if not result["raw_tags"] and path.suffix.lower() in (".jpg", ".jpeg"):
        result["flags"].append(
            "🚩 JPEG with NO EXIF metadata — likely stripped (could be evidence of intentional scrubbing)"
        )

    # ── Appended data check ─────────────────────────────────────────────────
    appended = _check_appended_data(image_path)
    result["file"]["appended_bytes"] = appended["appended_bytes"]
    if appended["suspicious"]:
        result["flags"].append(
            f"🚨 {appended['appended_bytes']} bytes of data appended AFTER image EOF — possible hidden file"
        )

    # ── XMP metadata ─────────────────────────────────────────────────────────
    xmp = _extract_xmp(image_path)
    result["xmp"] = xmp
    if xmp.get("creator"):
        result["flags"].append(f"👤 XMP Creator: {xmp['creator']}")
    if xmp.get("creator_tool") and not result["device"].get("software"):
        # Merge into device software if not already set from EXIF
        if result["device"]:
            result["device"]["software"] = result["device"].get("software") or xmp["creator_tool"]

    # ── IPTC metadata ─────────────────────────────────────────────────────────
    iptc = _extract_iptc(image_path)
    result["iptc"] = iptc
    if iptc.get("author"):
        result["flags"].append(f"👤 IPTC Author: {iptc['author']}")
    if iptc.get("city") or iptc.get("country"):
        loc_parts = [p for p in [iptc.get("city"), iptc.get("state"), iptc.get("country")] if p]
        result["flags"].append(f"📍 IPTC Location: {', '.join(loc_parts)}")

    # ── ICC profile ───────────────────────────────────────────────────────────
    icc = _extract_icc_profile(image_path)
    result["icc_profile"] = icc
    if icc.get("osint_hint"):
        result["flags"].append(f"🎨 ICC Profile: {icc['osint_hint']}")

    # ── Thumbnail forensics ───────────────────────────────────────────────────
    thumb = _extract_thumbnail(image_path)
    result["thumbnail"] = thumb
    if thumb.get("forensic_flag"):
        result["flags"].append(thumb["forensic_flag"])

    # ── Resolution consistency ────────────────────────────────────────────────
    actual_w = result["exif"].get("width_px")
    actual_h = result["exif"].get("height_px")
    if actual_w and actual_h:
        res_check = _check_resolution_consistency(result["exif"], actual_w, actual_h)
        result["resolution_check"] = res_check
        if res_check.get("flag"):
            result["flags"].append(res_check["flag"])

    return result


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python stage1_metadata.py <image>")
        sys.exit(1)
    data = extract(sys.argv[1])
    print(json.dumps(data, indent=2, default=str))
