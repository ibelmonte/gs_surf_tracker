"""
File serving endpoints - serve processed video frames and output files.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
import uuid

from database import get_db
from models import User, SurfingSession
from utils.dependencies import get_current_confirmed_user
from config import settings

router = APIRouter()


@router.get("/{file_path:path}")
async def get_file(
    file_path: str,
    current_user: User = Depends(get_current_confirmed_user),
    db: Session = Depends(get_db)
):
    """
    Serve files from session output directories.

    - Requires authentication and confirmed email
    - Users can only access files from their own sessions
    - Validates that the requested file belongs to user's session

    Expected file path format: {user_id}/{session_id}/elements/{surfer_id}/pictures/{frame}.png
    or: {user_id}/{session_id}/output.mp4
    """
    # Parse the file path to extract session_id
    path_parts = Path(file_path).parts

    if len(path_parts) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path"
        )

    # Second part should be the session ID (first is user_id)
    try:
        session_id = uuid.UUID(path_parts[1])
    except (ValueError, IndexError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID in file path"
        )

    # Verify that the session belongs to the current user
    session = db.query(SurfingSession).filter(
        SurfingSession.id == session_id,
        SurfingSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or access denied"
        )

    # Construct full file path
    # Files are stored in: /data/output/{session_id}/...
    full_path = Path(settings.OUTPUT_DIR) / file_path

    # Security check: ensure the resolved path is within the output directory
    # This prevents path traversal attacks
    try:
        resolved_path = full_path.resolve()
        output_dir_resolved = Path(settings.OUTPUT_DIR).resolve()

        if not str(resolved_path).startswith(str(output_dir_resolved)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path"
        )

    # Check if file exists
    if not resolved_path.exists() or not resolved_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Determine media type based on file extension
    media_type = None
    suffix = resolved_path.suffix.lower()

    if suffix in ['.jpg', '.jpeg']:
        media_type = 'image/jpeg'
    elif suffix == '.png':
        media_type = 'image/png'
    elif suffix == '.mp4':
        media_type = 'video/mp4'
    elif suffix == '.json':
        media_type = 'application/json'

    # Serve the file
    return FileResponse(
        path=str(resolved_path),
        media_type=media_type,
        filename=resolved_path.name
    )
