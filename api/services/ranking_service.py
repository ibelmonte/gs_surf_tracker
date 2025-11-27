"""
Service for managing user rankings across different time periods.
"""
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import logging

from models.ranking import SessionRanking
from models.session import SurfingSession
from models.user import User

logger = logging.getLogger(__name__)


class RankingService:
    """Service for calculating and managing user rankings."""

    PERIOD_DAILY = "daily"
    PERIOD_MONTHLY = "monthly"
    PERIOD_YEARLY = "yearly"

    @staticmethod
    def get_period_bounds(period: str, reference_date: Optional[datetime] = None) -> Tuple[datetime, datetime]:
        """
        Get the start and end datetime for a given period.

        Args:
            period: Period type ('daily', 'monthly', 'yearly')
            reference_date: Date to calculate period from (defaults to now)

        Returns:
            Tuple of (period_start, period_end) as datetime objects
        """
        if reference_date is None:
            reference_date = datetime.utcnow()

        if period == RankingService.PERIOD_DAILY:
            # Start of day to end of day
            period_start = reference_date.replace(hour=0, minute=0, second=0, microsecond=0)
            period_end = period_start + timedelta(days=1)

        elif period == RankingService.PERIOD_MONTHLY:
            # Start of month to start of next month
            period_start = reference_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Calculate next month
            if reference_date.month == 12:
                next_month = reference_date.replace(year=reference_date.year + 1, month=1)
            else:
                next_month = reference_date.replace(month=reference_date.month + 1)
            period_end = next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        elif period == RankingService.PERIOD_YEARLY:
            # Start of year to start of next year
            period_start = reference_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = period_start.replace(year=period_start.year + 1)

        else:
            raise ValueError(f"Invalid period: {period}")

        return period_start, period_end

    @staticmethod
    def get_period_label(period: str, period_start: datetime) -> str:
        """
        Generate human-readable label for a period.

        Args:
            period: Period type
            period_start: Start datetime of period

        Returns:
            Human-readable label (e.g., "Today", "November 2023", "2023")
        """
        if period == RankingService.PERIOD_DAILY:
            if period_start.date() == datetime.utcnow().date():
                return "Today"
            elif period_start.date() == (datetime.utcnow() - timedelta(days=1)).date():
                return "Yesterday"
            else:
                return period_start.strftime("%B %d, %Y")

        elif period == RankingService.PERIOD_MONTHLY:
            return period_start.strftime("%B %Y")

        elif period == RankingService.PERIOD_YEARLY:
            return str(period_start.year)

        return "Unknown"

    @staticmethod
    def update_user_ranking(
        db: Session,
        user_id: str,
        period: str,
        period_start: datetime,
        score_delta: float = 0.0,
        session_count_delta: int = 1
    ) -> SessionRanking:
        """
        Update or create a user's ranking entry for a specific period.

        Args:
            db: Database session
            user_id: User UUID
            period: Period type
            period_start: Start of period
            score_delta: Score to add (can be negative for recalculation)
            session_count_delta: Number of sessions to add

        Returns:
            Updated or created SessionRanking object
        """
        # Find or create ranking entry
        ranking = db.query(SessionRanking).filter(
            and_(
                SessionRanking.user_id == user_id,
                SessionRanking.period == period,
                SessionRanking.period_start == period_start
            )
        ).first()

        if ranking is None:
            # Create new ranking entry
            ranking = SessionRanking(
                user_id=user_id,
                period=period,
                period_start=period_start,
                total_score=max(0.0, score_delta),
                session_count=max(0, session_count_delta),
            )
            db.add(ranking)
        else:
            # Update existing ranking
            ranking.total_score = max(0.0, ranking.total_score + score_delta)
            ranking.session_count = max(0, ranking.session_count + session_count_delta)
            ranking.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(ranking)

        logger.info(
            f"Updated ranking for user {user_id}, period {period}, "
            f"score={ranking.total_score}, sessions={ranking.session_count}"
        )

        return ranking

    @staticmethod
    def recalculate_rankings_for_period(db: Session, period: str, period_start: datetime):
        """
        Recalculate all rankings for a specific period.

        This queries all completed sessions within the period and recalculates
        rankings from scratch.

        Args:
            db: Database session
            period: Period type
            period_start: Start of period
        """
        period_end = RankingService.get_period_bounds(period, period_start)[1]

        logger.info(f"Recalculating rankings for {period} starting {period_start}")

        # Get all completed sessions in this period
        sessions = db.query(SurfingSession).filter(
            and_(
                SurfingSession.status == "completed",
                SurfingSession.completed_at >= period_start,
                SurfingSession.completed_at < period_end,
                SurfingSession.score.isnot(None)
            )
        ).all()

        # Group by user
        user_scores = {}
        for session in sessions:
            if session.user_id not in user_scores:
                user_scores[session.user_id] = {
                    'total_score': 0.0,
                    'session_count': 0
                }
            user_scores[session.user_id]['total_score'] += session.score or 0.0
            user_scores[session.user_id]['session_count'] += 1

        # Delete existing rankings for this period
        db.query(SessionRanking).filter(
            and_(
                SessionRanking.period == period,
                SessionRanking.period_start == period_start
            )
        ).delete()

        # Create new rankings
        for user_id, stats in user_scores.items():
            ranking = SessionRanking(
                user_id=user_id,
                period=period,
                period_start=period_start,
                total_score=stats['total_score'],
                session_count=stats['session_count'],
            )
            db.add(ranking)

        db.commit()

        # Calculate and assign ranks (dense ranking)
        RankingService.assign_ranks(db, period, period_start)

        logger.info(f"Recalculated rankings for {len(user_scores)} users")

    @staticmethod
    def assign_ranks(db: Session, period: str, period_start: datetime):
        """
        Assign rank numbers based on total_score (dense ranking).

        Dense ranking means users with equal scores get the same rank,
        and the next rank continues sequentially (no gaps).

        Args:
            db: Database session
            period: Period type
            period_start: Start of period
        """
        # Get all rankings for this period, ordered by score (descending)
        rankings = db.query(SessionRanking).filter(
            and_(
                SessionRanking.period == period,
                SessionRanking.period_start == period_start
            )
        ).order_by(SessionRanking.total_score.desc()).all()

        if not rankings:
            return

        current_rank = 1
        previous_score = None

        for ranking in rankings:
            # Dense ranking: same score = same rank
            if previous_score is not None and ranking.total_score < previous_score:
                current_rank += 1

            ranking.rank = current_rank
            previous_score = ranking.total_score

        db.commit()

        logger.info(f"Assigned ranks for {len(rankings)} users in {period} period")

    @staticmethod
    def update_all_periods_for_session(db: Session, session: SurfingSession):
        """
        Update rankings for all periods (daily, monthly, yearly) when a session completes.

        Args:
            db: Database session
            session: The completed surfing session
        """
        if not session.completed_at or not session.score:
            logger.warning(f"Session {session.id} missing completed_at or score")
            return

        reference_date = session.completed_at

        for period in [RankingService.PERIOD_DAILY, RankingService.PERIOD_MONTHLY, RankingService.PERIOD_YEARLY]:
            period_start, _ = RankingService.get_period_bounds(period, reference_date)

            RankingService.update_user_ranking(
                db=db,
                user_id=session.user_id,
                period=period,
                period_start=period_start,
                score_delta=session.score,
                session_count_delta=1
            )

            # Recalculate ranks for this period
            RankingService.assign_ranks(db, period, period_start)

        logger.info(f"Updated all period rankings for session {session.id}")
