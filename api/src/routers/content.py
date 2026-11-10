from datetime import datetime, timezone
import os
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.src.auth.dependencies import get_current_user, get_db
from api.src.models.content import Content, Revision
from api.src.models.user import User
from api.src.services.storage import compute_sha256, save_upload_file, validate_file

router = APIRouter(prefix="/content", tags=["content"])

VALID_SENSITIVITIES = {"public", "internal", "restricted"}


class RevisionResponse(BaseModel):
    id: str
    content_id: str
    version_num: int
    content_hash: str
    raw_text: Optional[str] = None
    status: str
    approval_status: str
    created_at: datetime


class ContentResponse(BaseModel):
    id: str
    tenant_id: str
    title: str
    file_path: Optional[str] = None
    file_type: str
    sensitivity: str
    created_by: str
    created_at: datetime
    revisions: List[RevisionResponse] = []


@router.post("", response_model=ContentResponse, status_code=status.HTTP_201_CREATED)
async def create_content(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    sensitivity: str = Form("internal"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uploads draft content, enforces allow-list/size limits, computes SHA-256 hash, and stores revision."""
    sens_lower = sensitivity.lower()
    if sens_lower not in VALID_SENSITIVITIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid sensitivity '{sensitivity}'. Allowed: {sorted(list(VALID_SENSITIVITIES))}",
        )

    ext = validate_file(file)
    file_bytes = await file.read()
    content_hash = compute_sha256(file_bytes)

    tenant_id = current_user.tenant_id
    content_id = f"c_{uuid.uuid4().hex[:8]}"
    revision_id = f"rev_{uuid.uuid4().hex[:8]}"

    storage_path = save_upload_file(file_bytes, file.filename or "uploaded_file", tenant_id, content_id)

    raw_text = None
    if ext in {".txt", ".md", ".markdown"}:
        raw_text = file_bytes.decode("utf-8", errors="ignore")

    content = Content(
        id=content_id,
        tenant_id=tenant_id,
        title=title or (file.filename or "Untitled"),
        file_path=storage_path,
        file_type=ext.lstrip("."),
        sensitivity=sens_lower,
        created_by=current_user.id,
    )
    db.add(content)

    revision = Revision(
        id=revision_id,
        tenant_id=tenant_id,
        content_id=content_id,
        version_num=1,
        content_hash=content_hash,
        raw_text=raw_text,
        status="draft",
        approval_status="pending",
    )
    db.add(revision)
    db.commit()

    return ContentResponse(
        id=content.id,
        tenant_id=content.tenant_id,
        title=content.title,
        file_path=content.file_path,
        file_type=content.file_type,
        sensitivity=content.sensitivity,
        created_by=content.created_by,
        created_at=content.created_at,
        revisions=[
            RevisionResponse(
                id=revision.id,
                content_id=revision.content_id,
                version_num=revision.version_num,
                content_hash=revision.content_hash,
                raw_text=revision.raw_text,
                status=revision.status,
                approval_status=revision.approval_status,
                created_at=revision.created_at,
            )
        ],
    )


@router.post("/{content_id}/revisions", response_model=RevisionResponse, status_code=status.HTTP_201_CREATED)
async def create_revision(
    content_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Creates a new revision of existing content, storing SHA-256 hash and invalidating previous approval."""
    tenant_id = current_user.tenant_id
    content = (
        db.query(Content)
        .filter(Content.id == content_id, Content.tenant_id == tenant_id)
        .first()
    )
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content '{content_id}' not found",
        )

    ext = validate_file(file)
    file_bytes = await file.read()
    content_hash = compute_sha256(file_bytes)

    # Determine next version number
    latest_rev = (
        db.query(Revision)
        .filter(Revision.content_id == content_id, Revision.tenant_id == tenant_id)
        .order_by(Revision.version_num.desc())
        .first()
    )
    next_ver = (latest_rev.version_num + 1) if latest_rev else 1

    revision_id = f"rev_{uuid.uuid4().hex[:8]}"
    storage_path = save_upload_file(file_bytes, file.filename or f"revision_{next_ver}", tenant_id, content_id)

    raw_text = None
    if ext in {".txt", ".md", ".markdown"}:
        raw_text = file_bytes.decode("utf-8", errors="ignore")

    revision = Revision(
        id=revision_id,
        tenant_id=tenant_id,
        content_id=content_id,
        version_num=next_ver,
        content_hash=content_hash,
        raw_text=raw_text,
        status="draft",
        approval_status="pending",
    )
    db.add(revision)

    # If previous revision was approved, mark it superseded/invalidated
    if latest_rev and latest_rev.approval_status == "approved":
        latest_rev.status = "invalidated"

    db.commit()

    return RevisionResponse(
        id=revision.id,
        content_id=revision.content_id,
        version_num=revision.version_num,
        content_hash=revision.content_hash,
        raw_text=revision.raw_text,
        status=revision.status,
        approval_status=revision.approval_status,
        created_at=revision.created_at,
    )


@router.get("", response_model=List[ContentResponse])
def list_content(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists content items and their revisions for current tenant."""
    tenant_id = current_user.tenant_id
    contents = db.query(Content).filter(Content.tenant_id == tenant_id).all()
    results = []
    for c in contents:
        revisions = (
            db.query(Revision)
            .filter(Revision.content_id == c.id, Revision.tenant_id == tenant_id)
            .order_by(Revision.version_num.asc())
            .all()
        )
        results.append(
            ContentResponse(
                id=c.id,
                tenant_id=c.tenant_id,
                title=c.title,
                file_path=c.file_path,
                file_type=c.file_type,
                sensitivity=c.sensitivity,
                created_by=c.created_by,
                created_at=c.created_at,
                revisions=[
                    RevisionResponse(
                        id=r.id,
                        content_id=r.content_id,
                        version_num=r.version_num,
                        content_hash=r.content_hash,
                        raw_text=r.raw_text,
                        status=r.status,
                        approval_status=r.approval_status,
                        created_at=r.created_at,
                    )
                    for r in revisions
                ],
            )
        )
    return results

