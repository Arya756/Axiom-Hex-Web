from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.src.auth.dependencies import get_current_user, get_db
from api.src.models.review import FindingDecision, FindingModel
from api.src.models.user import User
from api.src.services.analytics import sync_rule_stat_for_decision
from api.src.services.governance import append_audit_log

router = APIRouter(prefix="/findings", tags=["findings"])

VALID_ACTIONS = {"accept", "reject", "override", "dispute"}
STATUS_MAP = {
    "accept": "accepted",
    "reject": "rejected",
    "override": "overridden",
    "dispute": "disputed",
}


class DecisionCreateRequest(BaseModel):
    action: str  # accept, reject, override, dispute
    reason: Optional[str] = None


class DecisionResponse(BaseModel):
    id: str
    finding_id: str
    user_id: str
    action: str
    reason: Optional[str] = None
    finding_status: str
    created_at: datetime


@router.post("/{finding_id}/decision", response_model=DecisionResponse, status_code=status.HTTP_201_CREATED)
def record_finding_decision(
    finding_id: str,
    payload: DecisionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Records a finding decision (accept, reject, override, dispute).
    
    Enforces written reason on override/dispute and prevents duplicate decisions on retry.
    """
    tenant_id = current_user.tenant_id
    action_lower = payload.action.lower()

    if action_lower not in VALID_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid action '{payload.action}'. Allowed actions: {sorted(list(VALID_ACTIONS))}",
        )

    # Enforce mandatory written reason for override and dispute (PRD §4.2 Y-09 & §5.3)
    if action_lower in {"override", "dispute"}:
        if not payload.reason or not payload.reason.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"A written reason is mandatory for '{action_lower}' decisions.",
            )

    finding = (
        db.query(FindingModel)
        .filter(FindingModel.finding_id == finding_id, FindingModel.tenant_id == tenant_id)
        .first()
    )
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding '{finding_id}' not found",
        )

    # Idempotency check: prevent duplicate decisions from double-clicks or retries
    existing_decision = (
        db.query(FindingDecision)
        .filter(
            FindingDecision.tenant_id == tenant_id,
            FindingDecision.finding_id == finding_id,
            FindingDecision.user_id == current_user.id,
            FindingDecision.action == action_lower,
        )
        .order_by(FindingDecision.created_at.desc())
        .first()
    )
    if existing_decision:
        return DecisionResponse(
            id=existing_decision.id,
            finding_id=existing_decision.finding_id,
            user_id=existing_decision.user_id,
            action=existing_decision.action,
            reason=existing_decision.reason,
            finding_status=finding.status,
            created_at=existing_decision.created_at,
        )

    # Create new decision and update finding status
    decision_id = f"dec_{uuid.uuid4().hex[:8]}"
    new_status = STATUS_MAP[action_lower]
    finding.status = new_status

    decision = FindingDecision(
        id=decision_id,
        tenant_id=tenant_id,
        finding_id=finding_id,
        user_id=current_user.id,
        action=action_lower,
        reason=payload.reason.strip() if payload.reason else None,
    )
    db.add(decision)
    sync_rule_stat_for_decision(db, tenant_id, finding, action_lower)
    append_audit_log(
        db=db,
        tenant_id=tenant_id,
        entity_type="finding",
        entity_id=finding_id,
        action=f"finding.{action_lower}",
        payload={
            "decision_id": decision_id,
            "revision_id": finding.revision_id,
            "user_id": current_user.id,
            "action": action_lower,
            "reason": decision.reason,
            "new_status": new_status,
        },
    )
    db.commit()

    return DecisionResponse(
        id=decision.id,
        finding_id=decision.finding_id,
        user_id=decision.user_id,
        action=decision.action,
        reason=decision.reason,
        finding_status=finding.status,
        created_at=decision.created_at,
    )


@router.get("/queue")
def get_finding_queue(
    role: Optional[str] = None,
    finding_status: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns findings routed to a reviewer role queue (Y-12)."""
    tenant_id = current_user.tenant_id
    target_role = (role or current_user.role).strip()
    query = db.query(FindingModel).filter(
        FindingModel.tenant_id == tenant_id,
        FindingModel.route_to == target_role,
    )
    if finding_status:
        query = query.filter(FindingModel.status == finding_status)

    findings = query.order_by(FindingModel.created_at.desc()).all()
    return [
        {
            "finding_id": f.finding_id,
            "revision_id": f.revision_id,
            "run_id": f.run_id,
            "type": f.type,
            "severity": f.severity,
            "confidence": f.confidence,
            "explanation": f.explanation,
            "route_to": f.route_to,
            "status": f.status,
            "abstained": f.abstained,
            "created_at": f.created_at,
        }
        for f in findings
    ]


@router.get("/{finding_id}")
def get_finding(
    finding_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves finding details and associated decisions."""
    tenant_id = current_user.tenant_id
    finding = (
        db.query(FindingModel)
        .filter(FindingModel.finding_id == finding_id, FindingModel.tenant_id == tenant_id)
        .first()
    )
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding '{finding_id}' not found",
        )
    decisions = (
        db.query(FindingDecision)
        .filter(FindingDecision.finding_id == finding_id, FindingDecision.tenant_id == tenant_id)
        .all()
    )
    return {
        "finding_id": finding.finding_id,
        "revision_id": finding.revision_id,
        "type": finding.type,
        "severity": finding.severity,
        "confidence": finding.confidence,
        "span": finding.span_json,
        "explanation": finding.explanation,
        "route_to": finding.route_to,
        "status": finding.status,
        "decisions": [
            {
                "id": d.id,
                "user_id": d.user_id,
                "action": d.action,
                "reason": d.reason,
                "created_at": d.created_at,
            }
            for d in decisions
        ],
    }

