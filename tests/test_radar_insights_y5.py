import io
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import api.src.database as db_module
from api.src.auth.dependencies import get_admin_db, get_db
from api.src.auth.jwt import hash_password
from api.src.database import Base
from api.src.main import app
from api.src.models.tenant import Tenant
from api.src.models.user import User
from api.src.models.workflow import RuleStat
from contracts import (
    DisclosureRecord,
    Evidence,
    Finding,
    FindingSeverity,
    FindingStatus,
    FindingType,
    Method,
    ReviewResult,
    Sensitivity,
    Span,
)
from scripts.generate_synthetic_history import run_synthetic_history


@pytest.fixture()
def y5_env(tmp_path: Path):
    """Isolated database and TestClient for Y5 tests so shared test_sources fixtures remain pristine."""
    db_url = f"sqlite:///{tmp_path / 'y5_test.db'}"
    eng = create_engine(db_url, connect_args={"check_same_thread": False})
    LocalSession = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    Base.metadata.create_all(bind=eng)

    with LocalSession() as seed_db:
        seed_db.add(Tenant(id="tenant_meridian", name="Meridian Flow", ruleset_version=1))
        seed_db.flush()
        pwd_hash = hash_password("password123")
        seed_db.add_all(
            [
                User(id="u_admin", tenant_id="tenant_meridian", email="admin@meridian.flow", hashed_password=pwd_hash, name="Admin", role="admin"),
                User(id="u_creator", tenant_id="tenant_meridian", email="creator@meridian.flow", hashed_password=pwd_hash, name="Creator", role="creator"),
                User(id="u_reviewer", tenant_id="tenant_meridian", email="reviewer@meridian.flow", hashed_password=pwd_hash, name="Reviewer", role="reviewer"),
                User(id="u_legal", tenant_id="tenant_meridian", email="legal@meridian.flow", hashed_password=pwd_hash, name="Legal", role="legal_reviewer"),
            ]
        )
        seed_db.commit()

    orig_session_local = db_module.SessionLocal
    orig_admin_session_local = db_module.AdminSessionLocal
    orig_engine = db_module.engine
    orig_admin_engine = db_module.admin_engine
    orig_overrides = dict(app.dependency_overrides)

    db_module.SessionLocal = LocalSession
    db_module.AdminSessionLocal = LocalSession
    db_module.engine = eng
    db_module.admin_engine = eng

    def _override_db():
        s = LocalSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_admin_db] = _override_db

    with LocalSession() as db_sess, TestClient(app) as c:
        try:
            yield c, db_sess
        finally:
            app.dependency_overrides = orig_overrides
            db_module.SessionLocal = orig_session_local
            db_module.AdminSessionLocal = orig_admin_session_local
            db_module.engine = orig_engine
            db_module.admin_engine = orig_admin_engine
            eng.dispose()


def _login(client: TestClient, email: str, password: str = "password123") -> dict:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_ambiguity_radar_flags_ambiguous_rules_with_zero_false_flags(y5_env):
    """Y-21, Y-24, I3: Synthetic history via real endpoints flags >=3/4 ambiguous rules and 0/4 clear controls."""
    client, db_session = y5_env
    admin_hdrs = _login(client, "admin@meridian.flow")

    gen_summary = run_synthetic_history(client, password="password123")
    assert gen_summary["created_findings"] >= 32
    assert gen_summary["created_decisions"] >= 32

    # Verify rule_stats table was populated via live API activity
    rule_stat_rows = (
        db_session.query(RuleStat)
        .filter(RuleStat.tenant_id == "tenant_meridian")
        .all()
    )
    stat_rule_ids = {r.rule_id for r in rule_stat_rows}
    assert {"R-01", "R-02", "R-03", "R-04", "R-07", "R-11", "R-14", "R-16"}.issubset(stat_rule_ids)

    radar_resp = client.get("/insights/radar", headers=admin_hdrs)
    assert radar_resp.status_code == 200, radar_resp.text
    radar = radar_resp.json()

    # Alias route /radar must match
    alias_resp = client.get("/radar", headers=admin_hdrs)
    assert alias_resp.status_code == 200
    assert alias_resp.json()["summary"] == radar["summary"]

    summary = radar["summary"]
    assert summary["seeded_ambiguous_flagged_count"] >= 3
    assert summary["seeded_ambiguous_flagged_count"] == 4
    assert summary["control_rules_evaluated"] >= 4
    assert summary["false_flags"] == 0
    assert summary["false_flag_rate"] == 0.0
    assert summary["contains_synthetic"] is True
    assert summary["total_synthetic_findings"] >= 32

    rules_by_id = {r["rule_id"]: r for r in radar["rules"]}

    # Verify clear control rules R-01..R-04 are not false-flagged
    for control_id in ("R-01", "R-02", "R-03", "R-04"):
        assert rules_by_id[control_id]["flagged"] is False
        assert rules_by_id[control_id]["is_control"] is True

    # Verify seeded ambiguous rules have evidence: non-zero signal counts, flag reasons, and example findings
    for ambig_id in ("R-07", "R-11", "R-14", "R-16"):
        entry = rules_by_id[ambig_id]
        assert entry["flagged"] is True
        assert entry["is_synthetic"] is True
        assert len(entry["flag_reasons"]) >= 1
        assert entry["signals"]["total_findings"] >= 4
        assert len(entry["example_findings"]) >= 1
        assert entry["example_findings"][0]["is_synthetic"] is True
        assert entry["example_findings"][0]["quote"] != ""

    # Check specific dominant signal per seeded ambiguous rule
    assert rules_by_id["R-07"]["signals"]["override_dispute_rate"] >= 0.50
    assert rules_by_id["R-07"]["signals"]["missing_owner"] is True
    assert rules_by_id["R-11"]["signals"]["abstain_rate"] >= 0.50
    assert rules_by_id["R-14"]["signals"]["disagreement_count"] >= 2
    assert "R-03" in rules_by_id["R-16"]["signals"]["collisions"]


def test_impact_analysis_matches_hand_derived_lists_for_two_source_changes(y5_env):
    """Y-22, I3.3, I3.4: GET /impact?source_id= matches hand-derived lists incl. Supported claims."""
    client, _ = y5_env
    admin_hdrs = _login(client, "admin@meridian.flow")
    creator_hdrs = _login(client, "creator@meridian.flow")
    reviewer_hdrs = _login(client, "reviewer@meridian.flow")

    # Seed facts F-112 (Customer Count) and F-108 (Uptime SLA) cleanly via /sources
    client.post(
        "/sources",
        json={
            "source_id": "F-112",
            "kind": "fact",
            "name": "Customer Count",
            "body": "Meridian Flow serves 18,000+ enterprise customers.",
            "value": "18,000+",
            "unit": "customers",
        },
        headers=admin_hdrs,
    )
    client.post(
        "/sources",
        json={
            "source_id": "F-108",
            "kind": "fact",
            "name": "Uptime SLA",
            "body": "Enterprise SLA ensures 99.9% uptime.",
            "value": "99.9%",
            "unit": "availability",
        },
        headers=admin_hdrs,
    )

    def _upload(title: str, body: bytes) -> tuple[str, dict]:
        resp = client.post(
            "/content",
            data={"title": title, "sensitivity": "internal"},
            files={"file": (f"{title.lower().replace(' ', '_')}.md", io.BytesIO(body), "text/markdown")},
            headers=creator_hdrs,
        )
        assert resp.status_code == 201
        d = resp.json()
        return d["id"], d["revisions"][0]

    # Doc A: In-review, cleanly passes F-112 (Supported claim -> matched_sources=['F-112'], 0 findings)
    cid_a, rev_a = _upload("Impact Doc A Supported", b"Meridian Flow serves 18,000+ customers.")
    res_a = ReviewResult(
        revision_id=rev_a["id"],
        ruleset_version=1,
        sensitivity=Sensitivity.internal,
        findings=[],
        matched_sources=["F-112"],
        partial=False,
        disclosures=[],
    )
    with patch("api.src.routers.revisions.run_review", return_value=res_a):
        client.post(f"/revisions/{rev_a['id']}/review", json={"sensitivity": "internal"}, headers=creator_hdrs)

    # Doc B: In-review, has an outdated finding citing F-112
    cid_b, rev_b = _upload("Impact Doc B Outdated", b"Meridian Flow serves 10,000+ customers.")
    res_b = ReviewResult(
        revision_id=rev_b["id"],
        ruleset_version=1,
        sensitivity=Sensitivity.internal,
        findings=[
            Finding(
                finding_id="f_imp_b1",
                type=FindingType.outdated,
                severity=FindingSeverity.high,
                confidence=0.95,
                span=Span(unit_id=f"u_{rev_b['id']}_1", start=0, end=17, quote="10,000+ customers"),
                evidence=[Evidence(source="F-112", version=1, status="superseded", current_value="18,000+")],
                explanation="Customer figure outdated.",
                route_to="legal_reviewer",
                disclosure=DisclosureRecord(
                    method=Method.deterministic_lookup,
                    sensitivity=Sensitivity.internal,
                    external_call=False,
                ),
                status=FindingStatus.open,
            )
        ],
        matched_sources=["F-112"],
        partial=False,
        disclosures=[],
    )
    with patch("api.src.routers.revisions.run_review", return_value=res_b):
        client.post(f"/revisions/{rev_b['id']}/review", json={"sensitivity": "internal"}, headers=creator_hdrs)

    # Doc C: Approved revision that referenced F-112 -> MUST be excluded from draft/in-review impact
    cid_c, rev_c = _upload("Impact Doc C Approved", b"Approved enterprise summary.")
    res_c = ReviewResult(
        revision_id=rev_c["id"],
        ruleset_version=1,
        sensitivity=Sensitivity.internal,
        findings=[],
        matched_sources=["F-112"],
        partial=False,
        disclosures=[],
    )
    with patch("api.src.routers.revisions.run_review", return_value=res_c):
        client.post(f"/revisions/{rev_c['id']}/review", json={"sensitivity": "internal"}, headers=creator_hdrs)
    apr_c = client.post(
        f"/revisions/{rev_c['id']}/approve",
        json={"content_hash": rev_c["content_hash"]},
        headers=reviewer_hdrs,
    )
    assert apr_c.status_code == 200

    # Doc D: In-review, references F-108 (Supported claim), NOT F-112
    cid_d, rev_d = _upload("Impact Doc D Uptime Only", b"99.9% uptime SLA.")
    res_d = ReviewResult(
        revision_id=rev_d["id"],
        ruleset_version=1,
        sensitivity=Sensitivity.internal,
        findings=[],
        matched_sources=["F-108"],
        partial=False,
        disclosures=[],
    )
    with patch("api.src.routers.revisions.run_review", return_value=res_d):
        client.post(f"/revisions/{rev_d['id']}/review", json={"sensitivity": "internal"}, headers=creator_hdrs)

    # Doc E: In-review, references F-108 (Supported claim)
    cid_e, rev_e = _upload("Impact Doc E Uptime SLA", b"Guaranteed 99.9% availability.")
    res_e = ReviewResult(
        revision_id=rev_e["id"],
        ruleset_version=1,
        sensitivity=Sensitivity.internal,
        findings=[],
        matched_sources=["F-108"],
        partial=False,
        disclosures=[],
    )
    with patch("api.src.routers.revisions.run_review", return_value=res_e):
        client.post(f"/revisions/{rev_e['id']}/review", json={"sensitivity": "internal"}, headers=creator_hdrs)

    # Source change #1: Admin updates F-112 to v2 (25,000+) -> check GET /impact?source_id=F-112
    ver_112 = client.post(
        "/sources/F-112/versions",
        json={"body": "Meridian Flow serves 25,000+ enterprise customers.", "value": "25,000+", "unit": "customers"},
        headers=admin_hdrs,
    )
    assert ver_112.status_code == 201

    impact_112_resp = client.get("/impact?source_id=F-112", headers=admin_hdrs)
    assert impact_112_resp.status_code == 200
    impact_112 = impact_112_resp.json()
    affected_112_ids = {item["content_id"] for item in impact_112["affected_items"]}
    # Hand-derived list: exactly Doc A (Supported claim) + Doc B (Finding evidence), excluding approved Doc C & unrelated Doc D/E
    assert affected_112_ids == {cid_a, cid_b}
    by_cid_112 = {item["content_id"]: item for item in impact_112["affected_items"]}
    assert by_cid_112[cid_a]["matched_via"] == "supported_claim"
    assert by_cid_112[cid_b]["matched_via"] == "finding_evidence"

    # Source change #2: Admin updates F-108 to v2 (99.95%) -> check GET /impact?source_id=F-108
    ver_108 = client.post(
        "/sources/F-108/versions",
        json={"body": "Enterprise SLA guarantees 99.95% high-availability uptime.", "value": "99.95%", "unit": "availability"},
        headers=admin_hdrs,
    )
    assert ver_108.status_code == 201

    impact_108_resp = client.get("/impact?source_id=F-108", headers=admin_hdrs)
    assert impact_108_resp.status_code == 200
    impact_108 = impact_108_resp.json()
    affected_108_ids = {item["content_id"] for item in impact_108["affected_items"]}
    # Hand-derived list: exactly Doc D + Doc E
    assert affected_108_ids == {cid_d, cid_e}


def test_recurring_insights_endpoint_y23(y5_env):
    """Y-23: GET /insights/recurring aggregates rules, types, severities, content hotspots, and synthetic flag."""
    client, _ = y5_env
    run_synthetic_history(client, password="password123")
    creator_hdrs = _login(client, "creator@meridian.flow")
    resp = client.get("/insights/recurring", headers=creator_hdrs)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "summary" in data
    assert data["summary"]["total_findings"] >= 1
    assert data["summary"]["contains_synthetic"] is True
    assert data["summary"]["synthetic_findings"] >= 1
    assert len(data["top_violated_rules"]) >= 1
    assert len(data["by_type"]) >= 1
    assert [s["severity"] for s in data["by_severity"]] == ["critical", "high", "medium", "low"]
    assert len(data["top_affected_content"]) >= 1
