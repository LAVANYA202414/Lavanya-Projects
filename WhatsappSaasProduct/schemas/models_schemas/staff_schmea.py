from pydantic import BaseModel, EmailStr , validator,ConfigDict, Field
from uuid import UUID
from enum import Enum
from typing import Optional, Dict, Any
from datetime import time


# ---------------- STAFF MEMBER TABLE SCHEMAS ----------------

class StaffStatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"

class StaffMemberCreate(BaseModel):
    business_id: UUID
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    job_title: Optional[str] = None
    status: StaffStatusEnum = "active"
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="_metadata")


class StaffMemberResponse(BaseModel):
    id: UUID
    business_id: UUID
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    job_title: Optional[str] = None
    status: StaffStatusEnum = "active"
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="_metadata")


    model_config = ConfigDict(from_attributes=True)


class StaffMemberUpdate(BaseModel):
    business_id: Optional[UUID] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    job_title: Optional[str] = None
    status: Optional[StaffStatusEnum] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="_metadata")


# ---------------- STAFF SERVICES TABLE SCHEMAS ----------------

class StaffServiceBase(BaseModel):
    staff_id: UUID
    service_id: UUID


class StaffServiceCreate(StaffServiceBase):
    pass


class StaffServiceResponse(StaffServiceBase):

    model_config = ConfigDict(from_attributes=True)


# ---------------- STAFF AVALIABILITY TABLE SCHEMAS ----------------

class StaffAvailabilityBase(BaseModel):
    tenant_id: UUID
    business_id: UUID
    staff_id: UUID

    weekday: int  # 0-6

    start_time: time
    end_time: time

    is_active: bool = True


    @validator("weekday")
    def validate_weekday(cls, v):
        if v < 0 or v > 6:
            raise ValueError("weekday must be between 0 and 6")
        return v

    @validator("end_time")
    def validate_time(cls, v, values):
        if "start_time" in values and v <= values["start_time"]:
            raise ValueError("end_time must be greater than start_time")
        return v


class StaffAvailabilityCreate(StaffAvailabilityBase):
    pass


class StaffAvailabilityResponse(StaffAvailabilityBase):
    id: UUID
    created_at: Optional[str]

    model_config = ConfigDict(from_attributes=True)