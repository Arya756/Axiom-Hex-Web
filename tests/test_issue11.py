"""Test suite for Issue #11 (A6 — Tone checker + Intent Card & fix generator, G3).

Verifies:
1. A-16 Tone Checker:
   - Reading level / Flesch-Kincaid statistics (Grade > 10 threshold).
   - Sentence length / complexity statistics.
   - Passive voice detection citing R-08 ("Use active voice").
   - Rubric / exemplar comparison for arrogant tone citing R-07 ("Confident but humble").
   - Rubric / exemplar comparison for jargon buzzwords citing R-11 ("Avoid jargon").
   - All tone findings tagged with abstained=True, route_to="creator", and explanation starting with "Needs judgment: ".
   - All tone findings pass Citation Verifier (true by construction; exact span and quote).
2. A-13 Auto-Extracted Intent Card:
   - Automatically extracted on pre-check with purpose, audience, key_message, cta.
   - Creator-editable drawer allows editing and re-running constrained fixes.
3. A-13 Minimal-Edit Fix Generator & Superlative Qualification:
   - Deterministic preferred-term replacement ("MFP" -> "Meridian Flow Platform").
   - Deterministic current-fact replacement ("10,000+ customers" -> "25,000+ customers").
   - Superlative "#1" / absolute claims qualified minimally per R1 §1.5.2 ("the #1" -> "a leading").
   - Intent similarity >= 0.85 preserved.
4. T9 Integration Contract (Fix Re-Check Gate):
   - Rejects fix that breaks intent (similarity < 0.85).
   - Rejects fix that introduces new violations (e.g. banned term "MFP").
   - Rejects fix that introduces new unqualified absolute claims ("#1").
   - Accepts valid minimal-edit fix.
5. Review Pipeline End-to-End Integration (G3 Gate):
   - Automated pre-check extracts Intent Card.
   - Tone findings present and routed to creator as Needs judgment.
   - Suggested fixes generated, self-checked, and attached.
   - Deterministic tone findings survive upstream LLM failure (graceful degradation).
"""

from __future__ import annotations

import pytest

from contracts.models import (
    ContentUnit,
    Finding,
    FindingSeverity,
    FindingStatus,
    FindingType,
    IntentCard,
    Method,
    RunNodeStatus,
    Sensitivity,
    Span,
    SuggestedFix,
)
from engine.intent_card import (
    compute_intent_similarity,
    extract_intent_card,
    generate_minimal_fix,
    recheck_fix,
    recheck_fix_detailed,
)
from engine.parsers import parse_markdown
from engine.pipeline import ReviewState, run_review
from engine.tone import ToneChecker
from engine.verifier import CitationVerifier


# ---------------------------------------------------------------------------
# 1. A-16 Tone Checker Tests
# ---------------------------------------------------------------------------

def test_tone_checker_passive_voice_detection():
    """Tone checker flags passive voice and cites R-08."""
    checker = ToneChecker()
    unit = ContentUnit(
        unit_id="u_tone_01",
        revision_id="rev_t1",
        kind="paragraph",
        text="The brand review workflow is automated by Meridian Flow to ensure quality.",
        start=0,
        end=75,
    )
    findings = checker.check_unit(unit)
    passive_findings = [f for f in findings if f.rule_id == "R-08"]

    assert len(passive_findings) == 1
    f = passive_findings[0]
    assert f.type == FindingType.tone
    assert f.abstained is True
    assert f.route_to == "creator"
    assert "Needs judgment: " in f.explanation
    assert "is automated by Meridian Flow" in f.span.quote
    assert f.span.quote in unit.text
    assert unit.text[f.span.start - unit.start : f.span.end - unit.start] == f.span.quote


def test_tone_checker_arrogant_tone_rubric():
    """Tone checker flags hyperbolic/arrogant phrasing and cites R-07 (Confident but humble)."""
    checker = ToneChecker()
    unit = ContentUnit(
        unit_id="u_tone_02",
        revision_id="rev_t1",
        kind="paragraph",
        text="Our groundbreaking platform crushes the competition with unmatched speed.",
        start=10,
        end=84,
    )
    findings = checker.check_unit(unit)
    arrogant_findings = [f for f in findings if f.rule_id == "R-07"]

    assert len(arrogant_findings) >= 1
    f = arrogant_findings[0]
    assert f.type == FindingType.tone
    assert f.abstained is True
    assert f.route_to == "creator"
    assert "Needs judgment: " in f.explanation
    assert "crushes the competition" in f.span.quote
    assert unit.text[f.span.start - unit.start : f.span.end - unit.start] == f.span.quote


def test_tone_checker_corporate_jargon_rubric():
    """Tone checker flags heavy buzzwords and cites R-11 (Avoid jargon)."""
    checker = ToneChecker()
    unit = ContentUnit(
        unit_id="u_tone_03",
        revision_id="rev_t1",
        kind="paragraph",
        text="We help companies synergize cross-functional paradigms for faster delivery.",
        start=0,
        end=75,
    )
    findings = checker.check_unit(unit)
    jargon_findings = [f for f in findings if f.rule_id == "R-11"]

    assert len(jargon_findings) >= 1
    f = jargon_findings[0]
    assert f.type == FindingType.tone
    assert f.abstained is True
    assert f.route_to == "creator"
    assert "Needs judgment: " in f.explanation
    assert "synergize cross-functional paradigms" in f.span.quote


def test_tone_checker_reading_grade_and_sentence_length():
    """Tone checker detects overly complex sentences with high Flesch-Kincaid grade."""
    checker = ToneChecker(reading_level_threshold=10.0)
    complex_text = (
        "Notwithstanding previous institutional deliberations regarding compartmentalised "
        "interoperability paradigms, bureaucratic multilateral methodologies necessitate "
        "substantive infrastructural synchronisation across contemporary organizational architectures."
    )
    unit = ContentUnit(
        unit_id="u_tone_04",
        revision_id="rev_t1",
        kind="paragraph",
        text=complex_text,
        start=0,
        end=len(complex_text),
    )
    grade = checker.calculate_reading_grade(complex_text)
    assert grade > 12.0

    findings = checker.check_unit(unit)
    stats_findings = [f for f in findings if f.rule_id == "R-04"]
    assert len(stats_findings) >= 1
    f = stats_findings[0]
    assert f.abstained is True
    assert f.route_to == "creator"
    assert "Needs judgment: " in f.explanation


def test_tone_findings_pass_citation_verifier():
    """Citation Verifier accepts all tone findings without dropping them."""
    checker = ToneChecker()
    verifier = CitationVerifier()

    unit = ContentUnit(
        unit_id="u_tone_05",
        revision_id="rev_t1",
        kind="paragraph",
        text="The copy was written by legal. Our system crushes the competition effortlessly.",
        start=50,
        end=130,
    )
    findings = checker.check_unit(unit)
    assert len(findings) >= 2

    verified, dropped_count, drop_rate = verifier.filter_findings(findings, {unit.unit_id: unit})
    assert dropped_count == 0
    assert drop_rate == 0.0
    assert len(verified) == len(findings)


# ---------------------------------------------------------------------------
# 2. A-13 Intent Card Extraction Tests
# ---------------------------------------------------------------------------

def test_extract_intent_card_from_document():
    """Auto-extracts Intent Card with purpose, audience, key_message, and CTA."""
    md = """# Meridian Flow Platform Release v2

Meridian Flow delivers enterprise-grade brand governance and automated compliance.
Marketing teams and legal counsel can collaborate seamlessly across all content channels.

[Start Free Trial](https://meridianflow.io/signup)
"""
    units = parse_markdown(md, "rev_doc_01")
    card = extract_intent_card(units)

    assert card.purpose is not None
    assert "announcement" in card.purpose.lower() or "governance" in card.purpose.lower()
    assert card.audience is not None
    assert "enterprise" in card.audience.lower() or "marketing" in card.audience.lower() or "legal" in card.audience.lower()
    assert "Meridian Flow delivers" in card.key_message
    assert card.cta == "Start Free Trial"


def test_extract_intent_card_empty_or_minimal():
    """Fallback Intent Card returned safely for empty document."""
    card = extract_intent_card([])
    assert card.purpose == "General brand communication"
    assert card.audience is not None
    assert card.key_message is not None
    assert card.cta is None


# ---------------------------------------------------------------------------
# 3. A-13 Fix Generator & Superlative Qualification Tests
# ---------------------------------------------------------------------------

def test_superlative_qualification_minimal_fix():
    """Superlative '#1' is qualified minimally while preserving Intent Card (R1 §1.5.2)."""
    unit = ContentUnit(
        unit_id="u_sup_01",
        revision_id="rev_fix_01",
        kind="paragraph",
        text="Meridian Flow is the #1 enterprise brand governance platform today.",
        start=0,
        end=66,
    )
    intent_card = IntentCard(
        purpose="Product capability showcase",
        audience="Enterprise brand managers",
        key_message="Meridian Flow is an enterprise brand governance platform.",
        cta="Learn More",
    )
    finding = Finding(
        finding_id="f_sup_01",
        type=FindingType.unsupported,
        severity=FindingSeverity.medium,
        confidence=0.85,
        span=Span(unit_id=unit.unit_id, start=17, end=23, quote="the #1"),
        evidence=[],
        explanation="Unsupported superlative: '#1' requires independent verification.",
        route_to="legal_reviewer",
        disclosure=finding_stub_disclosure(),
    )

    fix = generate_minimal_fix(finding, unit, intent_card)
    assert fix is not None
    assert fix.edit_budget == "minimal"
    assert fix.rechecked is True
    assert fix.intent_similarity is not None
    assert fix.intent_similarity >= 0.85
    assert "a leading" in fix.text
    assert "#1" not in fix.text
    assert "brand governance platform" in fix.text


def test_deterministic_terminology_fix():
    """Generates deterministic fix replacing banned abbreviation 'MFP'."""
    unit = ContentUnit(
        unit_id="u_term_01",
        revision_id="rev_fix_02",
        kind="paragraph",
        text="Welcome to MFP, the automated governance solution.",
        start=0,
        end=50,
    )
    finding = Finding(
        finding_id="f_term_01",
        type=FindingType.terminology,
        severity=FindingSeverity.medium,
        confidence=1.0,
        span=Span(unit_id=unit.unit_id, start=11, end=14, quote="MFP"),
        evidence=[],
        explanation="Banned abbreviation 'MFP' detected. Use 'Meridian Flow Platform'.",
        route_to="creator",
        disclosure=finding_stub_disclosure(),
    )

    fix = generate_minimal_fix(finding, unit)
    assert fix is not None
    assert fix.text == "Welcome to Meridian Flow Platform, the automated governance solution."
    assert fix.rechecked is True
    assert fix.intent_similarity >= 0.85


def test_deterministic_outdated_fact_fix():
    """Generates deterministic fix replacing superseded figure '10,000+ customers'."""
    unit = ContentUnit(
        unit_id="u_fact_01",
        revision_id="rev_fix_03",
        kind="paragraph",
        text="Trusted by 10,000+ customers worldwide.",
        start=0,
        end=39,
    )
    finding = Finding(
        finding_id="f_fact_01",
        type=FindingType.outdated,
        severity=FindingSeverity.high,
        confidence=0.95,
        span=Span(unit_id=unit.unit_id, start=11, end=27, quote="10,000+ customers"),
        evidence=[],
        explanation="Outdated claim: superseded by F-112 v3.",
        route_to="legal_reviewer",
        disclosure=finding_stub_disclosure(),
    )

    fix = generate_minimal_fix(finding, unit)
    assert fix is not None
    assert fix.text == "Trusted by 25,000+ customers worldwide."
    assert fix.rechecked is True
    assert fix.intent_similarity >= 0.85


# ---------------------------------------------------------------------------
# 4. T9 Integration Contract (Fix Re-Check Gate)
# ---------------------------------------------------------------------------

def test_t9_recheck_accepts_valid_minimal_fix():
    """T9 re-check accepts intent-preserving fix that introduces no violations."""
    unit = ContentUnit(
        unit_id="u_t9_01",
        revision_id="rev_t9",
        kind="paragraph",
        text="Meridian Flow is the #1 enterprise platform for reviews.",
        start=0,
        end=56,
    )
    fixed_text = "Meridian Flow is a leading enterprise platform for reviews."
    assert recheck_fix(unit, fixed_text) is True

    report = recheck_fix_detailed(unit, fixed_text)
    assert report.passed is True
    assert report.intent_similarity >= 0.85
    assert len(report.violations) == 0


def test_t9_recheck_rejects_intent_breaking_fix():
    """T9 re-check rejects edit that breaks document intent (similarity < 0.85)."""
    unit = ContentUnit(
        unit_id="u_t9_02",
        revision_id="rev_t9",
        kind="paragraph",
        text="Meridian Flow delivers real-time compliance governance for enterprise documents.",
        start=0,
        end=81,
    )
    irrelevant_text = "Bake the strawberry shortcake in the oven at 350 degrees for 25 minutes."
    assert recheck_fix(unit, irrelevant_text) is False

    report = recheck_fix_detailed(unit, irrelevant_text)
    assert report.passed is False
    assert report.intent_similarity < 0.85
    assert any("Breaks core intent" in v for v in report.violations)


def test_t9_recheck_rejects_introduced_banned_terminology():
    """T9 re-check rejects edit that introduces banned terminology ('MFP')."""
    unit = ContentUnit(
        unit_id="u_t9_03",
        revision_id="rev_t9",
        kind="paragraph",
        text="Meridian Flow provides automated brand reviews for enterprise teams.",
        start=0,
        end=69,
    )
    # Edit introduces banned abbreviation "MFP"
    bad_edit = "Meridian Flow (MFP) provides automated brand reviews for enterprise teams."
    assert recheck_fix(unit, bad_edit) is False

    report = recheck_fix_detailed(unit, bad_edit)
    assert report.passed is False
    assert any("Introduces banned terminology" in v for v in report.violations)


def test_t9_recheck_rejects_new_unapproved_superlative():
    """T9 re-check rejects edit that injects an unapproved absolute '#1'."""
    unit = ContentUnit(
        unit_id="u_t9_04",
        revision_id="rev_t9",
        kind="paragraph",
        text="Meridian Flow is a trusted enterprise governance solution.",
        start=0,
        end=58,
    )
    bad_edit = "Meridian Flow is the #1 trusted enterprise governance solution."
    assert recheck_fix(unit, bad_edit) is False

    report = recheck_fix_detailed(unit, bad_edit)
    assert report.passed is False
    assert any("unapproved absolute superlative" in v for v in report.violations)


# ---------------------------------------------------------------------------
# 5. Pipeline End-to-End Integration Tests (Gate G3)
# ---------------------------------------------------------------------------

def test_pipeline_precheck_auto_extracts_intent_card_and_runs_tone():
    """Pipeline auto-extracts Intent Card and surfaces verified tone findings."""
    md = """# Meridian Flow Brand Guidelines Overview

Our platform crushes the competition effortlessly with instant scans.
The quarterly compliance audit is completed by Meridian Flow.

[Schedule a Demo](https://meridianflow.io/demo)
"""
    units = parse_markdown(md, "rev_pipeline_g3")
    result = run_review(revision_units=units, ruleset_version=1)

    assert result.partial is False
    # Router node executed
    router_progress = next((p for p in result.run_progress if p.node == "router"), None)
    assert router_progress is not None
    assert router_progress.status == RunNodeStatus.done

    # Tone findings generated
    tone_findings = [f for f in result.findings if f.type == FindingType.tone]
    assert len(tone_findings) >= 2

    # All tone findings must have Needs judgment and abstained=True
    for tf in tone_findings:
        assert tf.abstained is True
        assert tf.route_to in ("creator", "reviewer")
        assert "Needs judgment: " in tf.explanation
        assert tf.suggested_fix is not None
        assert tf.suggested_fix.rechecked is True


def test_pipeline_creator_edited_intent_card_drawer_rerun():
    """Creator edits Intent Card in drawer and re-runs constrained fixes."""
    units = [
        ContentUnit(
            unit_id="u_draw_01",
            revision_id="rev_drawer",
            kind="paragraph",
            text="Meridian Flow is the #1 solution for automated brand reviews.",
            start=0,
            end=62,
        )
    ]
    custom_card = IntentCard(
        purpose="Custom Executive Briefing",
        audience="Chief Legal Officers",
        key_message="Meridian Flow is a trusted brand review platform.",
        cta="Contact General Counsel",
    )

    result = run_review(revision_units=units, ruleset_version=1, intent_card=custom_card)
    assert len(result.findings) >= 1
    # Check that fixes were generated against custom intent card
    for f in result.findings:
        if f.suggested_fix:
            assert f.suggested_fix.rechecked is True
            assert f.suggested_fix.intent_similarity >= 0.85


def test_pipeline_graceful_degradation_preserves_deterministic_tone():
    """Simulated LLM failure still preserves deterministic tone and terminology findings."""
    units = [
        ContentUnit(
            unit_id="u_deg_01",
            revision_id="rev_deg",
            kind="paragraph",
            text="The audit is executed by Meridian Flow. Our software crushes the competition.",
            start=0,
            end=78,
        )
    ]
    result = run_review(
        revision_units=units,
        ruleset_version=1,
        simulate_llm_failure=True,
    )

    assert result.partial is True
    # Progress shows tone_llm partial
    llm_node = next(p for p in result.run_progress if p.node == "tone_llm")
    assert llm_node.status == RunNodeStatus.partial

    # Deterministic tone findings survive!
    tone_findings = [f for f in result.findings if f.type == FindingType.tone]
    assert len(tone_findings) >= 1


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def finding_stub_disclosure():
    from contracts.models import DisclosureRecord, Method, Sensitivity
    return DisclosureRecord(
        method=Method.deterministic_lookup,
        provider=None,
        model=None,
        external_call=False,
        data_categories=["text"],
        sensitivity=Sensitivity.internal,
        latency_ms=1,
    )

