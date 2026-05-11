import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import jwt, JWTError
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models.user import User, RefreshToken, EmailVerification, PasswordReset, AuditLog, UserRole
from models.waitlist import Waitlist

settings = get_settings()

UTC = timezone.utc


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": expire, "type": "access"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_refresh_token(db: AsyncSession, user_id: uuid.UUID, user_agent: str, ip: str) -> str:
    raw = secrets.token_urlsafe(64)
    token_hash = _hash_token(raw)
    expires = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    rt = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires,
        user_agent=user_agent[:512] if user_agent else None,
        ip=ip,
    )
    db.add(rt)
    await db.commit()
    return raw


async def rotate_refresh_token(
    db: AsyncSession, raw_token: str, user_agent: str, ip: str
) -> tuple[str, "User"] | None:
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(
            and_(RefreshToken.token_hash == token_hash, RefreshToken.revoked == False)
        )
    )
    rt = result.scalar_one_or_none()
    if not rt or rt.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        return None

    user = await db.get(User, rt.user_id)
    if not user or user.is_banned:
        return None

    rt.revoked = True
    new_raw = secrets.token_urlsafe(64)
    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(new_raw),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        user_agent=user_agent[:512] if user_agent else None,
        ip=ip,
    )
    db.add(new_rt)
    await db.commit()
    return new_raw, user


async def revoke_refresh_token(db: AsyncSession, token_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    rt = await db.get(RefreshToken, token_id)
    if not rt or rt.user_id != user_id:
        return False
    rt.revoked = True
    await db.commit()
    return True


async def get_user_by_identifier(db: AsyncSession, identifier: str) -> Optional[User]:
    result = await db.execute(
        select(User).where(
            (User.email == identifier.lower()) | (User.username == identifier.lower())
        )
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    return await db.get(User, user_id)


async def check_username_available(db: AsyncSession, username: str) -> bool:
    result = await db.execute(select(User.id).where(User.username == username.lower()))
    return result.scalar_one_or_none() is None


async def register_user(
    db: AsyncSession,
    username: str,
    email: str,
    password: str,
    invite_code: Optional[str],
) -> tuple[User, str]:
    """Returns (user, email_verification_token)"""
    if not settings.open_registration:
        if not invite_code:
            raise ValueError("Invite code required")
        wl = await db.execute(
            select(Waitlist).where(
                and_(Waitlist.invite_token == invite_code, Waitlist.invite_used == False)
            )
        )
        wl_row = wl.scalar_one_or_none()
        if not wl_row or (wl_row.invite_expires and wl_row.invite_expires.replace(tzinfo=UTC) < datetime.now(UTC)):
            raise ValueError("Invalid or expired invite code")
        wl_row.invite_used = True

    user = User(
        username=username.lower(),
        email=email.lower(),
        password_hash=hash_password(password),
        role=UserRole.user,
        is_verified=False,
    )
    db.add(user)
    await db.flush()

    ev_token = secrets.token_urlsafe(32)
    ev = EmailVerification(
        user_id=user.id,
        token=ev_token,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(ev)
    await db.commit()
    return user, ev_token


async def verify_email_token(db: AsyncSession, token: str) -> Optional[User]:
    result = await db.execute(
        select(EmailVerification).where(
            and_(EmailVerification.token == token, EmailVerification.used == False)
        )
    )
    ev = result.scalar_one_or_none()
    if not ev or ev.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        return None
    ev.used = True
    user = await db.get(User, ev.user_id)
    if user:
        user.is_verified = True
    await db.commit()
    return user


async def create_password_reset(db: AsyncSession, email: str) -> Optional[str]:
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()
    if not user:
        return None
    token = secrets.token_urlsafe(32)
    pr = PasswordReset(
        user_id=user.id,
        token=token,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db.add(pr)
    await db.commit()
    return token


async def reset_password(db: AsyncSession, token: str, new_password: str) -> bool:
    result = await db.execute(
        select(PasswordReset).where(
            and_(PasswordReset.token == token, PasswordReset.used == False)
        )
    )
    pr = result.scalar_one_or_none()
    if not pr or pr.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        return False
    pr.used = True
    user = await db.get(User, pr.user_id)
    if user:
        user.password_hash = hash_password(new_password)
    await db.commit()
    return True


def create_guest_token() -> tuple[str, str]:
    """Returns (guest_id, access_token). No DB row — token carries is_guest claim."""
    guest_id = str(uuid.uuid4())
    expire = datetime.now(UTC) + timedelta(hours=24)
    token = jwt.encode(
        {"sub": guest_id, "role": "guest", "exp": expire, "type": "access", "is_guest": True},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return guest_id, token


async def google_login_or_create(
    db: AsyncSession, id_token_str: str, google_client_id: str
) -> "User":
    """Verify Google ID token. Link existing account by google_id or email, or auto-create."""
    import re as _re
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        idinfo = google_id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            google_client_id,
        )
    except Exception as exc:
        raise ValueError(f"Google token verification failed: {exc}") from exc

    google_sub = idinfo["sub"]
    email = idinfo.get("email", "").lower()

    # Lookup by google_id first
    result = await db.execute(select(User).where(User.google_id == google_sub))
    user = result.scalar_one_or_none()

    if not user and email:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            user.google_id = google_sub

    if not user:
        base = _re.sub(r"[^a-z0-9_]", "", idinfo.get("name", "user").lower())[:40] or "user"
        username = base
        suffix = 1
        while True:
            taken = await db.execute(select(User.id).where(User.username == username))
            if not taken.scalar_one_or_none():
                break
            username = f"{base}{suffix}"
            suffix += 1
        user = User(
            username=username,
            email=email,
            password_hash="",
            google_id=google_sub,
            is_verified=True,
            role=UserRole.user,
        )
        db.add(user)

    user.last_login = datetime.now(UTC)
    await db.commit()
    await db.refresh(user)
    return user


async def log_audit(
    db: AsyncSession,
    action: str,
    user_id: Optional[uuid.UUID] = None,
    target: Optional[str] = None,
    ip: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    db.add(AuditLog(user_id=user_id, action=action, target=target, ip=ip, detail=detail))
    await db.commit()
