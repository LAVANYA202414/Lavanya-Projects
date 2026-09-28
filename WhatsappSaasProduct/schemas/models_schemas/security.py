from pydantic import BaseModel, Field ,ConfigDict
from uuid import UUID
from typing import List, Optional
from datetime import datetime
from enum import Enum



# ---------------- API KEY TABLE SCHEMAS ----------------

class ApiKeyStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ApiKeyCreate(BaseModel):
    tenant_id: UUID
    business_id: UUID
    name: str = Field(..., max_length=150)

    scopes: List[str]

    expires_at: Optional[datetime]


class ApiKeyInternalCreate(ApiKeyCreate):
    key_prefix: str
    key_hash: str
    created_by: Optional[UUID]


class ApiKeyResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    business_id: UUID

    name: str
    key_prefix: str

    scopes: List[str]

    status: ApiKeyStatus

    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]

    created_by: Optional[UUID]

    created_at: datetime
    revoked_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class ApiKeyWithSecretResponse(ApiKeyResponse):
    api_key: str  # FULL KEY (shown only once)