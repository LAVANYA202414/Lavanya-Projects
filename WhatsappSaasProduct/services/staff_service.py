import sys
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from models.staff import StaffMember
from models.business import Business
from schemas.models_schemas.staff_schmea import (StaffStatusEnum,StaffMemberResponse)
from utils.logger import get_logger
from datetime import datetime , timezone
from utils.helper import (success_response,normalize_string,normalize_dict_data,deep_clean)


# Initialize logger
logger = get_logger(__name__)


class StaffService:

    def create_staff_func(self, request , db , current_user):
        try:
            
            payload = request.model_dump(by_alias= True)

            # Normalized payload data
            payload_data = normalize_dict_data(payload)

            # Add tenant id in payload
            payload_data["tenant_id"] = current_user.tenant_id

            #  validate business ownership
            business = db.query(Business).filter(
                Business.id == payload_data.get("business_id"),
                Business.tenant_id == current_user.tenant_id
            ).first()

            if not business:
                raise HTTPException(
                    status_code=404,
                    detail="Business not found."
                )

            # create staff menber
            staff_obj = StaffMember(**payload_data)

            db.add(staff_obj)
            db.commit()
            db.refresh(staff_obj)

            data = StaffMemberResponse.model_validate(staff_obj).model_dump(mode="json")

            return success_response(
                detail="Staff member created successfully.",
                status_code=201,
                data= data
            )

        except HTTPException:
            raise

        except IntegrityError as e:
            error_message = str(e.orig)

            if "uq_staff_email_per_business" in error_message:
                raise HTTPException(
                    status_code=400,
                    detail="A staff member with this email already exists in this business."
                )

            elif "uq_staff_phone_per_business" in error_message:
                raise HTTPException(
                    status_code=400,
                    detail="A staff member with this phone number already exists in this business."
                )

            else:
                raise HTTPException(
                    status_code=400,
                    detail="Duplicate staff member record found."
                )
            
        except Exception as e:
            db.rollback()

            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to create staff member. Error : %s , Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code=500,
                detail=f"Failed to create staff member."
            )
            
    def get_all_staff_func(self , db, status, current_user):
        try:
            status = normalize_string(status)

            try:
                status_enum = StaffStatusEnum(status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Allowed: {[e.value for e in StaffStatusEnum]}"
                )

            # Filter data
            query = db.query(StaffMember).filter(
                StaffMember.tenant_id == current_user.tenant_id
            )

            if status:
                query = query.filter(StaffMember.status == status)
            else:
                query = query.filter(StaffMember.status == "active")

            all_staff_members = query.all()
            
            if not all_staff_members:
                raise HTTPException(
                    status_code = 400,
                    detail = 'No Staff member found related to this business and tenant'
                )
            
            staff_data = [
                StaffMemberResponse.model_validate(staff).model_dump(mode="json")
                for staff in all_staff_members
            ]

            return success_response(
                detail="All staff members fetched successfully.",
                status_code=200,
                data=staff_data,
                meta={"count": len(staff_data)}
            )

        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to get all staff members : Error: %s , Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code = 500,
                detail = f"Failed to get all staff members.  Error: {str(e)} , Line : {exc_tb.tb_lineno}"
            )
        
    def get_staff_by_id_func(self , db, staff_id, current_user):
        try:
            
            staff_member = db.query(StaffMember).filter(
                StaffMember.tenant_id == current_user.tenant_id,
                StaffMember.id == staff_id
            ).first()

            if not staff_member:
                raise HTTPException(
                    status_code = 404,
                    detail = 'Invalid Staff ID : {}'.format(staff_id)
                )
            
            staff_obj = StaffMemberResponse.model_validate(staff_member).model_dump(mode="json")

            
            return success_response(
                detail="All staff members fetched successfully.",
                status_code=200,
                data=staff_obj,
            )

        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to  get staff member : Error: %s , Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code = 500,
                detail = f"Failed to get staff member.  Error: {str(e)} , Line : {exc_tb.tb_lineno}"
            )

    def update_staff_by_id_func(self,staff_id,request,db, current_user):
        try:
            
            payload_data = normalize_dict_data(request.model_dump())

            staff_member_obj = db.query(StaffMember).filter(
                StaffMember.tenant_id == current_user.tenant_id,
                StaffMember.id == staff_id
            ).first()

            if not staff_member_obj:
                raise HTTPException(
                    status_code = 404,
                    detail = "Invalid Staff ID , No Staff Member found related ID : {}".format(staff_id)
                    )
            

            # Get only provided fields
            cleaned_data = deep_clean(payload_data)
            

            # Updated value dynamically
            if len(cleaned_data) > 0:
                for key , value in cleaned_data.items():
                    setattr(staff_member_obj, key, value)

            db.commit()
            db.refresh(staff_member_obj)

            logger.info(
                "Staff member updated successfully. tenant_id=%s staff_id=%s",
                current_user.tenant_id,
                staff_id
            )

            return success_response(
                detail= "Business updated successfully.",
                status_code=200,
                data ={"response": StaffMemberResponse.model_validate(staff_member_obj).model_dump(mode='json')}
            )

        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to  update staff member : Error: %s , Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code = 500,
                detail = f"Failed to update staff member.  Error: {str(e)} , Line : {exc_tb.tb_lineno}"
            )

    def delete_staff_by_id_func(self,staff_id,db, current_user):
        try:
            staff_member_obj = db.query(StaffMember).filter(
                StaffMember.tenant_id == current_user.tenant_id,
                StaffMember.id == staff_id
            ).first()

            if not staff_member_obj:
                raise HTTPException(
                    status_code = 404,
                    detail = "Invalid Staff ID , No Staff Member found related ID : {}".format(staff_id)
                    )
            
            staff_member_obj.status= "deleted"
            staff_member_obj.deleted_at =  datetime.now(timezone.utc)

            db.commit()
            db.refresh(staff_member_obj)

            logger.info(
                "Staff member deleted successfully. tenant_id=%s staff_id=%s",
                current_user.tenant_id,
                staff_id
            )

            return success_response(
                detail= "Staff member deleted successfully.",
                status_code=204,
            )

        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to delete staff member : Error: %s , Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code = 500,
                detail = f"Failed to delete staff member.  Error: {str(e)} , Line : {exc_tb.tb_lineno}"
            )
