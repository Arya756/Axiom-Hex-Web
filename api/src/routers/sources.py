from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.src.auth.dependencies import get_current_user, get_db, require_admin
from api.src.models.source import Source, SourceVersion
from api.src.models.tenant import Tenant
from api.src.models.user import User
from api.src.services.governance import append_audit_log
from contracts import SourceVersion as SourceVersionContract, compile

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceCreateRequest(BaseModel):
    source_id: str
    kind: str  # rule, fact, glossary, palette, logo
    name: str
    description: Optional[str] = None
    body: str
    value: Optional[str] = None
    unit: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    superseded_by: Optional[int] = None
    metadata_json: Optional[Dict[str, Any]] = None


class SourceVersionCreateRequest(BaseModel):
    body: str
    value: Optional[str] = None
    unit: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    metadata_json: Optional[Dict[str, Any]] = None


class SourceVersionResponse(BaseModel):
    id: str
    source_id: str
    version: int
    body: str
    value: Optional[str] = None
    unit: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    superseded_by: Optional[int] = None
    content_hash: str
    lint_flags: List[str] = []
    collisions: List[str] = []


class SourceResponse(BaseModel):
    id: str
    tenant_id: str
    kind: str
    name: str
    description: Optional[str] = None
    current_version: int
    versions: List[SourceVersionResponse] = []


def _compute_hash(body: str, value: Optional[str], unit: Optional[str]) -> str:
    raw = f"{body}|{value or ''}|{unit or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _bump_ruleset_version(db: Session, tenant_id: str) -> int:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant:
        tenant.ruleset_version += 1
        return tenant.ruleset_version
    return 1


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def create_or_version_source(
    payload: SourceCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Idempotently creates a source or adds a new version.
    
    If the exact content_hash exists for (tenant_id, source_id), returns existing version without duplicating.
    """
    tenant_id = current_user.tenant_id
    content_hash = _compute_hash(payload.body, payload.value, payload.unit)

    # 1. Check if source exists for tenant
    source = (
        db.query(Source)
        .filter(Source.id == payload.source_id, Source.tenant_id == tenant_id)
        .first()
    )

    if not source:
        source = Source(
            id=payload.source_id,
            tenant_id=tenant_id,
            kind=payload.kind,
            name=payload.name,
            description=payload.description,
            current_version=1,
        )
        db.add(source)
        db.flush()
        version_num = 1
    else:
        # Check idempotency: does this exact content hash already exist?
        existing_version = (
            db.query(SourceVersion)
            .filter(
                SourceVersion.tenant_id == tenant_id,
                SourceVersion.source_id == payload.source_id,
                SourceVersion.content_hash == content_hash,
            )
            .first()
        )
        if existing_version:
            # Idempotent return without duplicate creation
            all_versions = (
                db.query(SourceVersion)
                .filter(
                    SourceVersion.tenant_id == tenant_id,
                    SourceVersion.source_id == payload.source_id,
                )
                .order_by(SourceVersion.version.asc())
                .all()
            )
            return SourceResponse(
                id=source.id,
                tenant_id=source.tenant_id,
                kind=source.kind,
                name=source.name,
                description=source.description,
                current_version=source.current_version,
                versions=[
                    SourceVersionResponse(
                        id=v.id,
                        source_id=v.source_id,
                        version=v.version,
                        body=v.body,
                        value=v.value,
                        unit=v.unit,
                        valid_from=v.valid_from,
                        valid_until=v.valid_until,
                        superseded_by=v.superseded_by,
                        content_hash=v.content_hash,
                        lint_flags=v.lint_flags or [],
                        collisions=v.collisions or [],
                    )
                    for v in all_versions
                ],
            )
        version_num = source.current_version + 1
        # Supersede previous version
        prev_v = (
            db.query(SourceVersion)
            .filter(
                SourceVersion.tenant_id == tenant_id,
                SourceVersion.source_id == payload.source_id,
                SourceVersion.version == source.current_version,
            )
            .first()
        )
        if prev_v:
            prev_v.superseded_by = version_num
            if not prev_v.valid_until:
                prev_v.valid_until = datetime.now(timezone.utc)

        source.current_version = version_num
        source.updated_at = datetime.now(timezone.utc)

    # 2. Call compile hook (T5) to generate 384-d embedding, lint flags, and collisions
    contract_sv = SourceVersionContract(
        source_id=payload.source_id,
        version=version_num,
        kind=payload.kind,
        body=payload.body,
    )
    compile_result = compile(contract_sv)

    # 3. Create SourceVersion record
    version_id = f"sv_{tenant_id}_{payload.source_id}_v{version_num}"
    source_version = SourceVersion(
        id=version_id,
        tenant_id=tenant_id,
        source_id=payload.source_id,
        version=version_num,
        body=payload.body,
        embedding=compile_result.embedding,  # 384-d vector column
        value=payload.value,
        unit=payload.unit,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        superseded_by=payload.superseded_by,
        content_hash=content_hash,
        lint_flags=compile_result.lint_flags,
        collisions=compile_result.collisions,
        metadata_json=payload.metadata_json or {},
    )
    db.add(source_version)
    _bump_ruleset_version(db, tenant_id)
    append_audit_log(
        db=db,
        tenant_id=tenant_id,
        entity_type="source",
        entity_id=payload.source_id,
        action="source.version_created",
        payload={
            "version": version_num,
            "kind": source.kind,
            "content_hash": content_hash,
            "actor_id": current_user.id,
        },
    )
    db.commit()

    all_versions = (
        db.query(SourceVersion)
        .filter(
            SourceVersion.tenant_id == tenant_id,
            SourceVersion.source_id == payload.source_id,
        )
        .order_by(SourceVersion.version.asc())
        .all()
    )

    return SourceResponse(
        id=source.id,
        tenant_id=source.tenant_id,
        kind=source.kind,
        name=source.name,
        description=source.description,
        current_version=source.current_version,
        versions=[
            SourceVersionResponse(
                id=v.id,
                source_id=v.source_id,
                version=v.version,
                body=v.body,
                value=v.value,
                unit=v.unit,
                valid_from=v.valid_from,
                valid_until=v.valid_until,
                superseded_by=v.superseded_by,
                content_hash=v.content_hash,
                lint_flags=v.lint_flags or [],
                collisions=v.collisions or [],
            )
            for v in all_versions
        ],
    )


@router.post("/{source_id}/versions", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def create_source_version(
    source_id: str,
    payload: SourceVersionCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Adds a new version to an existing source. Supersedes old version and bumps ruleset_version.
    
    Idempotent: matching content_hash returns existing version without duplicating.
    """
    tenant_id = current_user.tenant_id
    source = (
        db.query(Source)
        .filter(Source.id == source_id, Source.tenant_id == tenant_id)
        .first()
    )
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found for current tenant",
        )

    content_hash = _compute_hash(payload.body, payload.value, payload.unit)

    # Check idempotency
    existing_version = (
        db.query(SourceVersion)
        .filter(
            SourceVersion.tenant_id == tenant_id,
            SourceVersion.source_id == source_id,
            SourceVersion.content_hash == content_hash,
        )
        .first()
    )
    if existing_version:
        all_versions = (
            db.query(SourceVersion)
            .filter(
                SourceVersion.tenant_id == tenant_id,
                SourceVersion.source_id == source_id,
            )
            .order_by(SourceVersion.version.asc())
            .all()
        )
        return SourceResponse(
            id=source.id,
            tenant_id=source.tenant_id,
            kind=source.kind,
            name=source.name,
            description=source.description,
            current_version=source.current_version,
            versions=[
                SourceVersionResponse(
                    id=v.id,
                    source_id=v.source_id,
                    version=v.version,
                    body=v.body,
                    value=v.value,
                    unit=v.unit,
                    valid_from=v.valid_from,
                    valid_until=v.valid_until,
                    superseded_by=v.superseded_by,
                    content_hash=v.content_hash,
                    lint_flags=v.lint_flags or [],
                    collisions=v.collisions or [],
                )
                for v in all_versions
            ],
        )

    new_version_num = source.current_version + 1

    # Supersede previous version
    prev_v = (
        db.query(SourceVersion)
        .filter(
            SourceVersion.tenant_id == tenant_id,
            SourceVersion.source_id == source_id,
            SourceVersion.version == source.current_version,
        )
        .first()
    )
    if prev_v:
        prev_v.superseded_by = new_version_num
        if not prev_v.valid_until:
            prev_v.valid_until = datetime.now(timezone.utc)

    source.current_version = new_version_num
    source.updated_at = datetime.now(timezone.utc)

    # Call compile hook
    contract_sv = SourceVersionContract(
        source_id=source_id,
        version=new_version_num,
        kind=source.kind,
        body=payload.body,
    )
    compile_result = compile(contract_sv)

    version_id = f"sv_{tenant_id}_{source_id}_v{new_version_num}"
    source_version = SourceVersion(
        id=version_id,
        tenant_id=tenant_id,
        source_id=source_id,
        version=new_version_num,
        body=payload.body,
        embedding=compile_result.embedding,
        value=payload.value,
        unit=payload.unit,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        superseded_by=None,
        content_hash=content_hash,
        lint_flags=compile_result.lint_flags,
        collisions=compile_result.collisions,
        metadata_json=payload.metadata_json or {},
    )
    db.add(source_version)
    _bump_ruleset_version(db, tenant_id)
    append_audit_log(
        db=db,
        tenant_id=tenant_id,
        entity_type="source",
        entity_id=source_id,
        action="source.version_created",
        payload={
            "version": new_version_num,
            "kind": source.kind,
            "content_hash": content_hash,
            "actor_id": current_user.id,
        },
    )
    db.commit()

    all_versions = (
        db.query(SourceVersion)
        .filter(
            SourceVersion.tenant_id == tenant_id,
            SourceVersion.source_id == source_id,
        )
        .order_by(SourceVersion.version.asc())
        .all()
    )

    return SourceResponse(
        id=source.id,
        tenant_id=source.tenant_id,
        kind=source.kind,
        name=source.name,
        description=source.description,
        current_version=source.current_version,
        versions=[
            SourceVersionResponse(
                id=v.id,
                source_id=v.source_id,
                version=v.version,
                body=v.body,
                value=v.value,
                unit=v.unit,
                valid_from=v.valid_from,
                valid_until=v.valid_until,
                superseded_by=v.superseded_by,
                content_hash=v.content_hash,
                lint_flags=v.lint_flags or [],
                collisions=v.collisions or [],
            )
            for v in all_versions
        ],
    )



@router.get("", response_model=List[SourceResponse])
def list_sources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists all sources for the authenticated user's tenant (RLS scoped)."""
    tenant_id = current_user.tenant_id
    sources = db.query(Source).filter(Source.tenant_id == tenant_id).all()

    results = []
    for s in sources:
        versions = (
            db.query(SourceVersion)
            .filter(SourceVersion.tenant_id == tenant_id, SourceVersion.source_id == s.id)
            .order_by(SourceVersion.version.asc())
            .all()
        )
        results.append(
            SourceResponse(
                id=s.id,
                tenant_id=s.tenant_id,
                kind=s.kind,
                name=s.name,
                description=s.description,
                current_version=s.current_version,
                versions=[
                    SourceVersionResponse(
                        id=v.id,
                        source_id=v.source_id,
                        version=v.version,
                        body=v.body,
                        value=v.value,
                        unit=v.unit,
                        valid_from=v.valid_from,
                        valid_until=v.valid_until,
                        superseded_by=v.superseded_by,
                        content_hash=v.content_hash,
                        lint_flags=v.lint_flags or [],
                        collisions=v.collisions or [],
                    )
                    for v in versions
                ],
            )
        )
    return results


@router.get("/{source_id}", response_model=SourceResponse)
def get_source(
    source_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves a single source and its version history for the current tenant."""
    tenant_id = current_user.tenant_id
    source = (
        db.query(Source)
        .filter(Source.id == source_id, Source.tenant_id == tenant_id)
        .first()
    )
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found",
        )
    versions = (
        db.query(SourceVersion)
        .filter(SourceVersion.tenant_id == tenant_id, SourceVersion.source_id == source.id)
        .order_by(SourceVersion.version.asc())
        .all()
    )
    return SourceResponse(
        id=source.id,
        tenant_id=source.tenant_id,
        kind=source.kind,
        name=source.name,
        description=source.description,
        current_version=source.current_version,
        versions=[
            SourceVersionResponse(
                id=v.id,
                source_id=v.source_id,
                version=v.version,
                body=v.body,
                value=v.value,
                unit=v.unit,
                valid_from=v.valid_from,
                valid_until=v.valid_until,
                superseded_by=v.superseded_by,
                content_hash=v.content_hash,
                lint_flags=v.lint_flags or [],
                collisions=v.collisions or [],
            )
            for v in versions
        ],
    )


