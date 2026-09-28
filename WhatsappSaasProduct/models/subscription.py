import uuid
from sqlalchemy import (
    Column , String , TIMESTAMP, ForeignKey, Integer, Boolean, func , Enum as SQLEnum ,UniqueConstraint
)

from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from server.database import Base


# Plans Table
class Plans(Base):
    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name = Column(String(120), nullable=False)
    code = Column(String(80) , unique=True, nullable=False)

    monthly_price_cents = Column(Integer, nullable=False)
    yearly_price_cents = Column(Integer, nullable=False)

    currency = Column(String(10) , nullable=False)

    limits = Column(JSONB ,nullable=False , default=dict)
    features = Column(JSONB ,nullable=False , default=dict)

    is_active = Column(Boolean ,nullable=False ,default=True)
    
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    subscriptions = relationship(
        "BusinessSubscriptions",
        back_populates="plan"
    )


# Business Subscription Table
class BuisnessSubscriptionEnum(str,PyEnum):
    TRIAL="trial"
    ACTIVE="active"
    PASTDUE="past_due"
    CANCELLED="cancelled"
    EXPIRED="expired"

class BillingCycleEnum(str , PyEnum):
    MONTHLY="monthly"
    YEARLY="yearly"

class ProviderEnum(str, PyEnum):
    STRIPE ='stripe'
    RAZORPAY ='razorpay'
    MANUAL ='manual'


class BusinessSubscriptions(Base):
    __tablename__ = "business_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id",ondelete="CASCADE"),
        nullable=False
    )

    business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("business.id",ondelete="CASCADE"),
        nullable=False
    )

    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("plans.id",ondelete="CASCADE"),
        nullable=False
    )

    status = Column(
        SQLEnum(
            BuisnessSubscriptionEnum,
            name= "business_subscriptions_enum",
            values_callable=lambda enum: [e.value for e in enum]
        ),
        nullable=False,
        default=BuisnessSubscriptionEnum.TRIAL
    )

    billing_cycle = Column(
        SQLEnum(
            BillingCycleEnum,
            name= "billing_cycle_enum",
            values_callable=lambda enum: [e.value for e in enum]
        ),
        nullable=False,
        default=BillingCycleEnum.MONTHLY
    )

    current_period_start = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    current_period_end = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    provider = Column(
        SQLEnum(
            ProviderEnum,
            name= "provider_enum",
            values_callable=lambda enum: [e.value for e in enum]
        ),
        nullable=False,
        default=ProviderEnum.MANUAL
    )
    
    provider_subscription_id = Column(String(180))

    cancel_at_period_end = Column(Boolean, nullable=False , default=False)
    
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tenant = relationship(
        "Tenant",
        back_populates="subscriptions"
    )

    business = relationship(
        "Business",
        back_populates="subscriptions"
    )

    plan = relationship(
        "Plans",
        back_populates="subscriptions"
    )

    __table_args__ = (
        UniqueConstraint(
            "business_id",
            "plan_id",
            "billing_cycle",
            name="uq_business_plan_cycle"
        ),
    )