from pydantic import BaseModel , Field ,ConfigDict
from uuid import UUID
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime


# ---------------- BOOKING TABLE SCHEMAS ----------------

# Enums (same as DB)
class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class PaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class BookingSource(str, Enum):
    WHATSAPP = "whatsapp"
    DASHBOARD = "dashboard"
    API = "api"
    WEBSITE = "website"


class BookingBase(BaseModel):
    tenant_id: UUID
    business_id: UUID
    contact_id: UUID

    form_id: Optional[UUID] = None
    service_id: Optional[UUID] = None
    staff_id: Optional[UUID] = None

    start_time: datetime
    end_time: datetime

    status: BookingStatus = BookingStatus.pending
    payment_status: PaymentStatus = PaymentStatus.unpaid
    source: BookingSource

    language_code: Optional[str] = None

    answers: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None


class BookingCreate(BookingBase):
    pass


class BookingUpdate(BaseModel):
    service_id: Optional[UUID] = None
    staff_id: Optional[UUID] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    status: Optional[BookingStatus] = None
    payment_status: Optional[PaymentStatus] = None

    answers: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class BookingResponse(BookingBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------- BOOKING ANSWERS TABLE SCHEMAS ----------------

class BookingAnswerBase(BaseModel):
    tenant_id: UUID
    business_id: UUID
    booking_id: UUID
    booking_session_id: UUID

    question_id: Optional[UUID] = None
    question_key: Optional[str] = Field(None, max_length=100)

    answer_value: Dict[str, Any] = Field(default_factory=dict)

class BookingAnswerCreate(BookingAnswerBase):
    pass

# Bulk Create (Very useful for forms)
class BookingAnswerBulkCreate(BaseModel):
    answers: list[BookingAnswerCreate]


# Update Schema
class BookingAnswerUpdate(BaseModel):
    question_id: Optional[UUID] = None
    question_key: Optional[str] = None
    answer_value: Optional[Dict[str, Any]] = None


# Response Schema
class BookingAnswerResponse(BookingAnswerBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ---------------- BOOKING SESSSION TABLE SCHEMAS ----------------

class BookingStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    EXPIRED = "expired"


class BookingSessionBase(BaseModel):
    tenant_id: UUID
    business_id: UUID
    contact_id: UUID
    form_id: UUID

    current_question_id: Optional[UUID] = None
    language_code: Optional[str] = Field(None, max_length=10)

    status: BookingStatus = BookingStatus.IN_PROGRESS
    answers: Dict[str, Any] = {}

    expires_at: Optional[datetime] = None


class BookingSessionCreate(BookingSessionBase):
    pass


class BookingSessionUpdate(BaseModel):
    current_question_id: Optional[UUID] = None
    language_code: Optional[str] = None
    status: Optional[BookingStatus] = None
    answers: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None


class BookingSessionResponse(BookingSessionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------- BOOKING FORM TABLE SCHEMAS ----------------

class FormTypeEnum(str, Enum):
    BOOKING = "booking"
    ENQUIRY = "enquiry"
    SUUPORT = "support"
    LEAD = "lead"

class BookingFormCreate(BaseModel):
    tenant_id: UUID
    business_id: UUID
    name: str
    form_type: FormTypeEnum
    is_active: bool = True

class BookingFormUpdate(BaseModel):
    name: str | None = None
    form_type: FormTypeEnum | None = None
    is_active: bool | None = None


class BookingFormResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    business_id: UUID
    name: str
    form_type: FormTypeEnum
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ---------------- BOOKING QUESTIONS SCHEMAS ----------------

class QuestionTypeEnum(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    YES_NO = "yes_no"
    PHONE = "phone"
    EMAIL = "email"
    LOCATION = "location"
    FILE = "file"
    SERVICE_SELECTOR = "service_selector"
    STAFF_SELECTOR = "staff_selector"



class BookingQuestionCreate(BaseModel):
    tenant_id: UUID
    business_id: UUID
    form_id: UUID

    question_key: str
    question_text: str
    question_type: QuestionTypeEnum

    is_required: bool = True
    sort_order: int

    options: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    conditional_rules: Optional[Dict[str, Any]] = None

    maps_to_booking_field: Optional[str] = None
    is_active: bool = True


class BookingQuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    question_type: Optional[QuestionTypeEnum] = None
    is_required: Optional[bool] = None
    sort_order: Optional[int] = None

    options: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    conditional_rules: Optional[Dict[str, Any]] = None

    maps_to_booking_field: Optional[str] = None
    is_active: Optional[bool] = None

class BookingQuestionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    business_id: UUID
    form_id: UUID

    question_key: str
    question_text: str
    question_type: QuestionTypeEnum

    is_required: bool
    sort_order: int

    options: Optional[Dict[str, Any]]
    validation_rules: Optional[Dict[str, Any]]
    conditional_rules: Optional[Dict[str, Any]]

    maps_to_booking_field: Optional[str]
    is_active: bool

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------- BOOKING QUESTION TRANSLATION SCHEMAS ----------------

class BookingQuestionTranslationCreate(BaseModel):
    question_id: UUID
    language_code: str
    question_text: str
    options: Optional[Dict[str, Any]] = None

class BookingQuestionTranslationResponse(BaseModel):
    id: UUID
    question_id: UUID
    language_code: str
    question_text: str
    options: Optional[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)