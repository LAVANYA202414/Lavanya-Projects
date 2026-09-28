import uuid
from sqlalchemy import (
    Column ,Boolean, String , Text, ForeignKey, Enum as SQLEnum , DECIMAL ,TIMESTAMP,func,UniqueConstraint , Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID ,JSONB
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from server.database import Base



# ---------------- BUSINESS ----------------
# Purpose: Each physical branch/shop/clinic/hotel/gym is a separate subscribed business.

class BusinessIndustryEnum(str, PyEnum):
    SALON = "salon"
    CLINIC = "clinic"
    RESTAURANT = "restaurant"
    HOTEL = "hotel"
    GYM = "gym"
    REAL_ESTATE = "real_estate"
    CUSTOM = "custom"

class BusinessStatusEnum(str , PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"

class VerificationStatusEnum(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Business(Base):

    __tablename__ ="business"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "business_name",
            name="uq_business_tenant_name"
        ),
    )

    id = Column(UUID(as_uuid=True) , primary_key=True , default=uuid.uuid4)

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id" , ondelete="CASCADE"),
        nullable=False,
    )

    industry = Column(
        SQLEnum(
            BusinessIndustryEnum,
            name="business_industry_enum",
            values_callable=lambda enum: [e.value for e in enum]
        ),
        nullable=False,
    )

    business_name = Column(String(180) , nullable=False)
    branch_name = Column(String(150))

    phone = Column(String(30))
    email = Column(String(180))

    address = Column(Text)
    city= Column(String(100))
    state = Column(String(100))
    country= Column(String(100))

    latitude= Column(DECIMAL(10,7))
    longitude= Column(DECIMAL(10,7))

    timezone = Column(String(80), nullable=False)
    default_language= Column(String(100))

    status = Column(
        SQLEnum(
        BusinessStatusEnum,
        name="business_status_enum",
        values_callable=lambda enum: [e.value for e in enum]

        ),
        nullable=False,
        default=BusinessStatusEnum.ACTIVE
    )

    verification_status = Column(
        SQLEnum(
            VerificationStatusEnum,
            name="verification_status_enum",
            values_callable=lambda enum: [e.value for e in enum]
        ),
        nullable=False,
        default=VerificationStatusEnum.PENDING
    )

    verified_at = Column(TIMESTAMP(timezone=True))

    verified_by = Column(
        UUID(as_uuid=True), 
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True
        )

    settings = Column(JSONB, nullable=False, default=dict)

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

    deleted_at = Column(TIMESTAMP(timezone=True))

    # Relationships
    tenant = relationship(
        "Tenant", 
        back_populates="business",
        foreign_keys=[tenant_id]
    )
    
    subscriptions = relationship(
        "BusinessSubscriptions",
        back_populates="business"
    )


# ---------------- BUSINESS USERS ----------------
# Purpose: Mapping table: which user can access which business and with what role.
class BusinessUserRoleEnum(str, PyEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    STAFF = "staff"
    SUPPORT = "support"
    VIEWER = "viewer"


class BusinessUser(Base):
    __tablename__ = "business_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("tenants.id" , ondelete="CASCADE"), 
        nullable=False
    )

    business_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("business.id", ondelete='CASCADE'),
        nullable=False
    )

    user_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("users.id" , ondelete="CASCADE"), 
        nullable=False
    )

    role = Column(
        SQLEnum(
            BusinessUserRoleEnum,
            name="business_users_enum",
            values_callable=lambda enum: [e.value for e in enum]
            ),
        nullable=False,
        default=BusinessUserRoleEnum.OWNER
    )

    permissions = Column(JSONB, nullable=False, default=dict)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="business_users"
    )

    tenant = relationship(
        "Tenant",
        back_populates="business_users",
    )

    __table_args__ = (
        UniqueConstraint("business_id", "user_id", name="uq_business_user"),
    )
    

# ---------------- BUSINESS VERIFICATION ----------------
# Purpose: Business registration/license verification documents.

class BusinessVerificationTypeEnum(str, PyEnum):
    GST = "gst"
    VAT = "vat"
    COMPANY_REGISTRATION = "company_registration"
    LICENSE = "license"
    OTHER = "other"


class BusinessVerificationStatusEnum(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class BusinessVerification(Base):
    __tablename__ = "business_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )

    business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("business.id", ondelete="CASCADE"),
        nullable=False
    )

    verification_type = Column(
        SQLEnum(BusinessVerificationTypeEnum, name="business_verification_type_enum"),
        nullable=False
    )

    document_number = Column(String(150))

    document_url = Column(Text)

    status = Column(
        SQLEnum(BusinessVerificationStatusEnum, name="business_verification_status_enum"),
        nullable=False,
        default=BusinessVerificationStatusEnum.PENDING
    )

    reviewed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True
    )

    reviewed_at = Column(TIMESTAMP(timezone=True))
    rejection_reason = Column(Text)

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

# ---------------- BUSINESS LANGUAGES ----------------
# Purpose: Languages enabled for a specific business bot/dashboard.

class BusinessLanguages(Base):
    __tablename__ = "business_languages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )

    business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("business.id", ondelete="CASCADE"),
        nullable=False
    )

    language_code = Column(
        String(10), 
        ForeignKey("languages.code"), 
        nullable=False
    )

    is_default= Column(Boolean, nullable=False, default=False)

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    __table_args__ = (
        # Prevent duplicate language per business
        UniqueConstraint(
            "tenant_id",
            "business_id",
            "language_code",
            name="uq_business_language"
        ),
    )