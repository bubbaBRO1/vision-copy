import httpx
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User, RefreshToken, UserRole
from schemas.auth import (
    SignupRequest, LoginRequest, TokenResponse,
    ForgotPasswordRequest, ResetPasswordRequest, UserResponse, SessionInfo,
    GoogleAuthRequest, GuestLoginResponse,
)
from services import auth_service, email_service
from config import get_settings
from .deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
UTC = timezone.utc

LOCKOUT_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


async def _verify_hcaptcha(token: str) -> bool:
    if not settings.hcaptcha_secret or not token:
        return True
    async with httpx.AsyncClient() as c:
        r = await c.post(
            "https://hcaptcha.com/siteverify",
            data={"secret": settings.hcaptcha_secret, "response": token},
        )
        return r.json().get("success", False)


@router.post("/signup", response_model=UserResponse, status_code=201)
async def signup(req: SignupRequest, request: Request, db: AsyncSession = Depends(get_db)):
    if not req.accept_terms:
        raise HTTPException(400, "Must accept terms")

    if not await _verify_hcaptcha(req.hcaptcha_token or ""):
        raise HTTPException(400, "CAPTCHA verification failed")

    exists_check = await db.execute(
        select(User.id).where((User.email == req.email.lower()) | (User.username == req.username.lower()))
    )
    if exists_check.scalar_one_or_none():
        raise HTTPException(409, "Username or email already taken")

    try:
        user, ev_token = await auth_service.register_user(
            db, req.username, req.email, req.password, req.invite_code
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        email_service.send_verification_email(user.email, ev_token)
    except Exception:
        logger.warning("Failed to send verification email to %s", user.email, exc_info=True)

    await auth_service.log_audit(db, "signup", user.id, ip=request.client.host if request.client else None)

    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role.value,
        is_verified=user.is_verified,
        created_at=user.created_at.isoformat(),
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    user = await auth_service.get_user_by_identifier(db, req.identifier)
    if not user:
        raise HTTPException(401, "Invalid credentials")

    if user.is_banned:
        raise HTTPException(403, "Account suspended")

    now = datetime.now(UTC)
    if user.locked_until and user.locked_until.replace(tzinfo=UTC) > now:
        raise HTTPException(429, f"Account locked. Try again after {user.locked_until.isoformat()}")

    if not auth_service.verify_password(req.password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= LOCKOUT_ATTEMPTS:
            from datetime import timedelta
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_login_count = 0
        await db.commit()
        raise HTTPException(401, "Invalid credentials")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login = now
    await db.commit()

    ua = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else ""
    raw_refresh = await auth_service.create_refresh_token(db, user.id, ua, ip)
    access_token = auth_service.create_access_token(str(user.id), user.role.value)

    response.set_cookie(
        "refresh_token",
        raw_refresh,
        httponly=True,
        secure=settings.production,
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/auth/refresh",
    )

    await auth_service.log_audit(db, "login", user.id, ip=ip)
    return TokenResponse(access_token=access_token, expires_in=settings.access_token_expire_minutes * 60)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    raw = request.cookies.get("refresh_token")
    if not raw:
        raise HTTPException(401, "No refresh token")

    ua = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else ""
    result = await auth_service.rotate_refresh_token(db, raw, ua, ip)
    if not result:
        raise HTTPException(401, "Invalid or expired refresh token")

    new_raw, user = result
    response.set_cookie(
        "refresh_token",
        new_raw,
        httponly=True,
        secure=settings.production,
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/auth/refresh",
    )
    access_token = auth_service.create_access_token(str(user.id), user.role.value)
    return TokenResponse(access_token=access_token, expires_in=settings.access_token_expire_minutes * 60)


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    raw = request.cookies.get("refresh_token")
    if raw:
        from services.auth_service import _hash_token
        token_hash = _hash_token(raw)
        result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        rt = result.scalar_one_or_none()
        if rt:
            rt.revoked = True
            await db.commit()
    response.delete_cookie("refresh_token", path="/auth/refresh")
    return {"ok": True}


@router.get("/verify-email/{token}")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    user = await auth_service.verify_email_token(db, token)
    if not user:
        raise HTTPException(400, "Invalid or expired verification link")
    return {"ok": True, "message": "Email verified"}


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    token = await auth_service.create_password_reset(db, req.email)
    if token:
        try:
            email_service.send_password_reset_email(req.email, token)
        except Exception:
            logger.warning("Failed to send password reset email to %s", req.email, exc_info=True)
    return {"ok": True, "message": "If that email exists, a reset link was sent"}


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    ok = await auth_service.reset_password(db, req.token, req.new_password)
    if not ok:
        raise HTTPException(400, "Invalid or expired reset token")
    return {"ok": True}


@router.get("/sessions", response_model=list[SessionInfo])
async def get_sessions(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RefreshToken).where(
            and_(RefreshToken.user_id == current_user.id, RefreshToken.revoked == False)
        )
    )
    sessions = result.scalars().all()
    return [
        SessionInfo(
            id=str(s.id),
            user_agent=s.user_agent,
            ip=s.ip,
            created_at=s.created_at.isoformat(),
            expires_at=s.expires_at.isoformat(),
        )
        for s in sessions
    ]


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ok = await auth_service.revoke_refresh_token(db, session_id, current_user.id)
    if not ok:
        raise HTTPException(404, "Session not found")
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        role=current_user.role.value,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at.isoformat(),
    )


@router.get("/check-username/{username}")
async def check_username(username: str, db: AsyncSession = Depends(get_db)):
    available = await auth_service.check_username_available(db, username)
    return {"available": available}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if getattr(current_user, "google_id", None):
        raise HTTPException(400, "Account uses Google Sign-In — password not set")
    if not auth_service.verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(400, "Current password incorrect")
    if len(req.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    current_user.password_hash = auth_service.hash_password(req.new_password)
    await db.commit()
    return {"ok": True}


@router.post("/api-key/regenerate")
async def regenerate_api_key(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    import secrets
    current_user.api_key = secrets.token_urlsafe(32)
    await db.commit()
    return {"api_key": current_user.api_key}


@router.delete("/sessions")
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RefreshToken).where(
            and_(RefreshToken.user_id == current_user.id, RefreshToken.revoked == False)
        )
    )
    for rt in result.scalars().all():
        rt.revoked = True
    await db.commit()
    return {"ok": True}


@router.get("/export")
async def export_data(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    import json, io, zipfile
    from models.search import Search
    from models.research import ResearchJob, ChatSession

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Searches
        r = await db.execute(select(Search).where(Search.user_id == current_user.id))
        searches = [{"id": str(s.id), "filename": s.filename, "status": s.status.value,
                     "results": s.results_json, "created_at": s.created_at.isoformat()} for s in r.scalars().all()]
        zf.writestr("searches.json", json.dumps(searches, indent=2))

        # Research
        r = await db.execute(select(ResearchJob).where(ResearchJob.user_id == current_user.id))
        jobs = [{"id": str(j.id), "query": j.query, "depth": j.depth, "report": j.report_json,
                 "created_at": j.created_at.isoformat()} for j in r.scalars().all()]
        zf.writestr("research.json", json.dumps(jobs, indent=2))

        # Chat
        r = await db.execute(select(ChatSession).where(ChatSession.user_id == current_user.id))
        chats = [{"id": str(c.id), "title": c.title, "messages": c.messages_json,
                  "created_at": c.created_at.isoformat()} for c in r.scalars().all()]
        zf.writestr("chats.json", json.dumps(chats, indent=2))

    buf.seek(0)
    from fastapi.responses import StreamingResponse as SR
    return SR(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=vision-export-{current_user.username}.zip"},
    )


@router.delete("/account")
async def delete_account(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.delete(current_user)
    await db.commit()
    return {"ok": True}


class GuestUpgradeRequest(BaseModel):
    username: str
    email: str
    password: str
    accept_terms: bool


@router.post("/upgrade-guest", response_model=TokenResponse, status_code=201)
async def upgrade_guest(
    req: GuestUpgradeRequest,
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db),
):
    """Convert an anonymous guest session into a real account, preserving their data."""
    if not req.accept_terms:
        raise HTTPException(400, "Must accept terms")

    # Validate guest token and extract guest_id
    guest_id = None
    if credentials:
        try:
            payload = auth_service.decode_access_token(credentials.credentials)
            if payload.get("is_guest"):
                guest_id = payload["sub"]
        except Exception:
            pass

    exists = await db.execute(
        select(User.id).where((User.email == req.email.lower()) | (User.username == req.username.lower()))
    )
    if exists.scalar_one_or_none():
        raise HTTPException(409, "Username or email already taken")

    try:
        user, ev_token = await auth_service.register_user(db, req.username, req.email, req.password, None)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Re-own guest data
    if guest_id:
        import uuid as _uuid
        try:
            guest_uuid = _uuid.UUID(guest_id)
            from models.search import Search
            from models.research import ChatSession
            from sqlalchemy import update
            await db.execute(update(Search).where(Search.user_id == guest_uuid).values(user_id=user.id))
            await db.execute(update(ChatSession).where(ChatSession.user_id == guest_uuid).values(user_id=user.id))
            await db.commit()
        except Exception:
            pass  # best-effort; don't fail upgrade

    try:
        from services import email_service
        email_service.send_verification_email(user.email, ev_token)
    except Exception:
        pass

    ua = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else ""
    raw_refresh = await auth_service.create_refresh_token(db, user.id, ua, ip)
    access_token = auth_service.create_access_token(str(user.id), user.role.value)

    response.set_cookie(
        "refresh_token", raw_refresh,
        httponly=True, secure=settings.production, samesite="strict",
        max_age=settings.refresh_token_expire_days * 86400, path="/auth/refresh",
    )
    await auth_service.log_audit(db, "guest_upgrade", user.id, ip=ip)
    return TokenResponse(access_token=access_token, expires_in=settings.access_token_expire_minutes * 60)


@router.post("/google", response_model=TokenResponse)
async def google_auth(
    req: GoogleAuthRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    if not settings.google_client_id:
        raise HTTPException(501, "Google OAuth not configured — set GOOGLE_CLIENT_ID")
    try:
        user = await auth_service.google_login_or_create(db, req.id_token, settings.google_client_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    ua = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else ""
    raw_refresh = await auth_service.create_refresh_token(db, user.id, ua, ip)
    access_token = auth_service.create_access_token(str(user.id), user.role.value)

    response.set_cookie(
        "refresh_token",
        raw_refresh,
        httponly=True,
        secure=settings.production,
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/auth/refresh",
    )
    await auth_service.log_audit(db, "google_login", user.id, ip=ip)
    return TokenResponse(access_token=access_token, expires_in=settings.access_token_expire_minutes * 60)


@router.post("/guest", response_model=GuestLoginResponse)
async def guest_login(request: Request):
    _guest_id, token = auth_service.create_guest_token()
    return GuestLoginResponse(access_token=token, expires_in=24 * 3600)


