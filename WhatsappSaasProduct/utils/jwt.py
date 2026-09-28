import aiosmtplib
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends ,HTTPException, status
from sqlalchemy.orm import Session
from server.database import get_db
from datetime import datetime, timedelta
from typing import Dict, Any
from jose import jwt ,JWTError
from email.message import EmailMessage
from models import user , business
from core.config import settings
from utils.logger import get_logger


logger = get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")



class JWTService:
    """Service for handling JWT tokens and email verification."""

     # ---------------- CREATE ACCESS TOKEN ---------------- #
    def create_access_token(self,data: dict, expires_delta: int = None) -> str:
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )

        to_encode = data.copy()
        to_encode.update({"exp": expire})

        return jwt.encode(to_encode, settings.JWT_SECRET_KEY, settings.ALGORITHM)
    

    # Function for Refresh Token
    def create_refresh_token(self, subject: str, expires_delta: timedelta = None) -> str:
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
            )

        to_encode = {
            "exp": expire,
            "sub": str(subject),
            "type": "refresh"
        }

        return jwt.encode(to_encode, settings.JWT_REFRESH_SECRET_KEY, settings.ALGORITHM)
    

    # Function for verify token 
    def verify_token(self,token: str):
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except JWTError:
            return {
                "status_code": 401,
                "detail": "Invalid or expired token",
                "headers": {"WWW-Authenticate": "Bearer"},
            }


    # Create Role-Based Dependency
    def require_role(self, allowed_roles: list):
        def role_checker(current=Depends(self.get_current_user)):
            if current["role"] not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not enough permissions"
                )
            return current["user"]
        return role_checker
    

    # Dependency to get the current user
    async def get_current_user(
        self,
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db)):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )

            user_id: str = payload.get("sub")

            # Check email exists
            if user_id is None:
                raise credentials_exception

            # Check token type (VERY IMPORTANT)
            if payload.get("type") != "access":
                raise credentials_exception

        except JWTError as e:
            raise credentials_exception

        # Correct SQLAlchemy query
        user_obj =  db.query(user.User).filter(user.User.id == user_id).first()
       
        if user_obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Get Business ID
        business_obj =  db.query(business.Business).filter(business.Business.tenant_id == user_obj.tenant_id).first()
        
        user_role = "viewer"

        if business_obj:

            # get business user role
            business_user_obj =  db.query(business.BusinessUser).filter(
                business.BusinessUser.tenant_id == user_obj.tenant_id,
                business.BusinessUser.user_id == user_obj.id,
                business.BusinessUser.business_id == business_obj.id
                
            ).first()

            if business_user_obj:
                user_role =  business_user_obj.role.value

        return {
            "user": user_obj,
            "role": user_role
        }


    def create_email_verification_token(self, email: str) -> str:
        """Generate a JWT token for email verification."""
        expire = datetime.utcnow() + timedelta(hours=24)

        payload = {
            "sub": email,
            "type": "email_verification",
            "exp": expire,
        }

        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )

        return token


    async def send_verification_email(self, email: str, token: str) -> Dict[str, Any]:

        """Send email verification link asynchronously."""
        verify_link = f"{settings.HOST_URL}/auth/verify-email?token={token}"

        message = EmailMessage()
        message["From"] = settings.FROM_EMAIL
        message["To"] = email
        message["Subject"] = "Verify your email"

        message.set_content(
            f"""
                Hi,

                Please verify your email by clicking the link below:

                {verify_link}

                If you did not request this, please ignore this email.

                Thanks,
                Your Team
            """
        )

        try:
            await aiosmtplib.send(
                message,
                hostname=settings.HOSTNAME,
                port=settings.PORT,
                start_tls=True,
                username=settings.FROM_EMAIL,
                password=settings.APP_PASSWORD,
            )

            logger.info("Verification email sent to %s", email)

            return {
                "detail": "Email verify link sent successfully.",
                "status_code": 200,
            }

        except Exception as e:
            logger.exception("Error sending verify email to %s: %s", email, str(e))

            return {
                "detail": "Failed to send verification email.",
                "status_code": 500,
            }