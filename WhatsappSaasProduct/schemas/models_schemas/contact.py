from pydantic import BaseModel, EmailStr ,ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any , List


# ---------------- CONTACT TABLE SCHEMAS----------------

class ContactBase(BaseModel):
    phone: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    preferred_language: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = {}


class ContactCreate(ContactBase):
    tenant_id: UUID

class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    preferred_language: Optional[str] = None

    is_phone_verified: Optional[bool] = None
    last_verified_at: Optional[datetime] = None

    attributes: Optional[Dict[str, Any]] = None

class ContactResponse(BaseModel):
    id: UUID
    tenant_id: UUID

    phone: str
    name: Optional[str]
    email: Optional[str]

    preferred_language: Optional[str]

    is_phone_verified: bool
    last_verified_at: Optional[datetime]

    attributes: Dict[str, Any]

    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class ContactMiniResponse(BaseModel):
    id: UUID
    phone: str
    name: Optional[str]

    model_config = ConfigDict(from_attributes=True)


# ---------------- BUSINESS CONTACT TABLE SCHEMAS----------------

class BusinessContactBase(BaseModel):
    business_id: UUID
    contact_id: UUID

    tags: Optional[List[str]] = []


class BusinessContactCreate(BusinessContactBase):
    tenant_id: UUID


class BusinessContactUpdate(BaseModel):
    tags: Optional[List[str]] = None
    last_message_at: Optional[datetime] = None
    total_bookings: Optional[int] = None

class BusinessContactResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    business_id: UUID
    contact_id: UUID

    tags: List[str]

    last_message_at: Optional[datetime]
    total_bookings: int

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)