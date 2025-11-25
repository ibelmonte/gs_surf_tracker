"""
Profile management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
import os
import uuid
from pathlib import Path

from database import get_db
from models import User, Profile
from schemas import ProfileUpdate, ProfileResponse, ProfileWithUser
from utils.dependencies import get_current_user, get_current_confirmed_user
from config import settings

router = APIRouter()


@router.get("/me", response_model=ProfileWithUser)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's profile.

    - Requires authentication
    - Returns profile with user data
    """
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    # Combine profile with user data
    profile_data = ProfileWithUser(
        id=profile.id,
        user_id=profile.user_id,
        full_name=profile.full_name,
        alias=profile.alias,
        profile_picture_url=profile.profile_picture_url,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        email=current_user.email,
        is_email_confirmed=current_user.is_email_confirmed
    )

    return profile_data


@router.put("/me", response_model=ProfileResponse)
async def update_my_profile(
    profile_data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user's profile.

    - Requires authentication
    - Updates full_name and/or alias
    """
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    # Update fields if provided
    if profile_data.full_name is not None:
        profile.full_name = profile_data.full_name

    if profile_data.alias is not None:
        profile.alias = profile_data.alias

    db.commit()
    db.refresh(profile)

    return profile


@router.post("/me/picture", response_model=ProfileResponse)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload profile picture.

    - Requires authentication
    - Accepts image files (JPEG, PNG, GIF)
    - Max size: 5MB
    """
    # Validate file type
    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif"}
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Read file and validate size (5MB max)
    max_size = 5 * 1024 * 1024  # 5MB
    contents = await file.read()

    if len(contents) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size: 5MB"
        )

    # Create directory for profile pictures
    profile_pictures_dir = Path(settings.PROFILE_PICTURES_DIR)
    user_dir = profile_pictures_dir / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename with timestamp and UUID prefix
    from datetime import datetime
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    filename = f"{timestamp}_{unique_id}{file_ext}"
    file_path = user_dir / filename

    # Save file
    with open(file_path, "wb") as f:
        f.write(contents)

    # Update profile with picture URL
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    # Delete old picture if exists
    if profile.profile_picture_url:
        old_path = Path(profile.profile_picture_url)
        if old_path.exists():
            old_path.unlink()

    profile.profile_picture_url = str(file_path)
    db.commit()
    db.refresh(profile)

    return profile


@router.delete("/me/picture", response_model=ProfileResponse)
async def delete_profile_picture(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete profile picture.

    - Requires authentication
    - Removes picture file and clears URL
    """
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )

    if not profile.profile_picture_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No profile picture to delete"
        )

    # Delete file
    file_path = Path(profile.profile_picture_url)
    if file_path.exists():
        file_path.unlink()

    # Clear URL
    profile.profile_picture_url = None
    db.commit()
    db.refresh(profile)

    return profile
