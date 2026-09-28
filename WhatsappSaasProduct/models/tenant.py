import uuid
from enum import Enum as PyEnum
from sqlalchemy import (Column,String,TIMESTAMP,func,Enum as SQLEnum,)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from server.database import Base



class TenantStatusEnum(str, PyEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class Tenant(Base):

    __tablename__ = "tenants"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    owner_name = Column(
        String(200),
        nullable=False
    )

    owner_email = Column(
        String(200),
        nullable=False,
        unique=True
    )

    owner_phone = Column(
        String(30)
    )

    status = Column(
        SQLEnum(
            TenantStatusEnum,
            name="tenant_status_enum",
            values_callable=lambda enum: [e.value for e in enum]
        ),
        nullable=False,
        default=TenantStatusEnum.ACTIVE
    )

    timezone = Column(
        String(80),
        nullable=False
    )

    metadata_ = Column(
        JSONB,
        nullable=False,
        default=dict
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

    deleted_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True
    )

    # Relationship with Business table
    business = relationship(
        "Business",
        back_populates="tenant",
        foreign_keys="Business.tenant_id",
        cascade="all, delete-orphan",   
        passive_deletes=True            
    )

    # Relationship with BusinessSubscription table
    subscriptions = relationship(
        "BusinessSubscriptions",
        back_populates="tenant",
        cascade="all, delete-orphan",   
        passive_deletes=True            
    )

    # Relationship with BusinessUser table
    business_users = relationship(
        "BusinessUser",
        back_populates="tenant",
        cascade="all, delete-orphan",   
        passive_deletes=True            

    )