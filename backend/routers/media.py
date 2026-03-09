"""Serve media files (images) from dataset directories."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Message

router = APIRouter(prefix="/api/media", tags=["media"])


@router.get("/{dataset_id}/{media_index}")
def get_media(dataset_id: str, media_index: int, msg_id: str = "", db: Session = Depends(get_db)):
    """Serve a media file. Requires msg_id query param to locate the file."""
    if not msg_id:
        raise HTTPException(400, "msg_id query parameter required")

    m = db.query(Message).filter(Message.id == msg_id, Message.dataset_id == dataset_id).first()
    if not m:
        raise HTTPException(404, "Message not found")

    paths = m.media_paths
    if media_index < 0 or media_index >= len(paths):
        raise HTTPException(404, "Media index out of range")

    file_path = Path(paths[media_index])
    if not file_path.exists():
        raise HTTPException(404, "Media file not found on disk")

    suffix = file_path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return FileResponse(file_path, media_type=media_types.get(suffix, "application/octet-stream"))
