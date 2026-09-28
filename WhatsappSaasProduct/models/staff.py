from sqlalchemy import (
    Column, 
    String, 
    TIMESTAMP, 
    ForeignKey,
    Integer,
    Time, 
    Boolean,
    CheckConstraint,
    Enum as SQLEnum,
    UniqueConstraint
)

from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from server.database import Base
from enum import Enum as PyEnum

# ---------------- STAFF MEMBER TABLE ----------------
# Purpose: Staff of a business such as doctor, barber, trainer, receptionist.

class StaffStatus(PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"

class StaffMember(Base):
    __tablename__ = "staff_members"

    id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )

    tenant_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("tenants.id"), 
        nullable=False
    )

    business_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("business.id"), 
        nullable=False
    )

    name = Column(String(150), nullable=False)
    phone = Column(String(30), nullable=True)
    email = Column(String(180), nullable=True)

    job_title = Column(String(100), nullable=True)

    status = Column(
        SQLEnum(StaffStatus,
            name="staff_member_enum",
            values_callable=lambda enum: [e.value for e in enum]
        ), 
        nullable=False, 
        default=StaffStatus.ACTIVE
    )

    _metadata = Column(JSONB, nullable=False, default=dict)

    created_at = Column(
        TIMESTAMP(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

    updated_at = Column(
        TIMESTAMP(timezone=True), 
        onupdate=func.now(), 
        nullable=True
    )

    deleted_at = Column(
        TIMESTAMP(timezone=True), 
        nullable=True
    )

    __table_args__ = (
        UniqueConstraint("business_id", "email", name="uq_staff_email_per_business"),
        UniqueConstraint("business_id", "phone", name="uq_staff_phone_per_business"),
    )


# ---------------- STAFF SERVICE TABLE ----------------
# Purpose: Many-to-many relation: which staff can perform which service.

# class StaffService(Base):
#     __tablename__ = "staff_services"

#     staff_id = Column(UUID(as_uuid=True), ForeignKey("staff_members.id"), primary_key=True)
#     service_id = Column(UUID(as_uuid=True), ForeignKey("services.id"), primary_key=True)


# # ---------------- STAFF AVALIABILITY TABLE ----------------
# # Purpose: Weekly working hours used by booking engine.

# class StaffAvailability(Base):
#     __tablename__ = "staff_availability"

#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

#     tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
#     business_id = Column(UUID(as_uuid=True), ForeignKey("business.id"), nullable=False)

#     staff_id = Column(UUID(as_uuid=True), ForeignKey("staff_members.id"), nullable=False)

#     weekday = Column(Integer, nullable=False)  # 0-6

#     start_time = Column(Time, nullable=False)
#     end_time = Column(Time, nullable=False)

#     is_active = Column(Boolean, nullable=False, default=True)

#     created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

#     __table_args__ = (
#         CheckConstraint("weekday >= 0 AND weekday <= 6", name="check_weekday_range"),
#     )