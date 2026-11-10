"""Issue #2 smoke tests: Meridian Flow brand kit + FastAPI stub round-trip.

Acceptance criteria (PRD §4.3 A-01..A-03, Issue #2 §Gate G0):
  1. Contracts importable by both leads.
  2. Stub round-trips through FastAPI and returns a valid ReviewResult (T1).
  3. Brand kit loads via the import endpoint (idempotent re-import no-op).

Run:
    pytest tests/test_issue2.py -v
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from brand_kit.importer import import_brand_kit, reset_store
from brand_kit.meridian_flow import (
    FACTS,
    GLOSSARY,
    LICENSED_ASSETS,
    LOGOS,
    MERIDIAN_FLOW_KIT,
    PALETTE,
    RULES,
)
from brand_kit.models import BrandKit, BrandRule, FactVersion, RuleKind
from contracts import (
    ContentUnit,
    Finding,
    IntentCard,
    ReviewResult,
    Sensitivity,
    run_review,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_import_store():
    """Reset the in-memory import store before every test."""
    from engine.api import reset_store as reset_api_store
    reset_store()
    reset_api_store()
    yield
    reset_store()
    reset_api_store()


@pytest.fixture
def api_client():
    from api.main import app
    return TestClient(app)


@pytest.fixture
def sample_unit() -> ContentUnit:
    return ContentUnit(
        unit_id="u_01",
        revision_id="rev_mf_001",
        kind="paragraph",
        text="Over 10,000+ customers trust the MFP platform for compliance.",
        start=0,
        end=62,
        page=1,
    )


# ---------------------------------------------------------------------------
# A-01: Contracts importable
# ---------------------------------------------------------------------------


def test_contracts_importable():
    """All six A-01 contracts must be importable from the contracts package."""
    from contracts import (
        ContentUnit,
        DisclosureRecord,
        Evidence,
        Finding,
        ReviewResult,
        SuggestedFix,
    )
    # Just importing without error is the test
    assert ContentUnit is not None
    assert Finding is not None
    assert Evidence is not None
    assert SuggestedFix is not None
    assert ReviewResult is not None
    assert DisclosureRecord is not None


# ---------------------------------------------------------------------------
# A-03: Brand kit structure
# ---------------------------------------------------------------------------


def test_brand_kit_rule_count():
    """Brand kit must have exactly 18 rules (PRD §4.3 A-03: ~18 rules)."""
    assert len(RULES) == 18, f"Expected 18 rules, got {len(RULES)}"


def test_brand_kit_glossary_count():
    """Brand kit must have exactly 24 glossary terms (~24 per PRD)."""
    assert len(GLOSSARY) == 24, f"Expected 24 glossary terms, got {len(GLOSSARY)}"


def test_brand_kit_fact_count():
    """Brand kit must have exactly 14 facts (~14 per PRD)."""
    assert len(FACTS) == 14, f"Expected 14 facts, got {len(FACTS)}"


def test_brand_kit_palette_count():
    """Brand kit must have exactly 6 palette colours."""
    assert len(PALETTE) == 6, f"Expected 6 colours, got {len(PALETTE)}"


def test_brand_kit_logo_count():
    """Brand kit must have exactly 2 logos."""
    assert len(LOGOS) == 2, f"Expected 2 logos, got {len(LOGOS)}"


def test_brand_kit_licensed_assets():
    """Brand kit must have exactly 1 licensed asset expiring demo week + 2."""
    assert len(LICENSED_ASSETS) == 1
    asset = LICENSED_ASSETS[0]
    # Demo week is ~2026-11-10; demo week + 2 = 2026-11-24
    assert asset.expires == date(2026, 11, 24), f"Unexpected expiry: {asset.expires}"


def test_ambiguous_rules_present():
    """R-07, R-11, R-14, R-16 must be seeded as ambiguous."""
    ambiguous_ids = {r.rule_id for r in RULES if r.kind == RuleKind.ambiguous}
    assert ambiguous_ids == {"R-07", "R-11", "R-14", "R-16"}, (
        f"Unexpected ambiguous rule IDs: {ambiguous_ids}"
    )


def test_control_rules_r01_to_r04():
    """R-01..R-04 must be clear control rules."""
    control_ids = {r.rule_id for r in RULES if r.kind == RuleKind.control}
    assert {"R-01", "R-02", "R-03", "R-04"}.issubset(control_ids), (
        f"Control rules missing from: {control_ids}"
    )


def test_r07_has_no_owner_no_examples():
    """R-07 intentionally has no owner and no examples (triggers lint flags)."""
    r07 = next(r for r in RULES if r.rule_id == "R-07")
    assert r07.owner is None, "R-07 must have no owner"
    assert r07.good_examples == [], "R-07 must have no good examples"
    assert r07.bad_examples == [], "R-07 must have no bad examples"


def test_r16_collides_with_r03():
    """R-16 must declare a collision with R-03."""
    r16 = next(r for r in RULES if r.rule_id == "R-16")
    assert r16.collides_with == "R-03", f"R-16.collides_with={r16.collides_with!r}"


def test_f112_supersession_chain():
    """F-112 must have 3 versions: 10,000+ → 18,000+ → 25,000+ customers."""
    f112 = next(f for f in FACTS if f.fact_id == "F-112")
    assert len(f112.versions) == 3
    values = [v.value for v in f112.versions]
    assert values == ["10,000+", "18,000+", "25,000+"], f"Unexpected values: {values}"
    # Last version is active (no superseded_by)
    assert f112.versions[2].superseded_by is None
    # First two are superseded
    assert f112.versions[0].superseded_by == 2
    assert f112.versions[1].superseded_by == 3


def test_f108_supersession_chain():
    """F-108 must have 2 versions: 99.9% → 99.95% uptime."""
    f108 = next(f for f in FACTS if f.fact_id == "F-108")
    assert len(f108.versions) == 2
    assert f108.versions[0].value == "99.9%"
    assert f108.versions[1].value == "99.95%"
    assert f108.versions[0].superseded_by == 2
    assert f108.versions[1].superseded_by is None


def test_f115_supersession_chain():
    """F-115 must have 2 pricing versions."""
    f115 = next(f for f in FACTS if f.fact_id == "F-115")
    assert len(f115.versions) == 2
    assert f115.versions[0].superseded_by == 2
    assert f115.versions[1].superseded_by is None


def test_meridian_flow_kit_validates_as_brand_kit():
    """MERIDIAN_FLOW_KIT must be a valid BrandKit instance."""
    assert isinstance(MERIDIAN_FLOW_KIT, BrandKit)
    # Round-trip through JSON
    dumped = MERIDIAN_FLOW_KIT.model_dump_json()
    reloaded = BrandKit.model_validate_json(dumped)
    assert reloaded.tenant_id == "meridian-flow"
    assert len(reloaded.rules) == 18


def test_banned_term_mfp_in_glossary():
    """'MFP' must be a banned term in the glossary."""
    all_banned = {term for g in GLOSSARY for term in g.banned}
    assert "MFP" in all_banned, "'MFP' must appear as a banned term"


# ---------------------------------------------------------------------------
# A-03: Idempotent importer
# ---------------------------------------------------------------------------


def test_first_import_is_created():
    """First import of a brand kit sets created=True."""
    result = import_brand_kit(MERIDIAN_FLOW_KIT)
    assert result.created is True
    assert result.tenant_id == "meridian-flow"
    assert len(result.content_hash) == 64  # SHA-256 hex


def test_identical_reimport_is_noop():
    """Re-importing the same kit returns created=False (idempotent no-op)."""
    r1 = import_brand_kit(MERIDIAN_FLOW_KIT)
    r2 = import_brand_kit(MERIDIAN_FLOW_KIT)
    assert r1.content_hash == r2.content_hash
    assert r1.created is True
    assert r2.created is False  # no-op


def test_different_kit_version_creates_new_record():
    """A kit with different content gets a different hash and is stored separately."""
    import_brand_kit(MERIDIAN_FLOW_KIT)

    # Bump the kit version — creates a genuinely different kit
    modified_kit = MERIDIAN_FLOW_KIT.model_copy(update={"version": 2})
    r2 = import_brand_kit(modified_kit)
    assert r2.created is True


# ---------------------------------------------------------------------------
# A-02 + T1: Stub engine round-trip
# ---------------------------------------------------------------------------


def test_stub_engine_round_trip(sample_unit):
    """Stub run_review returns a valid ReviewResult with at least one finding."""
    result = run_review(
        revision_units=[sample_unit],
        ruleset_version=1,
        policy=Sensitivity.internal,
        intent_card=IntentCard(
            purpose="Product marketing one-pager",
            audience="Enterprise CIOs",
            key_message="Meridian Flow modernises compliance",
            cta="Book a demo",
        ),
    )
    assert isinstance(result, ReviewResult)
    assert result.revision_id == "rev_mf_001"
    assert result.ruleset_version == 1
    assert result.sensitivity == Sensitivity.internal
    assert len(result.findings) >= 1
    assert result.partial is False


def test_stub_finding_validates_against_schema(sample_unit):
    """Every finding from the stub engine must validate against Finding schema."""
    result = run_review(
        revision_units=[sample_unit],
        ruleset_version=1,
        policy=Sensitivity.internal,
    )
    for f in result.findings:
        assert isinstance(f, Finding)
        # Must have required fields
        assert f.finding_id
        assert f.type
        assert f.severity
        assert 0.0 <= f.confidence <= 1.0
        assert f.span.unit_id == sample_unit.unit_id
        assert f.explanation
        assert f.route_to
        assert f.disclosure


# ---------------------------------------------------------------------------
# FastAPI stub: POST /import/brand-kit
# ---------------------------------------------------------------------------


def test_api_import_brand_kit_endpoint(api_client):
    """POST /import/brand-kit with the Meridian Flow kit returns 200 and created=true."""
    payload = json.loads(MERIDIAN_FLOW_KIT.model_dump_json())
    response = api_client.post("/import/brand-kit", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] is True
    assert body["tenant_id"] == "meridian-flow"
    assert body["rule_count"] == 18
    assert body["glossary_count"] == 24
    assert body["fact_count"] == 14
    assert body["palette_count"] == 6
    assert body["logo_count"] == 2
    assert body["licensed_asset_count"] == 1
    assert len(body["content_hash"]) == 64


def test_api_import_idempotent_noop(api_client):
    """Re-importing the same kit returns created=false (idempotent no-op)."""
    payload = json.loads(MERIDIAN_FLOW_KIT.model_dump_json())
    r1 = api_client.post("/import/brand-kit", json=payload)
    r2 = api_client.post("/import/brand-kit", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["content_hash"] == r2.json()["content_hash"]
    assert r1.json()["created"] is True
    assert r2.json()["created"] is False


# ---------------------------------------------------------------------------
# FastAPI stub: POST /review  (T1 round-trip through API)
# ---------------------------------------------------------------------------


def test_api_review_endpoint_round_trip(api_client):
    """POST /review round-trips through FastAPI and returns a valid ReviewResult."""
    payload = {
        "revision_units": [
            {
                "unit_id": "u_01",
                "revision_id": "rev_api_001",
                "kind": "paragraph",
                "text": "Over 10,000+ customers trust the MFP platform.",
                "start": 0,
                "end": 47,
                "page": 1,
            }
        ],
        "ruleset_version": 1,
        "policy": "internal",
        "intent_card": {
            "purpose": "Homepage hero",
            "audience": "Enterprise buyers",
            "key_message": "Scale compliance with confidence",
            "cta": "Start free trial",
        },
    }
    response = api_client.post("/review", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()

    # Must be a ReviewResult-shaped object
    assert body["revision_id"] == "rev_api_001"
    assert body["ruleset_version"] == 1
    assert body["sensitivity"] == "internal"
    assert isinstance(body["findings"], list)
    assert len(body["findings"]) >= 1
    assert body["partial"] is False

    # Finding shape (T3 contract)
    finding = body["findings"][0]
    assert "finding_id" in finding
    assert "type" in finding
    assert "severity" in finding
    assert "confidence" in finding
    assert "span" in finding
    assert "explanation" in finding
    assert "route_to" in finding
    assert "disclosure" in finding


def test_api_health(api_client):
    """GET /health and GET /healthz return ok."""
    r1 = api_client.get("/health")
    assert r1.status_code == 200
    assert r1.json()["status"] == "ok"

    r2 = api_client.get("/healthz")
    assert r2.status_code == 200
    assert r2.json()["status"] == "ok"


def test_api_get_brand_kit_after_import(api_client):
    """GET /brand-kit returns summary of loaded kit."""
    payload = json.loads(MERIDIAN_FLOW_KIT.model_dump_json())
    imp_res = api_client.post("/import/brand-kit", json=payload)
    assert imp_res.status_code == 200

    res = api_client.get("/brand-kit")
    assert res.status_code == 200
    body = res.json()
    assert body["tenant_id"] == "meridian-flow"
    assert body["rules_count"] == 18
    assert body["glossary_count"] == 24
    assert body["facts_count"] == 14
    assert body["palette_count"] == 6
    assert body["logos_count"] == 2
    assert body["licensed_assets_count"] == 1


def test_api_review_with_units_field(api_client):
    """POST /review also accepts units field (compatibility)."""
    payload = {
        "revision_id": "rev_api_compat",
        "units": [
            {
                "unit_id": "u_02",
                "revision_id": "rev_api_compat",
                "kind": "paragraph",
                "text": "Meridian Flow guarantees 99.95% uptime.",
                "start": 0,
                "end": 39,
            }
        ],
        "ruleset_version": 1,
    }
    response = api_client.post("/review", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["revision_id"] == "rev_api_compat"
    assert len(body["findings"]) >= 1

