#!/usr/bin/env python3
"""Smoke test script for Issue #10 (A5 — Accessibility + Visual checkers, G3 / I2).

Verifies all Issue #10 acceptance criteria:
1. I2.1 Palette distance: CIEDE2000 vs nearest approved palette colour.
2. I2.2 WCAG contrast: relative-luminance ratio vs AA thresholds (4.5:1 normal, 3.0:1 large).
3. Demo moment: social image grey caption (#999999 on #FFFFFF) flagged "contrast 2.85:1, needs 4.5:1" with box drawn.
4. >= 20 measurements hand-checked against independent calculator (agreement >= 90%).
5. I2.3 OCR validation: words under confidence floor (< 0.60) excluded; high-confidence text tagged with BBox.
6. I2.4 Alt-text presence (suggest alt text, never claim missing, R1 §3.3) + heading order hierarchy.
7. End-to-End Review pipeline multimodal checks execution.
"""

from __future__ import annotations

import sys

from contracts.models import (
    BBox,
    ContentUnit,
    FindingType,
    Method,
    Sensitivity,
)
from engine.accessibility import (
    AccessibilityVisualChecker,
    ContrastChecker,
    OCRValidator,
    PaletteChecker,
    StructureChecker,
    calculate_ciede2000_delta_e,
    calculate_contrast_ratio,
)
from engine.pipeline import run_review


def main() -> int:
    print("======================================================================")
    print("AXIOM BRANDLEDGER — ISSUE #10 SMOKE TEST & ACCEPTANCE VERIFICATION (G3)")
    print("======================================================================\n")

    # ------------------------------------------------------------------
    # 1. Palette Distance (CIEDE2000)
    # ------------------------------------------------------------------
    print("--> 1. Testing Palette Distance (CIEDE2000)...")
    pal_checker = PaletteChecker()

    # Pass case: Meridian Blue (#1A73E8)
    u_pass = ContentUnit(unit_id="u_col_1", revision_id="r1", kind="text", text="Click here", start=0, end=10, style={"color": "#1A73E8"})
    f_pass, src_pass = pal_checker.check_unit(u_pass)
    assert f_pass is None and src_pass is not None
    print(f"    Compliant Meridian Blue (#1A73E8): PASS (matched {src_pass})")

    # Ambiguous case: slightly shifted blue (#1A73D4) -> Needs judgment (2.0 < Delta E <= 5.0)
    u_ambig = ContentUnit(unit_id="u_col_2", revision_id="r1", kind="text", text="Ambiguous blue", start=0, end=14, style={"color": "#1A73D4"})
    f_ambig, _ = pal_checker.check_unit(u_ambig)
    assert f_ambig is not None and f_ambig.abstained is True
    print(f"    Ambiguous blue (#1A73D4): Needs judgment (abstained={f_ambig.abstained}, explanation='{f_ambig.explanation}')")

    # Violation case: unapproved Magenta (#FF00FF) -> Violation (Delta E > 5.0)
    u_viol = ContentUnit(unit_id="u_col_3", revision_id="r1", kind="text", text="Magenta banner", start=0, end=14, style={"color": "#FF00FF"})
    f_viol, _ = pal_checker.check_unit(u_viol)
    assert f_viol is not None and f_viol.abstained is False
    print(f"    Off-brand Magenta (#FF00FF): VIOLATION (explanation='{f_viol.explanation}')")
    print("    [PASS] Palette distance checks verified.")

    # ------------------------------------------------------------------
    # 2. Demo Moment: Social image grey caption (#999999 on #FFFFFF)
    # ------------------------------------------------------------------
    print("\n--> 2. Testing Demo Moment: Social Image Grey Caption (#999999 on White)...")
    contrast_checker = ContrastChecker(default_bg="#FFFFFF")
    social_caption_unit = ContentUnit(
        unit_id="u_social_demo",
        revision_id="rev_demo",
        kind="paragraph",
        text="Photo by John Doe. All rights reserved.",
        start=0,
        end=39,
        page=1,
        bbox=BBox(page=1, x0=0.10, y0=0.85, x1=0.90, y1=0.92),
        style={
            "color": "#999999",
            "background_color": "#FFFFFF",
            "font_size": 12,
            "bold": False,
        },
    )

    demo_finding = contrast_checker.check_unit(social_caption_unit)
    assert demo_finding is not None
    print(f"    Measured Contrast:   {calculate_contrast_ratio('#999999', '#FFFFFF')}:1")
    print(f"    Required Contrast:   4.5:1")
    print(f"    Flagged Finding:     {demo_finding.finding_id} ({demo_finding.type.value})")
    print(f"    Explanation:         '{demo_finding.explanation}'")
    print(f"    Bounding Box:        page={social_caption_unit.bbox.page}, [x0={social_caption_unit.bbox.x0}, y0={social_caption_unit.bbox.y0}, x1={social_caption_unit.bbox.x1}, y1={social_caption_unit.bbox.y1}]")
    print(f"    Suggested Compliant: {demo_finding.suggested_fix.text}")

    assert "2.85:1" in demo_finding.explanation
    assert "4.5:1" in demo_finding.explanation
    print("    [PASS] Demo moment verified: social image grey caption flagged 'contrast 2.85:1, needs 4.5:1' with box.")

    # ------------------------------------------------------------------
    # 3. Hand-Checked Benchmark (>= 20 Measurements, Agreement >= 90%)
    # ------------------------------------------------------------------
    print("\n--> 3. Testing 20 Hand-Checked Measurements Benchmark against Ground Truth...")
    contrast_benchmarks = [
        ("#000000", "#FFFFFF", 21.00, True),
        ("#FFFFFF", "#FFFFFF", 1.00, False),
        ("#999999", "#FFFFFF", 2.85, False),
        ("#1A3C5E", "#FFFFFF", 11.34, True),
        ("#1A73E8", "#FFFFFF", 4.51, True),
        ("#616161", "#FFFFFF", 6.19, True),
        ("#00BCD4", "#FFFFFF", 2.30, False),
        ("#000000", "#00BCD4", 9.14, True),
        ("#595959", "#FFFFFF", 7.00, True),
        ("#777777", "#FFFFFF", 4.48, False),
    ]

    delta_e_benchmarks = [
        ("#1A73E8", "#1A73E8", 0.00, True),
        ("#1A73E8", "#1B74E9", 0.38, True),
        ("#1A73E8", "#1A74EA", 0.75, True),
        ("#1A3C5E", "#1A3C5E", 0.00, True),
        ("#1A3C5E", "#153350", 3.14, False),
        ("#00BCD4", "#00BCD4", 0.00, True),
        ("#FFFFFF", "#F5F5F5", 2.01, False),
        ("#1A73E8", "#00BCD4", 31.28, False),
        ("#1A3C5E", "#E81A1A", 47.72, False),
        ("#000000", "#FFFFFF", 100.00, False),
    ]

    total = len(contrast_benchmarks) + len(delta_e_benchmarks)
    agreed = 0

    for fg, bg, exp_r, exp_p in contrast_benchmarks:
        r = calculate_contrast_ratio(fg, bg)
        p = r >= 4.5
        if p == exp_p and abs(r - exp_r) <= 0.15:
            agreed += 1

    for h1, h2, exp_de, exp_p in delta_e_benchmarks:
        de = calculate_ciede2000_delta_e(h1, h2)
        p = de <= 2.0
        if p == exp_p and abs(de - exp_de) <= 1.0:
            agreed += 1

    rate = agreed / total
    print(f"    Total Hand-Checked Measurements: {total}")
    print(f"    Measurements in Agreement:       {agreed}")
    print(f"    Calculated Agreement Rate:       {rate * 100:.1f}%")
    assert rate >= 0.90
    print("    [PASS] Measurement agreement rate >= 90% benchmark satisfied.")

    # ------------------------------------------------------------------
    # 4. OCR Validation (Confidence Floor < 0.60 Excluded)
    # ------------------------------------------------------------------
    print("\n--> 4. Testing OCR Validation (< 0.60 Excluded)...")
    ocr_val = OCRValidator(confidence_floor=0.60)
    raw_ocr = [
        {"text": "Meridian", "confidence": 0.96},
        {"text": "artifact_glitch", "confidence": 0.42},
        {"text": "Flow", "confidence": 0.89},
    ]
    cleaned_ocr = ocr_val.filter_ocr_words(raw_ocr)
    words = [w["text"] for w in cleaned_ocr]
    print(f"    Raw OCR words:      {[w['text'] for w in raw_ocr]}")
    print(f"    Validated words:    {words}")
    assert "artifact_glitch" not in words
    assert "Meridian" in words and "Flow" in words
    print("    [PASS] OCR confidence filtering verified.")

    # ------------------------------------------------------------------
    # 5. Alt-Text Presence & Heading Order Skips
    # ------------------------------------------------------------------
    print("\n--> 5. Testing Alt-Text Presence (R1 §3.3) & Heading Hierarchy...")
    struct_checker = StructureChecker()

    # Image alt-text test
    img_unit = ContentUnit(
        unit_id="u_standalone_img",
        revision_id="r1",
        kind="image",
        text="[Architecture Diagram]",
        start=0,
        end=22,
        alt_text="",
    )
    alt_finding = struct_checker.check_alt_text(img_unit)
    assert alt_finding is not None
    print(f"    Standalone Image without alt-text:")
    print(f"      Explanation:   '{alt_finding.explanation}'")
    print(f"      Suggested Fix: '{alt_finding.suggested_fix.text}'")
    assert "Consider adding descriptive alt text" in alt_finding.explanation
    assert "missing" not in alt_finding.explanation.lower()

    # Heading skip test (H1 -> H3)
    h_units = [
        ContentUnit(unit_id="h1", revision_id="r1", kind="heading", text="# Header 1", start=0, end=10, style={"level": 1}),
        ContentUnit(unit_id="h3", revision_id="r1", kind="heading", text="### Header 3", start=11, end=23, style={"level": 3}),
    ]
    hdg_findings = struct_checker.check_heading_order(h_units)
    assert len(hdg_findings) == 1
    print(f"    Heading skip finding: '{hdg_findings[0].explanation}'")
    print("    [PASS] Alt-text suggestion and heading hierarchy verified.")

    # ------------------------------------------------------------------
    # 6. End-to-End Pipeline Multimodal Checks
    # ------------------------------------------------------------------
    print("\n--> 6. Testing End-to-End Pipeline Multimodal Review...")
    pipeline_units = [
        ContentUnit(
            unit_id="u_p_1",
            revision_id="rev_p",
            kind="heading",
            text="# Meridian Flow Security",
            start=0,
            end=25,
            style={"level": 1},
        ),
        social_caption_unit,
    ]
    result = run_review(revision_units=pipeline_units, policy=Sensitivity.internal)
    print(f"    Total Pipeline Findings: {len(result.findings)}")
    print(f"    Pipeline Partial:        {result.partial}")
    print(f"    Pipeline Matched Sources:{result.matched_sources}")

    acc_nodes = [p for p in result.run_progress if p.node == "accessibility_visual"]
    assert len(acc_nodes) == 1 and acc_nodes[0].status.value == "done"
    assert any(f.type == FindingType.accessibility for f in result.findings)
    print("    [PASS] Pipeline multimodal checks successfully integrated.")

    print("\n======================================================================")
    print("ALL ISSUE #10 ACCEPTANCE CRITERIA VERIFIED SUCCESSFULLY!")
    print("======================================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
