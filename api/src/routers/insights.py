"""Governance analytics & Ambiguity Radar API endpoints (Y-21, Y-22, Y-23, I3)."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.src.auth.dependencies import get_current_user, get_db
from api.src.models.user import User
from api.src.services.analytics import (
    get_ambiguity_radar,
    get_impact_analysis,
    get_recurring_insights,
)

router = APIRouter(tags=["insights"])


class RadarSignalMetrics(BaseModel):
    total_findings: int
    accepted_count: int
    overridden_count: int
    disputed_count: int
    abstained_count: int
    low_confidence_count: int
    disagreement_count: int
    collision_count: int
    collisions: List[str] = []
    lint_flags: List[str] = []
    missing_owner: bool = False
    missing_examples: bool = False
    synthetic_count: int = 0
    live_count: int = 0
    override_dispute_rate: float
    abstain_rate: float
    low_confidence_rate: float
    disagreement_rate: float


class RadarExampleDecision(BaseModel):
    action: str
    user_id: str
    reason: Optional[str] = None


class RadarExampleFinding(BaseModel):
    finding_id: str
    revision_id: str
    type: str
    severity: str
    confidence: float
    abstained: bool
    status: str
    quote: str = ""
    explanation: str
    is_synthetic: bool = False
    decisions: List[RadarExampleDecision] = []


class RadarRuleEntry(BaseModel):
    rule_id: str
    rule_name: str
    rule_body: str = ""
    current_version: int = 1
    flagged: bool
    ambiguity_score: float
    flag_reasons: List[str] = []
    is_control: bool = False
    is_synthetic: bool = False
    data_origin: str = "live"
    signals: RadarSignalMetrics
    example_findings: List[RadarExampleFinding] = []


class RadarSummaryResponse(BaseModel):
    total_rules_evaluated: int
    flagged_count: int
    seeded_ambiguous_flagged_count: int
    seeded_ambiguous_total: int
    control_rules_evaluated: int
    false_flags: int
    false_flagged_rule_ids: List[str] = []
    false_flag_rate: float
    total_synthetic_findings: int
    total_live_findings: int
    contains_synthetic: bool
    data_origin: str


class RadarResponse(BaseModel):
    tenant_id: str
    summary: RadarSummaryResponse
    thresholds: Dict[str, Any]
    rules: List[RadarRuleEntry]


class ImpactItemResponse(BaseModel):
    content_id: str
    title: str
    file_type: str
    revision_id: str
    version_num: int
    revision_status: str
    approval_status: str
    sensitivity: str
    latest_run_id: str
    latest_run_status: str
    matched_via: str
    findings_for_source_count: int
    last_checked_at: datetime


class ImpactAnalysisResponse(BaseModel):
    source_id: str
    source_name: Optional[str] = None
    source_kind: Optional[str] = None
    current_version: Optional[int] = None
    affected_count: int
    affected_items: List[ImpactItemResponse]


@router.get("/insights/radar", response_model=RadarResponse)
def read_ambiguity_radar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns Guideline Ambiguity Radar signals from rule_stats, collisions, and decisions (Y-21, I3)."""
    return get_ambiguity_radar(db, current_user.tenant_id)


@router.get("/radar", response_model=RadarResponse)
def read_ambiguity_radar_alias(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Alias for GET /insights/radar."""
    return get_ambiguity_radar(db, current_user.tenant_id)


@router.get("/impact", response_model=ImpactAnalysisResponse)
def read_impact_analysis(
    source_id: str = Query(..., description="Source ID (rule, fact, glossary, palette) to inspect"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists draft and in-review items whose latest review run referenced source_id (Y-22, I3.3, I3.4)."""
    return get_impact_analysis(db, current_user.tenant_id, source_id.strip())


@router.get("/insights/recurring")
def read_recurring_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregates recurring workflow violations, types, severities, and document hotspots (Y-23)."""
    return get_recurring_insights(db, current_user.tenant_id)

