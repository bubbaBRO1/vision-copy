import os
import asyncio
import whisper
from typing import Dict

model = whisper.load_model("base")

async def transcribe_audio(audio_path: str) -> Dict:
    """Return transcription of audio file using Whisper.
    Returns dict with keys: "text" and "duration".
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: model.transcribe(audio_path))
    return {"text": result["text"], "duration": result.get("duration", 0)}
