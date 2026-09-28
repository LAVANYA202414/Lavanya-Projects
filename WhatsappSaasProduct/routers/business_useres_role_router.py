from fastapi import APIRouter , Depends
from sqlalchemy.orm import Session
from server.database import get_db


from uuid import UUID

from schemas.models_schemas.onboarding_schemas import OnboardingRequest
from schemas.models_schemas.translation_schema import LanguageCreate
from services.onboarding_service import ONBoardingService

from services.business_user_role_service import BusinessUserRoleService
from utils.jwt import JWTService

# Configure service object
service = BusinessUserRoleService()

# configure router
router = APIRouter(
    prefix="/businesses",
    tags= ["Business User Role Management"]
)
