from sqlalchemy.exc import IntegrityError
import sys
from utils.logger import get_logger
from models.subscription import (
    Plans,
)
from schemas.models_schemas.subscription_schemas import (
    PlanResponse,
)
from utils.helper import (
    normalize_string,
    error_response,
    success_response,
    deep_clean
)

logger = get_logger(__name__)


class SubscriptionService:

    # CREATE PLAN
    def create_subscription_plan_func(self, request, db):
        try:
            logger.info("Subscription Plan creation request received.")

            payload_data = request.model_dump()

            # Normalize strings (lowercase + trim)
            payload_data["code"] = normalize_string(payload_data["code"])
            payload_data["name"] = normalize_string(payload_data["name"])

            # Validate prices
            if payload_data["monthly_price_cents"] < 0 or payload_data["yearly_price_cents"] < 0:
                return error_response(
                    message="Prices must be greater than or equal to 0",
                    status_code=400
                )

            # Check unique code
            if db.query(Plans).filter(Plans.code == payload_data["code"]).first():
                return error_response("Plan with this code already exists.", 400)

            # Check unique name
            if db.query(Plans).filter(Plans.name == payload_data["name"]).first():
                return error_response("Plan with this name already exists.", 400)

            subscription_plan = Plans(**payload_data)

            db.add(subscription_plan)
            db.commit()
            db.refresh(subscription_plan)

            return success_response(
                message="Subscription plan created successfully.",
                data=PlanResponse.model_validate(subscription_plan).model_dump(mode="json"),
                status_code=201
            )

        except IntegrityError:
            db.rollback()
            return error_response(
                message="Duplicate entry detected (code or name must be unique).",
                status_code=400
            )

        except Exception as e:
            db.rollback()
            exc_tb = sys.exc_info()[2]
            logger.exception(f"Error creating subscription plan. Error={str(e)} Line={exc_tb.tb_lineno}")

            return error_response(
                message=f"Failed to create plan. Error={str(e)} Line={exc_tb.tb_lineno}",
                status_code=500
            )

    # GET PLANS (PAGINATION)
    def get_subscription_plans_func(self, db, skip: int = 0, limit: int = 10):
        try:
            subscription_plans = (
                db.query(Plans)
                .filter(Plans.is_active == True)
                .order_by(Plans.created_at.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )

            data = [
                PlanResponse.model_validate(plan).model_dump(mode="json")
                for plan in subscription_plans
            ]

            return success_response(
                message="Subscription plans fetched successfully.",
                data=data,
                status_code=200
            )

        except Exception as e:
            exc_tb = sys.exc_info()[2]
            logger.exception("Error fetching subscription plans")

            return error_response(
                message=f"Failed to fetch plans. Error={str(e)} Line={exc_tb.tb_lineno}",
                status_code=500
            )

    # UPDATE PLAN
    def update_subscription_plan_func(self, plan_id, request, db):
        try:
            logger.info(f"Update request for plan_id={plan_id}")

            plan = db.query(Plans).filter(Plans.id == plan_id).first()

            if not plan:
                return error_response("Subscription plan not found.", 404)

            update_data = request.model_dump(exclude_unset=True)
            cleaned_data = deep_clean(update_data)

            # Normalize strings if present
            if "code" in cleaned_data:
                cleaned_data["code"] = normalize_string(cleaned_data["code"])

                existing_code = db.query(Plans).filter(
                    Plans.code == cleaned_data["code"],
                    Plans.id != plan_id
                ).first()

                if existing_code:
                    return error_response("Plan with this code already exists.", 400)

            if "name" in cleaned_data:
                cleaned_data["name"] = normalize_string(cleaned_data["name"])

                existing_name = db.query(Plans).filter(
                    Plans.name == cleaned_data["name"],
                    Plans.id != plan_id
                ).first()

                if existing_name:
                    return error_response("Plan with this name already exists.", 400)

            # Validate prices
            if "monthly_price_cents" in cleaned_data and cleaned_data["monthly_price_cents"] < 0:
                return error_response("Monthly price must be >= 0", 400)

            if "yearly_price_cents" in cleaned_data and cleaned_data["yearly_price_cents"] < 0:
                return error_response("Yearly price must be >= 0", 400)

            # Apply updates
            for key, value in cleaned_data.items():
                setattr(plan, key, value)

            db.commit()
            db.refresh(plan)

            return success_response(
                message="Subscription plan updated successfully.",
                data=PlanResponse.model_validate(plan).model_dump(mode="json"),
                status_code=200
            )

        except IntegrityError:
            db.rollback()
            return error_response(
                message="Duplicate entry detected.",
                status_code=400
            )

        except Exception as e:
            db.rollback()
            exc_tb = sys.exc_info()[2]
            logger.exception("Error updating subscription plan")

            return error_response(
                message=f"Failed to update plan. Error={str(e)} Line={exc_tb.tb_lineno}",
                status_code=500
            )

    # DELETE PLAN (SOFT DELETE)
    def delete_subscription_plan_func(self, plan_id, db):
        try:
            logger.info(f"Delete request for plan_id={plan_id}")

            plan = db.query(Plans).filter(Plans.id == plan_id).first()

            if not plan:
                return error_response("Subscription plan not found.", 404)

            # Soft delete
            plan.is_active = False

            db.commit()

            return success_response(
                message="Subscription plan deleted successfully.",
                data={},
                status_code=200
            )

        except Exception as e:
            db.rollback()
            exc_tb = sys.exc_info()[2]
            logger.exception("Error deleting subscription plan")

            return error_response(
                message=f"Failed to delete plan. Error={str(e)} Line={exc_tb.tb_lineno}",
                status_code=500
            )
        

