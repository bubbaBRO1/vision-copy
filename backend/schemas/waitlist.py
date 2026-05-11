from pydantic import BaseModel, EmailStr
from typing import Optional


class WaitlistJoinRequest(BaseModel):
    email: EmailStr
    name: str
    use_case: Optional[str] = None
    referral_code: Optional[str] = None


class WaitlistJoinResponse(BaseModel):
    position: int
    referral_code: str
    message: str


class WaitlistPositionResponse(BaseModel):
    email: str
    position: int
    approved: bool
    referral_count: int
    referral_code: str
