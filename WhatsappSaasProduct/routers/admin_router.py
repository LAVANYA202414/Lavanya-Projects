from fastapi import APIRouter , Depends
from sqlalchemy.orm import Session
from server.database import get_db
from uuid import UUID
from schemas.models_schemas.onboarding_schemas import OnboardingRequest
from schemas.models_schemas.translation_schema import LanguageCreate
from schemas.models_schemas.business_schemas import (
    AdminBusinessCreate,
    GetAllBusiness,
    BusinessStatusEnum
)
from schemas.models_schemas.tenant_schema import TenantStatusEnum
from services.onboarding_service import ONBoardingService
from services.admin_service import AdminServices
from utils.jwt import JWTService

# Configure service object
service = AdminServices()

# configure router
router = APIRouter(
    prefix="/admin",
    tags= ["Admin"]
)

@router.post("/create-tenant-and-business")
async def admin_create_tenant(
    request:OnboardingRequest,
    db: Session = Depends(get_db),
    current_user = Depends(JWTService().require_role(["admin"]))
):
    return ONBoardingService().business_signup(request, db)


@router.post("/create-business")
async def create_business(
    request:AdminBusinessCreate,
    db: Session = Depends(get_db),
    current_user = Depends(JWTService().require_role(["admin"]))
):
    return service.create_business_func(request , db)


@router.get("/businesses")
async def get_all_businesses(
    # request : GetAllBusiness
    status : BusinessStatusEnum,
    db: Session = Depends(get_db),
    current_user = Depends(JWTService().require_role(["admin"]))  
):
    return service.get_all_businesses_func(status,db)


@router.get("/tenant/businesses")
async def get_tenant_all_business(
    request : GetAllBusiness,
    db: Session = Depends(get_db),
    current_user = Depends(JWTService().require_role(["admin"]))  
):
    return service.get_tenant_businesses_func(request,db)


@router.get("/tenants")
async def get_all_tenants(
    status: TenantStatusEnum,
    db: Session = Depends(get_db),
    current_user = Depends(JWTService().require_role(["admin"]))  
):
    return service.get_all_tenants_func(status, db)


@router.get("/tenant/{tenant_id}")
async def get_tenant(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(JWTService().require_role(["admin"]))  
):
    return service.get_tenant_by_id(tenant_id, db)


@router.delete("/tenant/{tenant_id}")
async def delete_tenant(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(JWTService().require_role(["admin"]))  
):
    return service.delete_tenant_by_id(tenant_id, db)


@router.post("/create-langauge")
async def admin_create_langauge(
    request: LanguageCreate,
    db: Session = Depends(get_db),
    current_user = Depends(JWTService().require_role(["admin"]))  
):
    return service.create_language_func(request, db)


@router.delete("/delete-language/{lang_code}")
async def delete_tenant(
    lang_code: str,
    db: Session = Depends(get_db),
    current_user = Depends(JWTService().require_role(["admin"]))  
):
    return service.delete_language_func(lang_code, db)
