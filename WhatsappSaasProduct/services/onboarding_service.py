from sqlalchemy.exc import IntegrityError
import sys
from uuid import UUID
from utils.logger import get_logger
from utils.helper import (normalize_dict_data,success_response,)
from models import tenant, business, user
from services.users_service import UserService
from fastapi import HTTPException

logger = get_logger(__name__)

class ONBoardingService:

    def _validate_phone(self, phone: str):
        if phone:
            is_valid, normalized_phone = UserService().validate_phone(phone)
            if not is_valid:
                return False, normalized_phone
            return True, normalized_phone
        return True, phone

    def create_business_language(
        self,
        db,
        tenant_id: UUID,
        business_id: UUID,
        language_code: str,
        is_default: bool = False
        ):

        business_lang = business.BusinessLanguages(
            tenant_id= tenant_id,
            business_id= business_id,
            language_code= language_code,
            is_default= is_default,
        )

        db.add(business_lang)
        db.flush()

        return business_lang
        
    def create_business_user(
        self,
        db,
        tenant_id,
        business_id,
        user_id,
        role="owner"):
        business_user_obj = business.BusinessUser(
            tenant_id=tenant_id,
            business_id=business_id,
            user_id=user_id,
            role=role,
            permissions={},
            is_active=True
        )

        db.add(business_user_obj)
        db.flush() 

        return business_user_obj

    def create_tenant_and_user(self, db, payload_data: dict):
        payload = payload_data.copy()

        # Validate phone
        is_valid, phone = self._validate_phone(payload.get("owner_phone"))
        if not is_valid:
            raise HTTPException(status_code = 400 , detail = phone)

        payload["owner_phone"] = phone

        normalized = normalize_dict_data(
            payload,
            exclude_fields={"timezone", "owner_password"}
        )

        tenant_obj = tenant.Tenant(
            owner_name=normalized.get("owner_name"),
            owner_email=normalized.get("owner_email"),
            owner_phone=normalized.get("owner_phone"),
            status="active",
            timezone=normalized.get("timezone"),
            metadata_={}
        )

        db.add(tenant_obj)
        db.flush()

        user_obj = user.User(
            tenant_id=tenant_obj.id,  
            name=normalized.get("owner_name"),
            email=normalized.get("owner_email"),
            phone=normalized.get("owner_phone"),
            password_hash=UserService().hash_password(
                normalized.get("owner_password")
            ),
            preferred_language=normalized.get("preferred_language"),
            status=tenant_obj.status,
        )

        db.add(user_obj)
        db.flush()

        return tenant_obj, user_obj

    def create_business(self, db, tenant_id: UUID, business_payload: dict):
        payload = normalize_dict_data(
            business_payload,
            exclude_fields={"timezone", "phone"}
        )

        is_valid, phone = self._validate_phone(payload.get("phone"))
        if not is_valid:
            raise HTTPException(status_code = 400 , detail = phone)

        payload.update({
            "phone": phone,
            "tenant_id": tenant_id,
            "status": "active"
        })

        business_obj = business.Business(**payload)

        db.add(business_obj)
        db.flush()

        return business_obj

    def business_signup(self, request, db):
        try:
            payload = request.model_dump()

            # Step 1
            tenant_obj, user_obj = self.create_tenant_and_user(
                db,
                payload.get("owner")
            )

            # Step 2
            business_obj = self.create_business(
                db,
                tenant_obj.id,
                payload.get("business")
            )

            # Step 3
            business_lang = self.create_business_language(
                db,
                tenant_obj.id,
                business_obj.id,
                language_code= payload.get("owner").get("preferred_language"),
                is_default=True
            )

            # Step 4
            business_user_obj = self.create_business_user(
                db=db,
                tenant_id=tenant_obj.id,
                business_id=business_obj.id,
                user_id=user_obj.id,
                role=payload.get("owner").get("role")
            )

            # MAKE SINGLE COMMIT FOR ALL
            db.commit()

            return success_response(
                detail="Tenant and Business created successfully.",
                data={
                    "tenant_id": str(tenant_obj.id),
                    "user_id": str(user_obj.id),
                    "business_id": str(business_obj.id),
                    "business_user_id": str(business_user_obj.id)  
                },
                status_code=201
            )
        
        except IntegrityError as e:
            db.rollback()

            logger.warning("Integrity error: %s", str(e))
            raise HTTPException(
                status_code=409,
                detail=f"Key (owner_email)=({payload.get('owner').get('owner_email')}) already exists."
            )

        except ValueError as e:
            db.rollback()
            logger.error("Value error: %s", str(e))
            raise HTTPException(status_code=400,detail=str(e))
        
        except HTTPException:
            raise

        except Exception as e:
            db.rollback()

            exc_tb = sys.exc_info()[2]

            logger.error(
                "Onboarding failed. Error=%s Line=%s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code=500,
                detail=f"Onboarding failed: {str(e)} at line {exc_tb.tb_lineno}"
            )