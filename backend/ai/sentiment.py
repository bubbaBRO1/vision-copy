import os
import httpx
from typing import Dict

API_URL = os.getenv("ANthropic_SENTIMENT_ENDPOINT", "https://api.anthropic.com/v1/messages")
API_KEY = os.getenv("ANTHROPIC_API_KEY")

async def analyze_sentiment(text: str) -> Dict:
    """Return sentiment analysis using Anthropic Claude.
    Returns dict with keys: sentiment ('positive'|'negative'|'neutral'), confidence (0-1).
    """
    if not API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    headers = {"x-api-key": API_KEY, "content-type": "application/json"}
    payload = {
        "model": "claude-3-sonnet-20240229",
        "max_tokens": 100,
        "temperature": 0,
        "messages": [
            {"role": "user", "content": f"Analyze sentiment of the following text and return JSON with fields 'sentiment' and 'confidence' (0-1). Text: {text}"}
        ]
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(API_URL, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        # Assume Claude returns content as string JSON
        try:
            import json
            result = json.loads(data["content"][0]["text"])  # type: ignore
        except Exception:
            result = {"sentiment": "neutral", "confidence": 0.0}
        return result
