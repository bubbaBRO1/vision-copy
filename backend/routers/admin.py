import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User, UserRole, AuditLog
from models.waitlist import Waitlist
from models.search import Search
from models.research import ResearchJob
from routers.deps import require_admin
from services.email_service import send_invite_email

router = APIRouter(prefix="/admin", tags=["admin"])
UTC = timezone.utc


class UserUpdateRequest(BaseModel):
    role: str | None = None
    is_banned: bool | None = None


@router.get("/dashboard")
async def admin_dashboard(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar()
    search_today = (await db.execute(
        select(func.count()).select_from(Search).where(
            Search.created_at >= datetime.now(UTC).replace(hour=0, minute=0, second=0)
        )
    )).scalar()
    research_today = (await db.execute(
        select(func.count()).select_from(ResearchJob).where(
            ResearchJob.created_at >= datetime.now(UTC).replace(hour=0, minute=0, second=0)
        )
    )).scalar()
    waitlist_count = (await db.execute(select(func.count()).select_from(Waitlist))).scalar()
    return {
        "total_users": user_count,
        "searches_today": search_today,
        "research_jobs_today": research_today,
        "waitlist_count": waitlist_count,
    }


@router.get("/users")
async def list_users(
    limit: int = 50,
    offset: int = 0,
    search: str = "",
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(User).order_by(desc(User.created_at)).limit(limit).offset(offset)
    if search:
        query = query.where(
            User.username.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
        )
    result = await db.execute(query)
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "username": u.username,
            "email": u.email,
            "role": u.role.value,
            "is_verified": u.is_verified,
            "is_banned": u.is_banned,
            "created_at": u.created_at.isoformat(),
            "last_login": u.last_login.isoformat() if u.last_login else None,
        }
        for u in users
    ]


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    req: UserUpdateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    import uuid as _uuid
    user = await db.get(User, _uuid.UUID(user_id))
    if not user:
        raise HTTPException(404, "User not found")
    if req.role:
        if req.role not in [r.value for r in UserRole]:
            raise HTTPException(400, f"Invalid role: {req.role}")
        user.role = UserRole(req.role)
    if req.is_banned is not None:
        user.is_banned = req.is_banned
    db.add(AuditLog(
        user_id=admin.id,
        action="admin_update_user",
        target=str(user.id),
        detail=f"role={req.role} banned={req.is_banned}",
    ))
    await db.commit()
    return {"ok": True}


@router.get("/waitlist")
async def list_waitlist(
    limit: int = 100,
    offset: int = 0,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Waitlist).order_by(Waitlist.created_at).limit(limit).offset(offset)
    )
    entries = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "email": e.email,
            "name": e.name,
            "use_case": e.use_case,
            "position": i + 1 + offset,
            "referral_count": e.referral_count,
            "approved": e.approved,
            "invite_used": e.invite_used,
            "created_at": e.created_at.isoformat(),
        }
        for i, e in enumerate(entries)
    ]


@router.post("/waitlist/approve/{waitlist_id}")
async def approve_waitlist(
    waitlist_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    import uuid as _uuid
    entry = await db.get(Waitlist, _uuid.UUID(waitlist_id))
    if not entry:
        raise HTTPException(404, "Waitlist entry not found")

    token = secrets.token_urlsafe(32)
    entry.approved = True
    entry.invite_token = token
    entry.invite_expires = datetime.now(UTC) + timedelta(hours=72)

    db.add(AuditLog(user_id=admin.id, action="approve_waitlist", target=entry.email))
    await db.commit()

    try:
        send_invite_email(entry.email, token, entry.name)
    except Exception:
        pass

    return {"ok": True, "invite_token": token}


@router.post("/waitlist/bulk-approve")
async def bulk_approve(
    ids: list[str],
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    approved = 0
    import uuid as _uuid
    for wid in ids:
        try:
            entry = await db.get(Waitlist, _uuid.UUID(wid))
            if entry and not entry.approved:
                token = secrets.token_urlsafe(32)
                entry.approved = True
                entry.invite_token = token
                entry.invite_expires = datetime.now(UTC) + timedelta(hours=72)
                try:
                    send_invite_email(entry.email, token, entry.name)
                except Exception:
                    pass
                approved += 1
        except Exception:
            continue
    await db.commit()
    return {"approved": approved}


SETTINGS_GROUPS = {
    "auth": ["OPEN_REGISTRATION", "HCAPTCHA_SECRET"],
    "email": ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM"],
    "frontend": ["FRONTEND_URL"],
    "api_keys": [
        "ANTHROPIC_API_KEY", "TINEYE_API_KEY", "GEOSPY_API_KEY",
        "SHODAN_API_KEY", "VIRUSTOTAL_API_KEY", "HIBP_API_KEY", "GITHUB_TOKEN",
    ],
    "security": ["POSTGRES_PASSWORD", "JWT_SECRET"],
}

RESTART_REQUIRED = {"POSTGRES_PASSWORD", "JWT_SECRET", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD"}

SECRET_KEYS = {"HCAPTCHA_SECRET", "SMTP_PASSWORD", "ANTHROPIC_API_KEY", "TINEYE_API_KEY",
               "GEOSPY_API_KEY", "SHODAN_API_KEY", "VIRUSTOTAL_API_KEY", "HIBP_API_KEY",
               "GITHUB_TOKEN", "POSTGRES_PASSWORD", "JWT_SECRET"}

ALL_KEYS = [k for keys in SETTINGS_GROUPS.values() for k in keys]


def _mask(key: str, value: str) -> str:
    if not value or key not in SECRET_KEYS:
        return value
    return value[:4] + "****" if len(value) > 4 else "****"


def _env_path() -> str:
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, ".env")


@router.get("/settings")
async def get_settings_values(_: User = Depends(require_admin)):
    from dotenv import dotenv_values
    env_path = _env_path()
    values = dotenv_values(env_path)
    out = {}
    for key in ALL_KEYS:
        raw = values.get(key, "")
        out[key] = {
            "value": _mask(key, raw),
            "masked": key in SECRET_KEYS and bool(raw),
            "restart_required": key in RESTART_REQUIRED,
        }
    return {"groups": SETTINGS_GROUPS, "settings": out}


class SettingUpdate(BaseModel):
    key: str
    value: str


@router.post("/settings")
async def update_setting(req: SettingUpdate, _: User = Depends(require_admin)):
    if req.key not in ALL_KEYS:
        raise HTTPException(400, f"Unknown setting: {req.key}")
    from dotenv import dotenv_values, set_key
    from config import get_settings
    env_path = _env_path()
    # Capture current value for rollback
    current_value = dotenv_values(env_path).get(req.key, "")
    try:
        set_key(env_path, req.key, req.value)
        get_settings.cache_clear()
    except Exception as exc:
        try:
            set_key(env_path, req.key, current_value)
        except Exception:
            pass
        raise HTTPException(500, f"Failed to update setting: {exc}")
    return {"ok": True, "restart_required": req.key in RESTART_REQUIRED}


@router.get("/logs")
async def get_audit_logs(
    limit: int = 100,
    offset: int = 0,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit).offset(offset)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(l.id),
            "user_id": str(l.user_id) if l.user_id else None,
            "action": l.action,
            "target": l.target,
            "ip": l.ip,
            "detail": l.detail,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]
