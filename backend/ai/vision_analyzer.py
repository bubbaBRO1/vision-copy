"""Vision LLM analysis — send image to llava:13b or Claude claude-sonnet-4-6 for structured description."""
import base64
import json
import os
from pathlib import Path
from typing import Any
from ai.prompts import VISION_ANALYSIS_PROMPT

try:
    import requests as _requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
_ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

_VISION_PROMPT = VISION_ANALYSIS_PROMPT + """

Provide a structured JSON response:
{
  "description": "1-2 sentence overview",
  "people": [{"count": int, "description": "appearance, clothing, estimated age/gender if visible"}],
  "location_clues": ["environmental clues: signage, architecture, vegetation, terrain, landmarks"],
  "text_visible": ["all visible text"],
  "objects_of_interest": ["notable objects, devices, vehicles, logos"],
  "time_clues": ["clues about time of day or season"],
  "anomalies": ["anything unusual or suspicious"],
  "confidence_notes": "what you are uncertain about",
  "location_inference": "Possible location or Unknown — with confidence level"
}
Respond ONLY with valid JSON. No markdown code blocks."""


def _image_to_b64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _analyze_ollama(image_path: str) -> dict[str, Any]:
    """Send image to llava:13b via Ollama."""
    if not REQUESTS_OK:
        return {"error": "requests not installed"}
    b64 = _image_to_b64(image_path)
    payload = {
        "model": "llava:13b",
        "prompt": _VISION_PROMPT,
        "images": [b64],
        "stream": False,
        "format": "json",
    }
    try:
        r = _requests.post(f"{_OLLAMA_URL}/api/generate", json=payload, timeout=120)
        if r.status_code == 200:
            raw = r.json().get("response", "")
            return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw_response": r.json().get("response", ""), "parse_error": True}
    except Exception as e:
        return {"error": str(e)}
    return {"error": f"Ollama returned {r.status_code}"}


def _analyze_claude(image_path: str) -> dict[str, Any]:
    """Fallback: send image to Claude claude-sonnet-4-6 via Anthropic API."""
    if not _ANTHROPIC_KEY or not REQUESTS_OK:
        return {"error": "No Anthropic API key"}
    b64 = _image_to_b64(image_path)
    suffix = Path(image_path).suffix.lower()
    media_type_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
    media_type = media_type_map.get(suffix, "image/jpeg")
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": _VISION_PROMPT},
                ],
            }
        ],
    }
    try:
        r = _requests.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers={"x-api-key": _ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            timeout=60,
        )
        if r.status_code == 200:
            text = r.json()["content"][0]["text"]
            return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_response": text, "parse_error": True}
    except Exception as e:
        return {"error": str(e)}
    return {"error": f"Claude API returned {r.status_code}"}


def analyze_image(image_path: str) -> dict[str, Any]:
    """Analyze image with vision LLM. Tries Ollama first, falls back to Claude."""
    # Try Ollama llava first
    if REQUESTS_OK:
        try:
            r = _requests.get(f"{_OLLAMA_URL}/api/tags", timeout=5)
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                if any("llava" in m for m in models):
                    result = _analyze_ollama(image_path)
                    if "error" not in result:
                        result["_source"] = "ollama/llava"
                        return result
        except Exception:
            pass

    # Fallback to Claude
    result = _analyze_claude(image_path)
    result["_source"] = "anthropic/claude-sonnet-4-6"
    return result
