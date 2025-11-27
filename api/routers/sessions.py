"""
Session management endpoints - video upload and session tracking.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pathlib import Path
import uuid
from typing import List, Optional

from database import get_db
from models import User, SurfingSession
from schemas import (
    SessionResponse,
    SessionWithResults,
    SessionListResponse,
    UploadResponse,
    SessionStatus,
    MergeSurfersRequest,
    MergeSurfersResponse,
)
from utils.dependencies import get_current_confirmed_user
from config import settings

router = APIRouter()


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: UploadFile = File(...),
    location: Optional[str] = Form(None),
    date: Optional[str] = Form(None),
    current_user: User = Depends(get_current_confirmed_user),
    db: Session = Depends(get_db)
):
    """
    Upload a surfing video for analysis.

    - Requires authentication and confirmed email
    - Accepts video files (MP4, MOV, AVI, MKV)
    - Max size: 500MB (configurable)
    - Creates session and triggers background processing
    """
    # Validate file type
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in settings.ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_VIDEO_EXTENSIONS)}"
        )

    # Read file and validate size
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    contents = await file.read()

    if len(contents) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE_MB}MB"
        )

    # Create directory for user's videos
    queue_dir = Path(settings.QUEUE_DIR)
    user_dir = queue_dir / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename with timestamp and UUID prefix
    # Format: {timestamp}_{uuid}_{original_filename}
    from datetime import datetime
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]  # Use first 8 chars of UUID for brevity
    safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._- ")
    unique_filename = f"{timestamp}_{unique_id}_{safe_filename}"
    file_path = user_dir / unique_filename

    # Save file
    with open(file_path, "wb") as f:
        f.write(contents)

    # Create session record
    session = SurfingSession(
        user_id=current_user.id,
        video_filename=file.filename,
        video_path=str(file_path),
        location=location,
        session_date=date,
        status=SessionStatus.PENDING
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    # Trigger Celery task to process video
    try:
        from tasks.video_processing import process_video
        process_video.delay(str(session.id))
        print(f"[INFO] Video uploaded and processing triggered: session_id={session.id}")
    except Exception as e:
        print(f"[WARN] Failed to trigger video processing task: {e}")
        # Don't fail the upload if task scheduling fails

    print(f"[INFO] Video uploaded: session_id={session.id}, path={file_path}")

    return UploadResponse(
        session_id=session.id,
        message="Video uploaded successfully. Processing will begin shortly.",
        status=SessionStatus.PENDING
    )


@router.get("/", response_model=SessionListResponse)
async def list_sessions(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_confirmed_user),
    db: Session = Depends(get_db)
):
    """
    List all sessions for current user.

    - Requires authentication and confirmed email
    - Supports pagination
    - Returns sessions sorted by creation date (newest first)
    """
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    # Get total count
    total = db.query(SurfingSession).filter(SurfingSession.user_id == current_user.id).count()

    # Get paginated sessions
    sessions = (
        db.query(SurfingSession)
        .filter(SurfingSession.user_id == current_user.id)
        .order_by(SurfingSession.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return SessionListResponse(
        sessions=sessions,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{session_id}", response_model=SessionWithResults)
async def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_confirmed_user),
    db: Session = Depends(get_db)
):
    """
    Get session details with results.

    - Requires authentication and confirmed email
    - Returns full session data including results JSON
    - Only user who owns the session can access it
    """
    session = db.query(SurfingSession).filter(
        SurfingSession.id == session_id,
        SurfingSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Build video URL if output exists
    video_url = None
    if session.output_path:
        # Extract the relative path from the output_path
        # output_path format: /data/output/{user_id}/{session_id}
        # video URL format: /files/{user_id}/{session_id}/output.mp4
        # Note: Don't include /api prefix - the apiClient will add it automatically
        user_id_str = str(session.user_id)
        session_id_str = str(session.id)

        # Add timestamp query parameter for cache busting
        # This ensures browsers reload the video after reprocessing
        timestamp = int(session.updated_at.timestamp())
        video_url = f"/files/{user_id_str}/{session_id_str}/output.mp4?v={timestamp}"

    # Convert to dict and add video_url
    response_data = SessionWithResults.model_validate(session)
    response_data.video_url = video_url

    return response_data


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_confirmed_user),
    db: Session = Depends(get_db)
):
    """
    Delete a session and its associated files.

    - Requires authentication and confirmed email
    - Deletes video file, output files, and database record
    - Only user who owns the session can delete it
    """
    session = db.query(SurfingSession).filter(
        SurfingSession.id == session_id,
        SurfingSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Delete video file
    video_path = Path(session.video_path)
    if video_path.exists():
        video_path.unlink()

    # Delete output directory
    if session.output_path:
        output_path = Path(session.output_path)
        if output_path.exists() and output_path.is_dir():
            import shutil
            shutil.rmtree(output_path)

    # Delete session record
    db.delete(session)
    db.commit()

    print(f"[INFO] Session deleted: session_id={session_id}")

    return None


@router.post("/{session_id}/merge-surfers", response_model=MergeSurfersResponse)
async def merge_surfers(
    session_id: uuid.UUID,
    request: MergeSurfersRequest,
    current_user: User = Depends(get_current_confirmed_user),
    db: Session = Depends(get_db)
):
    """
    Merge multiple tracked surfers into a single identity.

    - Requires authentication and confirmed email
    - Session must be completed
    - Merges events chronologically and combines pictures
    - Deletes unselected surfer files permanently
    - This action cannot be undone
    """
    from services.surfer_merge_service import SurferMergeService

    # Get session and verify ownership
    session = db.query(SurfingSession).filter(
        SurfingSession.id == session_id,
        SurfingSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Validate session status
    if session.status != SessionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot merge surfers - session status is '{session.status}'. Must be 'completed'."
        )

    # Validate results exist
    if not session.results_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session has no results to merge"
        )

    # Validate multiple surfers exist
    surfers = session.results_json.get('surfers', [])
    if len(surfers) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session has only one surfer - nothing to merge"
        )

    # Validate surfer IDs
    is_valid, error_msg = SurferMergeService.validate_surfer_ids(
        session.results_json,
        request.surfer_ids
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    try:
        # Get all surfer IDs before merge
        all_surfer_ids = [s['id'] for s in surfers]

        # Perform merge on results_json
        merged_results = SurferMergeService.merge_surfers(
            session.results_json,
            request.surfer_ids
        )

        # Delete unselected surfer files
        deleted_ids = []
        if session.output_path:
            deleted_ids = SurferMergeService.delete_unselected_surfer_files(
                session.output_path,
                request.surfer_ids,
                all_surfer_ids
            )

        # Update session with merged results
        session.results_json = merged_results

        # Recalculate score after merge
        from services.scoring_service import ScoringService
        from services.ranking_service import RankingService

        new_score = ScoringService.calculate_session_score(merged_results)
        session.score = new_score

        db.commit()

        # Update rankings for all periods with new score
        try:
            RankingService.update_all_periods_for_session(db, session)
            print(f"[INFO] Updated rankings after merge for session {session_id}")
        except Exception as e:
            print(f"[WARN] Failed to update rankings after merge: {e}")

        # Trigger video reprocessing to show only merged surfers
        try:
            from tasks.video_reprocessing import reprocess_video_after_merge

            # Set reprocessing flag before queuing task
            session.is_reprocessing = 'pending'
            db.commit()

            reprocess_task = reprocess_video_after_merge.delay(
                str(session_id),
                request.surfer_ids
            )
            print(f"[INFO] Video reprocessing task queued: {reprocess_task.id}")
        except Exception as e:
            print(f"[WARN] Failed to queue video reprocessing: {e}")
            session.is_reprocessing = 'failed'
            db.commit()
            # Don't fail the merge if reprocessing fails to queue

        # Get statistics
        stats = SurferMergeService.get_merge_statistics(
            {'surfers': surfers},
            merged_results,
            deleted_ids
        )

        print(f"[INFO] Surfers merged: session_id={session_id}, surfer_ids={request.surfer_ids}, new_score={new_score}")

        return MergeSurfersResponse(**stats)

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Failed to merge surfers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to merge surfers: {str(e)}"
        )
