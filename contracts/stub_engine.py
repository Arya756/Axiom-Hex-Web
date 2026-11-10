"""Stub engine for Axiom (BrandLedger).

Returns fixture findings that satisfy the contracts in models.py.
Used by Yash's platform before the real engine (Issue #4) is built.
"""

from __future__ import annotations

import uuid
from typing import Any, List

from contracts.models import (
    ContentUnit,
    DisclosureRecord,
    Evidence,
    Finding,
    FindingSeverity,
    FindingStatus,
    FindingType,
    Method,
    ReviewResult,
    RunProgress,
    RunNodeStatus,
    Sensitivity,
    SuggestedFix,
)


def _fixture_finding(unit: ContentUnit, revision_id: str) -> Finding:
    """A single fixture finding used by the stub engine."""
    return Finding(
        finding_id=f"f_{uuid.uuid4().hex[:6]}",
        type=FindingType.terminology,
        severity=FindingSeverity.medium,
        confidence=0.9,
        span={
            "unit_id": unit.unit_id,
            "start": unit.start,
            "end": unit.end,
            "quote": unit.text[:60],
        },
        evidence=[
            Evidence(
                source="R-01",
                version=1,
                status="active",
                current_version=1,
                current_value=None,
                effective=None,
            )
        ],
        explanation="Stub finding: this is a placeholder emitted by the stub engine.",
        suggested_fix=SuggestedFix(
            text=unit.text,
            edit_budget="minimal",
            rechecked=False,
            intent_similarity=None,
        ),
        route_to="creator",
        disclosure=DisclosureRecord(
            method=Method.deterministic_lookup,
            provider=None,
            model=None,
            external_call=False,
            data_categories=["text"],
            sensitivity=Sensitivity.internal,
            tokens=None,
            cost=None,
            latency_ms=1,
        ),
        status=FindingStatus.open,
    )


def run_review(
    revision_units: List[ContentUnit],
    ruleset_version: int,
    session: Any = None,
    policy: Any = None,
    intent_card: Any = None,
) -> ReviewResult:
    """Stub engine entrypoint (T1). Returns fixture findings for every unit."""
    from typing import Any as _Any

    findings: List[Finding] = [_fixture_finding(u, u.revision_id) for u in revision_units]

    progress = [
        RunProgress(node="router", status=RunNodeStatus.done),
        RunProgress(node="terminology", status=RunNodeStatus.done),
        RunProgress(node="aggregator", status=RunNodeStatus.done),
    ]

    return ReviewResult(
        revision_id=revision_units[0].revision_id if revision_units else "rev_stub",
        ruleset_version=ruleset_version,
        sensitivity=Sensitivity.internal,
        findings=findings,
        matched_sources=["R-01"],
        run_progress=progress,
        disclosures=[],
        partial=False,
        cache_key=None,
    )


def recheck_fix(unit: ContentUnit, edited_text: str) -> bool:
    """Stub fix re-check (T9). Always accepts."""
    return True