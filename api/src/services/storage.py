import hashlib
import os
from typing import Optional, Set
from fastapi import HTTPException, UploadFile, status

from api.src.config import settings

ALLOWED_EXTENSIONS: Set[str] = {
    ".md",
    ".markdown",
    ".txt",
    ".pdf",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
}

# 25 MB default limit
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
LOCAL_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "../../../storage/uploads")


def validate_file(file: UploadFile) -> str:
    """Validates filename extension against allow-list and returns extension."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{ext}'. Allowed types: {sorted(list(ALLOWED_EXTENSIONS))}",
        )
    return ext


def save_upload_file(
    file_bytes: bytes,
    filename: str,
    tenant_id: str,
    content_id: str,
) -> str:
    """Saves file to storage and returns storage path."""
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB",
        )

    # In local/docker dev mode, persist to storage folder
    target_dir = os.path.join(LOCAL_STORAGE_DIR, tenant_id, content_id)
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, filename)

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    return file_path


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

