"""
Celery task for video reprocessing after surfer merging.
"""
from pathlib import Path
from datetime import datetime
import logging

from tasks.celery_app import celery_app
from database import SessionLocal
from models import SurfingSession
from tracker.reprocess_video import reprocess_video

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.reprocess_video_after_merge")
def reprocess_video_after_merge(self, session_id: str, merged_surfer_ids: list):
    """
    Reprocess video after surfer merge to show only selected surfers.

    This task:
    1. Finds the session's output directory
    2. Locates the original video and tracking_data.json
    3. Calls reprocess_video() to generate new output with only merged surfer IDs
    4. Replaces the old output.mp4 with the new one

    Args:
        session_id: UUID of the surfing session
        merged_surfer_ids: List of surfer IDs that were kept after merge
    """
    db = SessionLocal()

    try:
        # Get session from database
        session = db.query(SurfingSession).filter(SurfingSession.id == session_id).first()

        if not session:
            raise ValueError(f"Session {session_id} not found")

        if not session.output_path:
            raise ValueError(f"Session {session_id} has no output path")

        # Update reprocessing status to 'processing'
        session.is_reprocessing = 'processing'
        db.commit()

        print(f"[INFO] Reprocessing video for session {session_id}")
        print(f"[INFO] Merged surfer IDs: {merged_surfer_ids}")

        output_dir = Path(session.output_path)
        input_video_path = Path(session.video_path)
        tracking_data_path = output_dir / "tracking_data.json"
        current_output_video = output_dir / "output.mp4"
        temp_output_video = output_dir / "output_reprocessed.mp4"

        # Verify required files exist
        if not input_video_path.exists():
            raise FileNotFoundError(f"Input video not found: {input_video_path}")

        if not tracking_data_path.exists():
            raise FileNotFoundError(f"Tracking data not found: {tracking_data_path}")

        # Reprocess video
        success = reprocess_video(
            input_video_path=str(input_video_path),
            tracking_data_path=str(tracking_data_path),
            output_video_path=str(temp_output_video),
            selected_surfer_ids=merged_surfer_ids
        )

        if not success:
            raise RuntimeError("Video reprocessing failed")

        # Replace old output with new one
        if current_output_video.exists():
            # Backup old video
            backup_video = output_dir / "output_backup.mp4"
            current_output_video.rename(backup_video)
            print(f"[INFO] Backed up old video to: {backup_video}")

        # Move reprocessed video to output.mp4
        temp_output_video.rename(current_output_video)
        print(f"[INFO] Replaced output video with reprocessed version")

        # Touch the session to update updated_at timestamp for cache busting
        # and clear reprocessing flag
        from datetime import datetime
        session.updated_at = datetime.utcnow()
        session.is_reprocessing = None  # Clear reprocessing flag
        db.commit()
        print(f"[INFO] Updated session timestamp for cache invalidation")
        print(f"[INFO] Cleared reprocessing flag")

        print(f"[INFO] Video reprocessing completed for session {session_id}")

        return {
            "status": "success",
            "session_id": session_id,
            "merged_surfer_ids": merged_surfer_ids,
            "output_video": str(current_output_video)
        }

    except Exception as e:
        logger.error(f"Failed to reprocess video for session {session_id}: {e}")
        print(f"[ERROR] Video reprocessing failed for session {session_id}: {e}")

        # Mark reprocessing as failed
        try:
            session = db.query(SurfingSession).filter(SurfingSession.id == session_id).first()
            if session:
                session.is_reprocessing = 'failed'
                db.commit()
        except Exception as commit_error:
            print(f"[ERROR] Failed to update reprocessing status: {commit_error}")

        raise

    finally:
        db.close()
