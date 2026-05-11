from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
import re


class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    invite_code: Optional[str] = None
    hcaptcha_token: Optional[str] = None
    accept_terms: bool

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]{3,50}$", v):
            raise ValueError("Username must be 3-50 chars, alphanumeric/underscore/dash only")
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("accept_terms")
    @classmethod
    def must_accept(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Must accept terms of service")
        return v


class LoginRequest(BaseModel):
    identifier: str  # email or username
    password: str
    remember_me: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_verified: bool
    created_at: str

    model_config = {"from_attributes": True}


class SessionInfo(BaseModel):
    id: str
    user_agent: Optional[str]
    ip: Optional[str]
    created_at: str
    expires_at: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class GuestLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    is_guest: bool = True
