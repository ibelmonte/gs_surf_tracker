"""
Authentication service - business logic for user authentication.
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Tuple

from models import User, Profile
from schemas import UserCreate, TokenResponse
from utils.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    generate_token,
    validate_password_strength
)
from services.email_service import email_service


class AuthService:
    """Service for authentication operations."""

    @staticmethod
    def create_user(db: Session, user_data: UserCreate) -> Tuple[Optional[User], Optional[str]]:
        """
        Create a new user account.

        Args:
            db: Database session
            user_data: User registration data

        Returns:
            Tuple of (User object, error message). If successful, error is None.
        """
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            return None, "Email already registered"

        # Validate password strength
        is_valid, error_msg = validate_password_strength(user_data.password)
        if not is_valid:
            return None, error_msg

        # Create user
        hashed_password = get_password_hash(user_data.password)
        confirmation_token = generate_token()

        user = User(
            email=user_data.email,
            password_hash=hashed_password,
            is_email_confirmed=False,
            email_confirmation_token=confirmation_token,
            email_confirmation_sent_at=datetime.utcnow()
        )

        db.add(user)
        db.flush()  # Flush to get user.id

        # Create empty profile
        profile = Profile(user_id=user.id)
        db.add(profile)

        db.commit()
        db.refresh(user)

        # Send confirmation email
        email_sent = email_service.send_confirmation_email(user.email, confirmation_token)
        if not email_sent:
            print(f"[WARN] Failed to send confirmation email to {user.email}")

        return user, None

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        """
        Authenticate a user by email and password.

        Args:
            db: Database session
            email: User's email
            password: User's password

        Returns:
            User object if authentication successful, None otherwise
        """
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None

        if not verify_password(password, user.password_hash):
            return None

        return user

    @staticmethod
    def create_tokens(user_id: str) -> TokenResponse:
        """
        Create access and refresh tokens for a user.

        Args:
            user_id: User's UUID as string

        Returns:
            TokenResponse with access and refresh tokens
        """
        access_token = create_access_token(data={"sub": user_id})
        refresh_token = create_refresh_token(data={"sub": user_id})

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )

    @staticmethod
    def confirm_email(db: Session, token: str) -> Tuple[bool, str]:
        """
        Confirm a user's email with the confirmation token.

        Args:
            db: Database session
            token: Email confirmation token

        Returns:
            Tuple of (success, message)
        """
        user = db.query(User).filter(User.email_confirmation_token == token).first()

        if not user:
            return False, "Invalid confirmation token"

        if user.is_email_confirmed:
            return False, "Email already confirmed"

        # Check if token is expired (24 hours)
        if user.email_confirmation_sent_at:
            expiry_time = user.email_confirmation_sent_at + timedelta(hours=24)
            if datetime.utcnow() > expiry_time:
                return False, "Confirmation token expired"

        # Confirm email
        user.is_email_confirmed = True
        user.email_confirmation_token = None
        db.commit()

        return True, "Email confirmed successfully"

    @staticmethod
    def resend_confirmation(db: Session, email: str) -> Tuple[bool, str]:
        """
        Resend confirmation email.

        Args:
            db: Database session
            email: User's email

        Returns:
            Tuple of (success, message)
        """
        user = db.query(User).filter(User.email == email).first()

        if not user:
            return False, "User not found"

        if user.is_email_confirmed:
            return False, "Email already confirmed"

        # Generate new token
        new_token = generate_token()
        user.email_confirmation_token = new_token
        user.email_confirmation_sent_at = datetime.utcnow()
        db.commit()

        # Send email
        email_sent = email_service.send_confirmation_email(user.email, new_token)
        if not email_sent:
            return False, "Failed to send confirmation email"

        return True, "Confirmation email sent"

    @staticmethod
    def request_password_reset(db: Session, email: str) -> Tuple[bool, str]:
        """
        Request a password reset.

        Args:
            db: Database session
            email: User's email

        Returns:
            Tuple of (success, message)
        """
        user = db.query(User).filter(User.email == email).first()

        if not user:
            # Don't reveal if email exists
            return True, "If the email exists, a password reset link has been sent"

        # Generate reset token
        reset_token = generate_token()
        user.password_reset_token = reset_token
        user.password_reset_sent_at = datetime.utcnow()
        db.commit()

        # Send email
        email_sent = email_service.send_password_reset_email(user.email, reset_token)
        if not email_sent:
            print(f"[ERROR] Failed to send password reset email to {user.email}")

        return True, "If the email exists, a password reset link has been sent"

    @staticmethod
    def reset_password(db: Session, token: str, new_password: str) -> Tuple[bool, str]:
        """
        Reset password with reset token.

        Args:
            db: Database session
            token: Password reset token
            new_password: New password

        Returns:
            Tuple of (success, message)
        """
        user = db.query(User).filter(User.password_reset_token == token).first()

        if not user:
            return False, "Invalid reset token"

        # Check if token is expired (1 hour)
        if user.password_reset_sent_at:
            expiry_time = user.password_reset_sent_at + timedelta(hours=1)
            if datetime.utcnow() > expiry_time:
                return False, "Reset token expired"

        # Validate new password
        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            return False, error_msg

        # Update password
        user.password_hash = get_password_hash(new_password)
        user.password_reset_token = None
        user.password_reset_sent_at = None
        db.commit()

        return True, "Password reset successfully"


# Global service instance
auth_service = AuthService()
