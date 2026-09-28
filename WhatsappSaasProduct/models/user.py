import uuid
from sqlalchemy import Column, String, Boolean, Text, ForeignKey, TIMESTAMP ,Enum as SQLEnum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from server.database import Base
from enum import Enum as PyEnum
from sqlalchemy.orm import relationship


# users
#Purpose: Dashboard users who can login: owners, managers, staff, support users.

class UserEnum(str , PyEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    INVITED = "invited"
    DELETED = "deleted"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("tenants.id" , ondelete='CASCADE'),
        nullable=False
    )

    name = Column(String(150), nullable=False)
    email = Column(String(180), nullable=False)
    phone = Column(String(30))

    password_hash = Column(Text, nullable=False)

    preferred_language = Column(String(10))

    is_email_verified = Column(Boolean, default=False, nullable=False)
    is_phone_verified = Column(Boolean, default=False, nullable=False)
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    is_internal_user = Column(Boolean, default=False, nullable=False)

    status = Column(
        SQLEnum(
            UserEnum,
            name= "users_enum",
            values_callable=lambda enum: [e.value for e in enum]
        ),
        nullable=False,
        default=UserEnum.ACTIVE
    )

    last_login_at = Column(TIMESTAMP(timezone=True))

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

    business_users = relationship(
        "BusinessUser",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_tenant_email"),
        UniqueConstraint("tenant_id", "phone", name="uq_tenant_phone"),
    )


# ---------------- USER VERIFICATION ----------------
# Purpose: Stores email/phone/2FA/password reset verification attempts.

class VerificationTypeEnum(str, PyEnum):
    EMAIL = "email"
    PHONE = "phone"
    TWO_FACTOR = "two_factor"
    PASSWORD_RESET = "password_reset"


class VerificationStatusEnum(str, PyEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    EXPIRED = "expired"
    FAILED = "failed"


class UserVerification(Base):
    __tablename__ = "user_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    verification_type = Column(
        SQLEnum(VerificationTypeEnum, name="verification_type_enum"),
        nullable=False,
        default=VerificationTypeEnum.EMAIL
    )

    verification_value = Column(String(255), nullable=False)

    otp_hash = Column(Text, nullable=False)

    expires_at = Column(TIMESTAMP(timezone=True))
    verified_at = Column(TIMESTAMP(timezone=True))

    status = Column(
        SQLEnum(VerificationStatusEnum, name="verification_status_enum"),
        nullable=False,
        default=VerificationStatusEnum.PENDING
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )


# ---------------- PASSWORD RESET TABLE ----------------
# Purpose: Stores email/phone/2FA/password reset verification attemp

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    token = Column(String, unique=True, index=True)
    
    expires_at = Column(TIMESTAMP(timezone=True))

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )