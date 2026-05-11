import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.waitlist import Waitlist
from schemas.waitlist import WaitlistJoinRequest, WaitlistJoinResponse, WaitlistPositionResponse
from services.email_service import send_invite_email

router = APIRouter(prefix="/waitlist", tags=["waitlist"])
UTC = timezone.utc


def _gen_referral_code() -> str:
    return secrets.token_urlsafe(8)[:12].upper()


@router.post("/join", response_model=WaitlistJoinResponse, status_code=201)
async def join_waitlist(req: WaitlistJoinRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Waitlist).where(Waitlist.email == req.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Email already on waitlist")

    referrer = None
    if req.referral_code:
        ref_result = await db.execute(
            select(Waitlist).where(Waitlist.referral_code == req.referral_code.upper())
        )
        referrer = ref_result.scalar_one_or_none()

    entry = Waitlist(
        email=req.email.lower(),
        name=req.name,
        use_case=req.use_case,
        referral_code=_gen_referral_code(),
        referred_by=req.referral_code.upper() if req.referral_code and referrer else None,
    )
    db.add(entry)

    if referrer:
        referrer.referral_count += 1
        referrer.position_boost += 5

    await db.commit()

    count_result = await db.execute(
        select(func.count()).where(
            and_(Waitlist.created_at <= entry.created_at, Waitlist.approved == False)
        )
    )
    raw_position = count_result.scalar() or 1
    effective_position = max(1, raw_position - (referrer.position_boost if referrer else 0))

    return WaitlistJoinResponse(
        position=effective_position,
        referral_code=entry.referral_code,
        message=f"You are #{effective_position} on the waitlist. Share your referral link to move up!",
    )


@router.get("/position/{email}", response_model=WaitlistPositionResponse)
async def get_position(email: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Waitlist).where(Waitlist.email == email.lower()))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(404, "Email not found on waitlist")

    count_result = await db.execute(
        select(func.count()).where(
            and_(Waitlist.created_at <= entry.created_at, Waitlist.approved == False)
        )
    )
    raw_position = count_result.scalar() or 1
    effective_position = max(1, raw_position - entry.position_boost)

    return WaitlistPositionResponse(
        email=entry.email,
        position=effective_position,
        approved=entry.approved,
        referral_count=entry.referral_count,
        referral_code=entry.referral_code,
    )


@router.get("/count")
async def total_count(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count()).select_from(Waitlist))
    return {"count": result.scalar()}


@router.post("/refer")
async def refer(email: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Waitlist).where(Waitlist.email == email.lower()))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(404, "Not on waitlist")
    from config import get_settings
    settings = get_settings()
    return {
        "referral_url": f"{settings.frontend_url}/?ref={entry.referral_code}",
        "referral_code": entry.referral_code,
    }
