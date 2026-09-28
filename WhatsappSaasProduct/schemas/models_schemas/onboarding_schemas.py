from enum import Enum as PyEnum
from typing import Optional
from typing import Dict , Any

from pydantic import (
    BaseModel,
    EmailStr,
    ConfigDict,
    Field
)

from schemas.models_schemas.subscription_schemas import (
    BillingCycleEnum,
)

class BusinessIndustryEnum(str, PyEnum):
    SALON = "salon"
    CLINIC = "clinic"
    RESTAURANT = "restaurant"
    HOTEL = "hotel"
    GYM = "gym"
    REAL_ESTATE = "real_estate"
    CUSTOM = "custom"

class OwnerSignup(BaseModel):
    owner_name: str = Field(..., min_length=2, max_length=150)
    owner_email: EmailStr
    owner_phone: Optional[str] = None
    owner_password: str = Field(..., min_length=8)
    role: str
    preferred_language: str
    timezone: str
    metadata_ : Dict[str , Any]

class BusinessBase(BaseModel):
    industry: BusinessIndustryEnum
    business_name: str
    branch_name: str

    phone: str
    email: EmailStr

    address: str
    city: str
    state: str
    country: str

    latitude: float
    longitude: float

    timezone: str
    default_language: str

class SubscriptionSignup(BaseModel):
    plan_code: str
    billing_cycle: BillingCycleEnum

class WhatsAppSignup(BaseModel):
    connect_now: bool = False

    provider: Optional[str] = None
    waba_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    display_phone_number: Optional[str] = None

    # Plain token from frontend.
    # Backend will encrypt and store it.
    access_token: Optional[str] = None


class OnboardingRequest(BaseModel):
    owner: OwnerSignup
    business: BusinessBase
    # subscription: SubscriptionSignup
    # whatsapp: Optional[WhatsAppSignup] = None

    model_config = ConfigDict(

    json_schema_extra={
        "example": {
            "owner": {
                "owner_name": "John Smith",
                "owner_email": "john@gmail.com",
                "owner_phone": "+31612345678",
                "owner_password": "Password@123",
                "role": "owner",
                "preferred_language": 'en',
                'timezone': "Asia/Kolkatta",
                'metadata_' : {},
            },
            "business": {
                "industry": "clinic",
                "business_name": "Smile Dental Clinic",
                "branch_name": "Amsterdam Branch",
                "phone": "+31698765432",
                "email": "info@smileclinic.nl",
                "address": "Street 10",
                "city": "Amsterdam",
                "state": "North Holland",
                "country": "Netherlands",
                "latitude": 52.3676,
                "longitude": 4.9041,
                "timezone": "Europe/Amsterdam",
                "default_language": "en",
            }
            
        }
    }
)