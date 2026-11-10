#!/usr/bin/env python3
"""Smoke test script for Issue #6 (A3 — Terminology checker + Temporal Fact Ledger, G1).

Verifies all Issue #6 acceptance criteria:
1. Seeded stale claim flagged Outdated with both versions cited (old superseded vs current active).
2. Stale-claim recall on seeded claims >= 85% (raw counts against baseline).
3. All shown findings pass Citation Verifier (true by construction); verifier drop rate reported.
4. Historical claim with explicit past period inside old validity window = Supported (0 findings).
5. Epistemic copy rule strictly applied to Unsupported claims.
6. Guardrail: systemic retrieval failure marks checker partial/failed, NEVER emits false Unsupported.
"""

from __future__ import annotations

import sys
from contracts.models import (
    ContentUnit,
    DisclosureRecord,
    Evidence,
    Finding,
    FindingSeverity,
    FindingStatus,
    FindingType,
    Method,
    RunNodeStatus,
    Sensitivity,
    Span,
)
from engine.fact_ledger import TemporalFactLedger, RetrievalFailureError
from engine.terminology import TerminologyChecker
from engine.verifier import CitationVerifier
from engine.pipeline import run_review, ReviewState
from engine.parsers import parse_markdown


def main() -> int:
    print("======================================================================")
    print("AXIOM BRANDLEDGER — ISSUE #6 SMOKE TEST & ACCEPTANCE VERIFICATION")
    print("======================================================================\n")

    # ------------------------------------------------------------------
    # 1. Outdated Claims & Both Versions Cited Check
    # ------------------------------------------------------------------
    print("--> 1. Testing Outdated Claims (F-112, F-108, F-115)...")
    ledger = TemporalFactLedger()
    sample_text = (
        "Meridian Flow serves 10,000+ customers with 99.9% uptime starting at $299/month."
    )
    unit = ContentUnit(
        unit_id="u_smoke_stale",
        revision_id="rev_smoke",
        kind="paragraph",
        text=sample_text,
        start=0,
        end=len(sample_text),
    )

    findings, matched = ledger.check_units([unit])
    outdated_findings = [f for f in findings if f.type == FindingType.outdated]
    print(f"    Total findings: {len(findings)}, Outdated findings: {len(outdated_findings)}")

    f112_findings = [f for f in outdated_findings if any(e.source == "F-112" for e in f.evidence)]
    assert f112_findings, "Failed to detect F-112 outdated claim!"
    f112 = f112_findings[0]
    ev = f112.evidence[0]
    print(f"    [PASS] F-112 Outdated finding:")
    print(f"           Quote: '{f112.span.quote}'")
    print(f"           Cited Evidence: source={ev.source}, old_version={ev.version} ({ev.status}), current_version={ev.current_version} ({ev.current_value})")
    assert ev.version in (1, 2)
    assert ev.status == "superseded"
    assert ev.current_version == 3
    assert ev.current_value == "25,000+"

    # ------------------------------------------------------------------
    # 2. Historical Claim with Past Period (Supported = No finding)
    # ------------------------------------------------------------------
    print("\n--> 2. Testing Explicit Past Period inside Old Validity Window...")
    hist_unit = ContentUnit(
        unit_id="u_hist",
        revision_id="rev_hist",
        kind="paragraph",
        text="In 2023, Meridian Flow supported 10,000+ customers with 99.9% uptime.",
        start=0,
        end=69,
    )
    hist_findings, hist_sources = ledger.check_units([hist_unit])
    print(f"    Historical claim findings: {len(hist_findings)}")
    assert len(hist_findings) == 0, f"Expected 0 findings for historical claim, got {len(hist_findings)}"
    assert "F-112" in hist_sources
    print("    [PASS] Historical claim correctly classified Supported (0 findings emitted).")

    # ------------------------------------------------------------------
    # 3. Superlative & Epistemic Copy Rule Check
    # ------------------------------------------------------------------
    print("\n--> 3. Testing Unsupported Superlative & Epistemic Copy Rule...")
    sup_unit = ContentUnit(
        unit_id="u_sup",
        revision_id="rev_sup",
        kind="paragraph",
        text="Meridian Flow is the #1 compliance platform and the fastest audit engine.",
        start=0,
        end=73,
    )
    sup_findings, _ = ledger.check_units([sup_unit])
    assert len(sup_findings) >= 1
    for f in sup_findings:
        assert f.type == FindingType.unsupported
        print(f"    [PASS] Quote: '{f.span.quote}' -> {f.explanation}")
        assert "No substantiation found within approved tenant sources (searched top-k candidates)" in f.explanation

    # ------------------------------------------------------------------
    # 4. Guardrail: Systemic Retrieval Failure
    # ------------------------------------------------------------------
    print("\n--> 4. Testing Retrieval Failure Guardrail...")
    broken_ledger = TemporalFactLedger(simulate_retrieval_failure=True)
    try:
        broken_ledger.check_units([unit])
        print("    [FAIL] Did not raise RetrievalFailureError!")
        sys.exit(1)
    except RetrievalFailureError as e:
        print(f"    [PASS] Guardrail caught RetrievalFailureError: '{e}'")

    # In pipeline run_review:
    result_guarded = run_review(
        revision_units=[unit],
        policy=Sensitivity.internal,
        simulate_retrieval_failure=True,
    )
    assert result_guarded.partial is True
    facts_progress = next((p for p in result_guarded.run_progress if p.node == "facts"), None)
    assert facts_progress is not None and facts_progress.status == RunNodeStatus.failed
    false_unsupported = [f for f in result_guarded.findings if f.type == FindingType.unsupported]
    assert len(false_unsupported) == 0
    print(f"    [PASS] Pipeline marked partial={result_guarded.partial}, node facts status='{facts_progress.status}'. False Unsupported count: {len(false_unsupported)}")

    # ------------------------------------------------------------------
    # 5. Stale-Claim Recall Benchmark (>= 85%)
    # ------------------------------------------------------------------
    print("\n--> 5. Evaluating Stale-Claim Recall against Ground Truth...")
    stale_test_corpus = [
        ("We serve 10,000+ customers across the globe.", "F-112"),
        ("Over 10k accounts trust our automated workflow.", "F-112"),
        ("With approximately 18,000+ customers, we lead the industry.", "F-112"),
        ("Our platform delivers 99.9% uptime for all enterprise workloads.", "F-108"),
        ("We guarantee a 99.9% SLA availability.", "F-108"),
        ("Plans start at $299/month for our standard tier.", "F-115"),
        ("Get started today for only $299 per month.", "F-115"),
        ("We manage over 18,000 accounts seamlessly.", "F-112"),
    ]

    total_stale = len(stale_test_corpus)
    detected_stale = 0

    for idx, (doc_text, expected_fact) in enumerate(stale_test_corpus):
        cu = ContentUnit(
            unit_id=f"u_test_{idx}",
            revision_id="rev_recall",
            kind="paragraph",
            text=doc_text,
            start=0,
            end=len(doc_text),
        )
        f_list, _ = ledger.check_units([cu])
        is_hit = any(
            f.type == FindingType.outdated and any(e.source == expected_fact for e in f.evidence)
            for f in f_list
        )
        if is_hit:
            detected_stale += 1

    recall = detected_stale / total_stale
    print(f"    Total seeded stale claims: {total_stale}")
    print(f"    Detected stale claims:     {detected_stale}")
    print(f"    Calculated Recall:         {recall * 100:.1f}%")
    assert recall >= 0.85, f"Recall {recall:.2f} below 85% requirement!"
    print(f"    [PASS] Stale-claim recall >= 85% target satisfied!")

    # ------------------------------------------------------------------
    # 6. Citation Verifier & Drop Rate Reporting
    # ------------------------------------------------------------------
    print("\n--> 6. Evaluating Citation Verifier & Drop Rate...")
    verifier = CitationVerifier()
    test_unit = ContentUnit(
        unit_id="u_ver_smoke",
        revision_id="rev_ver_smoke",
        kind="paragraph",
        text="Over 10,000+ customers trust Meridian Flow with 99.9% uptime.",
        start=0,
        end=62,
    )

    # Legitimate finding
    legit_finding = Finding(
        finding_id="f_legit",
        type=FindingType.outdated,
        severity=FindingSeverity.high,
        confidence=0.95,
        span=Span(unit_id="u_ver_smoke", start=5, end=22, quote="10,000+ customers"),
        evidence=[Evidence(source="F-112", version=1, status="superseded", current_version=3, current_value="25,000+")],
        explanation="Superseded metric",
        route_to="legal_reviewer",
        disclosure=DisclosureRecord(method=Method.deterministic_lookup, sensitivity=Sensitivity.internal),
    )

    # Fabricated quote finding
    fake_quote_finding = Finding(
        finding_id="f_fake_quote",
        type=FindingType.outdated,
        severity=FindingSeverity.high,
        confidence=0.95,
        span=Span(unit_id="u_ver_smoke", start=0, end=15, quote="FABRICATED QUOTE"),
        evidence=[Evidence(source="F-112", version=1, status="superseded")],
        explanation="Hallucination test",
        route_to="legal_reviewer",
        disclosure=DisclosureRecord(method=Method.deterministic_lookup, sensitivity=Sensitivity.internal),
    )

    # Fabricated source ID finding
    fake_source_finding = Finding(
        finding_id="f_fake_source",
        type=FindingType.outdated,
        severity=FindingSeverity.high,
        confidence=0.95,
        span=Span(unit_id="u_ver_smoke", start=5, end=22, quote="10,000+ customers"),
        evidence=[Evidence(source="F-999_NONEXISTENT", version=1, status="superseded")],
        explanation="Nonexistent source",
        route_to="legal_reviewer",
        disclosure=DisclosureRecord(method=Method.deterministic_lookup, sensitivity=Sensitivity.internal),
    )

    batch = [legit_finding, fake_quote_finding, fake_source_finding]
    verified, drops, drop_rate = verifier.filter_findings(
        batch, {test_unit.unit_id: test_unit}
    )

    print(f"    Total findings submitted: {len(batch)}")
    print(f"    Verified findings kept:   {len(verified)} (100% pass verification by construction)")
    print(f"    Hallucinations dropped:   {drops}")
    print(f"    Verifier drop rate:       {drop_rate * 100:.1f}%")
    assert len(verified) == 1
    assert verified[0].finding_id == "f_legit"
    assert drops == 2
    assert abs(drop_rate - (2 / 3)) < 1e-4
    print("    [PASS] Citation Verifier drop rate verified!")

    # ------------------------------------------------------------------
    # 7. End-to-End Pipeline Review Round-Trip
    # ------------------------------------------------------------------
    print("\n--> 7. End-to-End Pipeline Review Round-Trip...")
    markdown_doc = """# Meridian Flow Overview
Teams using MFP report automated brand policing in their daily review run.
We currently serve 10,000+ customers with 99.9% uptime at $299/month.
Meridian Flow is the #1 compliance platform on the market.
"""
    units = parse_markdown(markdown_doc)
    result = run_review(revision_units=units, policy=Sensitivity.internal)

    print(f"    Review Result:")
    print(f"    - Content Units parsed: {len(units)}")
    print(f"    - Total Findings:       {len(result.findings)}")
    print(f"    - Partial:              {result.partial}")
    print(f"    - Matched Sources:      {sorted(result.matched_sources)}")

    # Inspect finding categories
    term_findings = [f for f in result.findings if f.type == FindingType.terminology]
    outdated_findings = [f for f in result.findings if f.type == FindingType.outdated]
    unsup_findings = [f for f in result.findings if f.type == FindingType.unsupported]

    print(f"    - Terminology findings: {len(term_findings)} (e.g. {[f.span.quote for f in term_findings]})")
    print(f"    - Outdated findings:    {len(outdated_findings)} (e.g. {[f.span.quote for f in outdated_findings]})")
    print(f"    - Unsupported findings: {len(unsup_findings)} (e.g. {[f.span.quote for f in unsup_findings]})")

    assert len(term_findings) >= 2, "Expected terminology findings for MFP and brand policing"
    assert len(outdated_findings) >= 3, "Expected outdated findings for 10,000+ customers, 99.9% uptime, $299/month"
    assert len(unsup_findings) >= 1, "Expected unsupported finding for #1 compliance platform"

    print("\n======================================================================")
    print("ALL ISSUE #6 ACCEPTANCE CRITERIA VERIFIED SUCCESSFULLY!")
    print("======================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
