"""
Rankings endpoints - leaderboards and user rankings.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from typing import Optional
import logging

from database import get_db
from models import User, SessionRanking
from schemas import LeaderboardResponse, RankingEntry
from utils.dependencies import get_current_user
from services.ranking_service import RankingService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/leaderboard/{period}", response_model=LeaderboardResponse)
async def get_leaderboard(
    period: str,
    reference_date: Optional[str] = Query(None, description="ISO date string for historical leaderboards (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get leaderboard for a specific period.

    - **period**: 'daily', 'monthly', or 'yearly'
    - **reference_date**: Optional date for historical leaderboards (defaults to today)
    - Returns top 10 users for the period
    - Includes current user's rank even if outside top 10
    """
    # Validate period
    valid_periods = [RankingService.PERIOD_DAILY, RankingService.PERIOD_MONTHLY, RankingService.PERIOD_YEARLY]
    if period not in valid_periods:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid period. Must be one of: {', '.join(valid_periods)}"
        )

    # Parse reference date if provided
    ref_date = datetime.utcnow()
    if reference_date:
        try:
            ref_date = datetime.fromisoformat(reference_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD"
            )

    # Get period bounds
    period_start, _ = RankingService.get_period_bounds(period, ref_date)
    period_label = RankingService.get_period_label(period, period_start)

    # Get top 10 rankings for this period
    top_rankings = db.query(SessionRanking, User).join(
        User, SessionRanking.user_id == User.id
    ).filter(
        and_(
            SessionRanking.period == period,
            SessionRanking.period_start == period_start
        )
    ).order_by(
        SessionRanking.rank.asc(),
        SessionRanking.total_score.desc()
    ).limit(10).all()

    # Build top entries
    top_entries = []
    for ranking, user in top_rankings:
        entry = RankingEntry(
            rank=ranking.rank or 0,
            user_id=str(ranking.user_id),
            user_name=user.email.split('@')[0],  # Use email username as display name
            total_score=ranking.total_score,
            session_count=ranking.session_count,
            is_current_user=(ranking.user_id == current_user.id)
        )
        top_entries.append(entry)

    # Get current user's ranking if not in top 10
    current_user_entry = None
    user_in_top_10 = any(ranking.user_id == current_user.id for ranking, _ in top_rankings)

    if not user_in_top_10:
        user_ranking = db.query(SessionRanking).filter(
            and_(
                SessionRanking.user_id == current_user.id,
                SessionRanking.period == period,
                SessionRanking.period_start == period_start
            )
        ).first()

        if user_ranking:
            current_user_entry = RankingEntry(
                rank=user_ranking.rank or 0,
                user_id=str(current_user.id),
                user_name=current_user.email.split('@')[0],
                total_score=user_ranking.total_score,
                session_count=user_ranking.session_count,
                is_current_user=True
            )

    # Get total number of participants
    total_participants = db.query(SessionRanking).filter(
        and_(
            SessionRanking.period == period,
            SessionRanking.period_start == period_start
        )
    ).count()

    return LeaderboardResponse(
        period=period,
        period_start=period_start,
        period_label=period_label,
        top_entries=top_entries,
        current_user_entry=current_user_entry,
        total_participants=total_participants
    )


@router.get("/leaderboard/{period}/user/{user_id}", response_model=Optional[RankingEntry])
async def get_user_ranking(
    period: str,
    user_id: str,
    reference_date: Optional[str] = Query(None, description="ISO date string (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get specific user's ranking for a period.

    - **period**: 'daily', 'monthly', or 'yearly'
    - **user_id**: UUID of user to look up
    - **reference_date**: Optional date (defaults to today)
    """
    # Validate period
    valid_periods = [RankingService.PERIOD_DAILY, RankingService.PERIOD_MONTHLY, RankingService.PERIOD_YEARLY]
    if period not in valid_periods:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid period. Must be one of: {', '.join(valid_periods)}"
        )

    # Parse reference date if provided
    ref_date = datetime.utcnow()
    if reference_date:
        try:
            ref_date = datetime.fromisoformat(reference_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD"
            )

    # Get period bounds
    period_start, _ = RankingService.get_period_bounds(period, ref_date)

    # Get user's ranking
    ranking = db.query(SessionRanking, User).join(
        User, SessionRanking.user_id == User.id
    ).filter(
        and_(
            SessionRanking.user_id == user_id,
            SessionRanking.period == period,
            SessionRanking.period_start == period_start
        )
    ).first()

    if not ranking:
        return None

    ranking_obj, user = ranking

    return RankingEntry(
        rank=ranking_obj.rank or 0,
        user_id=str(ranking_obj.user_id),
        user_name=user.email.split('@')[0],
        total_score=ranking_obj.total_score,
        session_count=ranking_obj.session_count,
        is_current_user=(ranking_obj.user_id == current_user.id)
    )


@router.post("/recalculate/{period}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_recalculation(
    period: str,
    reference_date: Optional[str] = Query(None, description="ISO date string (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually trigger ranking recalculation for a period.

    - **period**: 'daily', 'monthly', or 'yearly'
    - **reference_date**: Optional date (defaults to today)
    - Requires authentication
    - Useful for fixing data inconsistencies or manual updates
    """
    # Validate period
    valid_periods = [RankingService.PERIOD_DAILY, RankingService.PERIOD_MONTHLY, RankingService.PERIOD_YEARLY]
    if period not in valid_periods:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid period. Must be one of: {', '.join(valid_periods)}"
        )

    # Parse reference date if provided
    ref_date = datetime.utcnow()
    if reference_date:
        try:
            ref_date = datetime.fromisoformat(reference_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD"
            )

    # Get period bounds
    period_start, _ = RankingService.get_period_bounds(period, ref_date)

    # Trigger recalculation
    try:
        RankingService.recalculate_rankings_for_period(db, period, period_start)
        logger.info(f"Manual recalculation triggered for {period} period starting {period_start}")

        return {
            "message": f"Recalculation triggered for {period} period",
            "period": period,
            "period_start": period_start.isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to recalculate rankings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to recalculate rankings: {str(e)}"
        )
