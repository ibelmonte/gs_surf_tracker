"""
Pydantic schemas for SurfingSession model.
"""
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class SessionStatus(str, Enum):
    """Enum for session status values."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SessionBase(BaseModel):
    """Base session schema."""
    pass


class SessionCreate(SessionBase):
    """Schema for creating a session (used internally)."""
    user_id: UUID
    video_filename: str
    video_path: str
    status: SessionStatus = SessionStatus.PENDING


class SessionUpdate(BaseModel):
    """Schema for updating session status."""
    status: Optional[SessionStatus] = None
    error_message: Optional[str] = None
    output_path: Optional[str] = None
    results_json: Optional[Dict[str, Any]] = None
    started_processing_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class SessionResponse(BaseModel):
    """Schema for session responses."""
    id: UUID
    user_id: UUID
    video_filename: str
    location: Optional[str]
    session_date: Optional[str]
    status: SessionStatus
    error_message: Optional[str]
    output_path: Optional[str]
    created_at: datetime
    updated_at: datetime
    started_processing_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class SessionWithResults(SessionResponse):
    """Schema for session with full results."""
    results_json: Optional[Dict[str, Any]]


class SessionListResponse(BaseModel):
    """Schema for paginated session list."""
    sessions: List[SessionResponse]
    total: int
    page: int
    page_size: int


class UploadResponse(BaseModel):
    """Schema for video upload response."""
    session_id: UUID
    message: str
    status: SessionStatus


class MergeSurfersRequest(BaseModel):
    """Schema for merging surfers request."""
    surfer_ids: List[int] = Field(..., min_length=1, description="List of surfer IDs to merge")


class MergeSurfersResponse(BaseModel):
    """Schema for merging surfers response."""
    message: str
    merged_surfer_id: int
    total_events_merged: int
    surfers_removed: int
