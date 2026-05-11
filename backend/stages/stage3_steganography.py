"""
Stage 3 — Steganography Scanner
Detects hidden data using:
  - LSB (Least Significant Bit) analysis across RGB channels
  - DCT coefficient analysis for JPEG steganography
  - Appended data / file-within-file detection
  - Palette/color histogram analysis (GIF / PNG)
  - Chi-square statistical test for LSB randomness
"""

import io
import os
import math
import struct
import hashlib
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
    PIL_OK = True
except ImportError:
    PIL_OK = False


# ── LSB Extraction ─────────────────────────────────────────────────────────────

def _extract_lsb_bits(arr: "np.ndarray", channel: int = 0) -> bytes:
    """Extract the LSBs of a given channel as a byte string."""
    flat = arr[:, :, channel].flatten()
    bits = (flat & 1).astype(np.uint8)
    # Pack bits into bytes
    n_bytes = len(bits) // 8
    result = bytearray()
    for i in range(n_bytes):
        byte = 0
        for b in range(8):
            byte = (byte << 1) | int(bits[i * 8 + b])
        result.append(byte)
    return bytes(result)


def _chi_square_lsb(arr: "np.ndarray", channel: int = 0) -> float:
    """
    Chi-square test on LSBs of a channel.
    If LSBs are truly random (steganography present), chi² ≈ expected.
    Returns p-value proxy: lower means more suspicious.
    """
    flat = arr[:, :, channel].flatten()
    lsbs = flat & 1
    n = len(lsbs)
    if n < 100:
        return 1.0
    observed_0 = int(np.sum(lsbs == 0))
    observed_1 = int(np.sum(lsbs == 1))
    expected = n / 2
    chi2 = ((observed_0 - expected) ** 2 + (observed_1 - expected) ** 2) / expected
    # Approximate p-value for 1 df using survival function approximation
    # chi2 > 3.84 → p < 0.05 (not suspicious: natural)
    # chi2 < 0.5  → suspiciously uniform (too random = hidden data)
    return round(chi2, 4)


def _lsb_entropy(data: bytes) -> float:
    """Shannon entropy of byte string. High entropy (≈8) suggests encrypted/compressed hidden data."""
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    entropy = 0.0
    n = len(data)
    for c in counts:
        if c > 0:
            p = c / n
            entropy -= p * math.log2(p)
    return round(entropy, 4)


def _lsb_analysis(image_path: str) -> dict:
    result = {
        "method": "LSB",
        "suspicious": False,
        "channels": {},
        "hidden_text_preview": None,
        "verdict": "No hidden data detected",
    }
    if not PIL_OK:
        result["error"] = "Pillow/numpy not installed"
        return result
    try:
        img = Image.open(image_path).convert("RGB")
        arr = np.array(img)

        channel_names = ["Red", "Green", "Blue"]
        suspicious_channels = []

        for i, name in enumerate(channel_names):
            lsb_bytes = _extract_lsb_bits(arr, i)
            entropy = _lsb_entropy(lsb_bytes)
            chi2 = _chi_square_lsb(arr, i)

            # Heuristic: high entropy (>7.5) + low chi2 (<1.0) = suspicious
            suspicious = entropy > 7.2 and chi2 < 1.5

            result["channels"][name] = {
                "entropy": entropy,
                "chi2": chi2,
                "suspicious": suspicious,
            }
            if suspicious:
                suspicious_channels.append(name)

        if suspicious_channels:
            result["suspicious"] = True
            result["verdict"] = (
                f"⚠️  Possible LSB steganography in {', '.join(suspicious_channels)} channel(s)"
            )
            # Try to extract readable text from Red channel LSBs
            lsb_bytes = _extract_lsb_bits(arr, 0)
            try:
                preview = lsb_bytes[:200].decode("utf-8", errors="ignore")
                printable = "".join(c for c in preview if c.isprintable())
                if len(printable) > 10:
                    result["hidden_text_preview"] = printable[:100]
            except Exception:
                pass

    except Exception as e:
        result["error"] = str(e)
    return result


# ── DCT Analysis (JPEG) ───────────────────────────────────────────────────────

def _dct_analysis(image_path: str) -> dict:
    """
    JPEG DCT steganography heuristic.
    Compares the distribution of DCT coefficients. JSteg / OutGuess embed
    data by modifying DCT LSBs, which creates detectable statistical anomalies.
    We approximate this by comparing saved vs. re-saved coefficient distributions.
    """
    result = {
        "method": "DCT",
        "applicable": False,
        "suspicious": False,
        "verdict": "Not a JPEG or analysis skipped",
    }
    if not PIL_OK:
        return result

    path = Path(image_path)
    if path.suffix.lower() not in (".jpg", ".jpeg"):
        result["verdict"] = "Not a JPEG — DCT analysis not applicable"
        return result

    result["applicable"] = True
    try:
        # Re-save at slightly different quality and compare sizes
        # JSteg-encoded images often compress differently due to coefficient parity changes
        img = Image.open(image_path).convert("RGB")
        original_size = path.stat().st_size

        buf1 = io.BytesIO()
        img.save(buf1, format="JPEG", quality=85)
        size85 = len(buf1.getvalue())

        buf2 = io.BytesIO()
        img.save(buf2, format="JPEG", quality=75)
        size75 = len(buf2.getvalue())

        # Expected compression ratio between q=85 and q=75
        expected_ratio = 0.75
        actual_ratio = size75 / size85 if size85 > 0 else 1

        deviation = abs(actual_ratio - expected_ratio)

        result["original_size"] = original_size
        result["ratio_85_to_75"] = round(actual_ratio, 4)
        result["deviation"] = round(deviation, 4)

        if deviation > 0.15:
            result["suspicious"] = True
            result["verdict"] = (
                "⚠️  Unusual DCT compression ratio — possible JPEG steganography (JSteg/OutGuess)"
            )
        else:
            result["verdict"] = "DCT coefficients appear normal"

    except Exception as e:
        result["error"] = str(e)
    return result


# ── Palette Analysis (PNG/GIF) ─────────────────────────────────────────────────

def _palette_analysis(image_path: str) -> dict:
    """
    For palette-mode images (GIF, indexed PNG): check if palette entries
    are suspiciously close in color (classic GIF steganography hides data
    by slightly tweaking palette entries that appear identical visually).
    """
    result = {
        "method": "Palette",
        "applicable": False,
        "suspicious": False,
        "verdict": "Not a palette image",
    }
    if not PIL_OK:
        return result
    try:
        img = Image.open(image_path)
        if img.mode not in ("P", "L"):
            result["verdict"] = "Not a palette/indexed image"
            return result

        result["applicable"] = True
        palette = img.getpalette()
        if not palette:
            return result

        # Group into RGB triplets
        colors = [(palette[i], palette[i+1], palette[i+2])
                  for i in range(0, len(palette), 3)]

        # Count near-duplicate colors (differ by ≤4 in any channel)
        near_dupes = 0
        for i in range(len(colors)):
            for j in range(i+1, len(colors)):
                d = max(abs(colors[i][k] - colors[j][k]) for k in range(3))
                if d <= 4:
                    near_dupes += 1

        result["palette_size"] = len(colors)
        result["near_duplicate_pairs"] = near_dupes

        if near_dupes > 5:
            result["suspicious"] = True
            result["verdict"] = (
                f"⚠️  {near_dupes} near-duplicate palette pairs — possible palette steganography"
            )
        else:
            result["verdict"] = "Palette appears normal"

    except Exception as e:
        result["error"] = str(e)
    return result


# ── Appended / Embedded File Detection ───────────────────────────────────────

MAGIC_BYTES = {
    b'\x50\x4b\x03\x04': "ZIP archive",
    b'\x50\x4b\x05\x06': "ZIP archive (empty)",
    b'\x25\x50\x44\x46': "PDF document",
    b'\x89\x50\x4e\x47': "PNG image",
    b'\xff\xd8\xff':     "JPEG image",
    b'\x47\x49\x46\x38': "GIF image",
    b'\x52\x61\x72\x21': "RAR archive",
    b'\x37\x7a\xbc\xaf': "7-Zip archive",
    b'\x1f\x8b':         "Gzip compressed",
    b'\x42\x5a\x68':     "Bzip2 compressed",
    b'\x4d\x5a':         "Windows EXE",
    b'\x7f\x45\x4c\x46': "Linux ELF binary",
}


def _embedded_file_scan(image_path: str) -> dict:
    """
    Scan image bytes for embedded file magic numbers (polyglot files).
    Also checks for appended data after the image EOF marker.
    """
    result = {
        "method": "Embedded File",
        "suspicious": False,
        "embedded_files": [],
        "appended_bytes": 0,
        "verdict": "No embedded files detected",
    }
    try:
        with open(image_path, "rb") as f:
            data = f.read()

        # Skip the first 8 bytes (image header) and scan the rest
        scan_data = data[8:]
        found = []
        for magic, label in MAGIC_BYTES.items():
            idx = scan_data.find(magic)
            if idx != -1:
                found.append({
                    "type": label,
                    "offset": idx + 8,
                    "magic_hex": magic.hex(),
                })

        if found:
            result["suspicious"] = True
            result["embedded_files"] = found
            types = ", ".join(f["type"] for f in found)
            result["verdict"] = f"🚨 Embedded file(s) detected: {types}"

        # Appended bytes after EOF
        suffix = Path(image_path).suffix.lower()
        eof_marker = None
        if suffix in (".jpg", ".jpeg"):
            eof_marker = b'\xff\xd9'
        elif suffix == ".png":
            eof_marker = b'IEND\xaeB`\x82'

        if eof_marker:
            eof_idx = data.rfind(eof_marker)
            if eof_idx != -1:
                extra = len(data) - (eof_idx + len(eof_marker))
                if extra > 0:
                    result["appended_bytes"] = extra
                    result["suspicious"] = True
                    result["verdict"] += (
                        f" | 🚨 {extra} bytes appended after EOF"
                    )

    except Exception as e:
        result["error"] = str(e)
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def scan(image_path: str) -> dict:
    """Run all steganography detection methods on image_path."""
    lsb     = _lsb_analysis(image_path)
    dct     = _dct_analysis(image_path)
    palette = _palette_analysis(image_path)
    embedded = _embedded_file_scan(image_path)

    suspicious_methods = []
    if lsb.get("suspicious"):     suspicious_methods.append("LSB")
    if dct.get("suspicious"):     suspicious_methods.append("DCT")
    if palette.get("suspicious"): suspicious_methods.append("Palette")
    if embedded.get("suspicious"): suspicious_methods.append("Embedded File")

    overall = "✅ No steganography detected"
    if suspicious_methods:
        overall = f"🚨 HIDDEN DATA LIKELY — triggered: {', '.join(suspicious_methods)}"

    return {
        "stage": "steganography",
        "overall": overall,
        "suspicious": bool(suspicious_methods),
        "methods_triggered": suspicious_methods,
        "lsb": lsb,
        "dct": dct,
        "palette": palette,
        "embedded_file": embedded,
    }


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python stage3_steganography.py <image>")
        sys.exit(1)
    print(json.dumps(scan(sys.argv[1]), indent=2, default=str))
