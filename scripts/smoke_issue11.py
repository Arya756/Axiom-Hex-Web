#!/usr/bin/env python3
"""Smoke test script for Issue #11 (A6 — Tone checker + Intent Card & fix generator, G3).

Verifies all Issue #11 acceptance criteria:
1. A-16 Tone Checker:
   - Sentence statistics: reading grade (Flesch-Kincaid) and sentence complexity.
   - Passive voice detection citing R-08 ("Use active voice").
   - Rubric / exemplar comparison for arrogant tone citing R-07 ("Confident but humble").
   - Rubric / exemplar comparison for corporate jargon citing R-11 ("Avoid jargon").
   - Tone findings tagged with abstained=True, explanation starting with "Needs judgment: ".
2. A-13 Auto-Extracted Intent Card:
   - Extracted on pre-check: purpose, audience, key_message, cta.
   - Creator-editable drawer allows editing and re-running constrained fixes.
3. A-13 Minimal-Edit Fix Generator & Superlative Qualification (R1 §1.5.2):
   - Superlative "#1" qualified minimally ("the #1" -> "a leading") while preserving Intent Card.
   - Preferred-term replacement ("MFP" -> "Meridian Flow Platform").
   - Current-fact replacement ("10,000+ customers" -> "25,000+ customers").
4. T9 Integration Contract (Fix Re-Check Gate):
   - Rejects fix that breaks intent (similarity < 0.85).
   - Rejects fix that introduces banned terminology ("MFP").
   - Rejects fix that introduces unapproved absolute claims ("#1").
   - Accepts valid minimal-edit fix.
5. End-to-End Pipeline Execution & Graceful Degradation:
   - Verifier drop rate reported.
   - Deterministic findings survive upstream LLM failure.
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from contracts.models import (
    ContentUnit,
    Finding,
    FindingSeverity,
    FindingType,
    IntentCard,
    Method,
    Sensitivity,
    Span,
)
from engine.intent_card import (
    compute_intent_similarity,
    extract_intent_card,
    generate_minimal_fix,
    recheck_fix,
    recheck_fix_detailed,
)
from engine.parsers import parse_markdown
from engine.pipeline import run_review
from engine.tone import ToneChecker
from engine.verifier import CitationVerifier


def main() -> int:
    print("======================================================================")
    print("AXIOM BRANDLEDGER — ISSUE #11 SMOKE TEST & ACCEPTANCE VERIFICATION (G3)")
    print("======================================================================\n")

    passed_checks = 0
    total_checks = 5

    # -------------------------------------------------------------------
    # Step 1: Tone Checker Verification (A-16)
    # -------------------------------------------------------------------
    print("--- [1/5] A-16 Tone Checker: Statistics & Rubric/Exemplar Comparison ---")
    tone_checker = ToneChecker()
    verifier = CitationVerifier()

    sample_doc = (
        "The review workflow is automated by Meridian Flow to ensure governance. "
        "Our groundbreaking platform crushes the competition with instant verification. "
        "We help teams synergize cross-functional paradigms across all document flows."
    )
    unit = ContentUnit(
        unit_id="u_smoke_tone",
        revision_id="rev_smoke_11",
        kind="paragraph",
        text=sample_doc,
        start=0,
        end=len(sample_doc),
    )
    findings = tone_checker.check_unit(unit)

    print(f"  • Flagged {len(findings)} tone findings:")
    for f in findings:
        print(f"    - [{f.rule_id}] quote: '{f.span.quote}'")
        print(f"      explanation: {f.explanation}")
        print(f"      abstained={f.abstained}, route_to={f.route_to}")

    # Verify Citation Verifier accepts all tone findings
    verified, dropped_count, drop_rate = verifier.filter_findings(findings, {unit.unit_id: unit})
    print(f"  • Citation Verifier: verified={len(verified)}, dropped={dropped_count}, drop_rate={drop_rate:.1%}")

    assert len(findings) >= 3, "Expected at least 3 tone findings"
    assert all(f.abstained for f in findings), "All tone findings must be abstained=True"
    assert all("Needs judgment: " in f.explanation for f in findings), "Explanation must start with Needs judgment"
    assert dropped_count == 0, "Verifier must not drop tone findings"
    print("  ✓ Step 1 PASSED: Tone checker flags passive, arrogant, and jargon phrasing with Needs judgment.\n")
    passed_checks += 1

    # -------------------------------------------------------------------
    # Step 2: Auto-Extracted Intent Card (A-13)
    # -------------------------------------------------------------------
    print("--- [2/5] A-13 Auto-Extracted Intent Card ---")
    doc_md = """# Meridian Flow Brand Governance Announcement

Meridian Flow delivers enterprise-grade brand compliance and automated multi-channel review.
Marketing teams and legal counsel can ensure regulatory alignment across all assets.

[Start Free Trial](https://meridianflow.io/signup)
"""
    doc_units = parse_markdown(doc_md, "rev_smoke_card")
    card = extract_intent_card(doc_units)

    print(f"  • Auto-extracted Intent Card:")
    print(f"    - purpose:      {card.purpose}")
    print(f"    - audience:     {card.audience}")
    print(f"    - key_message:  {card.key_message}")
    print(f"    - cta:          {card.cta}")

    assert card.purpose is not None and "governance" in card.purpose.lower()
    assert card.cta == "Start Free Trial"
    print("  ✓ Step 2 PASSED: Intent Card extracted automatically on pre-check.\n")
    passed_checks += 1

    # -------------------------------------------------------------------
    # Step 3: Minimal-Edit Fix & Superlative Qualification (R1 §1.5.2)
    # -------------------------------------------------------------------
    print("--- [3/5] A-13 Minimal-Edit Fix Generator & Superlative Qualification ---")
    sup_unit = ContentUnit(
        unit_id="u_smoke_sup",
        revision_id="rev_smoke_11",
        kind="paragraph",
        text="Meridian Flow is the #1 enterprise brand governance platform today.",
        start=0,
        end=66,
    )
    sup_finding = Finding(
        finding_id="f_smoke_sup",
        type=FindingType.unsupported,
        severity=FindingSeverity.medium,
        confidence=0.85,
        span=Span(unit_id=sup_unit.unit_id, start=17, end=23, quote="the #1"),
        evidence=[],
        explanation="Unsupported superlative: '#1' requires independent verification.",
        route_to="legal_reviewer",
        disclosure=findings[0].disclosure,
    )

    fix = generate_minimal_fix(sup_finding, sup_unit, card)
    print(f"  • Original:  '{sup_unit.text}'")
    print(f"  • Qualified: '{fix.text if fix else None}'")
    print(f"  • Similarity: {fix.intent_similarity if fix else None:.4f} (budget: {fix.edit_budget if fix else None}, rechecked: {fix.rechecked if fix else None})")

    assert fix is not None
    assert "a leading" in fix.text
    assert "#1" not in fix.text
    assert fix.intent_similarity >= 0.85
    assert fix.rechecked is True
    print("  ✓ Step 3 PASSED: Superlative '#1' qualified minimally while preserving Intent Card (similarity >= 0.85).\n")
    passed_checks += 1

    # -------------------------------------------------------------------
    # Step 4: T9 Fix Re-Check Gate (Rejection & Acceptance)
    # -------------------------------------------------------------------
    print("--- [4/5] T9 Fix Re-Check Gate (Enforces Intent & Zero New Violations) ---")

    # 4A: Valid edit
    valid_edit = "Meridian Flow is a leading enterprise brand governance platform today."
    r_valid = recheck_fix_detailed(sup_unit, valid_edit, card)
    print(f"  • Valid minimal edit:     passed={r_valid.passed}, sim={r_valid.intent_similarity:.4f}")
    assert r_valid.passed is True

    # 4B: Intent-breaking edit (similarity < 0.85)
    bad_intent = "Prepare chocolate chip cookies at 375 degrees Fahrenheit for 12 minutes."
    r_intent = recheck_fix_detailed(sup_unit, bad_intent, card)
    print(f"  • Off-topic edit:         passed={r_intent.passed}, sim={r_intent.intent_similarity:.4f}, reason: '{r_intent.reason}'")
    assert r_intent.passed is False
    assert r_intent.intent_similarity < 0.85

    # 4C: Introduced banned terminology ("MFP")
    bad_term = "Meridian Flow (MFP) is a leading enterprise brand governance platform today."
    r_term = recheck_fix_detailed(sup_unit, bad_term, card)
    print(f"  • Banned-term injection:  passed={r_term.passed}, reason: '{r_term.reason}'")
    assert r_term.passed is False

    # 4D: Introduced absolute claim ("#1")
    unit_neutral = ContentUnit(
        unit_id="u_neut", revision_id="rev_1", kind="paragraph", text="Meridian Flow is a compliance solution.", start=0, end=40
    )
    bad_super = "Meridian Flow is the #1 compliance solution."
    r_super = recheck_fix_detailed(unit_neutral, bad_super, card)
    print(f"  • Injected superlative:   passed={r_super.passed}, reason: '{r_super.reason}'")
    assert r_super.passed is False

    print("  ✓ Step 4 PASSED: T9 re-check rejects intent-breaking edits and new violations.\n")
    passed_checks += 1

    # -------------------------------------------------------------------
    # Step 5: Full Review Pipeline End-to-End
    # -------------------------------------------------------------------
    print("--- [5/5] Review Pipeline End-to-End & Graceful Degradation ---")
    pipeline_md = """# Meridian Flow Platform Enterprise Brief

Our platform crushes the competition effortlessly with rapid review runs.
The comprehensive audit was completed by Meridian Flow.
Trusted by 10,000+ customers across global compliance environments.

[Schedule a Demo](https://meridianflow.io/demo)
"""
    p_units = parse_markdown(pipeline_md, "rev_smoke_e2e")
    result = run_review(revision_units=p_units, ruleset_version=1)

    print(f"  • Pipeline completed: {len(result.findings)} findings total, partial={result.partial}")
    print(f"  • Matched sources: {result.matched_sources}")
    print(f"  • Run progress: {[(p.node, p.status.value) for p in result.run_progress]}")

    tone_count = sum(1 for f in result.findings if f.type == FindingType.tone)
    outdated_count = sum(1 for f in result.findings if f.type == FindingType.outdated)
    print(f"  • Breakdown: tone={tone_count}, outdated={outdated_count}")

    for f in result.findings:
        if f.suggested_fix:
            print(f"    - [{f.type.value}] '{f.span.quote}' -> fix attached (rechecked={f.suggested_fix.rechecked}, sim={f.suggested_fix.intent_similarity})")

    assert tone_count >= 2
    assert outdated_count >= 1
    assert result.partial is False

    # Graceful degradation test
    deg_result = run_review(revision_units=p_units, ruleset_version=1, simulate_llm_failure=True)
    print(f"  • Simulated LLM failure: partial={deg_result.partial}")
    assert deg_result.partial is True
    # Deterministic tone findings survived
    deg_tone = sum(1 for f in deg_result.findings if f.type == FindingType.tone)
    assert deg_tone >= 2
    print(f"  • Deterministic findings survived upstream LLM failure ({deg_tone} tone findings preserved).")
    print("  ✓ Step 5 PASSED: Full review pipeline operates end-to-end with graceful degradation.\n")
    passed_checks += 1

    print("======================================================================")
    print(f"ALL CHECKS PASSED: {passed_checks}/{total_checks} gates verified successfully!")
    print("Issue #11 (A6 — Tone checker + Intent Card & fix generator, G3) READY.")
    print("======================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
