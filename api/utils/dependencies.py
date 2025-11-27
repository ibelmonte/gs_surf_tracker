"""
FastAPI dependency functions.
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from database import get_db
from models import User
from utils.security import decode_token

# Security scheme for JWT bearer tokens
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user ID from token
    user_id_str: Optional[str] = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_confirmed_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get the current user only if their email is confirmed.

    Raises:
        HTTPException: If email is not confirmed
    """
    if not current_user.is_email_confirmed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not confirmed. Please confirm your email to access this resource.",
        )
    return current_user


def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Dependency to optionally get the current authenticated user from JWT token.
    Returns None if no token is provided or if token is invalid.

    This allows endpoints to be accessed with or without authentication.
    """
    if credentials is None:
        return None

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        return None

    # Check token type
    if payload.get("type") != "access":
        return None

    # Extract user ID from token
    user_id_str: Optional[str] = payload.get("sub")
    if user_id_str is None:
        return None

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        return None

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    return user
