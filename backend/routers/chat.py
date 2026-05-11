import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.research import ChatSession
from models.user import User
from routers.deps import get_current_user, get_current_user_or_guest
from services.rate_limiter import check_rate_limit
from ai.prompts import CHAT_SYSTEM_PROMPT, INCOGNITO_SYSTEM_PROMPT, RESEARCH_SYSTEM_PROMPT, LOCATION_INFERENCE_PROMPT, FACE_SEARCH_REASONING_PROMPT

router = APIRouter(prefix="/api/chat", tags=["chat"])
UTC = timezone.utc

_MODE_PROMPTS: dict[str, str] = {
    "investigation": CHAT_SYSTEM_PROMPT,
    "research": RESEARCH_SYSTEM_PROMPT,
    "location": LOCATION_INFERENCE_PROMPT,
    "face": FACE_SEARCH_REASONING_PROMPT,
    "incognito": INCOGNITO_SYSTEM_PROMPT,
}


class ChatMessage(BaseModel):
    content: str
    model: str = "llama3:8b"
    session_id: str | None = None
    search_id: str | None = None
    project_id: str | None = None
    is_incognito: bool = False
    mode: Literal["investigation", "research", "location", "face", "incognito"] = "investigation"


@router.post("/")
async def send_message(
    req: ChatMessage,
    current_user=Depends(get_current_user_or_guest),
    db: AsyncSession = Depends(get_db),
):
    user_role = getattr(current_user, "role", "guest")
    role_str = user_role.value if hasattr(user_role, "value") else str(user_role)
    allowed, limit, remaining, reset_ts = await check_rate_limit(
        str(current_user.id), "ai_query", role_str
    )
    if not allowed:
        raise HTTPException(429, "AI rate limit exceeded", headers={
            "X-RateLimit-Limit": str(limit), "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset_ts)
        })

    from ai.ollama_client import stream_chat
    from ai.slash_commands import handle_slash_command

    # ── Incognito mode: never touch DB ──────────────────────────────────────
    if req.is_incognito:
        ephemeral = [{"role": "user", "content": req.content}]
        sys_prompt = INCOGNITO_SYSTEM_PROMPT

        async def _incognito_stream():
            async for token in stream_chat(ephemeral, model=req.model, system=sys_prompt):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            _incognito_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "X-Session-Id": "incognito"},
        )

    # ── Persistent (normal) mode ─────────────────────────────────────────────
    session = None
    if req.session_id:
        session = await db.get(ChatSession, uuid.UUID(req.session_id))
        if session and session.user_id != current_user.id:
            session = None  # ownership check

    if not session:
        session = ChatSession(
            user_id=current_user.id,
            model=req.model,
            search_id=uuid.UUID(req.search_id) if req.search_id else None,
            project_id=uuid.UUID(req.project_id) if req.project_id else None,
        )
        db.add(session)
        await db.flush()

    messages = list(session.messages_json or [])

    search_results = None
    if req.search_id:
        from models.search import Search
        search = await db.get(Search, uuid.UUID(req.search_id))
        if search:
            search_results = search.results_json

    cmd_result = await handle_slash_command(req.content, search_results=search_results)

    if cmd_result is not None:
        messages.append({"role": "user", "content": req.content})
        messages.append({"role": "assistant", "content": cmd_result})
        session.messages_json = messages
        await db.commit()

        async def _cmd_stream():
            yield f"data: {cmd_result}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            _cmd_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "X-Session-Id": str(session.id)},
        )

    messages.append({"role": "user", "content": req.content})

    context_data = None
    if search_results:
        context_data = {
            "search_id": req.search_id,
            "exif_summary": search_results.get("EXIF & Metadata", {}),
            "geolocation": search_results.get("Geolocation", {}),
            "faces_detected": len(search_results.get("Face & Object Detection", {}).get("faces", [])),
        }

    mode_sys_prompt = _MODE_PROMPTS.get(req.mode, CHAT_SYSTEM_PROMPT)

    # Inject user memory (skip for guests — no DB row)
    is_guest = getattr(current_user, "is_guest", False)
    if not is_guest and not req.is_incognito:
        from models.research import UserMemory
        from sqlalchemy import select, desc
        mem_q = (
            select(UserMemory)
            .where(UserMemory.user_id == current_user.id)
            .order_by(desc(UserMemory.created_at))
            .limit(20)
        )
        mem_rows = (await db.execute(mem_q)).scalars().all()
        if mem_rows:
            mem_block = "\n".join(f"- {m.content}" for m in mem_rows)
            mode_sys_prompt = (
                mode_sys_prompt
                + f"\n\n[USER MEMORY — use these facts about the user when relevant]\n{mem_block}"
            )

    async def _ai_stream():
        full_response = ""
        async for token in stream_chat(messages, model=req.model, system=mode_sys_prompt, context_data=context_data):
            full_response += token
            yield f"data: {token}\n\n"
        messages.append({"role": "assistant", "content": full_response})
        session.messages_json = messages
        session.updated_at = datetime.now(UTC)
        await db.commit()
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _ai_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "X-Session-Id": str(session.id)},
    )


@router.get("/models")
async def list_models(_: User = Depends(get_current_user)):
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get("http://ollama:11434/api/tags")
            data = r.json()
            models = [{"id": m["name"], "name": m["name"]} for m in data.get("models", [])]
    except Exception:
        models = []
    # Always include Claude fallback
    models.append({"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6 (cloud)"})
    return models


@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(desc(ChatSession.updated_at))
        .limit(50)
    )
    sessions = result.scalars().all()
    return [{"id": str(s.id), "title": s.title, "model": s.model, "updated_at": s.updated_at.isoformat()} for s in sessions]


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(ChatSession, uuid.UUID(session_id))
    if not session or session.user_id != current_user.id:
        raise HTTPException(404, "Session not found")
    await db.delete(session)
    await db.commit()
    return {"ok": True}
