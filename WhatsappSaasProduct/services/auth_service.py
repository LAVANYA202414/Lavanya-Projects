import sys
import secrets
from datetime import datetime , timedelta , timezone
from utils.logger import get_logger
from utils.helper import (normalize_string,success_response,)
from services.users_service import UserService
from models import user , business
from jose import jwt, JWTError, ExpiredSignatureError
from core.config import settings
from fastapi import HTTPException
from utils.jwt import JWTService
from sqlalchemy.orm import Session
from email.message import EmailMessage
import aiosmtplib

logger = get_logger(__name__)


class AuthService:

    async def send_password_forgot_email(self,token: str,  to_email: str):
        try:
            message = EmailMessage()
            message["From"] = settings.FROM_EMAIL
            message["To"] = to_email
            message["Subject"] = "Reset Your Password"

            # Create reset link
            # reset_link = f"{FRONTEND_URL}/reset-password?token={token}"
            reset_link = f"http://127.0.0.1:8000/reset-password?token={token}"
            
            message.set_content(
            f"""
                Hi,

                Please Click the below link to reset your password:

                {reset_link}

                If you did not request this, please ignore this email.

                Thanks,
                Your Team
            """
            )

            await aiosmtplib.send(
                message,
                hostname=settings.HOSTNAME,
                port=settings.PORT,
                start_tls=True,
                username=settings.FROM_EMAIL,
                password=settings.APP_PASSWORD,
            )

            logger.info("Password Forgot  email sent to %s", to_email)

            return {
                "detail": "Password Forgot link sent successfully.",
                "status_code": 200,
            }
        
        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to send password forgot email. Error: %s, Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code=500,
                detail=f"Failed to send password forgot email. Error: {str(e)}, Line : {exc_tb.tb_lineno}"
            )

    def user_login(self, form_data, db: Session):
        try:
            email = form_data.username

            normalize_email= normalize_string(email)
            password = form_data.password


            # 1. Check user
            user_obj = db.query(user.User).filter(user.User.email == normalize_email).first()

            if not user_obj:
                raise HTTPException(
                    status_code = 400, 
                    detail="Invalid Email"
                )

            # 2. Verify password
            if not UserService().verify_password(password, user_obj.password_hash):
                raise HTTPException(status_code = 401 , detail="Invalid credentials")
            
            # 3. Check user status
            if user_obj.status != "active":
                raise HTTPException(
                    status_code = 403, 
                    detail=f"User is {user_obj.status.title()}"
                )
            
            # 4. Get business mapping
            business_usr_obj = db.query(business.BusinessUser).filter(
                business.BusinessUser.user_id == user_obj.id,
                business.BusinessUser.is_active == True
            ).first()

            if not business_usr_obj:
                raise HTTPException(
                    status_code = 403, 
                    detail="User is not assigned to any business"
                )
            
            # 5. Create token payload
            token_payload = {
                "sub": str(user_obj.id),
                "tenant_id": str(user_obj.tenant_id),
                "business_id": str(business_usr_obj.business_id),
                "role": business_usr_obj.role,
                "type": "access"   
            }

            # 6. Generate tokens
            access_token = JWTService().create_access_token(token_payload)
            refresh_token = JWTService().create_refresh_token(str(user_obj.id))

            return {
                "user_id": str(user_obj.id),
                "tenant_id": str(user_obj.tenant_id),
                "business_id": str(business_usr_obj.business_id),
                "role": business_usr_obj.role,
                "refresh_token": refresh_token,
                "access_token": access_token,
                "token_type": "bearer",
            }

        except HTTPException:
            raise

        except Exception as e:
            db.rollback()

            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to Login Error=%s Line=%s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code = 403 , 
                detail=f"Failed to login: {str(e)} at line {exc_tb.tb_lineno}"
            )

    def send_email_func(self,background_task,current_user):
        try:    

            # Get User Object
            current_user_obj = current_user.get("user")


            if current_user_obj.is_email_verified:
                raise HTTPException(status_code= 400 , detail= "Email already verified")

            token = JWTService().create_email_verification_token(current_user_obj.email)

            background_task.add_task(
                JWTService().send_verification_email,
                current_user_obj.email,
                token
            )

            return success_response(
                detail="Verification email sent",
                status_code=200
            )
        
        except HTTPException:
            raise
        
        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to send email verification mail. Error: %s, Line: %s",
                str(e),
                exc_tb.tb_lineno
            )
            
            raise HTTPException(
                status_code=500,
                message= f"Failed to send email verification mail. Error: {str(e)}, Line: {exc_tb.tb_lineno}"
            )
    
    def email_verification_func(self , token , db: Session):
        try:

            payload = jwt.decode(token , settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])

            if payload.get("type") !="email_verification":
                return {"status_code": 400, "detail": 'Invalid token type'}
            
            email = payload.get("sub")

            user_obj = db.query(user.User).filter(user.User.email == email).first()

            if not user_obj:
                raise HTTPException(status_code=404, detail="User not found")


            if user_obj.is_email_verified:
                raise HTTPException(status_code=400, detail="Email already verified")

            user_obj.is_email_verified = True
            db.commit()

            return success_response(
                detail="Email verified successfully 🎉",
                status_code=200
            )

        except ExpiredSignatureError:
            raise HTTPException(401,"Token expired")

        except JWTError:
            raise HTTPException(400,"Invalid Token")

        except HTTPException:
            raise
        
        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(   
                "Failed to verify email. Error: %s, Line :%s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code = 500,
                detail= f"Error Occur Verifying email. Error: {str(e)}, Line :{exc_tb.tb_lineno}"
            )

    def refresh_token_func(self,refresh_token: str, db: Session):
        try:
            payload = jwt.decode(
                refresh_token,
                settings.JWT_REFRESH_SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )

            # Validate token type
            if payload.get("type") != "refresh":
                raise HTTPException(status_code=401, detail ="Invalid Token type")
            
            # Extract user
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code= 401, detail="Invalid token payload")
            
            # Check user exists
            user_obj = db.query(user.User).filter(user.User.id == user_id).first()
            if not user_obj:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Check user status
            if user_obj.status != "active":
                raise HTTPException(status_code=403,detail="User inactive")

            # Get business mapping
            business_usr_obj = db.query(business.BusinessUser).filter(
                business.BusinessUser.user_id == user_obj.id,
                business.BusinessUser.tenant_id == user_obj.tenant_id,
                business.BusinessUser.is_active == True
            ).first()

            if not business_usr_obj:
                raise HTTPException(status_code=403,detail="Business mapping not found")

            # Create NEW access token
            new_payload = {
                "sub": str(user_obj.id),
                "tenant_id": str(user_obj.tenant_id),
                "business_id": str(business_usr_obj.business_id),
                "role": business_usr_obj.role,
                "type": "access"
            }

            new_access_token = JWTService().create_access_token(new_payload)
            new_refresh_token = JWTService().create_refresh_token(str(user_obj.id))

            return {
                "status_code": 200,
                "message": "Token refreshed successfully",
                "access_token": new_access_token,
                "token_type": "bearer",
                "refresh_token": new_refresh_token   
            }
        
        except JWTError:
            raise HTTPException(status_code=401,detail="Invalid or expired refresh token")
        
        except HTTPException:
            raise
        
        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Failed to generate refresh token. Error: %s, Line :%s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                detail="Invalid or expired refresh token",
                status_code=401
            )

        
    def password_change_func(
        self,
        request,
        current_user,
        db: Session
    ):
        
        try:
            payload = request.model_dump()

            # Get Payload field data
            old_password = payload.get("old_password")
            new_password = payload.get("new_password")

            user_obj = current_user.get("user")

            filter_user = db.query(user.User).filter(
                user.User.id == user_obj.id
            ).first()

            
            # VERFIED NEW PASSWORD WITH OLD PASSWORD
            verified_password = UserService().verify_password(
                old_password , filter_user.password_hash
            )
            if not verified_password:
                logger.error("Incorrect old password")
                raise HTTPException(status_code=400, detail="Incorrect old password")

            # VALIDATE NEW PASSWORD
            status , message  = UserService().validate_password(new_password)
            if not status:
                raise HTTPException(status_code=400, detail=message)

            # UPDATE NEW PASSWORD
            filter_user.password_hash = UserService().hash_password(new_password)
            
            db.commit()
            db.refresh(filter_user)

            return success_response(
                detail="Password changed successfully",
                status_code=200
            )
        
        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "Error occur while changing password. Error: %s , Line : %S",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code=500,
                detail=f"Error occur while changing password. Error: {str(e)} , Line : {exc_tb.tb_lineno}"
            )

    def forgot_password_func(self,background_task, request , db: Session):
        try:
            payload_data = request.model_dump()

            user_obj = db.query(user.User).filter(
                user.User.email == payload_data.get("email")
            ).first()

            if not user_obj:
                raise HTTPException(400 , "Invalid user email")

            # Generate token
            token = secrets.token_urlsafe(32)

            # Delete Exist Record
            existing_record = db.query(user.PasswordResetToken).filter(
                user.PasswordResetToken.user_id == user_obj.id,
            ).first()
            
            if existing_record:
                db.delete(existing_record)
                db.commit()

            # enter new reset token
            reset_entry = user.PasswordResetToken(
                user_id = str(user_obj.id),
                token=token,
                expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
            )

            db.add(reset_entry)
            db.commit()
            db.refresh(reset_entry)

            # Send email
            background_task.add_task(
            self.send_password_forgot_email,
                token,
                user_obj.email
            )

            return success_response(
                detail="Password Forgot email sent",
                status_code=200
            )
        

        except HTTPException:
            raise

        except Exception as e:
            exc_tb = sys.exc_info()[2]

            logger.error(
                "[ERROR] Failed to send forgot password Email, Error: %s, Line : %s",
                str(e),
                exc_tb.tb_lineno
            )

            raise HTTPException(
                status_code=500,
                detail=f"[ERROR] Failed to send forgot password Email, Error: {str(e)}, Line : {exc_tb.tb_lineno}"
            )
        
    def reset_password_func(self, token: str, new_password: str, db):
        try:
            #Get token record
            record = db.query(user.PasswordResetToken).filter(
                user.PasswordResetToken.token == token
            ).first()

            if not record:
                raise HTTPException(status_code=400, detail="Invalid token")

            # Ensure timezone-aware datetime
            expires_at = record.expires_at

            now = datetime.now(timezone.utc)

            # 4. Expiry check (ONLY ONCE)
            if expires_at < now:
                raise HTTPException(status_code=400, detail="Token expired")

            #Get user
            user_obj = db.query(user.User).filter(
                user.User.id == record.user_id
            ).first()

            if not user_obj:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Validate Password
            status , message = UserService().validate_password(new_password)
            if not status:
                raise HTTPException(400 ,message)

            # Update password
            user_obj.password_hash = UserService().hash_password(new_password)

            # Delete token (one-time use)
            db.delete(record)

            #Commit changes
            db.commit()

            return success_response(
                detail="Password reset successfully",
                status_code=200
            )

        except HTTPException:
            raise

        except Exception:
            #Logs full traceback automatically
            logger.exception("Error while resetting password")

            raise HTTPException(
                status_code=500,
                detail="Something went wrong while changing password"
            )