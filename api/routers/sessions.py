"""
Session management endpoints - video upload and session tracking.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from pathlib import Path
import uuid
from typing import List

from database import get_db
from models import User, SurfingSession
from schemas import (
    SessionResponse,
    SessionWithResults,
    SessionListResponse,
    UploadResponse,
    SessionStatus,
)
from utils.dependencies import get_current_confirmed_user
from config import settings

router = APIRouter()


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: UploadFile = File(...),
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

    return session


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
