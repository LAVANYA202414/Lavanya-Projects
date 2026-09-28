from sqlalchemy import (
    Column, String, Integer, Boolean,
    ForeignKey, TIMESTAMP, Text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from server.database import Base



# ---------------- STAFF SERVICE TABLE ----------------
# Purpose: Bookable services/products such as haircut, consultation, room booking.

class Service(Base):
    __tablename__ = "services"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    business_id = Column(UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False)

    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)

    duration_minutes = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)

    currency = Column(String(10), nullable=False)

    is_active = Column(Boolean, nullable=False, default=True)

    metadata_ = Column(JSONB, nullable=False, default=dict)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), onupdate=func.now(), nullable=False)
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)