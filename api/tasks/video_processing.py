"""
Celery task for video processing using the tracker service.
"""
import os
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from tasks.celery_app import celery_app
from database import SessionLocal
from models import SurfingSession
from schemas import SessionStatus
from services.scoring_service import ScoringService
from services.ranking_service import RankingService


@celery_app.task(bind=True, name="tasks.process_video")
def process_video(self, session_id: str):
    """
    Background task to process a surfing video using the tracker service.

    This task:
    1. Updates session status to 'processing'
    2. Runs the tracker Docker container
    3. Monitors tracker progress
    4. Parses results and stores them in the database
    5. Updates session status to 'completed' or 'failed'

    Args:
        session_id: UUID of the surfing session to process
    """
    db = SessionLocal()

    try:
        # Get session from database
        session = db.query(SurfingSession).filter(SurfingSession.id == session_id).first()

        if not session:
            raise ValueError(f"Session {session_id} not found")

        print(f"[INFO] Starting video processing for session {session_id}")

        # Update status to processing
        session.status = SessionStatus.PROCESSING
        session.started_processing_at = datetime.utcnow()
        db.commit()

        # Prepare paths
        video_path = Path(session.video_path)
        user_id = str(session.user_id)
        output_dir = Path("/data/output") / user_id / session_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run tracker as subprocess
        success, error_message = run_tracker_subprocess(
            video_path=video_path,
            output_dir=output_dir
        )

        if not success:
            # Update session with error
            session.status = SessionStatus.FAILED
            session.error_message = error_message
            session.completed_at = datetime.utcnow()
            db.commit()
            print(f"[ERROR] Video processing failed for session {session_id}: {error_message}")
            return {"status": "failed", "error": error_message}

        # Parse results
        results = parse_tracker_results(output_dir)

        # Calculate session score
        score = ScoringService.calculate_session_score(results)
        print(f"[INFO] Calculated session score: {score}")

        # Update session with results
        session.status = SessionStatus.COMPLETED
        session.output_path = str(output_dir)
        session.results_json = results
        session.score = score
        session.completed_at = datetime.utcnow()
        db.commit()

        # Update rankings for all periods (daily, monthly, yearly)
        try:
            RankingService.update_all_periods_for_session(db, session)
            print(f"[INFO] Updated rankings for session {session_id}")
        except Exception as e:
            print(f"[WARN] Failed to update rankings: {e}")
            # Don't fail the entire task if ranking update fails

        print(f"[INFO] Video processing completed for session {session_id}")

        return {"status": "completed", "session_id": session_id, "score": score}

    except Exception as e:
        print(f"[ERROR] Video processing failed for session {session_id}: {e}")

        # Update session with error
        if session:
            session.status = SessionStatus.FAILED
            session.error_message = str(e)
            session.completed_at = datetime.utcnow()
            db.commit()

        raise

    finally:
        db.close()


def run_tracker_subprocess(video_path: Path, output_dir: Path) -> tuple[bool, Optional[str]]:
    """
    Run the tracker service as a subprocess.

    Args:
        video_path: Path to input video file
        output_dir: Path to output directory

    Returns:
        Tuple of (success, error_message)
    """
    try:
        print(f"[INFO] Running tracker subprocess")
        print(f"[INFO] Video: {video_path}")
        print(f"[INFO] Output: {output_dir}")

        # Set environment variables for tracker
        env = os.environ.copy()
        env["VIDEO_SOURCE"] = str(video_path)
        env["OUTPUT_DIR"] = str(output_dir)

        # Run tracker.py as subprocess
        tracker_script = Path(__file__).parent.parent / "tracker" / "tracker.py"

        result = subprocess.run(
            ["python", str(tracker_script)],
            env=env,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        if result.returncode != 0:
            error_msg = f"Tracker failed with exit code {result.returncode}:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            print(f"[ERROR] {error_msg}")
            return False, error_msg

        # Success
        print(f"[INFO] Tracker completed successfully")
        print(f"[INFO] STDOUT: {result.stdout}")
        return True, None

    except subprocess.TimeoutExpired:
        error_msg = "Tracker timed out after 10 minutes"
        print(f"[ERROR] {error_msg}")
        return False, error_msg

    except Exception as e:
        error_msg = f"Tracker error: {str(e)}"
        print(f"[ERROR] {error_msg}")
        return False, error_msg


def parse_tracker_results(output_dir: Path) -> dict:
    """
    Parse tracker output files and compile results.

    Args:
        output_dir: Directory containing tracker output

    Returns:
        Dictionary with compiled results
    """
    results = {
        "surfers": [],
        "output_video": None,
    }

    try:
        # Check for output video
        output_video = output_dir / "output.mp4"
        if output_video.exists():
            results["output_video"] = str(output_video)

        # Parse per-surfer results from elements directory
        elements_dir = output_dir / "elements"
        if elements_dir.exists():
            for surfer_dir in elements_dir.iterdir():
                if surfer_dir.is_dir():
                    # Parse maneuvers.json for this surfer
                    maneuvers_file = surfer_dir / "maneuvers.json"
                    if maneuvers_file.exists():
                        with open(maneuvers_file, "r") as f:
                            surfer_data = json.load(f)

                        # Add picture paths
                        pictures_dir = surfer_dir / "pictures"
                        pictures = []
                        if pictures_dir.exists():
                            pictures = [str(p) for p in sorted(pictures_dir.glob("*.png"))]

                        surfer_data["pictures"] = pictures
                        results["surfers"].append(surfer_data)

        print(f"[INFO] Parsed results: {len(results['surfers'])} surfers found")

    except Exception as e:
        print(f"[WARN] Error parsing tracker results: {e}")
        # Return partial results
        results["parse_error"] = str(e)

    return results
