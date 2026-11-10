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
                policy=Sensitivity(sensitivity_str),
                intent_card=intent_card_contract,
            )

            # 3. Only API writes workflow tables (T1 contract requirement)
            for f in result.findings:
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
                    route_to=f.route_to,
                    status=f.status.value,
                    abstained=f.abstained,
                    rule_id=f.rule_id,
                    disclosure_json=f.disclosure.model_dump() if f.disclosure else None,
                )
                db.add(finding_model)

            run.status = "partial" if result.partial else "done"
            run.partial = result.partial
            run.matched_sources = result.matched_sources
            run.run_progress = [p.model_dump(mode="json") for p in result.run_progress]
            run.finished_at = datetime.now(timezone.utc)
            revision.status = "in_review"
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns all findings for the given revision."""
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

    findings = (
        db.query(FindingModel)
        .filter(FindingModel.revision_id == revision_id, FindingModel.tenant_id == tenant_id)
        .all()
    )

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
