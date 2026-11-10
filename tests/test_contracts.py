"""Tests for Axiom shared contracts and stub engine (Issue #1, G0)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts import (
    BBox,
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
    RunNodeStatus,
    RunProgress,
    Sensitivity,
    SourceVersion,
    Span,
    SuggestedFix,
    compile,
    recheck_fix,
    run_review,
)


def test_bbox_normalized_bounds():
    """BBox must enforce 0.0-1.0 normalized coordinates."""
    bbox = BBox(page=1, x0=0.1, y0=0.2, x1=0.8, y1=0.9)
    assert bbox.page == 1
    assert bbox.x0 == 0.1
    assert bbox.y1 == 0.9

    with pytest.raises(ValidationError):
        BBox(page=1, x0=-0.1, y0=0.0, x1=1.0, y1=1.0)

    with pytest.raises(ValidationError):
        BBox(page=1, x0=0.0, y0=0.0, x1=1.1, y1=1.0)


def test_content_unit_offsets_and_serialization():
    """ContentUnit should provide offsets and serialize/deserialize cleanly."""
    cu = ContentUnit(
        unit_id="u_01",
        revision_id="rev_01",
        kind="paragraph",
        text="Over 10,000+ customers trust Meridian Flow.",
        start=0,
        end=42,
        page=1,
        bbox=BBox(page=1, x0=0.05, y0=0.1, x1=0.95, y1=0.15),
    )
    assert cu.offsets == [0, 42]

    dumped = cu.model_dump()
    reloaded = ContentUnit.model_validate(dumped)
    assert reloaded.unit_id == "u_01"
    assert reloaded.bbox.x0 == 0.05
    assert reloaded.offsets == [0, 42]


def test_canonical_finding_schema_roundtrip():
    """Canonical PRD §4.4 JSON example should validate and round-trip."""
    raw_json = """{
      "finding_id": "f_81c2",
      "type": "outdated",
      "severity": "high",
      "confidence": 0.93,
      "span": {"unit_id": "p3", "start": 41, "end": 58, "quote": "10,000+ customers"},
      "evidence": [{
        "source": "F-112", "version": 2, "status": "superseded",
        "current_version": 3, "current_value": "25,000+ customers",
        "effective": "2025-03-01"
      }],
      "explanation": "This figure matches an earlier approved fact that has since been replaced.",
      "suggested_fix": {
        "text": "25,000+ customers",
        "edit_budget": "minimal",
        "rechecked": true,
        "intent_similarity": 0.97
      },
      "route_to": "legal_reviewer",
      "disclosure": {"method": "deterministic_lookup", "external_call": false, "sensitivity": "internal"},
      "status": "open"
    }"""
    finding = Finding.model_validate_json(raw_json)
    assert finding.finding_id == "f_81c2"
    assert finding.type == FindingType.outdated
    assert finding.span.quote == "10,000+ customers"
    assert finding.span["unit_id"] == "p3"
    assert finding.abstained is False
    assert finding.rule_id is None
    assert len(finding.evidence) == 1
    assert finding.evidence[0].current_version == 3

    dumped_json = finding.model_dump_json()
    reloaded = Finding.model_validate_json(dumped_json)
    assert reloaded == finding


def test_run_review_stub():
    """Stub engine run_review returns fixture findings and progress."""
    cu = ContentUnit(
        unit_id="u_01",
        revision_id="rev_100",
        kind="text",
        text="Sample draft text.",
        start=0,
        end=17,
    )
    result = run_review(
        revision_units=[cu],
        ruleset_version=1,
        policy=Sensitivity.internal,
        intent_card=IntentCard(
            purpose="Product announcement",
            audience="Enterprise buyers",
            key_message="Meridian Flow scales compliance",
        ),
    )
    assert isinstance(result, ReviewResult)
    assert result.revision_id == "rev_100"
    assert result.ruleset_version == 1
    assert result.sensitivity == Sensitivity.internal
    assert len(result.findings) == 1
    assert result.findings[0].span.unit_id == "u_01"
    assert result.findings[0].abstained is False
    assert result.matched_sources == ["R-01"]
    assert len(result.run_progress) == 3
    assert all(node.status == RunNodeStatus.done for node in result.run_progress)


def test_compile_hook_stub():
    """Stub compile hook returns 384-dimensional embedding (T5)."""
    sv = SourceVersion(
        source_id="F-112",
        version=1,
        kind="fact",
        body="10,000+ customers",
    )
    res = compile(sv)
    assert isinstance(res, CompileResult)
    assert res.source_id == "F-112"
    assert res.version == 1
    assert len(res.embedding) == 384
    assert res.lint_flags == []
    assert res.collisions == []


def test_recheck_fix_stub():
    """Stub recheck_fix accepts edits (T9)."""
    cu = ContentUnit(
        unit_id="u_01",
        revision_id="rev_100",
        kind="text",
        text="Old text",
        start=0,
        end=8,
    )
    assert recheck_fix(cu, "New text") is True


def test_finding_schema_file_in_sync():
    """contracts/finding_schema.json must match Finding.model_json_schema()."""
    schema_path = Path(__file__).parent.parent / "contracts" / "finding_schema.json"
    assert schema_path.exists(), "contracts/finding_schema.json must exist"
    with open(schema_path, "r", encoding="utf-8") as f:
        saved_schema = json.load(f)
    generated_schema = Finding.model_json_schema()
    assert saved_schema == generated_schema

