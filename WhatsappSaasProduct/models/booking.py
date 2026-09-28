import uuid
from sqlalchemy import Column, String, Boolean, Enum, ForeignKey, TIMESTAMP ,Integer,Text
from sqlalchemy.dialects.postgresql import UUID , JSONB
from sqlalchemy.sql import func
from server.database import Base
import enum

# ---------------- BOOKINGS TABLE ----------------
# Purpose: Final booking/appointment/reservation record.

booking_status_enum = Enum(
    "pending",
    "confirmed",
    "cancelled",
    "rescheduled",
    "completed",
    "no_show",
    name="booking_status_enum"
)

payment_status_enum = Enum(
    "unpaid",
    "paid",
    "failed",
    "refunded",
    "partially_refunded",
    name="payment_status_enum"
)

booking_source_enum = Enum(
    "whatsapp",
    "dashboard",
    "api",
    "website",
    name="booking_source_enum"
)

class Booking(Base):

    __tablename__ = "bookings"

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
        nullable=False
    )

    form_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("booking_forms.id"), 
        nullable=True
    )


    service_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("services.id"), 
        nullable=True
    )

    staff_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("staff_members.id"), 
        nullable=True
    )

    start_time = Column(TIMESTAMP(timezone=True), nullable=False)
    end_time = Column(TIMESTAMP(timezone=True), nullable=False)

    status = Column(
        booking_status_enum, 
        nullable=False, 
        default="pending"
    )

    payment_status = Column(
        payment_status_enum, 
        nullable=False, 
        default="unpaid"
    )

    source = Column(
        booking_source_enum, 
        nullable=False
    )

    language_code = Column(
        String(10), 
        ForeignKey("languages.code"), 
        nullable=True
    )

    answers = Column(JSONB, nullable=False, default=dict)

    notes = Column(Text, nullable=True)

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)


# ---------------- BOOKING ANSWERS TABLE ----------------
# Purpose: Question-level answers for filtering/reporting; bookings.answers stores full snapshot.

class BookingAnswers:

    __tablename__ = "booking_answers"
    
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

    booking_id = Column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id"),
        nullable=False
    )

    booking_session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("booking_sessions.id"),
        nullable=False
    )

    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("booking_questions.id"),
        nullable=True
    )

    question_key = Column(
        String(100)
    )

    answer_value = Column(
        JSONB,
        nullable=False,
        default=dict
    )
   
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )

# ---------------- BOOKING SESSSION TABLE ----------------
# Purpose: Temporary WhatsApp booking flow before final booking is created.

booking_status_enum = Enum(
    "in_progress",
    "completed",
    "abandoned",
    "expired",
    name="booking_status_enum"
)

class BookingSession(Base):
    __tablename__ = "booking_sessions"

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
        nullable=False
    )

    form_id = Column(
        UUID(as_uuid=True),
        ForeignKey("booking_forms.id"),
        nullable=False
    )

    current_question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("booking_questions.id"),
        nullable=True
    )

    language_code = Column(
        String(10),
        ForeignKey("languages.code"),
        nullable=True
    )

    status = Column(
        booking_status_enum,
        nullable=False,
        default="in_progress"
    )

    answers = Column(
        JSONB,
        nullable=False,
        default=dict
    )

    expires_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


# ---------------- BOOKING FORMS TABLE ----------------
# Purpose: Dynamic form per business. Allows each business to ask different questions.

class FormType(str, enum.Enum):
    BOOKING = "booking"
    ENQUIRY = "enquiry"
    SUUPORT = "support"
    LEAD = "lead"

class BookingForm(Base):
    __tablename__ = "booking_forms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("tenants.id", ondelete="CASCADE"), 
        nullable=False
    )

    business_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("businesses.id", ondelete="CASCADE"), 
        nullable=False
    )

    name = Column(String(150), nullable=False)

    form_type = Column(
        Enum(FormType, name="form_type_enum"), 
        nullable=False
    )

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

    updated_at = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )


# ---------------- BOOKING QUESTIONS TABLE ----------------
# Purpose: Dynamic questions asked during WhatsApp booking flow.

class QuestionType(str, enum.Enum):
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


class BookingQuestion(Base):
    __tablename__ = "booking_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("tenants.id", ondelete="CASCADE"), 
        nullable=False
    )

    business_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("businesses.id", ondelete="CASCADE"), 
        nullable=False
    )

    form_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("booking_forms.id", ondelete="CASCADE"), 
        nullable=False
    )

    question_key = Column(String(100), nullable=False)
    question_text = Column(String, nullable=False)

    question_type = Column(
        Enum(QuestionType, name="question_type_enum"), 
        nullable=False
    )

    is_required = Column(Boolean, nullable=False, default=True)

    sort_order = Column(Integer, nullable=False)

    options = Column(JSONB, nullable=True)  # for choice आधारित questions
    validation_rules = Column(JSONB, nullable=True)
    conditional_rules = Column(JSONB, nullable=True)

    maps_to_booking_field = Column(String(100), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

    updated_at = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

# ---------------- BOOKING QUESTION TRANSLATION TABLE ----------------
# Purpose: Translated text/options for booking questions.

class BookingQuestionTranslation(Base):
    __tablename__ = "booking_question_translations"

    id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )

    question_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("booking_questions.id", ondelete="CASCADE"), 
        nullable=False
    )

    language_code = Column(
        String(10), 
        nullable=False
    )  

    question_text = Column(String, nullable=False)
    options = Column(JSONB, nullable=True)  # translated options

    created_at = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )