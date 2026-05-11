import os
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Dict

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.post("/process")
async def process_video(file: UploadFile = File(...)) -> Dict:
    """Save uploaded video, run AI modules, return combined result."""
    temp_path = f"/tmp/{file.filename}"  # simple temp location
    try:
        with open(temp_path, "wb") as out:
            content = await file.read()
            out.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    try:
        from ai.sentiment import analyze_sentiment
        from ai.transcribe import transcribe_audio
        from ai.pose import analyze_pose
        from ai.audio_sentiment import audio_sentiment
    except ImportError as e:
        raise HTTPException(
            status_code=501,
            detail=f"Video analysis dependency is not installed: {e.name}",
        )

    # Run modules (placeholder async calls)
    sentiment = await analyze_sentiment("sample text")  # replace with actual transcription later
    transcription = await transcribe_audio(temp_path)
    pose = await analyze_pose(temp_path)
    audio_sent = await audio_sentiment(temp_path)
    return {
        "sentiment": sentiment,
        "transcription": transcription,
        "pose": pose,
        "audio_sentiment": audio_sent,
    }
