from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.src.auth.dependencies import get_current_user, get_db
from api.src.database import AdminSessionLocal, SessionLocal
from api.src.models.content import Content, Revision
from api.src.models.review import Comment, FindingModel, ReviewRun
from api.src.models.tenant import Tenant
from api.src.models.user import User
from api.src.models.workflow import Approval
from api.src.services.governance import (
    CLAIM_FINDING_TYPES,
    append_audit_log,
    record_usage_entries,
    route_finding_by_type,
)
from contracts import (
    ContentUnit,
    IntentCard as IntentCardContract,
    ReviewResult,
    RunNodeStatus,
    Sensitivity,
    run_review,
)

router = APIRouter(prefix="/revisions", tags=["revisions"])

STALE_RUN_TIMEOUT_SECONDS = 300  # 5 minutes
INVALIDATED_NEW_STATUS = "Invalidated (New Unapproved Revision)"
APPROVER_ROLES = {"reviewer", "legal_reviewer", "admin"}


class IntentCardPayload(BaseModel):
    purpose: str
    audience: str
    key_message: str
    cta: Optional[str] = None


class ReviewRunRequest(BaseModel):
    sensitivity: Optional[str] = None  # public, internal, restricted
    intent_card: Optional[IntentCardPayload] = None


class ReviewRunResponse(BaseModel):
    id: str
    revision_id: str
    ruleset_version: int
    sensitivity: str
    status: str
    cached: bool = False
    cache_key: Optional[str] = None
    partial: bool = False
    matched_sources: List[str] = []
    started_at: datetime
    finished_at: Optional[datetime] = None


class FindingResponse(BaseModel):
    finding_id: str
    revision_id: str
    run_id: Optional[str] = None
    type: str
    severity: str
    confidence: float
    span: Dict[str, Any]
    evidence: List[Dict[str, Any]] = []
    explanation: str
    suggested_fix: Optional[Dict[str, Any]] = None
    route_to: str
    status: str
    abstained: bool = False
    rule_id: Optional[str] = None
    disclosure: Optional[Dict[str, Any]] = None
    created_at: datetime


class CommentCreateRequest(BaseModel):
    text: str
    finding_id: Optional[str] = None
    span: Optional[Dict[str, Any]] = None


class CommentResponse(BaseModel):
    id: str
    revision_id: str
    finding_id: Optional[str] = None
    user_id: str
    text: str
    span: Optional[Dict[str, Any]] = None
    created_at: datetime


class ApproveRequest(BaseModel):
    content_hash: str
    comment: Optional[str] = None


class ApprovalResponse(BaseModel):
    id: str
    revision_id: str
    approver_id: str
    content_hash: str
    revision_status: str
    approval_status: str
    approved_at: datetime
    idempotent: bool = False


class EditRevisionRequest(BaseModel):
    raw_text: str
    comment: Optional[str] = None


class EditRevisionResponse(BaseModel):
    id: str
    content_id: str
    version_num: int
    content_hash: str
    raw_text: Optional[str] = None
    created_by: Optional[str] = None
    status: str
    approval_status: str
    previous_revision_id: str
    previous_status: str
    created_at: datetime


class RequestChangesPayload(BaseModel):
    reason: str
    comment: Optional[str] = None


class RequestChangesResponse(BaseModel):
    revision_id: str
    status: str
    approval_status: str
    requested_by: str
    reason: str


def _compute_cache_key(
    tenant_id: str,
    content_hash: str,
    ruleset_version: int,
    sensitivity: str,
    intent_card: Optional[IntentCardPayload],
) -> str:
    card_dict = intent_card.model_dump() if intent_card else {}
    intent_hash = hashlib.sha256(json.dumps(card_dict, sort_keys=True).encode()).hexdigest()
    raw = f"{tenant_id}:{content_hash}:{ruleset_version}:{sensitivity}:{intent_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _run_stale_watchdog(db: Session, revision_id: str, tenant_id: str) -> None:
    """Watchdog: fails any previous runs stuck in 'running' beyond timeout."""
    threshold = datetime.now(timezone.utc) - timedelta(seconds=STALE_RUN_TIMEOUT_SECONDS)
    stale_runs = (
        db.query(ReviewRun)
        .filter(
            ReviewRun.tenant_id == tenant_id,
            ReviewRun.revision_id == revision_id,
            ReviewRun.status == "running",
            ReviewRun.started_at < threshold,
        )
        .all()
    )
    for run in stale_runs:
        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
    if stale_runs:
        db.commit()


def execute_review_run_task(
    run_id: str,
    tenant_id: str,
    revision_id: str,
    ruleset_version: int,
    sensitivity_str: str,
    intent_card_dict: Optional[Dict[str, Any]],
) -> None:
    """Background task executing the multimodal pre-check review run."""
    import api.src.database as db_module
    with db_module.SessionLocal() as db:
        # Set tenant context
        db_module.set_tenant_context(db, tenant_id)

        run = db.query(ReviewRun).filter(ReviewRun.id == run_id).first()
        revision = db.query(Revision).filter(Revision.id == revision_id).first()
        if not run or not revision:
            return

        run.status = "running"
        db.commit()

        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            enforce_no_external = bool(tenant and tenant.no_external_processing)
            effective_sensitivity = (
                "restricted" if enforce_no_external else sensitivity_str
            )

            # 1. Parse or construct ContentUnits
            text_content = revision.raw_text or "Sample content unit placeholder"
            units = [
                ContentUnit(
                    unit_id=f"u_{revision.id}_1",
                    revision_id=revision.id,
                    kind="text",
                    text=text_content,
                    start=0,
                    end=len(text_content),
                )
            ]

            intent_card_contract = (
                IntentCardContract(**intent_card_dict) if intent_card_dict else None
            )

            # 2. Call engine entrypoint (contracts / stub engine)
            result: ReviewResult = run_review(
                revision_units=units,
                ruleset_version=ruleset_version,
                policy=Sensitivity(effective_sensitivity),
                intent_card=intent_card_contract,
            )

            # 3. Only API writes workflow tables (T1 contract requirement)
            for f in result.findings:
                routed_role = route_finding_by_type(
                    f.type.value, abstained=f.abstained
                )
                finding_model = FindingModel(
                    finding_id=f.finding_id,
                    tenant_id=tenant_id,
                    revision_id=revision.id,
                    run_id=run.id,
                    type=f.type.value,
                    severity=f.severity.value,
                    confidence=f.confidence,
                    span_json=f.span.model_dump(),
                    evidence_json=[e.model_dump() for e in f.evidence],
                    explanation=f.explanation,
                    suggested_fix_json=f.suggested_fix.model_dump() if f.suggested_fix else None,
                    route_to=routed_role,
                    status=f.status.value,
                    abstained=f.abstained,
                    rule_id=f.rule_id,
                    disclosure_json=f.disclosure.model_dump() if f.disclosure else None,
                )
                db.add(finding_model)

            record_usage_entries(
                db=db,
                tenant_id=tenant_id,
                run_id=run.id,
                sensitivity=effective_sensitivity,
                result=result,
                enforce_no_external=enforce_no_external,
            )

            run.status = "partial" if result.partial else "done"
            run.partial = result.partial
            run.matched_sources = result.matched_sources
            run.run_progress = [p.model_dump(mode="json") for p in result.run_progress]
            run.finished_at = datetime.now(timezone.utc)
            revision.status = "in_review"
            append_audit_log(
                db=db,
                tenant_id=tenant_id,
                entity_type="review_run",
                entity_id=run.id,
                action="review_run.completed",
                payload={
                    "revision_id": revision.id,
                    "sensitivity": effective_sensitivity,
                    "partial": result.partial,
                    "findings_count": len(result.findings),
                },
            )
            db.commit()

        except Exception as e:
            db.rollback()
            run.status = "failed"
            run.finished_at = datetime.now(timezone.utc)
            db.commit()


@router.post("/{revision_id}/review", response_model=ReviewRunResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_review_run(
    revision_id: str,
    payload: ReviewRunRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Triggers review background task or returns cached result keyed by (tenant, hash, ruleset, policy, card)."""
    tenant_id = current_user.tenant_id

    revision = (
        db.query(Revision)
        .filter(Revision.id == revision_id, Revision.tenant_id == tenant_id)
        .first()
    )
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Revision '{revision_id}' not found",
        )

    content = db.query(Content).filter(Content.id == revision.content_id).first()
    sensitivity = (payload.sensitivity or (content.sensitivity if content else "internal")).lower()

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant and tenant.no_external_processing:
        sensitivity = "restricted"
    ruleset_version = tenant.ruleset_version if tenant else 1

    # Stale run watchdog
    _run_stale_watchdog(db, revision_id, tenant_id)

    # Composite cache key
    cache_key = _compute_cache_key(
        tenant_id=tenant_id,
        content_hash=revision.content_hash,
        ruleset_version=ruleset_version,
        sensitivity=sensitivity,
        intent_card=payload.intent_card,
    )

    # Cache lookup
    cached_run = (
        db.query(ReviewRun)
        .filter(
            ReviewRun.tenant_id == tenant_id,
            ReviewRun.revision_id == revision.id,
            ReviewRun.cache_key == cache_key,
            ReviewRun.status.in_(["done", "partial"]),
        )
        .order_by(ReviewRun.started_at.desc())
        .first()
    )
    if cached_run:
        return ReviewRunResponse(
            id=cached_run.id,
            revision_id=cached_run.revision_id,
            ruleset_version=cached_run.ruleset_version,
            sensitivity=cached_run.sensitivity,
            status=cached_run.status,
            cached=True,
            cache_key=cached_run.cache_key,
            partial=cached_run.partial,
            matched_sources=cached_run.matched_sources or [],
            started_at=cached_run.started_at,
            finished_at=cached_run.finished_at,
        )

    # Create new run
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    new_run = ReviewRun(
        id=run_id,
        tenant_id=tenant_id,
        revision_id=revision.id,
        ruleset_version=ruleset_version,
        sensitivity=sensitivity,
        status="queued",
        cache_key=cache_key,
        partial=False,
        matched_sources=[],
        run_progress=[],
    )
    db.add(new_run)
    db.commit()

    card_dict = payload.intent_card.model_dump() if payload.intent_card else None
    background_tasks.add_task(
        execute_review_run_task,
        run_id=run_id,
        tenant_id=tenant_id,
        revision_id=revision.id,
        ruleset_version=ruleset_version,
        sensitivity_str=sensitivity,
        intent_card_dict=card_dict,
    )

    return ReviewRunResponse(
        id=new_run.id,
        revision_id=new_run.revision_id,
        ruleset_version=new_run.ruleset_version,
        sensitivity=new_run.sensitivity,
        status="queued",
        cached=False,
        cache_key=cache_key,
        partial=False,
        matched_sources=[],
        started_at=new_run.started_at,
        finished_at=None,
    )


@router.get("/{revision_id}/findings", response_model=List[FindingResponse])
def get_revision_findings(
    revision_id: str,
    route_to: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns all findings for the given revision, optionally filtered by routed role queue."""
    tenant_id = current_user.tenant_id
    revision = (
        db.query(Revision)
        .filter(Revision.id == revision_id, Revision.tenant_id == tenant_id)
        .first()
    )
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Revision '{revision_id}' not found",
        )

    query = db.query(FindingModel).filter(
        FindingModel.revision_id == revision_id,
        FindingModel.tenant_id == tenant_id,
    )
    if route_to:
        query = query.filter(FindingModel.route_to == route_to.strip())
    findings = query.all()

    return [
        FindingResponse(
            finding_id=f.finding_id,
            revision_id=f.revision_id,
            run_id=f.run_id,
            type=f.type,
            severity=f.severity,
            confidence=f.confidence,
            span=f.span_json,
            evidence=f.evidence_json or [],
            explanation=f.explanation,
            suggested_fix=f.suggested_fix_json,
            route_to=f.route_to,
            status=f.status,
            abstained=f.abstained,
            rule_id=f.rule_id,
            disclosure=f.disclosure_json,
            created_at=f.created_at,
        )
        for f in findings
    ]


@router.post("/{revision_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(
    revision_id: str,
    payload: CommentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Creates a comment anchored to a text span or a specific finding (Y-10)."""
    tenant_id = current_user.tenant_id
    if not payload.finding_id and not payload.span:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Comment must be anchored to either a finding_id or a text span",
        )

    revision = (
        db.query(Revision)
        .filter(Revision.id == revision_id, Revision.tenant_id == tenant_id)
        .first()
    )
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Revision '{revision_id}' not found",
        )

    if payload.finding_id:
        finding = (
            db.query(FindingModel)
            .filter(FindingModel.finding_id == payload.finding_id, FindingModel.tenant_id == tenant_id)
            .first()
        )
        if not finding:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Finding '{payload.finding_id}' not found",
            )

    comment_id = f"cm_{uuid.uuid4().hex[:8]}"
    comment = Comment(
        id=comment_id,
        tenant_id=tenant_id,
        revision_id=revision_id,
        finding_id=payload.finding_id,
        user_id=current_user.id,
        text=payload.text,
        span_json=payload.span,
    )
    db.add(comment)
    append_audit_log(
        db=db,
        tenant_id=tenant_id,
        entity_type="comment",
        entity_id=comment.id,
        action="comment.created",
        payload={
            "revision_id": revision_id,
            "finding_id": payload.finding_id,
            "user_id": current_user.id,
        },
    )
    db.commit()

    return CommentResponse(
        id=comment.id,
        revision_id=comment.revision_id,
        finding_id=comment.finding_id,
        user_id=comment.user_id,
        text=comment.text,
        span=comment.span_json,
        created_at=comment.created_at,
    )


@router.get("/{revision_id}/comments", response_model=List[CommentResponse])
def get_comments(
    revision_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves all comments for a revision."""
    tenant_id = current_user.tenant_id
    comments = (
        db.query(Comment)
        .filter(Comment.revision_id == revision_id, Comment.tenant_id == tenant_id)
        .order_by(Comment.created_at.asc())
        .all()
    )
    return [
        CommentResponse(
            id=c.id,
            revision_id=c.revision_id,
            finding_id=c.finding_id,
            user_id=c.user_id,
            text=c.text,
            span=c.span_json,
            created_at=c.created_at,
        )
        for c in comments
    ]


@router.post("/{revision_id}/approve", response_model=ApprovalResponse)
def approve_revision(
    revision_id: str,
    payload: ApproveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hash-bound idempotent revision approval enforcing SoD and mandatory legal sign-off (Y-11, Y-13)."""
    tenant_id = current_user.tenant_id

    revision = (
        db.query(Revision)
        .filter(Revision.id == revision_id, Revision.tenant_id == tenant_id)
        .first()
    )
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Revision '{revision_id}' not found",
        )

    if current_user.role not in APPROVER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{current_user.role}' is not permitted to approve revisions",
        )

    content = (
        db.query(Content)
        .filter(Content.id == revision.content_id, Content.tenant_id == tenant_id)
        .first()
    )
    author_id = revision.created_by or (content.created_by if content else None)
    if author_id and current_user.id == author_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Separation of duties violation: authors cannot approve their own revisions",
        )

    if revision.status == "invalidated" or revision.approval_status == "invalidated":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Revision has been invalidated by a newer edit and cannot be approved",
        )

    if payload.content_hash != revision.content_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Content hash mismatch: expected '{revision.content_hash}', "
                f"got '{payload.content_hash}'"
            ),
        )

    existing_approval = (
        db.query(Approval)
        .filter(
            Approval.tenant_id == tenant_id,
            Approval.revision_id == revision.id,
            Approval.approver_id == current_user.id,
            Approval.content_hash == payload.content_hash,
        )
        .first()
    )
    if existing_approval:
        return ApprovalResponse(
            id=existing_approval.id,
            revision_id=existing_approval.revision_id,
            approver_id=existing_approval.approver_id,
            content_hash=existing_approval.content_hash,
            revision_status=revision.status,
            approval_status=revision.approval_status,
            approved_at=existing_approval.approved_at,
            idempotent=True,
        )

    findings = (
        db.query(FindingModel)
        .filter(
            FindingModel.revision_id == revision.id,
            FindingModel.tenant_id == tenant_id,
        )
        .all()
    )

    has_claim_finding = any(f.type.lower() in CLAIM_FINDING_TYPES for f in findings)
    if has_claim_finding and current_user.role != "legal_reviewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mandatory legal_reviewer sign-off is required when claim findings exist on this revision",
        )

    open_findings = [f for f in findings if f.status == "open"]
    if open_findings:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot approve revision while {len(open_findings)} finding(s) remain open",
        )

    approval_id = f"apr_{uuid.uuid4().hex[:8]}"
    approval = Approval(
        id=approval_id,
        tenant_id=tenant_id,
        revision_id=revision.id,
        approver_id=current_user.id,
        content_hash=payload.content_hash,
    )
    db.add(approval)
    revision.status = "approved"
    revision.approval_status = "approved"

    append_audit_log(
        db=db,
        tenant_id=tenant_id,
        entity_type="revision",
        entity_id=revision.id,
        action="revision.approved",
        payload={
            "approval_id": approval_id,
            "approver_id": current_user.id,
            "approver_role": current_user.role,
            "content_hash": payload.content_hash,
            "comment": payload.comment,
            "has_claim_finding": has_claim_finding,
        },
    )
    db.commit()

    return ApprovalResponse(
        id=approval.id,
        revision_id=approval.revision_id,
        approver_id=approval.approver_id,
        content_hash=approval.content_hash,
        revision_status=revision.status,
        approval_status=revision.approval_status,
        approved_at=approval.approved_at,
        idempotent=False,
    )


def _edit_revision_impl(
    revision_id: str,
    payload: EditRevisionRequest,
    current_user: User,
    db: Session,
) -> EditRevisionResponse:
    tenant_id = current_user.tenant_id
    revision = (
        db.query(Revision)
        .filter(Revision.id == revision_id, Revision.tenant_id == tenant_id)
        .first()
    )
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Revision '{revision_id}' not found",
        )

    latest_rev = (
        db.query(Revision)
        .filter(Revision.content_id == revision.content_id, Revision.tenant_id == tenant_id)
        .order_by(Revision.version_num.desc())
        .first()
    )
    next_ver = (latest_rev.version_num + 1) if latest_rev else (revision.version_num + 1)

    was_approved = bool(
        revision.approval_status == "approved"
        or revision.status == "approved"
        or (
            latest_rev is not None
            and (latest_rev.approval_status == "approved" or latest_rev.status == "approved")
        )
    )
    new_status = INVALIDATED_NEW_STATUS if was_approved else "draft"
    new_hash = hashlib.sha256(payload.raw_text.encode("utf-8")).hexdigest()
    new_rev_id = f"rev_{uuid.uuid4().hex[:8]}"

    new_revision = Revision(
        id=new_rev_id,
        tenant_id=tenant_id,
        content_id=revision.content_id,
        version_num=next_ver,
        content_hash=new_hash,
        raw_text=payload.raw_text,
        created_by=current_user.id,
        status=new_status,
        approval_status="pending",
    )
    db.add(new_revision)

    if was_approved:
        for prior in [revision, latest_rev]:
            if prior is not None and (
                prior.approval_status == "approved" or prior.status == "approved"
            ):
                prior.status = "invalidated"
                prior.approval_status = "invalidated"
                append_audit_log(
                    db=db,
                    tenant_id=tenant_id,
                    entity_type="revision",
                    entity_id=prior.id,
                    action="revision.invalidated",
                    payload={
                        "content_id": revision.content_id,
                        "superseded_by": new_rev_id,
                        "previous_hash": prior.content_hash,
                        "new_hash": new_hash,
                        "actor_id": current_user.id,
                    },
                )

    append_audit_log(
        db=db,
        tenant_id=tenant_id,
        entity_type="revision",
        entity_id=new_rev_id,
        action="revision.created",
        payload={
            "content_id": revision.content_id,
            "edited_from_revision_id": revision.id,
            "version_num": next_ver,
            "content_hash": new_hash,
            "status": new_status,
            "created_by": current_user.id,
            "comment": payload.comment,
        },
    )
    db.commit()

    return EditRevisionResponse(
        id=new_revision.id,
        content_id=new_revision.content_id,
        version_num=new_revision.version_num,
        content_hash=new_revision.content_hash,
        raw_text=new_revision.raw_text,
        created_by=new_revision.created_by,
        status=new_revision.status,
        approval_status=new_revision.approval_status,
        previous_revision_id=revision.id,
        previous_status=revision.status,
        created_at=new_revision.created_at,
    )


@router.post(
    "/{revision_id}/edit",
    response_model=EditRevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def edit_revision_post(
    revision_id: str,
    payload: EditRevisionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Creates a new revision from a text edit; invalidates any approved revision (Y-11)."""
    return _edit_revision_impl(revision_id, payload, current_user, db)


@router.patch(
    "/{revision_id}",
    response_model=EditRevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def edit_revision_patch(
    revision_id: str,
    payload: EditRevisionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Creates a new revision via PATCH; invalidates any approved revision (Y-11)."""
    return _edit_revision_impl(revision_id, payload, current_user, db)


@router.post("/{revision_id}/request-changes", response_model=RequestChangesResponse)
def request_changes_on_revision(
    revision_id: str,
    payload: RequestChangesPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Transitions a revision to changes_requested with audit logging (Y-11)."""
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A non-empty reason is required when requesting changes",
        )
    if current_user.role not in APPROVER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{current_user.role}' cannot request changes",
        )

    tenant_id = current_user.tenant_id
    revision = (
        db.query(Revision)
        .filter(Revision.id == revision_id, Revision.tenant_id == tenant_id)
        .first()
    )
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Revision '{revision_id}' not found",
        )

    revision.status = "changes_requested"
    revision.approval_status = "changes_requested"
    append_audit_log(
        db=db,
        tenant_id=tenant_id,
        entity_type="revision",
        entity_id=revision.id,
        action="revision.changes_requested",
        payload={
            "requested_by": current_user.id,
            "reason": payload.reason.strip(),
            "comment": payload.comment,
        },
    )
    db.commit()

    return RequestChangesResponse(
        revision_id=revision.id,
        status=revision.status,
        approval_status=revision.approval_status,
        requested_by=current_user.id,
        reason=payload.reason.strip(),
    )
