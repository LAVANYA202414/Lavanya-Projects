
from pydantic import BaseModel, HttpUrl , ConfigDict
from uuid import UUID
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


# ----------------  WEBHOOK SUBSCRIPTIONS TABLE SCHEMAS ----------------

class WebhookStatus(str, Enum):
    ACTIVE = "active"
    DIABLED = "disabled"
    FAILED = "failed"


class WebhookSubscriptionCreate(BaseModel):
    tenant_id: UUID
    business_id: UUID

    target_url: HttpUrl
    event_types: List[str]


class WebhookSubscriptionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    business_id: UUID

    target_url: HttpUrl
    event_types: List[str]

    status: WebhookStatus

    created_by: Optional[UUID]

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ----------------  WEBHOOK DELIVERIES TABLE SCHEMAS ----------------

class DeliveryStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"

class WebhookDeliveryCreate(BaseModel):
    subscription_id: UUID
    tenant_id: UUID
    business_id: UUID

    event_type: str
    payload: Dict


class WebhookDeliveryResponse(BaseModel):
    id: UUID
    subscription_id: UUID

    tenant_id: UUID
    business_id: UUID

    event_type: str
    payload: Dict

    response_status: Optional[int]
    response_body: Optional[str]

    attempt_count: int
    status: DeliveryStatus

    next_retry_at: Optional[datetime]

    created_at: datetime
    delivered_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)