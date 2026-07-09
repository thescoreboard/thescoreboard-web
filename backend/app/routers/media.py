"""
Media upload router — direct backend upload to Supabase Storage.

POST /api/media/upload   — multipart file upload, backend proxies to Supabase with service key
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional

from app.models.user import User
from app.utils.auth import get_current_user
from app.services import storage

router = APIRouter()

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("/upload")
async def upload_media(
    file: UploadFile = File(...),
    bucket: str = Form(...),
    path: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
):
    """
    Upload an image file to Supabase Storage.
    Returns { public_url: str }

    Sponsor logos (path starts with "sponsors/") are free-plan — sponsor
    management itself isn't Pro-gated, so a sponsor's logo shouldn't be
    either. Tournament branding (posters/logos/team banners) stays Pro-only.
    """
    is_sponsor_logo = bool(path) and path.startswith("sponsors/")
    if not is_sponsor_logo and current_user.plan != "pro":
        raise HTTPException(status_code=403, detail="pro_required")

    if bucket not in storage.VALID_BUCKETS:
        raise HTTPException(status_code=422, detail=f"Unknown bucket '{bucket}'")

    content_type = file.content_type or "image/jpeg"
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=422, detail=f"File type '{content_type}' not allowed. Use JPEG, PNG, or WebP.")

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=422, detail="File too large. Maximum 5 MB.")

    # Auto-generate path if not provided
    if not path:
        ext = (file.filename or "upload").rsplit(".", 1)[-1].lower() or "jpg"
        path = f"uploads/{uuid.uuid4()}.{ext}"

    try:
        public_url = storage.upload_bytes(bucket, path, data, content_type, upsert=True)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Storage error: {exc}")

    return {"public_url": public_url, "path": path}
