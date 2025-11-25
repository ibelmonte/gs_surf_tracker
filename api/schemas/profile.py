"""
Pydantic schemas for Profile model.
"""
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional


class ProfileBase(BaseModel):
    """Base profile schema."""
    full_name: Optional[str] = Field(None, max_length=255)
    alias: Optional[str] = Field(None, max_length=100)


class ProfileCreate(ProfileBase):
    """Schema for creating a profile."""
    pass


class ProfileUpdate(ProfileBase):
    """Schema for updating a profile."""
    pass


class ProfileResponse(ProfileBase):
    """Schema for profile responses."""
    id: UUID
    user_id: UUID
    profile_picture_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProfileWithUser(ProfileResponse):
    """Schema for profile with user data."""
    email: str
    is_email_confirmed: bool
