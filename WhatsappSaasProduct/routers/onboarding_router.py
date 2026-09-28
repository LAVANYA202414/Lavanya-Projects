from fastapi import APIRouter , Depends
from sqlalchemy.orm import Session
from server.database import get_db
from services.onboarding_service import ONBoardingService
from schemas.models_schemas.onboarding_schemas import OnboardingRequest

# Configure service object
service = ONBoardingService()

# configure router
router = APIRouter(
    prefix="/onboarding",
    tags= ["OnBoarding"]
)


@router.post("/signup")
async def register_business(
    request: OnboardingRequest,
    db: Session = Depends(get_db)
):
    return service.business_signup(request, db)
