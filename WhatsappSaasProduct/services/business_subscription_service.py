from sqlalchemy.exc import IntegrityError
import sys
from utils.logger import get_logger
from models.subscription import (BusinessSubscriptions,Plans)
from schemas.models_schemas.subscription_schemas import (BusinessSubscriptionResponse)
from utils.helper import (normalize_string,error_response,success_response,deep_clean)

logger = get_logger(__name__)
        

class BusinessSubscriptionService:

    def create_business_subscription(self, request, db):
        try:
            
            logger.info("Business Subscription Plan creation request received.")
            payload = request.model_dump()
            for key , value in payload.items():
                if isinstance(value, str):
                    payload[key] = normalize_string(value)


            existing = db.query(BusinessSubscriptions).filter(
                BusinessSubscriptions.business_id == payload["business_id"],
                BusinessSubscriptions.plan_id == payload["plan_id"],
                BusinessSubscriptions.billing_cycle == payload["billing_cycle"]
            ).first()

            if existing:
                return error_response(
                    "Subscription already exists for this business, plan and billing cycle",
                    400
                )
            business_subscription = BusinessSubscriptions(**payload)

            db.add(business_subscription)
            db.commit()
            db.refresh(business_subscription)

            return success_response(
                "Subscription created",
                BusinessSubscriptionResponse.model_validate(business_subscription).model_dump(mode="json"),
                201
            )

        except IntegrityError:
            db.rollback()
            logger.warning(f"Integrity error while creating business subscription: {str(e)}")

            return error_response(f"Integrity error while creating business subscription: {str(e)}", 400)

        except Exception as e:
            db.rollback()
            exc_tb = sys.exc_info()[2]

            logger.exception(
                "Error creating business subscription. Error: %s, Line: %s",
                str(e),
                exc_tb.tb_lineno
            )

            return error_response(str(e), 500)

    def get_all_subscriptions_func(self, db, skip=0, limit=10):

        try:
            subs = (
                db.query(BusinessSubscriptions)
                .offset(skip)
                .limit(limit)
                .all()
            )

            if not subs:
                return error_response(
                    message="Business Subscriptions Not Found.",
                    status_code=404
                )
            
            data = [
                BusinessSubscriptionResponse
                .model_validate(s)
                .model_dump(mode="json")
                for s in subs
            ]

            return success_response(
                "Subscriptions fetched",
                data= data,
                status_code=200,
                meta={"count": len(data)}
            )

        except Exception as e:
            db.rollback()
            exc_tb = sys.exc_info()[2]

            logger.exception(
                "Error fetching business subscriptions. Error: %s, Line: %s",
                str(e),
                exc_tb.tb_lineno
            )
            return error_response(str(e), 500)
        
    def cancel_subscription(self, sub_id , db):
        try: 
            subs = db.query(BusinessSubscriptions).filter(
                BusinessSubscriptions.id == sub_id
            ).first()

            if not subs:
                return error_response(
                    message=f"No Business Subscription found for ID : {sub_id}",
                    status_code=404
                )

            # Soft delete
            subs.status = "cancelled"
            db.commit()
            
            return success_response(
                message="Business Subscription cancelled successfully.",
                data={},
                status_code=200
            )
        
        except Exception as e:
            db.rollback()
            exc_tb = sys.exc_info()[2]

            error_message = f"Error while deleting business subscriptions. Error: {str(e)}, Line: {exc_tb.tb_lineno}",
            logger.exception(error_message)

            return error_response(error_message, 500)

    def get_subscription_by_id_func(self, sub_id, db):
        try:

            sub = db.query(BusinessSubscriptions).filter_by(id=sub_id).first()

            if not sub:
                return error_response("Subscription not found", 404)

            return success_response(
                "Subscription fetched",
                BusinessSubscriptionResponse.model_validate(sub).model_dump(mode="json"),
                200
            )

        except Exception as e:
            db.rollback()
            exc_tb = sys.exc_info()[2]

            error_message = f"Error while fetching business subscriptions based on ID. Error: {str(e)}, Line: {exc_tb.tb_lineno}",
            logger.exception(error_message)

            return error_response(error_message, 500)

    def update_business_subscription_func(self, sub_id, request, db):
        try:
            sub = db.query(BusinessSubscriptions).filter_by(id=sub_id).first()

            if not sub:
                return error_response("Business Subscription not found", 404)

            update_data = request.model_dump(exclude_unset=True)
            cleaned_data = deep_clean(update_data)

            #PLAN VALIDATION
            if "plan_id" in cleaned_data:
                new_plan_id = cleaned_data["plan_id"]

                # Check plan exists
                plan_exists = db.query(Plans).filter(Plans.id == new_plan_id).first()
                if not plan_exists:
                    return error_response(
                        f"Invalid plan_id: {new_plan_id} does not exist",
                        400
                    )

                # Check duplicate (exclude current record)
                duplicate = db.query(BusinessSubscriptions).filter(
                    BusinessSubscriptions.business_id == sub.business_id,
                    BusinessSubscriptions.plan_id == new_plan_id,
                    BusinessSubscriptions.billing_cycle == cleaned_data.get(
                        "billing_cycle", sub.billing_cycle
                    ),
                    BusinessSubscriptions.id != sub.id   #
                ).first()

                if duplicate:
                    return error_response(
                        "Subscription already exists for this business, plan and billing cycle",
                        400
                    )

            # Prevent multiple active subscriptions
            if cleaned_data.get("status") == "active":
                active_sub = db.query(BusinessSubscriptions).filter(
                    BusinessSubscriptions.business_id == sub.business_id,
                    BusinessSubscriptions.status == "active",
                    BusinessSubscriptions.id != sub.id
                ).first()

                if active_sub:
                    return error_response(
                        "Business already has an active subscription",
                        400
                    )

            # APPLY UPDATE
            for key, value in cleaned_data.items():
                if isinstance(value, str):
                    value = normalize_string(value)
                setattr(sub, key, value)

            db.commit()
            db.refresh(sub)

            return success_response(
                "Subscription updated",
                BusinessSubscriptionResponse.model_validate(sub).model_dump(mode="json"),
                200
            )

        except IntegrityError:
            db.rollback()
            return error_response("Database constraint error", 400)

        except Exception as e:
            db.rollback()
            exc_tb = sys.exc_info()[2]

            logger.exception(
                "Error while updating business subscription. Error: %s, Line: %s",
                str(e),
                exc_tb.tb_lineno
            )

            return error_response("Internal server error", 500)