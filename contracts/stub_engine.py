"""Stub engine for Axiom (BrandLedger).

Returns fixture findings that satisfy the contracts in models.py.
Used by Yash's platform before the real engine (Issue #4) is built.
"""

from __future__ import annotations

import uuid
from typing import Any, List, Optional

from contracts.models import (
    CompileResult,
    ContentUnit,
    DisclosureRecord,
    Evidence,
    Finding,
    FindingSeverity,
    FindingStatus,
    FindingType,
    IntentCard,
    Method,
    ReviewResult,
    RunProgress,
    RunNodeStatus,
    Sensitivity,
    SourceVersion,
    Span,
    SuggestedFix,
)


def _fixture_finding(unit: ContentUnit, revision_id: str) -> Finding:
    """A single fixture finding used by the stub engine."""
    return Finding(
        finding_id=f"f_{uuid.uuid4().hex[:6]}",
        type=FindingType.terminology,
        severity=FindingSeverity.medium,
        confidence=0.9,
        span=Span(
            unit_id=unit.unit_id,
            start=unit.start,
            end=unit.end,
            quote=unit.text[:60],
        ),
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
        abstained=False,
        rule_id="R-01",
    )


def run_review(
    revision_units: List[ContentUnit],
    ruleset_version: int,
    session: Any = None,
    policy: Optional[Sensitivity] = None,
    intent_card: Optional[IntentCard] = None,
) -> ReviewResult:
    """Stub engine entrypoint (T1). Returns fixture findings for every unit."""
    findings: List[Finding] = [_fixture_finding(u, u.revision_id) for u in revision_units]

    progress = [
        RunProgress(node="router", status=RunNodeStatus.done),
        RunProgress(node="terminology", status=RunNodeStatus.done),
        RunProgress(node="aggregator", status=RunNodeStatus.done),
    ]

    return ReviewResult(
        revision_id=revision_units[0].revision_id if revision_units else "rev_stub",
        ruleset_version=ruleset_version,
        sensitivity=policy or Sensitivity.internal,
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


def compile(source_version: SourceVersion) -> CompileResult:
    """Stub guideline compiler (T5).

    Returns a dummy 384-dimensional embedding, empty lint flags, and collisions.
    """
    return CompileResult(
        source_id=source_version.source_id,
        version=source_version.version,
        embedding=[0.0] * 384,
        lint_flags=[],
        collisions=[],
    )
