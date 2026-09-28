import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, TIMESTAMP , Integer , ARRAY , TEXT
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from server.database import Base
from sqlalchemy import UniqueConstraint

# ---------------- CONTACT TABLE ----------------
# Purpose: Customer master profile by phone under tenant. Customers do not login.

class Contact(Base):
    __tablename__ = "contacts"

    __table_args__ = (
        UniqueConstraint("tenant_id", "phone", name="uq_tenant_phone"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )

    phone = Column(String(30), nullable=False)

    name = Column(String(150), nullable=True)
    email = Column(String(180), nullable=True)

    preferred_language = Column(
        String(10),
        ForeignKey("languages.code"),
        nullable=True
    )

    is_phone_verified = Column(Boolean, default=False, nullable=False)
    last_verified_at = Column(TIMESTAMP(timezone=True), nullable=True)

    attributes = Column(JSONB, default=dict, nullable=False)

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


# ---------------- BUSINESS CONTACT TABLE ----------------
# Purpose: Customer master profile by phone under tenant. Customers do not login.

class BusinessContact(Base):
    __tablename__ = "business_contacts"

    # Unique per business + contact
    __table_args__ = (
        UniqueConstraint("business_id", "contact_id", name="uq_business_contact"),
    )

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

    contact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False
    )

    tags = Column(ARRAY(TEXT), default=list, nullable=True)

    last_message_at = Column(TIMESTAMP(timezone=True), nullable=True)

    total_bookings = Column(Integer, default=0, nullable=False)

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