from dataclasses import dataclass
from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError
import uuid

from database import get_db
from models.user import User, UserRole
from services.auth_service import decode_access_token, get_user_by_id

bearer = HTTPBearer(auto_error=False)


@dataclass
class GuestUser:
    """Synthetic user for guest sessions — never persisted in DB."""
    id: uuid.UUID
    role: str = "guest"
    is_banned: bool = False
    is_guest: bool = True
    username: str = "Guest"
    email: str = ""


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid token")

    user = await get_user_by_id(db, user_id)
    if not user or user.is_banned:
        raise HTTPException(401, "User not found or banned")
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if not credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
        return await get_user_by_id(db, user_id)
    except Exception:
        return None


async def get_current_user_or_guest(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
):
    """Like get_current_user but also accepts guest JWTs (no DB row required)."""
    if not credentials:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
        if payload.get("is_guest"):
            return GuestUser(id=uuid.UUID(payload["sub"]))
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid token")

    user = await get_user_by_id(db, user_id)
    if not user or user.is_banned:
        raise HTTPException(401, "User not found or banned")
    return user


def require_role(*roles: UserRole):
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(403, "Insufficient permissions")
        return current_user
    return _check


require_admin = require_role(UserRole.admin)
require_pro_or_above = require_role(UserRole.admin, UserRole.pro)
