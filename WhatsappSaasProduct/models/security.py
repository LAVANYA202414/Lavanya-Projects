import uuid
import enum
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, ARRAY, TEXT
from sqlalchemy.sql import func
from server.database import Base


# ---------------- API KEY TABLE ----------------
# Purpose: API keys for external integrations. Store hash only, not raw key

class ApiKeyStatus(str, enum.Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ApiKey(Base):
    __tablename__ = "api_keys"

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

    name = Column(String(150), nullable=False)

    key_prefix = Column(String(40), nullable=False)
    key_hash = Column(TEXT, nullable=False)

    scopes = Column(ARRAY(TEXT), nullable=False)

    status = Column(
        Enum(ApiKeyStatus), 
        nullable=False, 
        default=ApiKeyStatus.ACTIVE
    )

    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    created_by = Column(
        UUID(as_uuid=True), 
        ForeignKey("users.id"), 
        nullable=True
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)