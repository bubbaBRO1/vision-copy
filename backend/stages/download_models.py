"""Download YOLO model files if not present. Run on startup or manually."""
import os
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"

MODELS = {
    "yolov8n.onnx": "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.onnx",
    "yolov8n-face.onnx": "https://github.com/akanametov/yolo-face/releases/download/v0.0.0/yolov8n-face.onnx",
}


def _download(url: str, dest: Path) -> None:
    print(f"Downloading {dest.name}…", flush=True)
    tmp = dest.with_suffix(".tmp")
    try:
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(dest)
        size_mb = dest.stat().st_size / 1_048_576
        print(f"  ✓ {dest.name} ({size_mb:.1f} MB)")
    except Exception as e:
        tmp.unlink(missing_ok=True)
        print(f"  ✗ Failed to download {dest.name}: {e}", file=sys.stderr)


def ensure_models(force: bool = False) -> None:
    MODELS_DIR.mkdir(exist_ok=True)
    for filename, url in MODELS.items():
        dest = MODELS_DIR / filename
        if dest.exists() and not force:
            continue
        _download(url, dest)


if __name__ == "__main__":
    force = "--force" in sys.argv
    ensure_models(force=force)
    print("Done.")
