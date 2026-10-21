from pydantic import BaseModel, Field, field_validator
from typing import Optional, Union
from uuid import UUID
from datetime import datetime


def _clean_phone(v: str) -> str:
    if isinstance(v, str):
        s = v.replace(" ", "").replace("-", "").strip()
        if s.startswith("+91"):
            s = s[3:]
        return s
    return v


class LoginRequest(BaseModel):
    phone_number: str
    password: Optional[str] = None
    login_type: str = "password"  # "password" | "otp"

    @field_validator("phone_number", mode="before")
    @classmethod
    def clean_phone(cls, v: str) -> str:
        return _clean_phone(v)


class TokenResponse(BaseModel):
    accessToken: str
    citizen_account_id: Union[str, UUID]
    family_account_id: Optional[Union[str, UUID]] = None  # alias of citizen_account_id; see docs/LEGACY_COMPATIBILITY.md
    phone_number: Optional[str] = None
    display_name: Optional[str] = None


class OTPRequest(BaseModel):
    phone_number: str

    @field_validator("phone_number", mode="before")
    @classmethod
    def clean_phone(cls, v: str) -> str:
        return _clean_phone(v)


class OTPVerifyRequest(BaseModel):
    phone_number: str
    code: str

    @field_validator("phone_number", mode="before")
    @classmethod
    def clean_phone(cls, v: str) -> str:
        return _clean_phone(v)

    @field_validator("code", mode="before")
    @classmethod
    def clean_code(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class ForgotPasswordResetRequest(BaseModel):
    phone_number: str
    otp_code: str
    new_password: str = Field(..., min_length=8)

    @field_validator("phone_number", mode="before")
    @classmethod
    def clean_phone(cls, v: str) -> str:
        return _clean_phone(v)


class RegisterCredentials(BaseModel):
    phone_number: str
    password: Optional[str] = None

    @field_validator("phone_number", mode="before")
    @classmethod
    def clean_phone(cls, v: str) -> str:
        return _clean_phone(v)


class RegisterRequest(BaseModel):
    credentials: RegisterCredentials
    display_name: Optional[str] = None


class OTPDevRetrievalResponse(BaseModel):
    otp: str
    expires_at: datetime
    phone_number: str
