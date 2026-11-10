"""Test suite for Issue #6 (A3 — Terminology checker + Temporal Fact Ledger, G1).

Verifies:
1. A-08 Terminology Checker:
   - Banned terms detection (MFP, the platform, brand policing, etc.)
   - Product-name casing rules (meridian flow -> Meridian Flow)
   - Platform terminology casing rules (knowledge base, intent card, etc.)
   - Fix suggestion generation and span alignment
2. A-09 Temporal Fact Ledger:
   - Deterministic claim extraction (numbers with units, superlatives, compliance assertions)
   - Normalisation of values ("10k" -> "10,000+", "customers" vs "accounts")
   - Outdated claim detection citing old version and current active version
   - Special case: explicit past period inside validity window = Supported
   - Contradicted claims detection
   - Unsupported claims with epistemic copy rule
   - Guardrail: systemic retrieval failure marks checker partial/failed, NEVER false Unsupported
   - Stale-claim recall >= 85%
3. Citation Verifier:
   - Anti-hallucination verification, verbatim quote checking
   - Drops invalid/fabricated citations and reports verifier drop rate
"""

from __future__ import annotations

import pytest

from contracts.models import (
    ContentUnit,
    DisclosureRecord,
    Evidence,
    Finding,
    FindingSeverity,
    FindingStatus,
    FindingType,
    Method,
    Sensitivity,
    Span,
)
from engine.fact_ledger import ExtractedClaim, RetrievalFailureError, TemporalFactLedger
from engine.parsers import parse_markdown, parse_text
from engine.pipeline import ReviewState, run_review
from engine.terminology import TerminologyChecker
from engine.verifier import CitationVerifier


# ---------------------------------------------------------------------------
# 1. A-08 Terminology Checker Tests
# ---------------------------------------------------------------------------


def test_terminology_banned_terms():
    """Detects banned terms and generates compliant SuggestedFix."""
    checker = TerminologyChecker()
    units = parse_text("Teams using MFP report automated brand policing in their daily review run.")
    findings, sources = checker.check_units(units)

    # Should detect "MFP" and "brand policing"
    banned_quotes = [f.span.quote for f in findings]
    assert "MFP" in banned_quotes
    assert "brand policing" in banned_quotes

    mfp_finding = next(f for f in findings if f.span.quote == "MFP")
    assert mfp_finding.type == FindingType.terminology
    assert mfp_finding.severity == FindingSeverity.medium
    assert mfp_finding.suggested_fix is not None
    assert mfp_finding.suggested_fix.text == "Meridian Flow"
    assert mfp_finding.route_to == "creator"
    assert "G-01" in [e.source for e in mfp_finding.evidence]


def test_terminology_product_name_casing():
    """Detects lowercase or improper casing of Meridian Flow and platform terms."""
    checker = TerminologyChecker()
    raw = (
        "Welcome to meridian flow. Review your intent card and check the "
        "knowledge base before submitting to the temporal fact ledger."
    )
    units = parse_text(raw)
    findings, sources = checker.check_units(units)

    quotes = [f.span.quote.lower() for f in findings]
    assert "meridian flow" in quotes
    assert "intent card" in quotes
    assert "knowledge base" in quotes
    assert "temporal fact ledger" in quotes

    # Check suggested fixes have proper title case
    for f in findings:
        if f.span.quote.lower() == "meridian flow":
            assert f.suggested_fix.text == "Meridian Flow"
        elif f.span.quote.lower() == "intent card":
            assert f.suggested_fix.text == "Intent Card"
        elif f.span.quote.lower() == "knowledge base":
            assert f.suggested_fix.text == "Knowledge Base"


def test_terminology_canonical_preferred_terms_not_flagged():
    """Properly cased canonical terms must never trigger false-positive findings."""
    checker = TerminologyChecker()
    clean = "Meridian Flow provides an Intent Card, a Knowledge Base, and a Temporal Fact Ledger."
    units = parse_text(clean)
    findings, sources = checker.check_units(units)
    assert len(findings) == 0, f"Unexpected false positives: {[f.span.quote for f in findings]}"


# ---------------------------------------------------------------------------
# 2. A-09 Temporal Fact Ledger Tests
# ---------------------------------------------------------------------------


def test_fact_ledger_claim_extraction_and_normalisation():
    """Extracts and normalises 10k vs 10,000, and customers vs accounts."""
    ledger = TemporalFactLedger()

    # Test "10k accounts"
    u1 = ContentUnit(
        unit_id="u_01",
        revision_id="rev_1",
        kind="paragraph",
        text="Over 10k accounts rely on our infrastructure.",
        start=0,
        end=45,
    )
    claims1 = ledger.extract_claims(u1)
    assert len(claims1) == 1
    assert claims1[0].subject == "customers"
    assert claims1[0].normalized_value == "10,000+"

    # Test "25,000+ customers"
    u2 = ContentUnit(
        unit_id="u_02",
        revision_id="rev_1",
        kind="paragraph",
        text="Serving more than 25,000+ customers globally.",
        start=0,
        end=45,
    )
    claims2 = ledger.extract_claims(u2)
    assert len(claims2) == 1
    assert claims2[0].subject == "customers"
    assert claims2[0].normalized_value == "25,000+"

    # Test "99.9% uptime" and "$299/month"
    u3 = ContentUnit(
        unit_id="u_03",
        revision_id="rev_1",
        kind="paragraph",
        text="Guaranteed 99.9% uptime starting at $299/month.",
        start=0,
        end=47,
    )
    claims3 = ledger.extract_claims(u3)
    subjects = [c.subject for c in claims3]
    assert "uptime" in subjects
    assert "pricing" in subjects


def test_fact_ledger_outdated_claim_both_versions_cited():
    """Seeded stale claim flagged Outdated with both old and current versions cited."""
    ledger = TemporalFactLedger()
    unit = ContentUnit(
        unit_id="u_stale",
        revision_id="rev_stale",
        kind="paragraph",
        text="Meridian Flow proudly serves 10,000+ customers worldwide.",
        start=0,
        end=58,
    )
    findings, sources = ledger.check_units([unit])
    assert len(findings) == 1
    f = findings[0]

    assert f.type == FindingType.outdated
    assert f.severity == FindingSeverity.high
    assert f.span.quote == "10,000+ customers"
    assert f.route_to == "legal_reviewer"

    # Evidence must cite BOTH old superseded version (v1) and current active version (v3)
    assert len(f.evidence) >= 1
    ev = f.evidence[0]
    assert ev.source == "F-112"
    assert ev.version == 1  # Old version
    assert ev.status == "superseded"
    assert ev.current_version == 3  # Current active version
    assert ev.current_value == "25,000+" or "25,000+ customers" in str(ev.current_value)

    assert f.suggested_fix is not None
    assert "25,000+" in f.suggested_fix.text


def test_fact_ledger_supported_active_version_no_finding():
    """Claim matching the active version is Supported (no finding, source recorded)."""
    ledger = TemporalFactLedger()
    unit = ContentUnit(
        unit_id="u_act",
        revision_id="rev_act",
        kind="paragraph",
        text="Over 25,000+ customers trust Meridian Flow with 99.95% uptime.",
        start=0,
        end=62,
    )
    findings, sources = ledger.check_units([unit])
    assert len(findings) == 0, f"Expected 0 findings for active version, got {findings}"
    assert "F-112" in sources
    assert "F-108" in sources


def test_fact_ledger_explicit_past_period_supported():
    """Special case (PRD I1.3): Claim with explicit past period inside validity window = Supported."""
    ledger = TemporalFactLedger()
    # F-112 v1 (10,000+) was valid from 2023-01-01 to 2024-06-30
    unit = ContentUnit(
        unit_id="u_hist",
        revision_id="rev_hist",
        kind="paragraph",
        text="In 2023, Meridian Flow supported over 10,000+ customers.",
        start=0,
        end=56,
    )
    findings, sources = ledger.check_units([unit])
    # Must NOT emit Outdated or Contradicted finding because explicit period matches validity window!
    assert len(findings) == 0, f"Expected Supported (no finding), but got: {findings}"
    assert "F-112" in sources


def test_fact_ledger_contradicted_claim():
    """Known metric with an unapproved value is classified Contradicted."""
    ledger = TemporalFactLedger()
    unit = ContentUnit(
        unit_id="u_contra",
        revision_id="rev_contra",
        kind="paragraph",
        text="Meridian Flow offers 99.5% uptime across regions.",
        start=0,
        end=49,
    )
    findings, sources = ledger.check_units([unit])
    assert len(findings) == 1
    f = findings[0]
    assert f.type == FindingType.contradicted
    assert f.route_to == "legal_reviewer"
    assert "F-108" in [e.source for e in f.evidence]
    assert f.suggested_fix is not None
    assert "99.95%" in f.suggested_fix.text


def test_fact_ledger_unsupported_superlative_epistemic_copy():
    """Unsubstantiated superlative flagged Unsupported with exact epistemic copy rule."""
    ledger = TemporalFactLedger()
    unit = ContentUnit(
        unit_id="u_unsup",
        revision_id="rev_unsup",
        kind="paragraph",
        text="Meridian Flow is the #1 compliance platform on the market.",
        start=0,
        end=58,
    )
    findings, sources = ledger.check_units([unit])
    assert len(findings) == 1
    f = findings[0]
    assert f.type == FindingType.unsupported
    assert f.route_to == "legal_reviewer"
    # PRD I1.6 epistemic copy rule:
    expected_copy = "No substantiation found within approved tenant sources (searched top-k candidates)"
    assert expected_copy in f.explanation
    assert "factually false" not in f.explanation.lower()


def test_fact_ledger_retrieval_guardrail_never_false_unsupported():
    """Guardrail: If retrieval fails, mark checker partial/failed — NEVER emit false Unsupported."""
    # When simulate_retrieval_failure is enabled, run_review must NOT emit Unsupported
    units = parse_text("Meridian Flow is trusted by 10,000+ customers.", revision_id="rev_guard")
    result = run_review(
        revision_units=units,
        ruleset_version=1,
        simulate_retrieval_failure=True,
    )

    # Checker should be marked partial
    assert result.partial is True
    # Crucial guardrail check: MUST NOT emit any false Unsupported findings!
    unsupported_findings = [f for f in result.findings if f.type == FindingType.unsupported]
    assert len(unsupported_findings) == 0, "Guardrail breached: false Unsupported finding emitted!"

    # Run progress must visibly record the failure
    facts_progress = next(p for p in result.run_progress if p.node == "facts")
    assert facts_progress.status.value in ("failed", "partial")


def test_stale_claim_recall_above_85_percent():
    """I1 Acceptance: Stale-claim recall on seeded test set is >= 85% (at least 7/8)."""
    ledger = TemporalFactLedger()

    seeded_stale_test_items = [
        # (text, expected_source, expected_quote_snippet)
        ("Over 10,000+ customers use our platform.", "F-112", "10,000+"),
        ("Trusted by 10k accounts worldwide.", "F-112", "10k"),
        ("We serve 18,000+ customers today.", "F-112", "18,000+"),
        ("More than 18k clients rely on us.", "F-112", "18k"),
        ("Providing guaranteed 99.9% uptime SLA.", "F-108", "99.9%"),
        ("Industry-leading 99.9% availability guaranteed.", "F-108", "99.9%"),
        ("Our pricing starts at $299/month for teams.", "F-115", "$299/month"),
        ("Plans available from $299/mo with full support.", "F-115", "$299/mo"),
    ]

    detected = 0
    total = len(seeded_stale_test_items)

    for text, expected_src, expected_snippet in seeded_stale_test_items:
        unit = ContentUnit(
            unit_id=f"u_{detected}",
            revision_id="rev_recall",
            kind="paragraph",
            text=text,
            start=0,
            end=len(text),
        )
        findings, _ = ledger.check_units([unit])
        outdated = [f for f in findings if f.type == FindingType.outdated]

        if outdated and any(expected_snippet in f.span.quote for f in outdated):
            detected += 1

    recall = detected / total
    print(f"\n[EVAL] Stale-Claim Recall: {detected}/{total} ({recall:.1%})")
    assert recall >= 0.85, f"Recall {recall:.1%} fell below target 85% ({detected}/{total})"
    assert detected >= 7, f"Expected at least 7/8 detected, got {detected}/{total}"


# ---------------------------------------------------------------------------
# 3. Citation Verifier Tests (A-11, I1.5)
# ---------------------------------------------------------------------------


def test_citation_verifier_drops_hallucinated_citations():
    """Citation Verifier drops findings with invalid quotes or fake source IDs."""
    verifier = CitationVerifier()

    unit = ContentUnit(
        unit_id="u_ver",
        revision_id="rev_ver",
        kind="paragraph",
        text="Over 10,000+ customers trust Meridian Flow.",
        start=0,
        end=42,
    )

    # 1. Valid finding: should pass
    valid_finding = Finding(
        finding_id="f_valid",
        type=FindingType.outdated,
        severity=FindingSeverity.high,
        confidence=0.95,
        span=Span(unit_id="u_ver", start=5, end=22, quote="10,000+ customers"),
        evidence=[Evidence(source="F-112", version=1, status="superseded")],
        explanation="Valid finding",
        route_to="legal_reviewer",
        disclosure=DisclosureRecord(method=Method.deterministic_lookup, sensitivity=Sensitivity.internal),
    )
    passes, reason = verifier.verify_finding(valid_finding, unit)
    assert passes is True
    assert reason is None

    # 2. Fabricated source ID (e.g. prompt injection fake rule R-99@v4)
    forged_finding = Finding(
        finding_id="f_fake_src",
        type=FindingType.unsupported,
        severity=FindingSeverity.high,
        confidence=0.95,
        span=Span(unit_id="u_ver", start=5, end=22, quote="10,000+ customers"),
        evidence=[Evidence(source="R-99", version=4, status="active")],  # R-99 does not exist!
        explanation="Forged source citation",
        route_to="legal_reviewer",
        disclosure=DisclosureRecord(method=Method.deterministic_lookup, sensitivity=Sensitivity.internal),
    )
    passes, reason = verifier.verify_finding(forged_finding, unit)
    assert passes is False
    assert "does not resolve" in reason

    # 3. Altered quote not present in unit text
    altered_finding = Finding(
        finding_id="f_altered",
        type=FindingType.outdated,
        severity=FindingSeverity.high,
        confidence=0.95,
        span=Span(unit_id="u_ver", start=0, end=10, quote="nonexistent text"),
        evidence=[Evidence(source="F-112", version=1, status="superseded")],
        explanation="Altered quote",
        route_to="legal_reviewer",
        disclosure=DisclosureRecord(method=Method.deterministic_lookup, sensitivity=Sensitivity.internal),
    )
    passes, reason = verifier.verify_finding(altered_finding, unit)
    assert passes is False
    assert "does not exist verbatim" in reason


def test_citation_verifier_filter_and_drop_rate():
    """All shown findings pass verifier (true by construction); verifier drop rate reported."""
    verifier = CitationVerifier()
    unit = ContentUnit(
        unit_id="u_drop",
        revision_id="rev_drop",
        kind="paragraph",
        text="Over 10,000+ customers trust Meridian Flow.",
        start=0,
        end=42,
    )

    valid_f = Finding(
        finding_id="f_1",
        type=FindingType.outdated,
        severity=FindingSeverity.high,
        confidence=0.95,
        span=Span(unit_id="u_drop", start=5, end=22, quote="10,000+ customers"),
        evidence=[Evidence(source="F-112", version=1, status="superseded")],
        explanation="Valid",
        route_to="legal_reviewer",
        disclosure=DisclosureRecord(method=Method.deterministic_lookup, sensitivity=Sensitivity.internal),
    )
    fake_f = Finding(
        finding_id="f_2",
        type=FindingType.outdated,
        severity=FindingSeverity.high,
        confidence=0.95,
        span=Span(unit_id="u_drop", start=0, end=4, quote="Over"),
        evidence=[Evidence(source="FAKE-01", version=1, status="superseded")],
        explanation="Fake",
        route_to="legal_reviewer",
        disclosure=DisclosureRecord(method=Method.deterministic_lookup, sensitivity=Sensitivity.internal),
    )

    verified, dropped, drop_rate = verifier.filter_findings([valid_f, fake_f], {"u_drop": unit})
    assert len(verified) == 1
    assert verified[0].finding_id == "f_1"
    assert dropped == 1
    assert drop_rate == 0.5  # 1 dropped out of 2 = 50.0%
