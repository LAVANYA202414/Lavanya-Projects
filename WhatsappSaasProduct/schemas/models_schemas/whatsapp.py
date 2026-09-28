from pydantic import BaseModel, Field ,ConfigDict 
from typing import Optional ,Dict , Any
from uuid import UUID
from datetime import datetime
from enum import Enum



# ---------------- WHATSAPP ACCOUNTS TABLE SCHEMAS ----------------

# Enums
class WhatsAppProvider(str, Enum):
    META = "meta"
    TWILIO = "twilio"
    DIALOG360 = "360dialog"


class WhatsAppStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONNECTED = "disconnected"
    SUSPENDED = "suspended"


# Base Schema
class WhatsAppAccountBase(BaseModel):
    tenant_id: UUID
    business_id: UUID

    provider: WhatsAppProvider
    waba_id: Optional[str] = None

    phone_number_id: str = Field(..., max_length=100)
    display_phone_number: Optional[str] = None

    webhook_verified: bool = False
    phone_verified: bool = False

    status: WhatsAppStatus = WhatsAppStatus.INACTIVE

    last_token_refresh_at: Optional[datetime] = None
    token_expires_at: Optional[datetime] = None


# Create Schema
class WhatsAppAccountCreate(WhatsAppAccountBase):
    access_token_encrypted: Optional[str] = None


# Update Schema
class WhatsAppAccountUpdate(BaseModel):
    display_phone_number: Optional[str] = None
    webhook_verified: Optional[bool] = None
    phone_verified: Optional[bool] = None
    status: Optional[WhatsAppStatus] = None

    last_token_refresh_at: Optional[datetime] = None
    token_expires_at: Optional[datetime] = None


# Response Schema
class WhatsAppAccountResponse(WhatsAppAccountBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ---------------- CONVERSATIONS TABLE SCHEMAS ----------------

class ConversationStatus(str, Enum):
    OPEN = "open"
    PENDING = "pending"
    CLOSED = "closed"

class ConversationCreate(BaseModel):
    tenant_id: UUID
    business_id: UUID
    contact_id: UUID
    whatsapp_account_id: UUID

    assigned_user_id: Optional[UUID] = None
    language_code: Optional[str] = None
    ai_enabled: Optional[bool] = True

class ConversationUpdate(BaseModel):
    status: Optional[ConversationStatus] = None
    assigned_user_id: Optional[UUID] = None
    ai_enabled: Optional[bool] = None
    unread_count: Optional[int] = None

class ConversationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    business_id: UUID
    contact_id: UUID
    whatsapp_account_id: UUID

    assigned_user_id: Optional[UUID]
    status: ConversationStatus

    ai_enabled: bool
    language_code: Optional[str]

    last_message_at: Optional[datetime]
    unread_count: int

    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

# ---------------- MESSAGES TABLE SCHEMAS ----------------

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


class MessageCreate(BaseModel):
    tenant_id: UUID
    business_id: UUID
    conversation_id: UUID
    contact_id: UUID

    direction: MessageDirection
    message_type: MessageType

    content: Optional[str] = None
    payload: Dict[str, Any]

    language_code: Optional[str] = None


class MessageResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    business_id: UUID
    conversation_id: UUID
    contact_id: UUID

    direction: MessageDirection
    message_type: MessageType

    provider_message_id: Optional[str]
    content: Optional[str]
    payload: Dict[str, Any]

    status: MessageStatus
    error_reason: Optional[str]

    language_code: Optional[str]

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------- MESSAGE TEMPLATE TABLE SCHEMAS ----------------

class TemplateCategory(str, Enum):
    marketing = "marketing"
    utility = "utility"
    authentication = "authentication"


class TemplateStatus(str, Enum):
    draft = "draft"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    paused = "paused"
    disabled = "disabled"

class MessageTemplateCreate(BaseModel):
    tenant_id: UUID
    business_id: UUID
    whatsapp_account_id: UUID

    template_name: str
    category: TemplateCategory

    language_code: Optional[str] = None
    components: Dict[str, Any]


class MessageTemplateUpdate(BaseModel):
    status: Optional[TemplateStatus] = None
    components: Optional[Dict[str, Any]] = None
    rejection_reason: Optional[str] = None


class MessageTemplateResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    business_id: UUID
    whatsapp_account_id: UUID

    template_name: str
    category: TemplateCategory
    status: TemplateStatus

    language_code: Optional[str]
    components: Dict[str, Any]

    provider_template_id: Optional[str]
    rejection_reason: Optional[str]

    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)