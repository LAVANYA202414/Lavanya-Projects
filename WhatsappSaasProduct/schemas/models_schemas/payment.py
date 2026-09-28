from pydantic import BaseModel ,ConfigDict
from uuid import UUID
from typing import Optional, Dict
from enum import Enum


# ---------------- PAYMENT TABLE SCHEMAS ----------------

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


class PaymentCreate(BaseModel):
    tenant_id: UUID
    business_id: UUID
    contact_id: Optional[UUID]
    booking_id: Optional[UUID]

    amount_cents: int
    currency: str

    purpose: PaymentPurpose
    provider: PaymentProvider

    provider_payment_id: Optional[str]
    metadata: Dict = {}


class PaymentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    business_id: UUID
    contact_id: Optional[UUID]
    booking_id: Optional[UUID]

    amount_cents: int
    currency: str

    purpose: PaymentPurpose
    provider: PaymentProvider
    provider_payment_id: Optional[str]

    status: PaymentStatus
    metadata: Dict

    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)

# ---------------- PAYMENT TRANSACTION TABLE SCHEMAS ----------------

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


class PaymentTransactionCreate(BaseModel):
    payment_id: UUID
    tenant_id: UUID
    business_id: UUID

    transaction_type: TransactionType
    amount_cents: int
    currency: str

    status: TransactionStatus

    provider_transaction_id: Optional[str]
    provider_payload: Dict = {}


class PaymentTransactionResponse(BaseModel):
    id: UUID
    payment_id: UUID
    tenant_id: UUID
    business_id: UUID

    transaction_type: TransactionType
    amount_cents: int
    currency: str

    status: TransactionStatus

    provider_transaction_id: Optional[str]
    provider_payload: Dict

    created_at: str

    model_config = ConfigDict(from_attributes=True)