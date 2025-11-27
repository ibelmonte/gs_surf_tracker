"""
SessionRanking model - stores aggregated rankings per user per period.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Integer, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base
import uuid
from datetime import datetime


class SessionRanking(Base):
    """Session ranking model for tracking user rankings across different periods."""
    __tablename__ = "session_rankings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Ranking period
    # Period type: 'daily', 'monthly', 'yearly'
    period = Column(String(20), nullable=False, index=True)
    # Period start date (for the specific day/month/year being ranked)
    period_start = Column(DateTime, nullable=False, index=True)

    # Aggregated metrics
    total_score = Column(Float, nullable=False, default=0.0, index=True)
    session_count = Column(Integer, nullable=False, default=0)

    # Computed rank (updated by ranking service)
    rank = Column(Integer, nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="rankings")

    # Composite indexes for efficient queries
    __table_args__ = (
        # Ensure unique ranking per user per period
        Index('idx_user_period_unique', 'user_id', 'period', 'period_start', unique=True),
        # Leaderboard query optimization (get top scores for a period)
        Index('idx_leaderboard_query', 'period', 'period_start', 'total_score'),
    )

    def __repr__(self):
        return f"<SessionRanking(user_id={self.user_id}, period={self.period}, rank={self.rank}, score={self.total_score})>"
