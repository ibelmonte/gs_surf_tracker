"""
Pydantic schemas for ranking-related requests and responses.
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RankingEntry(BaseModel):
    """Single entry in a leaderboard."""
    rank: int
    user_id: str
    user_name: str
    total_score: float
    session_count: int
    is_current_user: bool = False

    class Config:
        from_attributes = True


class LeaderboardResponse(BaseModel):
    """Response containing leaderboard data for a specific period."""
    period: str  # 'daily', 'monthly', 'yearly'
    period_start: datetime
    period_label: str  # Human-readable label (e.g., "Today", "November 2023", "2023")
    top_entries: list[RankingEntry]  # Top 10 entries
    current_user_entry: Optional[RankingEntry] = None  # Current user's entry (if outside top 10)
    total_participants: int

    class Config:
        from_attributes = True
