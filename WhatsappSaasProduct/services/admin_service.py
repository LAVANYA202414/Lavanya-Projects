import sys
from datetime import datetime , timezone
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from utils.logger import get_logger
from models import (translation,tenant,business)
from schemas.models_schemas.tenant_schema import (TenantAllResponse,TenantResponse,TenantStatusEnum)
from services.users_service import UserService
from schemas.models_schemas.business_schemas import (AllBusinessResponse,BusinessResponse,BusinessStatusEnum)
from utils.helper import (success_response,normalize_string,normalize_dict_data,deep_clean)

# Initialize logger
logger = get_logger(__name__)



class AdminServices:

    def create_business_func(self, request , db):
        try:

            payload = normalize_dict_data(
                request.model_dump(),
                exclude_fields={"timezone"}
            )

            is_valid, phone = UserService().validate_phone(payload.get("phone"))
            if not is_valid:
                raise HTTPException(status_code = 400 , detail = phone)

            payload.update({
                "phone": phone,
            })

            business_obj = business.Business(**payload)

            db.add(business_obj)
            db.commit()
            db.refresh(business_obj)

            data = BusinessResponse.model_validate(business_obj).model_dump(mode="json")

            return success_response(
                detail="Business created successfully",
                status_code=201,
                data = data
            )
        
        except HTTPException:
            raise

        except IntegrityError as e:
            raise HTTPException(
                status_code = 400,
                detail= "Duplicate record Found."
            )

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to create business. Error: %s , Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code = 500,
                detail = f"Failed to create business. Error: {str(e)} , Line : {exc_tb.tb_lineno}",
            )


    def get_all_businesses_func(self,status, db):

        try:
            normalize_status = normalize_string(status)

            try:
                status_enum = BusinessStatusEnum(status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Allowed: {[e.value for e in BusinessStatusEnum]}"
                )

            normalize_status = normalize_status if normalize_status else "active"


            all_businesses = db.query(business.Business).filter(
                business.Business.status == normalize_status
            ).all()

            if not all_businesses:
                raise HTTPException(
                    status_code = 404,
                    detail = 'Businesses not Found for status : {}'.format(normalize_status)
                )

            data = [
                AllBusinessResponse.model_validate(b).model_dump(mode="json")
                for b in all_businesses
            ]

            return success_response(
                detail="All Businesses fetched successfully.",
                status_code=200,
                data=data,
                meta={"count": len(data)}
            )

        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to get all businesses. Error: %s , Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code = 500,
                detail = f"Failed to get all businesses. Error: {str(e)} , Line : {exc_tb.tb_lineno}",
            )
        
        
    def get_tenant_businesses_func(self,status, db):
        try:
            normalize_status = normalize_string(status)

            try:
                status_enum = BusinessStatusEnum(status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Allowed: {[e.value for e in BusinessStatusEnum]}"
                )

            normalize_status = normalize_status if normalize_status else "active"

            all_businesses = db.query(business.Business).filter(
                business.Business.status == normalize_status
            ).all()

            if not all_businesses:
                raise HTTPException(
                    status_code = 404,
                    detail = 'Businesses not Found for status : {}'.format(normalize_status)
                )

            data = [
                AllBusinessResponse.model_validate(b).model_dump(mode="json")
                for b in all_businesses
            ]

            return success_response(
                detail="All Businesses fetched successfully.",
                status_code=200,
                data=data,
                meta={"count": len(data)}
            )

        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to get all businesses. Error: %s , Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code = 500,
                detail = f"Failed to get all businesses. Error: {str(e)} , Line : {exc_tb.tb_lineno}",
            )


    def get_all_tenants_func(self, status ,db):

        try:
            normalize_status = normalize_string(status)

            try:
                status_enum = TenantStatusEnum(normalize_status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Allowed: {[e.value for e in TenantStatusEnum]}"
                )

            normalize_status = normalize_status if normalize_status else "active"

            all_tenants = db.query(tenant.Tenant).filter(
                tenant.Tenant.status  == normalize_status
            ).all()

            if not all_tenants:
                raise HTTPException(
                    status_code = 404,
                    detail= "Tenants Not Found for status: {}".format(normalize_status)
                )

            data = [
                TenantAllResponse.model_validate(t).model_dump(mode="json")
                for t in all_tenants
            ]

            return success_response(
                detail="All tenant fetched successfully.",
                status_code=200,
                data=data,
                meta={"count": len(data)}
            )

        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to get all tenants. Error: %s , Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code = 500,
                detail = f"Failed to get all tenants. Error: {str(e)} , Line : {exc_tb.tb_lineno}",
            )

    
    def get_tenant_by_id(self,tenant_id, db):

        try:

            tenant_obj = db.query(tenant.Tenant).filter(
                tenant.Tenant.id == tenant_id
            ).first()

            if not tenant_obj:
                raise HTTPException(
                    status_code = 404, 
                    detail = "No Tenant Found with ID: {}".format(tenant_id)
                )

            data = TenantResponse \
                .model_validate(tenant_obj) \
                .model_dump(mode="json")
            
            
            # Fetch all Business based on tenant id
            businessess_obj = db.query(business.Business).filter(
                business.Business.tenant_id == tenant_id
            ).all()

            if businessess_obj:
                business_data = [
                    AllBusinessResponse.model_validate(buss).model_dump(mode="json")
                    for buss in businessess_obj
                ]

                # Add business and metadata
                data["business"] = business_data

            # Count business
            total_business= len(data.get("business")) if len(data.get("business")) > 0 else 0

            return success_response(
                detail="Tenant fetched successfully.",
                status_code=200,
                data=data,
                meta= {"total_business": total_business}
            )

        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to get Tenant. Error: %s , Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code = 500,
                detail = f"Failed to delete Tenant. Error: {str(e)} , Line : {exc_tb.tb_lineno}",
            )


    def delete_tenant_by_id(self,tenant_id, db):

        try:

            tenant_obj = db.query(tenant.Tenant).filter(
                tenant.Tenant.id == tenant_id
            ).first()

            if not tenant_obj:
                raise HTTPException(
                    status_code = 404 , 
                    detail = "No Tenant Found with ID: {}".format(tenant_id)
                )
            
            # Update status
            tenant_obj.status = 'deleted'
            tenant_obj.deleted_at = datetime.now(timezone.utc())

            db.commit()
            db.refresh(tenant_obj)

            return success_response(
                detail="Tenant delete successfully.",
                status_code=204
            )

        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to delete tenant. Error: %s , Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code = 500,
                detail = f"Failed to delete tenant. Error: {str(e)} , Line : {exc_tb.tb_lineno}",
            )

    
    def create_language_func(self,request,db,):
        try:

            normalize_code = normalize_string(request.code)
            normalize_name = normalize_string(request.name)
            
            lang_obj = translation.Langauges(
                code = normalize_code,
                name= normalize_name,
                is_active= request.is_active,
            )

            db.add(lang_obj)
            db.commit()
            db.refresh(lang_obj)

            return success_response(
                detail="Language created successfully.",
                status_code=201
            )

        except HTTPException:
            raise


        except IntegrityError as e:
            raise HTTPException(
                status_code = 400,
                detail= "Duplicate record Found."
            )

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to create langauge. Error: %s , Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code = 500,
                detail = f"Failed to create langauge. Error: {str(e)} , Line : {exc_tb.tb_lineno}",
            )
        

    def delete_language_func(self,lang_code, db):

        try:
            
            normalize_language_code = normalize_string(lang_code)

            lang_obj = db.query(translation.Langauges).filter(
                translation.Langauges.code == normalize_language_code
            ).first()

            if not lang_obj:
                raise HTTPException(
                    status_code = 404 , 
                    detail = "Invalid langauge code."
                )

            db.delete(lang_obj)
            db.commit()

            return success_response(
                detail="Language delete successfully.",
                status_code=204
            )

        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to delete tenant. Error: %s , Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code = 500,
                detail = f"Failed to delete tenant. Error: {str(e)} , Line : {exc_tb.tb_lineno}",
            )