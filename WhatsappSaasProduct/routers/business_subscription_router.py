from fastapi import APIRouter , Depends
from uuid import UUID
from sqlalchemy.orm import Session
from server.database import get_db
from schemas.models_schemas.subscription_schemas import (
    BusinessSubscriptionCreate,
    BusinessSubscriptionUpdate,
)
from services.business_subscription_service import (
    BusinessSubscriptionService
)

# Configure service object
service = BusinessSubscriptionService()

# configure router
router = APIRouter(
    prefix="/business-subscription",
    tags= ["Business Subscription Plans"]
)

@router.post("/create")
async def create_business_subscription_plan(
    request : BusinessSubscriptionCreate,
    db: Session = Depends(get_db)
):
    return service.create_business_subscription(request , db)


@router.get("/list")
async def get_all_business_subscriptions(
    db: Session = Depends(get_db)
):
    return service.get_all_subscriptions_func(db)


@router.get("/{sub_id}")
async def get_business_subscription_by_id(
    sub_id : UUID,
    db: Session = Depends(get_db)
):
    return service.get_subscription_by_id_func(sub_id  , db)

@router.patch("/{sub_id}")
async def update_business_subscription(
    sub_id : UUID,
    request: BusinessSubscriptionUpdate,
    db: Session = Depends(get_db)
):
    return service.update_business_subscription_func(sub_id ,request, db)


@router.delete("/{sub_id}/delete")
async def delete_business_subscription_plans(
    sub_id : UUID,
    db: Session = Depends(get_db)
):
    return service.cancel_subscription(sub_id  , db)

