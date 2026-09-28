import sys
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from utils.logger import get_logger
from models.business import (Business,BusinessUser,BusinessLanguages,)
from models.user import User
from services.users_service import UserService
from schemas.models_schemas.business_schemas import (AllBusinessResponse,BusinessResponse,BusinessLanguageResponse,BusinessUserResponse,)
from schemas.models_schemas.user_schemas import TenantUserResponse
from utils.helper import (success_response,deep_clean,normalize_string,normalize_dict_data,)

# Initialize logger
logger = get_logger(__name__)


class BusinessService:

    """
    Purpose: Allow the Tenant Owner to configure and manage their business after registration."
    """

    def get_businesses_func(self, current_user,db):
        try:
            all_businesses = db.query(Business).filter(
                Business.tenant_id == current_user.tenant_id
            ).all()

            if not all_businesses:
                raise HTTPException(
                    status_code=404,
                    detail= f"No businesses found for tenant_id: {current_user.tenant_id}"
                )
                
            data = [
                AllBusinessResponse.model_validate(b).model_dump(mode="json")
                for b in all_businesses
            ]

            return success_response(
                detail="Businesses fetched successfully.",
                data=data,
                meta={"count": len(data)}
            )

        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Error while fetching businesses by ID. Error: %s, Line: %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code=500,
                detail= f"Failed to fetch businesses. Error: {str(e)}, Line: {exc_tb.tb_lineno}"
            )
    

    def create_user_func(self,request, current_user, db):
        try:
            
            # Convert into dict
            payload = request.model_dump()

            # normalized payload
            normalized_payload= normalize_dict_data(
                payload,
                exclude_fields={"password"}
            )

            # phone validation
            is_valid, normalized_phone = UserService().validate_phone(normalized_payload.get('phone'))
            if not is_valid:
                raise HTTPException(
                    status_code = 400,
                    detail= normalized_phone
                )

            # create user object
            user_obj = User(
                tenant_id=current_user.tenant_id,  
                name=normalized_payload.get("name"),
                email=normalized_payload.get("email"),
                phone=normalized_payload.get("phone"),

                password_hash=UserService().hash_password(
                    normalized_payload.get("password")
                ),
                preferred_language=normalized_payload.get("preferred_language"),
                status=normalized_payload.get("status"),
            )

            db.add(user_obj)
            db.commit()
            db.refresh(user_obj)

            data = TenantUserResponse.model_validate(user_obj).model_dump(mode="json")

            return success_response(
                detail="user created successfully.",
                status_code=201,
                data= data
            )

        except HTTPException:
            raise
            
        except IntegrityError as e:
            raise HTTPException(
                status_code = 400,
                detail= "Duplicate record Found for email =({})".format(normalized_payload.get('email'))
            )

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Error while creating user by ID. Error: %s, Line: %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code=500,
                detail= f"Failed to create user. Error: {str(e)}, Line: {exc_tb.tb_lineno}"
            )
    

    def create_business_user_func(self,request, current_user, db):
        try:

            # create user object
            business_obj = BusinessUser(
                tenant_id = current_user.tenant_id,  
                business_id = request.business_id,
                user_id = request.user_id,
                role = request.role,
                is_active = request.is_active
            )

            db.add(business_obj)
            db.commit()
            db.refresh(business_obj)

            data = BusinessUserResponse \
                .model_validate(business_obj) \
                .model_dump(mode="json")

            return success_response(
                detail="user created successfully.",
                status_code=201,
                data=data
            )

        except HTTPException:
            raise
            
        except IntegrityError as e:
            raise HTTPException(
                status_code = 400,
                detail= "Duplicate record Found")
        
        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Error while creating user by ID. Error: %s, Line: %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code=500,
                detail= f"Failed to create user. Error: {str(e)}, Line: {exc_tb.tb_lineno}"
            )

    
    def get_businesses_by_id(self, business_id ,current_user,db):
        
        try:
            
            # Fetch Business Based on business and tenant id
            business = db.query(Business).filter(
                Business.id == business_id,
                Business.tenant_id == current_user.tenant_id
            ).first()

            if not business:
                raise HTTPException(
                    status_code=404,
                    detail= f"Business not found for id: {business_id}"
                )
               
            data = BusinessResponse \
                .model_validate(business) \
                .model_dump(mode="json")
            
            return success_response(
                detail="Business fetched successfully.",
                status_code=200,
                data=data
            )
        
        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.exception(
                "Error while fetching businesses by ID. Error: %s, Line: %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code=500,
                detail= f"Error while fetching businesses by ID. Error: {str(e)}, Line: {exc_tb.tb_lineno}"
            )
    

    def update_business_by_id(self,business_id,request,current_user, db):
        try:

            # Fetch tenant
            business = db.query(Business).filter(
                Business.id == business_id,
                Business.tenant_id == current_user.tenant_id
            ).first()


            if not business:
                raise HTTPException(
                    status_code=404,
                    detail= "Invalid Business ID : {}".format(business_id)
                )
            
            # Get only provided fields
            update_data = request.model_dump(exclude_unset=True)

            if not update_data:
                raise HTTPException(
                    status_code=404,
                    detail="No fields provided for update"
                )
                
            # Update fields dynamically
            cleaned_data = deep_clean(update_data)

            if len(cleaned_data) > 0:
                for key , value in cleaned_data.items():
                    setattr(business, key, value)
                    
            db.commit()
            db.refresh(business)

            logger.info(
                "Buiness updated successfully. tenant_id=%s business_id=%s",
                current_user.tenant_id,
                business_id
            )

            return success_response(
                detail= "Business updated successfully.",
                status_code=200,
                data ={"response": BusinessResponse.model_validate(business).model_dump(mode='json')}
            )
        
        except HTTPException:
            raise
    
        except Exception as e:
            exc_tb = sys.exc_info()[2]

            db.rollback()
            logger.exception("Error while updating Business: %s", str(e))

            raise HTTPException(
                status_code=500,
                detail= "Failed to Update tenant business. Error: {} , Line : {}".format(str(e), exc_tb.tb_lineno)
            )
        

    def delete_business_by_id(self,business_id,current_user, db):
        try:
            business = db.query(Business).filter(
                Business.id == business_id,
                Business.tenant_id == current_user.tenant_id
            ).first()

            if not business:
                raise HTTPException(
                    status_code=404,
                    detail= f"No business found for ID: {business_id}"
                )
               

            db.delete(business)
            db.commit()

            return success_response(
                detail="Business deleted successfully.",
                status_code=200
            )
        
        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            db.rollback()
            logger.exception(
                "Error while deleting business by ID. Error: %s , Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code=500,
                detail= "Error while deleting business by ID. Error: {} , Line : {}".format(str(e), exc_tb.tb_lineno)
            )
        

    def get_all_business_languages(self, business_id,current_user, db):
        try:
            
            business_lang_obj = db.query(BusinessLanguages).filter(
                BusinessLanguages.tenant_id == current_user.tenant_id,
                BusinessLanguages.business_id == business_id
            ).all()

            if not business_lang_obj:
                raise HTTPException(
                    status_code = 400,
                    detail= "Business Languages not found for business id: {}".format(business_id)
                )
            
            data = [
                BusinessLanguageResponse.model_validate(buss).model_dump(mode="json")
                for buss in business_lang_obj
            ]
            
            return success_response(
                detail='Successfully get all languages',
                status_code=200,
                data=data,
                meta={"count": len(data)}
            )

        except HTTPException:
            raise


        except Exception as e:
            exc_tb = sys.exc_info()[2]

            db.rollback()
            logger.exception(
                "Error while getting business languages. Error: %s , Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code=500,
                detail= "Error while getting business languages. Error: {} , Line : {}".format(str(e), exc_tb.tb_lineno)
            )
        

    def add_business_lang(self, business_id, request, db, current_user):
        try:
            
            business_lang = BusinessLanguages(
                tenant_id= current_user.tenant_id,
                business_id= business_id,
                language_code= request.language_code,
                is_default= request.is_default,
            )


            db.add(business_lang)
            db.commit()
            db.refresh(business_lang)

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
        

    def remove_business_lang_func(
        self,
        business_id,
        language, 
        db, 
        current_user
    ):
        try:
            normalize_langauge = normalize_string(language)
           
            business_lang = db.query(BusinessLanguages).filter(
                BusinessLanguages.tenant_id == current_user.tenant_id,
                BusinessLanguages.business_id == business_id,
                BusinessLanguages.language_code  == normalize_langauge
            ).first()

            if not business_lang:
                raise HTTPException(
                    status_code=404, 
                    detail="Language not enabled for this business"
                )
            
            #  Cannot delete default language
            if normalize_langauge == business_lang.is_default:
                raise HTTPException(
                    status_code=400,
                    detail="Default language cannot be deleted"
                )
            
            db.delete(business_lang)
            db.commit()

            return success_response(
                detail="Language deleted successfully.",
                status_code=204
            )

        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to remove langauge. Error: %s , Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code = 500,
                detail = f"Failed to remove langauge. Error: {str(e)} , Line : {exc_tb.tb_lineno}",
            )
    
    