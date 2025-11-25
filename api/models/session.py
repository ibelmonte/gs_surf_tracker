"""
SurfingSession model - stores video processing sessions.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from database import Base
import uuid
from datetime import datetime


class SurfingSession(Base):
    """Surfing session model for tracking video processing."""
    __tablename__ = "surfing_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Video file information
    video_filename = Column(String(255), nullable=False)
    video_path = Column(String(500), nullable=False)

    # Processing status
    status = Column(String(50), nullable=False, default="pending", index=True)
    # Status options: 'pending', 'processing', 'completed', 'failed'

    error_message = Column(Text, nullable=True)

    # Output information
    output_path = Column(String(500), nullable=True)
    results_json = Column(JSONB, nullable=True)  # Store tracker results

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_processing_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="sessions")

    def __repr__(self):
        return f"<SurfingSession(id={self.id}, user_id={self.user_id}, status={self.status})>"
