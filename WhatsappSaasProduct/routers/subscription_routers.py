from fastapi import APIRouter , Depends
from uuid import UUID
from sqlalchemy.orm import Session
from server.database import get_db
from schemas.models_schemas.subscription_schemas import (
    PlanCreate,
    PlanUpdate,
)
from services.subscription_service import (
    SubscriptionService,
)

# Configure service object
service= SubscriptionService()

# configure router
router = APIRouter(
    prefix="/plan",
    tags= ["Subscription Plans"]
)


#-----------------------------------------------------------------------------------------------------------
################################# SUBSCRIPTION PLAN ROUTER ###############################################
#-----------------------------------------------------------------------------------------------------------

@router.post("/")
async def create_subscription_plan(
    request : PlanCreate,
    db: Session = Depends(get_db)
):
    
    return service.create_subscription_plan_func(request , db)


@router.get("/list")
async def get_subscription_plans(
    db: Session = Depends(get_db)
):
    return service.get_subscription_plans_func(db)


@router.patch("/{plan_id}/update")
async def update_subscription_plans(
    plan_id : UUID,
    request: PlanUpdate,
    db: Session = Depends(get_db)
):
    return service.update_subscription_plan_func(plan_id , request , db)


@router.delete("/{plan_id}/delete")
async def delete_subscription_plans(
    plan_id : UUID,
    db: Session = Depends(get_db)
):
    return service.delete_subscription_plan_func(plan_id  , db)