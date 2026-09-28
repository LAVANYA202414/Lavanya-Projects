from fastapi import APIRouter , Depends
from sqlalchemy.orm import Session
from server.database import get_db
from uuid import UUID


from utils.jwt import JWTService

from schemas.models_schemas import (
    staff_schmea
)

from services.staff_service import StaffService

# Configure Service
services = StaffService()


# configure router
router = APIRouter(
    prefix="/tenant/staff",
    tags= ["Staff"]
)


@router.post("/create")
async def create_staff_member(
    request : staff_schmea.StaffMemberCreate,
    db: Session = Depends(get_db),
    current_user = Depends(JWTService().require_role(["owner"]))
):
    return services.create_staff_func(request , db , current_user)



@router.get("/")
async def get_all_staff_members_across_all_business(
    status: staff_schmea.StaffStatusEnum,
    db: Session = Depends(get_db),
    current_user = Depends(JWTService().require_role(["owner"]))
):
    return services.get_all_staff_func(db, status, current_user)



@router.get("/{staff_id}")
async def get_staff_member_by_id(
    staff_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(JWTService().require_role(["owner"]))
):
    return services.get_staff_by_id_func(db, staff_id, current_user)


@router.patch("/{staff_id}/update")
async def update_staff_member(
    staff_id: UUID,
    request: staff_schmea.StaffMemberUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(JWTService().require_role(["owner"]))
):
    return services.update_staff_by_id_func(staff_id,request,db, current_user)


@router.delete("/{staff_id}/delete")
async def delete_staff_member(
    staff_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(JWTService().require_role(["owner"]))
):
    return services.delete_staff_by_id_func(staff_id,db, current_user)