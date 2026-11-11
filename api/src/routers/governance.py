"""Governance API endpoints: audit log query (Y-14), usage ledger & settings (Y-15)."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.src.auth.dependencies import get_current_user, get_db, require_admin
from api.src.models.content import Revision
from api.src.models.review import Comment, FindingModel, ReviewRun
from api.src.models.tenant import Tenant
from api.src.models.user import User
from api.src.models.workflow import AuditLog, UsageLedger
from api.src.services.governance import EXTERNAL_SERVICES_CATALOG, append_audit_log

router = APIRouter(tags=["governance"])


class AuditLogResponse(BaseModel):
    id: int
    tenant_id: str
    entity_type: str
    entity_id: str
    action: str
    payload: Dict[str, Any]
    prev_hash: str
    curr_hash: str
    timestamp: datetime


class UsageEntryResponse(BaseModel):
    id: str
    tenant_id: str
    run_id: Optional[str] = None
    node: str
    method: str
    provider: Optional[str] = None
    model: Optional[str] = None
    external_call: bool
    data_categories: List[str] = []
    sensitivity: str
    tokens: Optional[int] = 0
    cost: Optional[float] = 0.0
    latency_ms: Optional[int] = 0
    created_at: datetime


class UsageSummaryResponse(BaseModel):
    total_entries: int
    total_runs: int
    total_external_calls: int
    total_tokens: int
    total_cost: float
    total_latency_ms: int
    restricted_runs_external_calls: int


class UsageLedgerListResponse(BaseModel):
    summary: UsageSummaryResponse
    entries: List[UsageEntryResponse]


class ExternalServiceInfo(BaseModel):
    id: str
    name: str
    purpose: str
    data_sent: List[str]
    allowed_sensitivities: List[str]
    disabled_on_restricted: bool
    enabled: bool


class TenantSettingsResponse(BaseModel):
    tenant_id: str
    ruleset_version: int
    no_external_processing: bool
    external_services: List[ExternalServiceInfo]


class TenantSettingsUpdateRequest(BaseModel):
    no_external_processing: bool


def _related_entity_ids(db: Session, tenant_id: str, item: str) -> List[str]:
    """Collect entity IDs associated with a content_id or revision_id for GET /audit?item=."""
    ids = {item}
    rev_ids = [
        r.id
        for r in db.query(Revision.id)
        .filter(
            Revision.tenant_id == tenant_id,
            (Revision.content_id == item) | (Revision.id == item),
        )
        .all()
    ]
    ids.update(rev_ids)

    if rev_ids:
        finding_ids = [
            f.finding_id
            for f in db.query(FindingModel.finding_id)
            .filter(
                FindingModel.tenant_id == tenant_id,
                FindingModel.revision_id.in_(rev_ids),
            )
            .all()
        ]
        run_ids = [
            r.id
            for r in db.query(ReviewRun.id)
            .filter(
                ReviewRun.tenant_id == tenant_id,
                ReviewRun.revision_id.in_(rev_ids),
            )
            .all()
        ]
        comment_ids = [
            c.id
            for c in db.query(Comment.id)
            .filter(
                Comment.tenant_id == tenant_id,
                Comment.revision_id.in_(rev_ids),
            )
            .all()
        ]
        ids.update(finding_ids)
        ids.update(run_ids)
        ids.update(comment_ids)

    return list(ids)


@router.get("/audit", response_model=List[AuditLogResponse])
def list_audit_log(
    item: Optional[str] = Query(None, description="Filter audit events by item/entity id"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns hash-chained audit_log entries for the current tenant (Y-14)."""
    tenant_id = current_user.tenant_id
    query = db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id)
    if item:
        entity_ids = _related_entity_ids(db, tenant_id, item.strip())
        query = query.filter(AuditLog.entity_id.in_(entity_ids))

    rows = query.order_by(AuditLog.id.asc()).all()
    return [
        AuditLogResponse(
            id=r.id,
            tenant_id=r.tenant_id,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            action=r.action,
            payload=r.payload or {},
            prev_hash=r.prev_hash,
            curr_hash=r.curr_hash,
            timestamp=r.timestamp,
        )
        for r in rows
    ]


@router.get("/usage", response_model=UsageLedgerListResponse)
def list_usage_ledger(
    run_id: Optional[str] = Query(None),
    sensitivity: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns persisted UsageLedger telemetry records and aggregated summary (Y-15)."""
    tenant_id = current_user.tenant_id
    query = db.query(UsageLedger).filter(UsageLedger.tenant_id == tenant_id)
    if run_id:
        query = query.filter(UsageLedger.run_id == run_id.strip())
    if sensitivity:
        query = query.filter(UsageLedger.sensitivity == sensitivity.strip().lower())

    entries = query.order_by(UsageLedger.created_at.desc()).all()

    distinct_runs = {e.run_id for e in entries if e.run_id}
    summary = UsageSummaryResponse(
        total_entries=len(entries),
        total_runs=len(distinct_runs),
        total_external_calls=sum(1 for e in entries if e.external_call),
        total_tokens=sum(int(e.tokens or 0) for e in entries),
        total_cost=round(sum(float(e.cost or 0.0) for e in entries), 6),
        total_latency_ms=sum(int(e.latency_ms or 0) for e in entries),
        restricted_runs_external_calls=sum(
            1 for e in entries if e.sensitivity == "restricted" and e.external_call
        ),
    )

    return UsageLedgerListResponse(
        summary=summary,
        entries=[
            UsageEntryResponse(
                id=e.id,
                tenant_id=e.tenant_id,
                run_id=e.run_id,
                node=e.node,
                method=e.method,
                provider=e.provider,
                model=e.model,
                external_call=e.external_call,
                data_categories=e.data_categories or [],
                sensitivity=e.sensitivity,
                tokens=e.tokens or 0,
                cost=e.cost or 0.0,
                latency_ms=e.latency_ms or 0,
                created_at=e.created_at,
            )
            for e in entries
        ],
    )


def _build_settings_response(tenant: Tenant) -> TenantSettingsResponse:
    services = [
        ExternalServiceInfo(
            **svc,
            enabled=(not tenant.no_external_processing) or (not svc["disabled_on_restricted"]),
        )
        for svc in EXTERNAL_SERVICES_CATALOG
    ]
    return TenantSettingsResponse(
        tenant_id=tenant.id,
        ruleset_version=tenant.ruleset_version,
        no_external_processing=tenant.no_external_processing,
        external_services=services,
    )


@router.get("/settings", response_model=TenantSettingsResponse)
def get_tenant_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns configured external services and no_external_processing switch state (Y-15)."""
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{current_user.tenant_id}' not found",
        )
    return _build_settings_response(tenant)


def _update_tenant_settings(
    payload: TenantSettingsUpdateRequest,
    current_user: User,
    db: Session,
) -> TenantSettingsResponse:
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{current_user.tenant_id}' not found",
        )

    previous_val = bool(tenant.no_external_processing)
    tenant.no_external_processing = payload.no_external_processing

    append_audit_log(
        db=db,
        tenant_id=tenant.id,
        entity_type="tenant",
        entity_id=tenant.id,
        action="settings.updated",
        payload={
            "previous_no_external_processing": previous_val,
            "no_external_processing": payload.no_external_processing,
            "updated_by": current_user.id,
        },
    )
    db.commit()
    return _build_settings_response(tenant)


@router.put("/settings", response_model=TenantSettingsResponse)
def put_tenant_settings(
    payload: TenantSettingsUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Persists the no_external_processing switch (admin only, Y-15)."""
    return _update_tenant_settings(payload, current_user, db)


@router.patch("/settings", response_model=TenantSettingsResponse)
def patch_tenant_settings(
    payload: TenantSettingsUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Updates the no_external_processing switch via PATCH (admin only, Y-15)."""
    return _update_tenant_settings(payload, current_user, db)

