import sys
import bcrypt
import re
import phonenumbers
from utils.logger import get_logger
from models.user import User
from utils.helper import (error_response,success_response,normalize_string,)
from schemas.models_schemas.user_schemas import (TenantUserResponse,)
from sqlalchemy.exc import IntegrityError
from core.config import settings

# Initialize logger
logger = get_logger(__name__)

class UserService:

    # ---------------- PHONE VALIDATION ---------------- #
    def validate_phone(self, phone: str, region: str = None):
        try:
            parsed = phonenumbers.parse(phone, region)

            if not phonenumbers.is_valid_number(parsed):
                return False, "Invalid phone number"

            formatted = phonenumbers.format_number(
                parsed,
                phonenumbers.PhoneNumberFormat.E164
            )

            return True, formatted

        except Exception:
            return False, "Invalid phone format"
        

    # ---------------- PASSWORD VALIDATION ---------------- #
    def validate_password(self, password: str):
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"

        if not re.search(r"[A-Z]", password):
            return False, "Password must include at least one uppercase letter"

        if not re.search(r"[a-z]", password):
            return False, "Password must include at least one lowercase letter"

        if not re.search(r"[0-9]", password):
            return False, "Password must include at least one digit"

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return False, "Password must include at least one special character"

        return True, "Valid password"


    # ---------------- PASSWORD HASHING ---------------- #
    def hash_password(self, password: str):
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # ---------------- VERIFY PASSWORD ---------------- #
    def verify_password(self, password: str, hashed: str):
        return bcrypt.checkpw(password.encode(), hashed.encode())


    # CREATE USER
    def create_user_func(self, request , db):
        try:
            logger.info("User Creation request recieved.")
            
            payload = request.model_dump()

            # Normalize email
            payload["email"] = normalize_string(payload["email"])

            # PHONE VALIDATION
            if payload.get("phone"):
                is_valid, phone = self.validate_phone(payload["phone"])
                if not is_valid:
                    return error_response(
                        message=phone,
                        status_code=400
                    )

                payload["phone"] = phone

            # PASSWORD VALIDATION
            is_valid_pwd, pwd_msg = self.validate_password(payload["password"])
            if not is_valid_pwd:
                return error_response(
                    message=pwd_msg,
                    status_code=400
                )

            # HASH PASSWORD
            password = payload.pop("password")
            payload["password_hash"] = self.hash_password(password)

            # CREATE USER
            user = User(**payload)

            db.add(user)
            db.commit()
            db.refresh(user)

            return success_response(
                "User created",
                TenantUserResponse.model_validate(user).model_dump(mode="json"),
                201
            )

        #  HANDLE UNIQUE CONSTRAINT
        except IntegrityError as e:
            db.rollback()

            error_str = str(e.orig)

            if "uq_tenant_email" in error_str:
                return error_response(
                    "Email already exists in this tenant",
                    400
                )
            
            if "uq_tenant_phone" in error_str:
                return error_response(
                    message="Phone already exists in this tenant",
                    status_code=400
                )
            return error_response("Database constraint error", 400)
        
        except Exception as e:
            db.rollback()
            exc_tb = sys.exc_info()[2]

            error_message = f"Failed to create user. Error: {str(e)} , Line: {exc_tb.tb_lineno}"

            logger.exception(error_message)
            return error_response(error_message , 500)
        

    # GET USER BASED ON ID
    def get_all_users(self , tenant_id, db):
        try:
            
            users = db.query(User).filter(
                User.tenant_id == tenant_id
            ).all()

            if not users:
                return error_response(
                    message="No User Exist",
                    status_code=404
                )
            
            data = [TenantUserResponse.model_validate(user).model_dump(mode="json") for user in users]

            return success_response(
                message="Users Fetch Successfully.",
                data=  data,
                status_code= 200,
                meta={"count": len(data)}
            )
        

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            error_message = f"Failed to fetch users. Error: {str(e)} , Line: {exc_tb.tb_lineno}"

            logger.exception(error_message)
            return error_response(error_message , 500)
        

    # GET ALL USERS
    def get_user(self,tenant_id,user_id, db):
        try:
            
            user = db.query(User).filter(
                User.id == user_id,
                User.tenant_id == tenant_id
            ).first()

            if not user:
                return error_response(
                    message="No User Found",
                    status_code=404
                )
            
            return success_response(
                message="User Fetch Successfully.",
                data=  TenantUserResponse.model_validate(user).model_dump(mode="json"),
                status_code= 200
            )
        

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            error_message = f"Failed to fetch user. Error: {str(e)} , Line: {exc_tb.tb_lineno}"

            logger.exception(error_message)
            return error_response(error_message , 500)
        