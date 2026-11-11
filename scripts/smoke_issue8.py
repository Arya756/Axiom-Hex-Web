#!/usr/bin/env python3
"""Smoke test script for Issue #8 (A4 — Hybrid retrieval + Citation Verifier, G2).

Verifies all Issue #8 acceptance criteria:
1. Hybrid retrieval (BM25 + vector exact KNN + RRF k=60, tenant-scoped).
2. Citation Verifier:
   - Verbatim quote & offset consistency
   - Source_id@version resolution
   - Numerical comparison recomputation
   - Hallucinations dropped and drop rate reported
   - All shown findings pass verifier (true by construction)
3. Retrieval trace visible in Unsupported receipt.
4. Epistemic copy for Unsupported:
   "No substantiation found within approved tenant sources (searched top-k candidates)" — never assert claim is factually false.
5. Abstain / route_to rule:
   - Ambiguous rules / borderline findings tagged with abstained=True (Needs judgment)
   - route_to assigned according to R1 §2.5
   - Matched sources recorded for every run, including Supported claims (PRD I3.4).
"""

from __future__ import annotations

import sys

from contracts.models import (
    ContentUnit,
    DisclosureRecord,
    Evidence,
    Finding,
    FindingSeverity,
    FindingType,
    Method,
    Sensitivity,
    Span,
)
from engine.abstain import AbstainRouter, route_to_for_type
from engine.parsers import parse_markdown
from engine.pipeline import run_review
from engine.retrieval import (
    HybridRetriever,
    SourceRecord,
    get_default_retriever,
)
from engine.verifier import CitationVerifier


def main() -> int:
    print("======================================================================")
    print("AXIOM BRANDLEDGER — ISSUE #8 SMOKE TEST & ACCEPTANCE VERIFICATION (G2)")
    print("======================================================================\n")

    # ------------------------------------------------------------------
    # 1. Hybrid Retrieval (BM25 + exact KNN + RRF k=60)
    # ------------------------------------------------------------------
    print("--> 1. Testing Tenant-Scoped Hybrid Retrieval (BM25 + vector KNN + RRF k=60)...")
    retriever = get_default_retriever()
    query = "compliance platform customers"
    res = retriever.query(query, tenant_id="tenant_meridian", top_k=3)

    assert len(res.hits) >= 1, "Expected at least 1 hit from default tenant retriever"
    print(f"    Query: '{query}' on tenant: '{res.tenant_id}'")
    print(f"    Trace Summary: {res.trace_summary}")
    for idx, hit in enumerate(res.hits):
        print(f"      Hit #{idx + 1}: {hit.trace}")
        assert hit.rrf_score > 0.0

    # Tenant isolation check
    acme_retriever = HybridRetriever()
    acme_retriever.add_source(SourceRecord(
        source_id="F-ACME-99", version=1, tenant_id="tenant_acme", kind="fact", body="Acme widgets"
    ))
    meridian_check = acme_retriever.query("Acme widgets", tenant_id="tenant_meridian")
    assert len(meridian_check.hits) == 0, "Tenant isolation violated!"
    print("    [PASS] Hybrid retrieval + tenant isolation verified.")

    # ------------------------------------------------------------------
    # 2. Citation Verifier: Dropping Hallucinations & Drop Rate
    # ------------------------------------------------------------------
    print("\n--> 2. Testing Citation Verifier Anti-Hallucination Gate...")
    verifier = CitationVerifier()
    unit = ContentUnit(
        unit_id="u_smoke_v",
        revision_id="rev_smoke",
        kind="paragraph",
        text="Over 10,000+ customers trust Meridian Flow.",
        start=0,
        end=42,
    )

    # Valid finding
    valid_f = Finding(
        finding_id="f_valid",
        type=FindingType.outdated,
        severity=FindingSeverity.high,
        confidence=0.95,
        span=Span(unit_id="u_smoke_v", start=5, end=22, quote="10,000+ customers"),
        evidence=[Evidence(source="F-112", version=1, status="superseded", current_version=3, current_value="25,000+")],
        explanation="Superseded metric",
        route_to="legal_reviewer",
        disclosure=DisclosureRecord(method=Method.deterministic_lookup, sensitivity=Sensitivity.internal),
    )

    # Fake version: F-112@v99
    fake_ver_f = Finding(
        finding_id="f_fake_ver",
        type=FindingType.outdated,
        severity=FindingSeverity.high,
        confidence=0.95,
        span=Span(unit_id="u_smoke_v", start=5, end=22, quote="10,000+ customers"),
        evidence=[Evidence(source="F-112", version=99, status="superseded")],
        explanation="Hallucinated version",
        route_to="legal_reviewer",
        disclosure=DisclosureRecord(method=Method.deterministic_lookup, sensitivity=Sensitivity.internal),
    )

    # False comparison: claims quote is outdated when it matches current value
    false_comp_f = Finding(
        finding_id="f_false_comp",
        type=FindingType.outdated,
        severity=FindingSeverity.high,
        confidence=0.95,
        span=Span(unit_id="u_smoke_v", start=5, end=22, quote="10,000+ customers"),
        evidence=[Evidence(source="F-112", version=1, status="superseded", current_value="10,000+")],
        explanation="Quote already matches current value",
        route_to="legal_reviewer",
        disclosure=DisclosureRecord(method=Method.deterministic_lookup, sensitivity=Sensitivity.internal),
    )

    test_batch = [valid_f, fake_ver_f, false_comp_f]
    verified, dropped, rate = verifier.filter_findings(test_batch, {unit.unit_id: unit})

    print(f"    Total findings checked: {len(test_batch)}")
    print(f"    Verified findings:     {len(verified)} (100% pass verification by construction)")
    print(f"    Dropped hallucinations: {dropped}")
    print(f"    Verifier Drop Rate:     {rate * 100:.1f}%")
    assert len(verified) == 1
    assert verified[0].finding_id == "f_valid"
    assert dropped == 2
    assert abs(rate - (2 / 3)) < 1e-4

    # Assert true by construction: every verified finding passes verify_finding
    p, _ = verifier.verify_finding(verified[0], unit)
    assert p is True
    print("    [PASS] Citation Verifier drop rate & anti-hallucination checks verified.")

    # ------------------------------------------------------------------
    # 3. Retrieval Trace in Unsupported Receipt & Epistemic Copy Rule
    # ------------------------------------------------------------------
    print("\n--> 3. Testing Unsupported Finding with Hybrid Retrieval Trace & Epistemic Copy...")
    markdown_doc = """# Meridian Flow
Meridian Flow is the #1 compliance platform on the market.
"""
    units = parse_markdown(markdown_doc)
    review_res = run_review(revision_units=units, policy=Sensitivity.internal)

    unsup_findings = [f for f in review_res.findings if f.type == FindingType.unsupported]
    assert len(unsup_findings) >= 1, "Expected unsupported finding for #1 superlative"
    unsup = unsup_findings[0]

    print(f"    Quote:       '{unsup.span.quote}'")
    print(f"    Explanation: '{unsup.explanation}'")
    print(f"    Method:      '{unsup.disclosure.method}'")

    # Epistemic copy rule check
    assert "No substantiation found within approved tenant sources (searched top-k candidates)" in unsup.explanation
    assert "factually false" not in unsup.explanation.lower()
    # Retrieval trace check
    assert "Retrieval trace:" in unsup.explanation
    # Disclosure check
    assert unsup.disclosure.method == Method.hybrid_retrieval
    print("    [PASS] Unsupported receipt contains hybrid retrieval trace and strict epistemic copy.")

    # ------------------------------------------------------------------
    # 4. Abstain Rule & Route-to Routing (A-12)
    # ------------------------------------------------------------------
    print("\n--> 4. Testing Abstain Rule & route_to Queues...")
    router = AbstainRouter()
    ambiguous_set = {"R-07", "R-11", "R-14", "R-17"}

    # Ambiguous rule finding
    ambig_f = Finding(
        finding_id="f_r07",
        type=FindingType.tone,
        severity=FindingSeverity.medium,
        confidence=0.85,
        span=Span(unit_id="u_smoke_v", start=0, end=10, quote="humble tone"),
        evidence=[Evidence(source="R-07", version=1, status="active")],
        explanation="Tone requires discretion",
        route_to="creator",
        rule_id="R-07",
        disclosure=DisclosureRecord(method=Method.llm_assisted, sensitivity=Sensitivity.internal),
    )

    tagged = router.apply_needs_judgment([ambig_f], ambiguous_set)
    processed, _ = router.process_findings(tagged, ambiguous_rule_ids=ambiguous_set)

    assert len(processed) == 1
    assert processed[0].abstained is True
    assert "Needs judgment" in processed[0].explanation
    assert processed[0].route_to == "reviewer"
    print(f"    Ambiguous rule finding: abstained={processed[0].abstained}, route_to={processed[0].route_to}")
    print(f"    Explanation: '{processed[0].explanation}'")

    # Verify route_to mapping per R1 §2.5
    for t_name, expected_route in [
        ("terminology", "creator"),
        ("outdated", "legal_reviewer"),
        ("contradicted", "legal_reviewer"),
        ("unsupported", "legal_reviewer"),
    ]:
        assert route_to_for_type(t_name) == expected_route
    print("    [PASS] Abstain rule and route_to queues verified.")

    # ------------------------------------------------------------------
    # 5. Matched Sources Tracking (including Supported Claims)
    # ------------------------------------------------------------------
    print("\n--> 5. Testing Matched Sources Tracking (PRD I3.4)...")
    supported_doc = "Meridian Flow serves 25,000+ customers with 99.95% uptime."
    s_units = parse_markdown(supported_doc)
    s_result = run_review(revision_units=s_units, policy=Sensitivity.internal)

    print(f"    Active claim findings count: {len(s_result.findings)} (0 expected for clean active values)")
    print(f"    Matched sources recorded:    {s_result.matched_sources}")

    assert len([f for f in s_result.findings if f.type == FindingType.outdated]) == 0
    assert "F-112" in s_result.matched_sources
    assert "F-108" in s_result.matched_sources
    assert "R-03" in s_result.matched_sources
    print("    [PASS] Supported claims correctly recorded in matched_sources for impact analysis.")

    print("\n======================================================================")
    print("ALL ISSUE #8 ACCEPTANCE CRITERIA VERIFIED SUCCESSFULLY!")
    print("======================================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
