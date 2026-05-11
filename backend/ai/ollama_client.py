"""Streaming Ollama client. Falls back to Anthropic if Ollama unreachable."""
import json
from typing import AsyncGenerator, Optional
import httpx
from config import get_settings
from ai.prompts import CHAT_SYSTEM_PROMPT

settings = get_settings()

OLLAMA_BASE = settings.ollama_url
DEFAULT_MODEL = "llama3:8b"
VISION_MODEL = "llava:13b"
RESEARCH_MODEL = "mistral:7b"

# Keep for backward compat — callers that import SYSTEM_PROMPT directly still work
SYSTEM_PROMPT = CHAT_SYSTEM_PROMPT


async def stream_chat(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    system: Optional[str] = None,
    context_data: Optional[dict] = None,
) -> AsyncGenerator[str, None]:
    """Yields tokens from Ollama streaming API. Falls back to Anthropic on connection error."""
    sys_prompt = system or CHAT_SYSTEM_PROMPT
    if context_data:
        sys_prompt += f"\n\n[SESSION CONTEXT]\n{json.dumps(context_data, indent=2)}"

    payload = {
        "model": model,
        "messages": [{"role": "system", "content": sys_prompt}] + messages,
        "stream": True,
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", f"{OLLAMA_BASE}/api/chat", json=payload) as r:
                if r.status_code != 200:
                    raise ConnectionError(f"Ollama returned {r.status_code}")
                async for line in r.aiter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            content = chunk.get("message", {}).get("content", "")
                            if content:
                                yield content
                            if chunk.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
    except (ConnectionError, httpx.ConnectError, httpx.TimeoutException):
        if settings.anthropic_api_key:
            async for token in _anthropic_fallback(messages, sys_prompt):
                yield token
        else:
            yield "\n\n[VISION-AI: Ollama unavailable and no Anthropic API key configured]\n"


async def _anthropic_fallback(messages: list[dict], system: str) -> AsyncGenerator[str, None]:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    async with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=system,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def list_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/tags")
            if r.status_code == 200:
                return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return [DEFAULT_MODEL, VISION_MODEL, RESEARCH_MODEL]


async def generate_one_shot(prompt: str, model: str = DEFAULT_MODEL) -> str:
    """Non-streaming single completion."""
    result = ""
    async for token in stream_chat([{"role": "user", "content": prompt}], model=model):
        result += token
    return result
