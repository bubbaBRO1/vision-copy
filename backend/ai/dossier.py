"""Auto dossier generator — synthesize all stage results into an executive intelligence report."""
import json
import os
from typing import Any
from ai.prompts import DOSSIER_PROMPT

try:
    import requests as _requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
_ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

_DOSSIER_SYSTEM = DOSSIER_PROMPT


def _summarize_results(results: dict) -> str:
    """Create a condensed summary of all stage results for the LLM prompt."""
    lines = []
    for stage_name, data in results.items():
        if isinstance(data, dict) and data.get("skipped"):
            continue
        if isinstance(data, dict) and data.get("error"):
            continue
        lines.append(f"\n### {stage_name}")
        # Truncate large data to avoid token overflow
        serialized = json.dumps(data, default=str, indent=2)
        if len(serialized) > 2000:
            serialized = serialized[:2000] + "\n... (truncated)"
        lines.append(serialized)
    return "\n".join(lines)


def _generate_ollama(prompt: str) -> str:
    payload = {"model": "mistral:7b", "prompt": prompt, "stream": False}
    try:
        r = _requests.post(f"{_OLLAMA_URL}/api/generate", json=payload, timeout=180)
        if r.status_code == 200:
            return r.json().get("response", "")
    except Exception as e:
        return f"Ollama error: {e}"
    return f"Ollama returned {r.status_code}"


def _generate_claude(prompt: str) -> str:
    if not _ANTHROPIC_KEY:
        return "No Anthropic API key configured."
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 2048,
        "system": _DOSSIER_SYSTEM,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        r = _requests.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers={"x-api-key": _ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            timeout=60,
        )
        if r.status_code == 200:
            return r.json()["content"][0]["text"]
    except Exception as e:
        return f"Claude error: {e}"
    return f"Claude API returned {r.status_code}"


def generate_dossier(results: dict[str, Any], filename: str = "image") -> dict[str, Any]:
    """Generate intelligence dossier from all stage results."""
    if not REQUESTS_OK:
        return {"error": "requests not installed", "dossier": ""}

    summary = _summarize_results(results)
    prompt = f"Analyze the following OSINT investigation results for image '{filename}' and produce the intelligence dossier:\n\n{summary}"

    dossier_text = ""
    source = ""

    # Try Ollama first
    try:
        r = _requests.get(f"{_OLLAMA_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            if any("mistral" in m or "llama" in m for m in models):
                dossier_text = _generate_ollama(prompt)
                source = "ollama/mistral"
    except Exception:
        pass

    if not dossier_text:
        dossier_text = _generate_claude(prompt)
        source = "anthropic/claude-sonnet-4-6"

    # Extract intel score from existing report stage if available
    report_data = results.get("Scoring & Report", {})
    intel_score = report_data.get("intel_score", None)

    return {
        "dossier": dossier_text,
        "intel_score": intel_score,
        "source": source,
        "stages_analyzed": len([k for k, v in results.items() if isinstance(v, dict) and not v.get("error") and not v.get("skipped")]),
    }
