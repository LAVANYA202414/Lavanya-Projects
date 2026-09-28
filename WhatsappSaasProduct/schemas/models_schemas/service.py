from pydantic import BaseModel, Field, validator ,ConfigDict
from uuid import UUID
from typing import Optional, Dict, Any


# ---------------- SERVICES TABLE SCHEMAS ----------------

class ServiceBase(BaseModel):
    tenant_id: UUID
    business_id: UUID

    name: str
    description: Optional[str] = None

    duration_minutes: int = Field(..., gt=0)
    price_cents: int = Field(..., ge=0)

    currency: str

    is_active: bool = True
    metadata: Dict[str, Any] = {}

    @validator("currency")
    def validate_currency(cls, v):
        return v.upper()


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
    duration_minutes: Optional[int]
    price_cents: Optional[int]
    currency: Optional[str]
    is_active: Optional[bool]
    metadata: Optional[Dict[str, Any]]


class ServiceResponse(ServiceBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)