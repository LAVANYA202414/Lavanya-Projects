from pydantic import BaseModel,ConfigDict
from uuid import UUID
from enum import Enum



# ---------------- LANGUAGES TABLE SCHEMAS ----------------
class LanguageBase(BaseModel):
    code: str
    name: str
    is_active: bool = True

class LanguageCreate(LanguageBase):
    pass

class LanguageResponse(LanguageBase):

    model_config = ConfigDict(from_attributes=True)


# ---------------- TRANSLATION TABLE SCHEMAS ----------------

class TranslationScopeEnum(str, Enum):
    SYSTEM = "system"
    BUSINESS = "business"
    BOOKING = "booking"
    CAMPAIGN = "campaign"
    SUPPORT = "support"
    NOTIFICATION = "notification"


class TranslationBase(BaseModel):
    tenant_id: UUID
    business_id: UUID
    language_code: str
    translation_key: str
    translation_value: str
    scope: TranslationScopeEnum


class TranslationCreate(TranslationBase):
    pass


class TranslationResponse(TranslationBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)