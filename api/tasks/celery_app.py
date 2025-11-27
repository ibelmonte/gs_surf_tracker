"""
Celery application configuration.
"""
from celery import Celery
from celery.schedules import crontab
from config import settings

# Create Celery app
celery_app = Celery(
    "surf_tracker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["tasks.video_processing", "tasks.ranking_updates", "tasks.video_reprocessing"]  # Include task modules
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,  # Only fetch one task at a time
    worker_max_tasks_per_child=10,  # Restart worker after 10 tasks
)

# Optional: Configure result expiration
celery_app.conf.result_expires = 3600  # Results expire after 1 hour

# Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "recalculate-all-rankings-daily": {
        "task": "tasks.recalculate_all_rankings",
        "schedule": crontab(hour=0, minute=0),  # Run daily at midnight UTC
    },
}

if __name__ == "__main__":
    celery_app.start()
