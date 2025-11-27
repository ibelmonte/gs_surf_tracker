"""
File serving endpoints - serve processed video frames and output files.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from pathlib import Path
import uuid
import os
from typing import Optional

from database import get_db
from models import User, SurfingSession
from utils.dependencies import get_current_confirmed_user, get_optional_current_user
from config import settings

router = APIRouter()


def parse_range_header(range_header: str, file_size: int) -> Optional[tuple]:
    """
    Parse HTTP Range header and return (start, end) byte positions.

    Args:
        range_header: Range header value (e.g., "bytes=0-1023")
        file_size: Total file size in bytes

    Returns:
        Tuple of (start, end) positions, or None if invalid
    """
    try:
        # Parse "bytes=start-end" format
        if not range_header.startswith("bytes="):
            return None

        range_spec = range_header[6:]  # Remove "bytes=" prefix

        if "-" not in range_spec:
            return None

        parts = range_spec.split("-")

        # Handle "bytes=start-end"
        if parts[0] and parts[1]:
            start = int(parts[0])
            end = int(parts[1])
        # Handle "bytes=start-" (from start to end of file)
        elif parts[0] and not parts[1]:
            start = int(parts[0])
            end = file_size - 1
        # Handle "bytes=-end" (last N bytes)
        elif not parts[0] and parts[1]:
            start = file_size - int(parts[1])
            end = file_size - 1
        else:
            return None

        # Validate range
        if start < 0 or end >= file_size or start > end:
            return None

        return (start, end)

    except (ValueError, IndexError):
        return None


@router.get("/{file_path:path}")
async def get_file(
    file_path: str,
    request: Request,
    token: Optional[str] = None,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Serve files from session output directories with HTTP Range support for video streaming.

    - Requires authentication and confirmed email
    - Users can only access files from their own sessions
    - Validates that the requested file belongs to user's session
    - Supports HTTP Range requests for video seeking (206 Partial Content)

    Expected file path format: {user_id}/{session_id}/elements/{surfer_id}/pictures/{frame}.png
    or: {user_id}/{session_id}/output.mp4
    """
    # Require authentication
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Require email confirmation
    if not current_user.is_email_confirmed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not confirmed. Please confirm your email to access this resource.",
        )

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

    # Get file size
    file_size = resolved_path.stat().st_size

    # Handle HTTP Range requests for video files (enables seeking)
    range_header = request.headers.get("range")

    if range_header and suffix == '.mp4':
        # Parse range header
        range_tuple = parse_range_header(range_header, file_size)

        if range_tuple is None:
            # Invalid range, return 416 Range Not Satisfiable
            return StreamingResponse(
                content=iter([]),
                status_code=416,
                headers={"Content-Range": f"bytes */{file_size}"}
            )

        start, end = range_tuple
        content_length = end - start + 1

        # Open file and seek to start position
        def iterfile():
            with open(resolved_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                chunk_size = 8192  # 8KB chunks

                while remaining > 0:
                    chunk = f.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        # Return 206 Partial Content
        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": media_type or "application/octet-stream"
        }

        return StreamingResponse(
            content=iterfile(),
            status_code=206,
            headers=headers,
            media_type=media_type
        )

    # For non-range requests or non-video files, use FileResponse
    return FileResponse(
        path=str(resolved_path),
        media_type=media_type,
        filename=resolved_path.name,
        headers={"Accept-Ranges": "bytes"} if suffix == '.mp4' else {}
    )
