"""Test suite for Issue #8 (A4 — Hybrid retrieval + Citation Verifier, G2).

Verifies:
1. A-10 Hybrid Retrieval:
   - BM25 (rank_bm25) lexical retrieval
   - Vector exact KNN (no ANN; full recall)
   - Reciprocal Rank Fusion (RRF, k=60)
   - Tenant-scoped query filtering
   - Retrieval trace formatting
2. A-11 Citation Verifier Node (G2):
   - Verbatim quote & offset consistency
   - Real source_id@version resolution (e.g. drops F-112@v99)
   - Numerical comparison recomputation (drops false outdated findings)
   - Failures dropped and counted in run metrics (drop rate reported)
   - All shown findings pass verifier (true by construction)
   - Hybrid retrieval trace embedded in Unsupported receipt
   - Epistemic copy rule: "No substantiation found within approved tenant sources (searched top-k candidates)"
3. A-12 Abstain / route_to Rule:
   - Findings that cannot be verified / ambiguous rules -> Needs judgment (abstained=True)
   - route_to by finding type (R1 §2.5)
   - Matched sources recorded for every run, including Supported claims
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
from engine.abstain import AbstainRouter, apply_needs_judgment, process_findings, route_to_for_type
from engine.parsers import parse_markdown, parse_text
from engine.pipeline import ReviewState, run_review
from engine.retrieval import (
    HybridRetriever,
    RetrievalHit,
    SourceRecord,
    get_default_retriever,
)
from engine.verifier import CitationVerifier


# ---------------------------------------------------------------------------
# 1. A-10 Hybrid Retrieval Tests
# ---------------------------------------------------------------------------


def test_hybrid_retrieval_bm25_vector_and_rrf():
    """Hybrid retrieval executes BM25, exact vector KNN, and RRF (k=60) fusion."""
    retriever = HybridRetriever()
    tenant = "tenant_test"

    retriever.add_source(SourceRecord(
        source_id="F-112",
        version=3,
        tenant_id=tenant,
        kind="fact",
        body="customers: 25,000+ active customers across enterprise (valid from 2025-03-01)",
    ))
    retriever.add_source(SourceRecord(
        source_id="F-108",
        version=2,
        tenant_id=tenant,
        kind="fact",
        body="uptime: 99.95% production SLA availability (valid from 2025-01-01)",
    ))
    retriever.add_source(SourceRecord(
        source_id="R-01",
        version=1,
        tenant_id=tenant,
        kind="rule",
        body="Always refer to the product by its proper casing: Meridian Flow.",
    ))

    result = retriever.query("25,000 customers uptime", tenant_id=tenant, top_k=3)
    assert len(result.hits) >= 2
    top_hit = result.hits[0]
    # F-112 should be top or top-2 because it matches "25,000 customers"
    hit_ids = [h.source_id for h in result.hits]
    assert "F-112" in hit_ids
    assert "F-108" in hit_ids

    # RRF score should be positive and bounded by 2 / (60 + 1) ~ 0.0328
    assert 0.0 < top_hit.rrf_score <= 2.0 / 61.0
    # Retrieval trace should contain source and rank info
    assert "F-" in top_hit.trace
    assert "rrf=" in top_hit.trace


def test_hybrid_retrieval_tenant_isolation():
    """Queries return only records belonging to the requested tenant."""
    retriever = HybridRetriever()

    # Tenant A
    retriever.add_source(SourceRecord(
        source_id="F-112",
        version=3,
        tenant_id="tenant_meridian",
        kind="fact",
        body="Meridian Flow 25,000+ customers",
    ))
    # Tenant B
    retriever.add_source(SourceRecord(
        source_id="F-ACME-01",
        version=1,
        tenant_id="tenant_acme",
        kind="fact",
        body="Acme Corp 500 widgets",
    ))

    # Query for Meridian should NEVER return Acme
    meridian_res = retriever.query("customers widgets", tenant_id="tenant_meridian")
    assert all(h.source_id != "F-ACME-01" for h in meridian_res.hits)
    assert any(h.source_id == "F-112" for h in meridian_res.hits)

    # Query for Acme should NEVER return Meridian
    acme_res = retriever.query("customers widgets", tenant_id="tenant_acme")
    assert all(h.source_id != "F-112" for h in acme_res.hits)
    assert any(h.source_id == "F-ACME-01" for h in acme_res.hits)


def test_hybrid_retrieval_trace_formatting():
    """RetrievalResult formats human-readable trace lines and summaries."""
    retriever = get_default_retriever()
    res = retriever.query("compliance platform uptime", tenant_id="tenant_meridian", top_k=3)

    assert res.hits
    summary = res.trace_summary
    assert "tenant_meridian" in summary
    assert "rrf=" in summary
    trace_lines = res.trace_lines
    assert len(trace_lines) == len(res.hits[:3])
    for line in trace_lines:
        assert "@v" in line
        assert "rrf=" in line


# ---------------------------------------------------------------------------
# 2. A-11 Citation Verifier Tests
# ---------------------------------------------------------------------------


def test_citation_verifier_drops_fabricated_source_version():
    """Verifier drops findings citing nonexistent source versions (e.g. F-112@v99)."""
    verifier = CitationVerifier()
    unit = ContentUnit(
        unit_id="u_fake_ver",
        revision_id="rev_ver",
        kind="paragraph",
        text="We serve 10,000+ customers globally.",
        start=0,
        end=36,
    )

    fake_ver_finding = Finding(
        finding_id="f_fake_ver",
        type=FindingType.outdated,
        severity=FindingSeverity.high,
        confidence=0.95,
        span=Span(unit_id="u_fake_ver", start=9, end=26, quote="10,000+ customers"),
        evidence=[Evidence(source="F-112", version=99, status="superseded")],  # v99 is fake
        explanation="Fake version test",
        route_to="legal_reviewer",
        disclosure=DisclosureRecord(method=Method.deterministic_lookup, sensitivity=Sensitivity.internal),
    )

    passes, reason = verifier.verify_finding(fake_ver_finding, unit)
    assert passes is False
    assert "does not resolve to a real knowledge base version" in reason


def test_citation_verifier_recomputes_numerical_comparison():
    """Verifier recomputes numerical comparison and drops false outdated findings."""
    verifier = CitationVerifier()
    unit = ContentUnit(
        unit_id="u_num_rec",
        revision_id="rev_num",
        kind="paragraph",
        text="We currently serve 25,000+ customers globally.",
        start=0,
        end=46,
    )

    # Finding falsely claims that "25,000+ customers" is outdated when it matches current_value
    false_outdated = Finding(
        finding_id="f_false_outdated",
        type=FindingType.outdated,
        severity=FindingSeverity.high,
        confidence=0.95,
        span=Span(unit_id="u_num_rec", start=19, end=36, quote="25,000+ customers"),
        evidence=[
            Evidence(
                source="F-112",
                version=1,
                status="superseded",
                current_version=3,
                current_value="25,000+",
            )
        ],
        explanation="Falsely claims current value is outdated",
        route_to="legal_reviewer",
        disclosure=DisclosureRecord(method=Method.deterministic_lookup, sensitivity=Sensitivity.internal),
    )

    passes, reason = verifier.verify_finding(false_outdated, unit)
    assert passes is False
    assert "already matches current active value" in reason


def test_citation_verifier_all_shown_pass_and_drop_rate():
    """All verified findings pass verifier (true by construction); drop rate reported."""
    verifier = CitationVerifier()
    unit = ContentUnit(
        unit_id="u_drop_test",
        revision_id="rev_drop",
        kind="paragraph",
        text="Over 10,000+ customers trust Meridian Flow with 99.9% uptime.",
        start=0,
        end=62,
    )

    legit = Finding(
        finding_id="f_legit",
        type=FindingType.outdated,
        severity=FindingSeverity.high,
        confidence=0.95,
        span=Span(unit_id="u_drop_test", start=5, end=22, quote="10,000+ customers"),
        evidence=[Evidence(source="F-112", version=1, status="superseded", current_version=3, current_value="25,000+")],
        explanation="Valid outdated finding",
        route_to="legal_reviewer",
        disclosure=DisclosureRecord(method=Method.deterministic_lookup, sensitivity=Sensitivity.internal),
    )
    fake_quote = Finding(
        finding_id="f_bad_quote",
        type=FindingType.outdated,
        severity=FindingSeverity.high,
        confidence=0.95,
        span=Span(unit_id="u_drop_test", start=0, end=10, quote="NONEXISTENT QUOTE"),
        evidence=[Evidence(source="F-112", version=1, status="superseded")],
        explanation="Bad quote",
        route_to="legal_reviewer",
        disclosure=DisclosureRecord(method=Method.deterministic_lookup, sensitivity=Sensitivity.internal),
    )

    verified, drops, drop_rate = verifier.filter_findings([legit, fake_quote], {unit.unit_id: unit})
    assert len(verified) == 1
    assert verified[0].finding_id == "f_legit"
    assert drops == 1
    assert drop_rate == 0.5

    # True by construction: every verified finding passes verification
    for vf in verified:
        p, _ = verifier.verify_finding(vf, unit)
        assert p is True


def test_retrieval_trace_in_unsupported_receipt():
    """Unsupported findings are enriched with retrieval trace and adhere to epistemic copy rule."""
    doc = "Meridian Flow is the #1 compliance platform on the planet."
    units = parse_markdown(doc)
    result = run_review(revision_units=units, policy=Sensitivity.internal)

    unsupported_findings = [f for f in result.findings if f.type == FindingType.unsupported]
    assert len(unsupported_findings) >= 1

    unsup = unsupported_findings[0]
    # 1. Epistemic copy rule strictly enforced
    assert "No substantiation found within approved tenant sources (searched top-k candidates)" in unsup.explanation
    # Never asserts factually false
    assert "factually false" not in unsup.explanation.lower()
    # 2. Retrieval trace visible in receipt
    assert "Retrieval trace:" in unsup.explanation
    # 3. Disclosure method updated to hybrid_retrieval
    assert unsup.disclosure.method == Method.hybrid_retrieval


# ---------------------------------------------------------------------------
# 3. A-12 Abstain / route_to Rule Tests
# ---------------------------------------------------------------------------


def test_route_to_by_finding_type():
    """Findings are routed to role queues according to R1 §2.5."""
    assert route_to_for_type("terminology") == "creator"
    assert route_to_for_type("tone") == "creator"
    assert route_to_for_type("visual") == "creator"
    assert route_to_for_type("accessibility") == "creator"
    assert route_to_for_type("outdated") == "legal_reviewer"
    assert route_to_for_type("contradicted") == "legal_reviewer"
    assert route_to_for_type("unsupported") == "legal_reviewer"


def test_abstain_rule_tags_ambiguous_rules_needs_judgment():
    """Findings referencing ambiguous rules (R-07, R-11, R-14, R-17) get abstained=True and route to reviewer."""
    router = AbstainRouter()
    ambiguous_set = {"R-07", "R-11", "R-14", "R-17"}

    ambiguous_finding = Finding(
        finding_id="f_ambig",
        type=FindingType.tone,
        severity=FindingSeverity.medium,
        confidence=0.80,
        span=Span(unit_id="u_ambig", start=0, end=10, quote="humble tone"),
        evidence=[Evidence(source="R-07", version=1, status="active")],
        explanation="Tone seems overly proud",
        route_to="creator",
        rule_id="R-07",
        disclosure=DisclosureRecord(method=Method.llm_assisted, sensitivity=Sensitivity.internal),
    )

    tagged = router.apply_needs_judgment([ambiguous_finding], ambiguous_set)
    assert len(tagged) == 1
    assert tagged[0].abstained is True
    assert "Needs judgment" in tagged[0].explanation

    processed, matched = router.process_findings(tagged, ambiguous_rule_ids=ambiguous_set)
    assert len(processed) == 1
    # Ambiguous rule routes to reviewer queue for human sign-off
    assert processed[0].route_to == "reviewer"
    assert "R-07" in matched


def test_matched_sources_includes_supported_claims():
    """Every source matched by the run — including Supported claims — is recorded for impact analysis (I3.4)."""
    # Text contains supported claim matching active F-112 (25,000+ customers) and active F-108 (99.95% uptime)
    doc = "Meridian Flow currently serves 25,000+ customers with 99.95% uptime."
    units = parse_markdown(doc)
    result = run_review(revision_units=units, policy=Sensitivity.internal)

    # No outdated findings should be emitted for current values
    outdated_findings = [f for f in result.findings if f.type == FindingType.outdated]
    assert len(outdated_findings) == 0

    # BUT matched_sources MUST contain F-112 and F-108 (PRD I3.4 requirement)
    assert "F-112" in result.matched_sources
    assert "F-108" in result.matched_sources
    assert "R-03" in result.matched_sources
