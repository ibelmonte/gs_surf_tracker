"""
Authentication endpoints - user registration, login, email confirmation.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    EmailConfirmRequest,
    ResendConfirmationRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from services.auth_service import auth_service

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user account.

    - Creates user account with hashed password
    - Creates empty user profile
    - Sends email confirmation link
    - Returns user data (without password)
    """
    user, error = auth_service.create_user(db, user_data)

    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )

    return user


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Login with email and password.

    - Validates credentials
    - Returns JWT access and refresh tokens
    - Does not require email confirmation
    """
    user = auth_service.authenticate_user(db, credentials.email, credentials.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create tokens
    tokens = auth_service.create_tokens(str(user.id))
    return tokens


@router.post("/confirm-email")
async def confirm_email(request: EmailConfirmRequest, db: Session = Depends(get_db)):
    """
    Confirm email address with token from confirmation email.

    - Validates token
    - Marks email as confirmed
    - Token expires after 24 hours
    """
    success, message = auth_service.confirm_email(db, request.token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    return {"message": message}


@router.post("/resend-confirmation")
async def resend_confirmation(request: ResendConfirmationRequest, db: Session = Depends(get_db)):
    """
    Resend email confirmation link.

    - Generates new confirmation token
    - Sends new confirmation email
    """
    success, message = auth_service.resend_confirmation(db, request.email)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    return {"message": message}


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Request password reset link.

    - Sends password reset email if user exists
    - Always returns success to prevent email enumeration
    """
    success, message = auth_service.request_password_reset(db, request.email)
    return {"message": message}


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Reset password with reset token.

    - Validates reset token
    - Updates password
    - Token expires after 1 hour
    """
    success, message = auth_service.reset_password(db, request.token, request.new_password)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    return {"message": message}
