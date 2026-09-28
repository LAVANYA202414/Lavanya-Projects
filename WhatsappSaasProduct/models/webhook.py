
import uuid
from enum import Enum
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Enum as PyEnum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.sql import func
from server.database import Base


# ---------------- WEBHOOK SUBSCRIPTIONS TABLE ----------------
# Purpose: Outbound webhooks configured by tenant/business.

class WebhookStatus(str, Enum):
    ACTIVE = "active"
    DIABLED = "disabled"
    FAILED = "failed"


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("tenants.id"), 
        nullable=False
    )

    business_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("businesses.id"), 
        nullable=False
    )

    target_url = Column(Text, nullable=False)
    secret_encrypted = Column(Text, nullable=True)

    event_types = Column(ARRAY(String), nullable=False)

    status = Column(
        PyEnum(WebhookStatus), 
        nullable=False, 
        default=
        WebhookStatus.active
    )

    created_by = Column(
        UUID(as_uuid=True), 
        ForeignKey("users.id"), 
        nullable=True
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# ---------------- WEBHOOK DELIVERIES TABLE ----------------
# Purpose: Delivery attempts for outbound webhooks with retry tracking.

class DeliveryStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    subscription_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("webhook_subscriptions.id"), 
        nullable=False
    )

    tenant_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("tenants.id"), 
        nullable=False
    )

    business_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("businesses.id"), 
        nullable=False
    )

    event_type = Column(String(120), nullable=False)

    payload = Column(JSONB, nullable=False)

    response_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)

    attempt_count = Column(Integer, nullable=False, default=0)

    status = Column(
        PyEnum(DeliveryStatus), 
        nullable=False, 
        default=DeliveryStatus.PENDING
    )

    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    delivered_at = Column(DateTime(timezone=True), nullable=True)


