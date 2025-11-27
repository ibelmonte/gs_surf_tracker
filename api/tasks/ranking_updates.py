"""
Celery tasks for ranking updates and recalculation.
"""
from datetime import datetime, timedelta
import logging

from tasks.celery_app import celery_app
from database import SessionLocal
from services.ranking_service import RankingService

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.recalculate_daily_rankings")
def recalculate_daily_rankings():
    """
    Recalculate daily rankings for today.

    This task should run at midnight UTC daily to ensure rankings
    are accurate for the new day.
    """
    db = SessionLocal()

    try:
        today = datetime.utcnow()
        period_start, _ = RankingService.get_period_bounds(
            RankingService.PERIOD_DAILY,
            today
        )

        logger.info(f"Recalculating daily rankings for {period_start.date()}")

        RankingService.recalculate_rankings_for_period(
            db,
            RankingService.PERIOD_DAILY,
            period_start
        )

        logger.info("Daily rankings recalculation completed")

        return {
            "status": "success",
            "period": "daily",
            "period_start": period_start.isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to recalculate daily rankings: {e}")
        raise

    finally:
        db.close()


@celery_app.task(name="tasks.recalculate_monthly_rankings")
def recalculate_monthly_rankings():
    """
    Recalculate monthly rankings for the current month.

    This task should run daily to keep monthly rankings up to date,
    or at minimum on the 1st of each month.
    """
    db = SessionLocal()

    try:
        today = datetime.utcnow()
        period_start, _ = RankingService.get_period_bounds(
            RankingService.PERIOD_MONTHLY,
            today
        )

        logger.info(f"Recalculating monthly rankings for {period_start.strftime('%B %Y')}")

        RankingService.recalculate_rankings_for_period(
            db,
            RankingService.PERIOD_MONTHLY,
            period_start
        )

        logger.info("Monthly rankings recalculation completed")

        return {
            "status": "success",
            "period": "monthly",
            "period_start": period_start.isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to recalculate monthly rankings: {e}")
        raise

    finally:
        db.close()


@celery_app.task(name="tasks.recalculate_yearly_rankings")
def recalculate_yearly_rankings():
    """
    Recalculate yearly rankings for the current year.

    This task should run daily to keep yearly rankings up to date,
    or at minimum on the 1st of each year.
    """
    db = SessionLocal()

    try:
        today = datetime.utcnow()
        period_start, _ = RankingService.get_period_bounds(
            RankingService.PERIOD_YEARLY,
            today
        )

        logger.info(f"Recalculating yearly rankings for {period_start.year}")

        RankingService.recalculate_rankings_for_period(
            db,
            RankingService.PERIOD_YEARLY,
            period_start
        )

        logger.info("Yearly rankings recalculation completed")

        return {
            "status": "success",
            "period": "yearly",
            "period_start": period_start.isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to recalculate yearly rankings: {e}")
        raise

    finally:
        db.close()


@celery_app.task(name="tasks.recalculate_all_rankings")
def recalculate_all_rankings():
    """
    Recalculate all rankings (daily, monthly, yearly) for current periods.

    This is the main scheduled task that should run daily at midnight.
    """
    logger.info("Starting full ranking recalculation for all periods")

    results = {
        "daily": None,
        "monthly": None,
        "yearly": None
    }

    try:
        # Recalculate daily
        results["daily"] = recalculate_daily_rankings()

        # Recalculate monthly
        results["monthly"] = recalculate_monthly_rankings()

        # Recalculate yearly
        results["yearly"] = recalculate_yearly_rankings()

        logger.info("All rankings recalculation completed successfully")

        return {
            "status": "success",
            "message": "All rankings recalculated",
            "results": results
        }

    except Exception as e:
        logger.error(f"Failed to recalculate all rankings: {e}")
        return {
            "status": "error",
            "message": str(e),
            "results": results
        }
