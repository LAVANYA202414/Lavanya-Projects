from pydantic import BaseModel, EmailStr,ConfigDict, Field
from typing import Optional
from uuid import UUID
from datetime import datetime
from enum import Enum

# ---------------- USERS SCHEMAS----------------

class UserEnum(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    INVITED = "invited"
    DELETED = "deleted"

# Tenant user create schemas  
class TenantUserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    preferred_language: Optional[str] = "en"
    status: UserEnum

# Admin user create schemas  
class AdminUserCreate(BaseModel):
    tenant_id: UUID
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    preferred_language: Optional[str] = "en"

class TenantUserResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    email: EmailStr
    phone: Optional[str] = None

    preferred_language: Optional[str] = "en"
    status: UserEnum

    is_email_verified: bool
    is_phone_verified: bool
    two_factor_enabled: bool
    is_internal_user: bool

    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ---------------- USERS VERIFICATION SCHEMAS----------------
class VerificationTypeEnum(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    TWO_FACTOR = "two_factor"
    PASSWORD_RESET = "password_reset"


class VerificationStatusEnum(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    EXPIRED = "expired"
    FAILED = "failed"

class UserVerificationBase(BaseModel):
    tenant_id: UUID
    user_id: UUID
    verification_type: VerificationTypeEnum
    verification_value: str


class UserVerificationCreate(UserVerificationBase):
    otp_hash: str
    expires_at: Optional[datetime]


class UserVerificationResponse(UserVerificationBase):
    id: UUID
    status: VerificationStatusEnum

    expires_at: Optional[datetime]
    verified_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------- USERS LOGIN SCHEMAS----------------
class VerifyPhoneRequest(BaseModel):
    otp: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    email : EmailStr

class ResetPasswordRequest(BaseModel):
    token : str
    new_password: str

    
