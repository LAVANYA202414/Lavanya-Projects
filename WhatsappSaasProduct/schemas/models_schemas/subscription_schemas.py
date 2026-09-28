from pydantic import BaseModel ,ConfigDict, Field
from uuid import UUID
from typing import Dict , Optional
from datetime import datetime
from enum import Enum


# Plans Table Schemas
class PlanBase(BaseModel):
    name: str
    code: str

    monthly_price_cents: int
    yearly_price_cents: int

    currency: str

    limits: Dict = Field(default_factory=dict)
    features: Dict = Field(default_factory=dict)

    is_active: bool = True


class PlanCreate(PlanBase):
    pass


class PlanResponse(PlanBase):
    id: UUID
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None

    monthly_price_cents: Optional[int] = None
    yearly_price_cents: Optional[int] = None

    currency: Optional[str] = None

    limits: Optional[Dict] = None
    features: Optional[Dict] = None

    is_active: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")


# Business Subscription Plans
class BuisnessSubscriptionEnum(str,Enum):
    TRIAL= "trial"
    ACTIVE= "active"
    PASTDUE= "past_due"
    CANCELLED= "cancelled"
    EXPIRED = "expired"

class BillingCycleEnum(str , Enum):
    MONTHL = "monthly"
    YEARLY = "yearly"

class ProviderEnum(str, Enum):
    STRIPE ='stripe'
    RAZORPAY ='razorpay'
    MANUAL ='manual'


class BusinessSubscriptionBase(BaseModel):
    tenant_id: UUID
    business_id: UUID
    plan_id: UUID
    status: BuisnessSubscriptionEnum
    billing_cycle : BillingCycleEnum

    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]

    provider: ProviderEnum
    provider_subscription_id: Optional[str]

    cancel_at_period_end: bool = False


class BusinessSubscriptionCreate(BusinessSubscriptionBase):
    pass


class BusinessSubscriptionResponse(BusinessSubscriptionBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class BusinessSubscriptionUpdate(BaseModel):
    plan_id: Optional[UUID] = Field(default=None)
    status: Optional[BuisnessSubscriptionEnum] = Field(default=None)
    billing_cycle: Optional[BillingCycleEnum] = Field(default=None)

    current_period_start: Optional[datetime] = Field(default=None)
    current_period_end: Optional[datetime] = Field(default=None)

    provider: Optional[ProviderEnum] = Field(default=None)
    provider_subscription_id: Optional[str] = Field(default=None)

    cancel_at_period_end: Optional[bool] = Field(default=None)

    model_config = ConfigDict(from_attributes=True)

    # only show plan ID in swagger payload
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "plan_id": "3fa85f64-5717-4562-b3fc-2c963f66afa"
            }
        }
    )