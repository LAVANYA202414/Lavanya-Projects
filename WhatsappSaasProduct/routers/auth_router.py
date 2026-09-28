from fastapi import APIRouter , Depends
from sqlalchemy.orm import Session
from server.database import get_db
from services.auth_service import AuthService
from models import user
from utils.jwt import JWTService
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import BackgroundTasks
from schemas.models_schemas.user_schemas import (
    RefreshTokenRequest,
    PasswordChangeRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)

# Configure service
service = AuthService()



# configure router
router = APIRouter(
    prefix="/auth",
    tags= ["OnBoarding"],
)

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    return service.user_login(form_data, db)

@router.post("/refresh-token")
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    return service.refresh_token_func(request.refresh_token, db)


@router.post("/logout")
async def logout(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    return service.user_logout(request.refresh_token, db)


@router.post("/send-verification-email")
async def send_verification_email(
    background_task: BackgroundTasks,
    current_user: user.User = Depends(JWTService().get_current_user),
):  
    return service.send_email_func(background_task,current_user)

@router.get("/verify-email")
async def email_verification(
    token: str,
    db: Session = Depends(get_db)
):
    return service.email_verification_func(token,db)


@router.post("/change-password")
async def change_password(
    request: PasswordChangeRequest,
    current_user: user.User = Depends(JWTService().get_current_user),
    db: Session = Depends(get_db)
):
    return service.password_change_func(request,current_user,db)


@router.post("/forgot-password")
async def forgot_password(
    background_task: BackgroundTasks,
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    return service.forgot_password_func(background_task,request,db)


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    return service.reset_password_func(
        request.token,
        request.new_password,
        db
    )
