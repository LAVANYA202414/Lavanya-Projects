from sqlalchemy import (
    Column, String, Boolean ,ForeignKey , Text ,Enum,func, TIMESTAMP,UniqueConstraint
)
from server.database import Base
import uuid
from enum import Enum as PyEnum
from sqlalchemy.dialects.postgresql import UUID

# ---------------- LANGUAGES TABLE ----------------
# Purpose: Supported languages such as en, hi, nl.

class Langauges(Base):
    __tablename__ ="languages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(10),index=True, unique = True)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint(
            "code",
            "name",
            name="uq__language"
        ),
    )



# ---------------- TRANSLATION TABLE ----------------
# Purpose: Reusable translated text for bot, notifications, dashboard, support.

class TranslationScope(PyEnum):
    SYSTEM = "system"
    BUSINESS = "business"
    BOOKING = "booking"
    CAMPAIGN = "campaign"
    SUPPORT = "support"
    NOTIFICATION = "notification"


class Translations(Base):
    __tablename__ = "translations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id",ondelete="CASCADE"),
        nullable=False
    )

    business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("business.id",ondelete="CASCADE"),
        nullable=False
    )

    language_code = Column(
        String(10), 
        ForeignKey("languages.code"), 
        nullable=False
    )

    translation_key = Column(String(180), nullable=False)
    translation_value = Column(Text, nullable=False)


    scope = Column(
        Enum(TranslationScope), 
        nullable=False,
        )
    
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
