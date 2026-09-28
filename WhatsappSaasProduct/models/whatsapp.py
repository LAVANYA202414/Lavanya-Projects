import uuid
from sqlalchemy import (
    Column, String, ForeignKey,  TIMESTAMP, Boolean, Text, Integer ,Enum as SqlEnum
)
from sqlalchemy.dialects.postgresql import UUID ,JSONB
from sqlalchemy.sql import func
from server.database import Base
from enum import Enum

# ---------------- WHATSAPP ACCOUNTS TABLE ----------------
# Purpose: WhatsApp bot number connected to a subscribed business.

provider_enum = Enum(
    "meta",
    "twilio",
    "360dialog",
    name="whatsapp_provider_enum"
)

whatsapp_status_enum = Enum(
    "active",
    "inactive",
    "disconnected",
    "suspended",
    name="whatsapp_status_enum"
)

class WhatsAppAccount(Base):
    __tablename__ = "whatsapp_accounts"

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

    # External provider such as Meta, Stripe,Razorpay. 
    provider = Column(
        provider_enum,
        nullable=False
    )

    # whatsapp business id
    waba_id = Column(
        String(100),
        nullable=True
    )

    phone_number_id = Column(
        String(100),
        unique=True,
        nullable=False
    )

    display_phone_number = Column(
        String(30),
        nullable=True
    )

    access_token_encrypted = Column(
        Text,
        nullable=True
    )

    webhook_verified = Column(
        Boolean,
        default=False,
        nullable=False
    )

    phone_verified = Column(
        Boolean,
        default=False,
        nullable=False
    )

    last_token_refresh_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True
    )

    token_expires_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True
    )

    status = Column(
        whatsapp_status_enum,
        nullable=False,
        default="inactive"
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

# ---------------- CONVERSATIONS TABLE ----------------
# Purpose: WhatsApp chat thread between business and contact.

class ConversationStatus(str, Enum):
    OPEN = "open"
    PENDING = "pending"
    CLOSED = "closed"

class Conversation(Base):
    __tablename__ = "conversations"

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

    whatsapp_account_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("whatsapp_accounts.id"), 
        nullable=False
    )

    assigned_user_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("users.id"), 
        nullable=True
    )

    status = Column(
        SqlEnum(ConversationStatus, name="conversation_status"),
        nullable=False,
        default=ConversationStatus.OPEN
    )

    ai_enabled = Column(Boolean, nullable=False, default=True)

    language_code = Column(String(10), ForeignKey("languages.code"), nullable=True)

    last_message_at = Column(TIMESTAMP(timezone=True), nullable=True)

    unread_count = Column(Integer, nullable=False, default=0)

    created_at = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

    updated_at = Column(
        TIMESTAMP(timezone=True), 
        onupdate=func.now(), 
        nullable=False
    )


# ---------------- MESSAGES TABLE ----------------
# Purpose: Individual WhatsApp messages. Partition/archive later at high scale.

class MessageDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    BUTTON = "button"
    TEMPLATE = "template"
    INTERACTIVE = "interactive"

class MessageStatus(str, Enum):
    RECEIVED = "received"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

class Message(Base):
    __tablename__ = "messages"

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

    conversation_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("conversations.id"), 
        nullable=False
    )

    contact_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("contacts.id"), 
        nullable=False
    )

    direction = Column(
        SqlEnum(MessageDirection, name="message_direction"),
        nullable=False
    )

    message_type = Column(
        SqlEnum(MessageType, name="message_type"),
        nullable=False
    )

    provider_message_id = Column(String(150), nullable=True)

    content = Column(Text, nullable=True)

    payload = Column(JSONB, nullable=False)

    status = Column(
        SqlEnum(MessageStatus, name="message_status"),
        nullable=False,
        default=MessageStatus.QUEUED
    )

    error_reason = Column(Text, nullable=True)

    language_code = Column(
        String(10), 
        ForeignKey("languages.code"), 
        nullable=True
    )

    created_at = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

# ---------------- MESSAGE TEMPLATE TABLE ----------------
# Purpose: WhatsApp approved templates for campaigns and notifications.

class TemplateCategory(str, Enum):
    MARKETING = "marketing"
    UTILITY = "utility"
    AUTHENTICATION = "authentication"


class TemplateStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAUSED = "paused"
    DISABLED = "disabled"


class MessageTemplate(Base):

    __tablename__ = "message_templates"

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

    whatsapp_account_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("whatsapp_accounts.id"), 
        nullable=False
    )

    template_name = Column(String(150), nullable=False)

    language_code = Column(
        String(10), 
        ForeignKey("languages.code"), 
        nullable=True
    )

    category = Column(
        SqlEnum(TemplateCategory, name="template_category"),
        nullable=False
    )

    status = Column(
        SqlEnum(TemplateStatus, name="template_status"),
        nullable=False,
        default=TemplateStatus.DRAFT
    )

    components = Column(JSONB, nullable=False)

    provider_template_id = Column(String(150), nullable=True)

    rejection_reason = Column(Text, nullable=True)

    created_at = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

    updated_at = Column(
        TIMESTAMP(timezone=True), 
        onupdate=func.now(), 
        nullable=False
    )