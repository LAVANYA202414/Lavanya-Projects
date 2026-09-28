from fastapi import APIRouter , Depends
from uuid import UUID
from sqlalchemy.orm import Session
from server.database import get_db
from schemas.models_schemas.business_schemas import (
    BusinessUserCreate,
    BusinessUpdate,
    BusinessLanguageCreate,
)
from schemas.models_schemas.user_schemas import TenantUserCreate
from services.business_service import BusinessService
from utils.jwt import JWTService

# Configure service object
service = BusinessService()

# configure router
router = APIRouter(
    prefix="/tenant/businesses",
    tags= ["Owner Business"]
)


@router.get("/")
async def get_businesses(
    current_user = Depends(JWTService().require_role(["owner"])),
    db: Session = Depends(get_db)
):
    return service.get_businesses_func(current_user, db)


@router.post("/create-user")
async def create_user(
    request: TenantUserCreate,
    current_user = Depends(JWTService().require_role(["owner"])),
    db: Session = Depends(get_db)
):
    return service.create_user_func(request, current_user, db)


@router.post("/create-business-user")
async def create_business_user(
    request: BusinessUserCreate,
    current_user = Depends(JWTService().require_role(["owner"])),
    db: Session = Depends(get_db)
):
    return service.create_business_user_func(request, current_user, db)

@router.get("/{business_id}")
async def get_business_detail(
    business_id: UUID,
    current_user = Depends(JWTService().require_role(["owner"])),
    db: Session = Depends(get_db)
):
    return service.get_businesses_by_id(business_id,current_user, db)


@router.patch("/{business_id}")
async def update_business(
    business_id: UUID,
    request: BusinessUpdate,
    current_user = Depends(JWTService().require_role(["owner"])),
    db: Session = Depends(get_db)
):
    return service.update_business_by_id(business_id,request,current_user, db)


@router.delete("/{business_id}")
async def delete_business(
    business_id: UUID,
    current_user = Depends(JWTService().require_role(["owner"])),
    db: Session = Depends(get_db)
):
    return service.delete_business_by_id(business_id,current_user, db)


@router.get("/{business_id}/languages")
async def business_languages(
    business_id: UUID,
    current_user = Depends(JWTService().require_role(["owner"])),
    db: Session = Depends(get_db)
):
    return service.get_all_business_languages(business_id, current_user, db)


@router.post("/{business_id}/add-language")
async def add_business_language(
    business_id : UUID,
    request: BusinessLanguageCreate,
    db: Session = Depends(get_db),
    current_user = Depends(JWTService().require_role(["owner"]))  # 
):
    return service.add_business_lang(business_id, request, db, current_user)


@router.delete("/{business_id}/languages/{language}")
async def remove_business_language(
    business_id : UUID,
    language: str,
    db: Session = Depends(get_db),
    current_user = Depends(JWTService().require_role(["owner"]))  # 
):
    return service.remove_business_lang_func(business_id,language, db, current_user)

