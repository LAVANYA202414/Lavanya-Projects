from fastapi import APIRouter , Depends
from uuid import UUID
from sqlalchemy.orm import Session
from server.database import get_db
from services.users_service import UserService
from schemas.models_schemas.user_schemas import TenantUserCreate


# Configure service object
service = UserService()

# configure router
router = APIRouter(
    prefix="/tenant",
    tags= ["Users"]
)


@router.post("/create-user")
async def create_user(
    request: TenantUserCreate,
    db: Session = Depends(get_db)
):
    return service.create_user_func(request , db)


@router.get("/{tenant_id}/list")
async def get_all_users(
    tenant_id: UUID,
    db: Session = Depends(get_db)
):
    return service.get_all_users(tenant_id , db)


@router.get("/{tenant_id}/user/{user_id}")
async def get_user_by_id(
    tenant_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db)
):
    return service.get_user(tenant_id ,user_id, db)