from pydantic import BaseModel , EmailStr ,ConfigDict
from typing import Optional, Dict , Any
from uuid import UUID
from datetime import datetime
from enum import Enum



class TenantStatusEnum(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"

# Base
class TenantBase(BaseModel):
    owner_name : str
    owner_email: EmailStr
    owner_phone : Optional[str] =None
    timezone: str
    metadata_ : Dict[str , Any]

# Create 
class TenantCreate(TenantBase):
    pass

# update
class TenantUpdate(BaseModel):
    owner_name: Optional[str] = None
    # owner_email: Optional[EmailStr] = None
    owner_phone: Optional[str] = None
    timezone: Optional[str] = None
    metadata_: Optional[Dict[str, Any]] = None
    status: Optional[TenantStatusEnum] = None

    model_config = ConfigDict(extra="forbid")  # blocks unwanted fields


# Response 
class TenantResponse(BaseModel):
    id: UUID   

    owner_name: str
    owner_email: EmailStr
    owner_phone: Optional[str] = None
    timezone: str
    metadata_: Dict[str, Any]

    status: TenantStatusEnum
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# Response 
class TenantAllResponse(BaseModel):
    id: UUID   
    owner_name: str
    owner_email: EmailStr
    owner_phone: Optional[str] = None
    status: TenantStatusEnum

    model_config = ConfigDict(from_attributes=True)