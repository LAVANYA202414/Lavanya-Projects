import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from server.database import Base
from enum import Enum



# ---------------- PAYMENT TABLE ----------------
# Purpose: High-level payment record for subscriptions/bookings/topups.

class PaymentPurpose(str, Enum):
    SUBSCRIPTION = "subscription"
    BOOKING = "booking"
    TOPUP = "topup"
    OTHER = "other"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentProvider(str, Enum):
    STRIPE = "stripe"
    RAZORPAY = "razorpay"
    MANUAL = "manual"


class Payment(Base):
    __tablename__ = "payments"

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

    contact_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("contacts.id"), 
        nullable=True
    )

    booking_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("bookings.id"), 
        nullable=True
    )

    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(10), nullable=False)

    purpose = Column(Enum(PaymentPurpose), nullable=False)

    provider = Column(Enum(PaymentProvider), nullable=False)
    provider_payment_id = Column(String(180), nullable=True)

    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.pending)

    metadata = Column(JSONB, nullable=False, default=dict)

    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now()
    )

    updated_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )


# ---------------- PAYMENT TRANSACTION TABLE ----------------
# Purpose: Detailed transaction logs under a payment.

class TransactionType(str, Enum):
    CHARGE = "charge"
    REFUND = "refund"
    CAPTURE = "capture"
    AUTHORIZATION = "authorization"
    PAYOUT = "payout"
    ADJUSTMENT = "adjustment"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    payment_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("payments.id"), 
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

    transaction_type = Column(Enum(TransactionType), nullable=False)

    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(10), nullable=False)

    status = Column(Enum(TransactionStatus), nullable=False)

    provider_transaction_id = Column(String(180), nullable=True)

    provider_payload = Column(JSONB, nullable=False, default=dict)

    created_at = Column(DateTime(timezone=True), server_default=func.now())