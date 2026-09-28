# app/schemas/business.py

from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum

# ---------------- BUSINESS SCHEMAS----------------
class BusinessIndustryEnum(str, Enum):
    SALON = "salon"
    CLINIC = "clinic"
    RESTAURANT = "restaurant"
    HOTEL = "hotel"
    GYM = "gym"
    REAL_ESTATE = "real_estate"
    CUSTOM = "custom"


class BusinessStatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class VerificationStatusEnum(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class BusinessBase(BaseModel):
    industry: BusinessIndustryEnum
    business_name: str
    branch_name: str

    phone: str
    email: EmailStr

    address: str
    city: str
    state: str
    country: str

    latitude: float
    longitude: float

    timezone: str
    default_language: str

    status: BusinessStatusEnum

    settings: Dict[str, Any]

class BusinessCreate(BusinessBase):
    pass

class AdminBusinessCreate(BaseModel):
    tenant_id : UUID
    industry: BusinessIndustryEnum
    business_name: str
    branch_name: str

    phone: str
    email: EmailStr

    address: str
    city: str
    state: str
    country: str

    latitude: float
    longitude: float

    timezone: str
    default_language: str

    status: BusinessStatusEnum

    settings: Dict[str, Any]


class BusinessUpdate(BaseModel):
    business_name: Optional[str]
    branch_name: Optional[str]
    status: Optional[BusinessStatusEnum]
    verification_status: Optional[VerificationStatusEnum]


class BusinessResponse(BusinessBase):
    id: UUID
    tenant_id: UUID

    status: BusinessStatusEnum
    verification_status: VerificationStatusEnum

    verified_at: Optional[datetime]
    # verified_by: Optional[UUID]

    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class AllBusinessResponse(BaseModel):
    id: UUID
    business_name: str
    branch_name: str
    status: BusinessStatusEnum

    model_config = ConfigDict(from_attributes=True)


class GetAllBusiness(BaseModel):
    status : BusinessStatusEnum
    tenant_id : UUID

# ---------------- BUSINESS USERS SCHEMAS----------------

class BusinessUserRoleEnum(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    STAFF = "staff"
    SUPPORT = "support"
    VIEWER = "viewer"


class BusinessUserCreate(BaseModel):
    business_id: UUID
    user_id: UUID
    role: BusinessUserRoleEnum = BusinessUserRoleEnum.STAFF
    is_active: bool = False


class BusinessUserResponse(BaseModel):
    id: UUID
    role: BusinessUserRoleEnum
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------- BUSINESS USER VERIFICATION SCHEMAS----------------

class BusinessVerificationTypeEnum(str, Enum):
    GST = "gst"
    VAT = "vat"
    COMPANY_REGISTRATION = "company_registration"
    LICENSE = "license"
    OTHER = "other"


class BusinessVerificationStatusEnum(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class BusinessVerificationBase(BaseModel):
    tenant_id: UUID
    business_id: UUID
    verification_type: BusinessVerificationTypeEnum
    document_number: Optional[str]
    document_url: Optional[str]


class BusinessVerificationCreate(BusinessVerificationBase):
    pass


class BusinessVerificationReview(BaseModel):
    status: BusinessVerificationStatusEnum
    rejection_reason: Optional[str]


class BusinessVerificationResponse(BusinessVerificationBase):
    id: UUID
    status: BusinessVerificationStatusEnum

    reviewed_by: Optional[UUID]
    reviewed_at: Optional[datetime]

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)



# ---------------- BUSINESS LANGUAGES SCHEMAS----------------
class BusinessLanguageCreate(BaseModel):
    language_code: str
    is_default : bool = False

class BusinessLanguageResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    business_id: UUID
    language_code: str
    is_default: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)