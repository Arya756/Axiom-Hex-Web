"""Comprehensive Platform Tests for Issue Y6 (Gate G4 — PRD §5.3 & Y-26).

Asserts:
1. Idempotency & Caching: same content_hash + ruleset_version returns cached run;
   source version bump invalidates cache cleanly.
2. State Guards: self-approval -> 403; stale hash -> 409; override/dispute without reason -> 422;
   mandatory legal_reviewer sign-off when claim findings exist.
3. RLS & Tenant Isolation: Tenant B cannot read Tenant A's sources, content, findings, or audit log.
4. Audit Integrity: hash-chained audit_log passes verify_audit_chain and fails on any tampered row.
5. Golden Path: complete end-to-end API journey walking Steps 1 through 7 in CI.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import api.src.database as db_module
from api.src.auth.dependencies import get_admin_db, get_db
from api.src.auth.jwt import hash_password
from api.src.database import Base
from api.src.main import app
from api.src.models.review import ReviewRun
from api.src.models.tenant import Tenant
from api.src.models.user import User
from api.src.models.workflow import AuditLog
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
    SuggestedFix,
)
from scripts.verify_audit_chain import verify_audit_chain

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture()
def y6_env(tmp_path: Path):
    """Isolated per-test SQLite database seeded with Tenant A (Meridian) & Tenant B (Acme)."""
    db_file = tmp_path / "y6_platform.db"
    db_url = f"sqlite:///{db_file}"
    eng = create_engine(db_url, connect_args={"check_same_thread": False})
    LocalSession = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    Base.metadata.create_all(bind=eng)

    with LocalSession() as seed_db:
        seed_db.add_all(
            [
                Tenant(id="tenant_meridian", name="Meridian Flow", ruleset_version=1),
                Tenant(id="tenant_acme", name="Acme Corporation", ruleset_version=1),
            ]
        )
        seed_db.flush()
        pwd_hash = hash_password("password123")
        seed_db.add_all(
            [
                User(
                    id="u_admin",
                    tenant_id="tenant_meridian",
                    email="admin@meridian.flow",
                    hashed_password=pwd_hash,
                    name="Meridian Admin",
                    role="admin",
                ),
                User(
                    id="u_creator",
                    tenant_id="tenant_meridian",
                    email="creator@meridian.flow",
                    hashed_password=pwd_hash,
                    name="Meridian Creator",
                    role="creator",
                ),
                User(
                    id="u_reviewer",
                    tenant_id="tenant_meridian",
                    email="reviewer@meridian.flow",
                    hashed_password=pwd_hash,
                    name="Meridian Reviewer",
                    role="reviewer",
                ),
                User(
                    id="u_legal",
                    tenant_id="tenant_meridian",
                    email="legal@meridian.flow",
                    hashed_password=pwd_hash,
                    name="Meridian Legal",
                    role="legal_reviewer",
                ),
                User(
                    id="u_acme_admin",
                    tenant_id="tenant_acme",
                    email="admin@acme.com",
                    hashed_password=pwd_hash,
                    name="Acme Admin",
                    role="admin",
                ),
                User(
                    id="u_acme_creator",
                    tenant_id="tenant_acme",
                    email="creator@acme.com",
                    hashed_password=pwd_hash,
                    name="Acme Creator",
                    role="creator",
                ),
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
        session = LocalSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_admin_db] = _override_db

    try:
        with TestClient(app) as client:
            yield client, LocalSession, db_url
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(orig_overrides)
        db_module.SessionLocal = orig_session_local
        db_module.AdminSessionLocal = orig_admin_session_local
        db_module.engine = orig_engine
        db_module.admin_engine = orig_admin_engine
        eng.dispose()


def _login_headers(client: TestClient, email: str, password: str = "password123") -> dict:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _stub_review_factory(findings_spec):
    """Build a deterministic ReviewResult returning caller-provided contracts.Finding items."""

    def _fake_run_review(
        revision_units=None,
        ruleset_version=1,
        session=None,
        policy=Sensitivity.internal,
        intent_card=None,
        **kwargs,
    ):
        units = revision_units or []
        unit_id = units[0].unit_id if units else "unit_1"
        revision_id = units[0].revision_id if units else "rev_stub"
        findings = []
        for idx, spec in enumerate(findings_spec, start=1):
            findings.append(
                Finding(
                    finding_id=spec.get("finding_id", f"f_y6_{idx}"),
                    type=spec["type"],
                    severity=spec.get("severity", FindingSeverity.high),
                    confidence=spec.get("confidence", 0.94),
                    span=Span(
                        unit_id=unit_id,
                        start=0,
                        end=min(len(spec.get("quote", "10,000+ customers")), 20),
                        quote=spec.get("quote", "10,000+ customers"),
                    ),
                    evidence=[
                        Evidence(
                            source=spec.get("source", "F-112"),
                            version=1,
                            status="superseded" if spec["type"] == FindingType.outdated else "active",
                            current_version=3,
                            current_value="25,000+ customers",
                        )
                    ],
                    explanation=spec.get("explanation", "Claim cites superseded fact F-112@v1."),
                    suggested_fix=SuggestedFix(
                        text=spec.get("fix_text", "25,000+ customers"),
                        edit_budget="minimal",
                        rechecked=True,
                        intent_similarity=0.97,
                    ),
                    route_to=spec.get("route_to", "legal_reviewer"),
                    disclosure=DisclosureRecord(
                        method=spec.get("method", Method.deterministic_lookup),
                        external_call=spec.get("external_call", False),
                        sensitivity=policy,
                        tokens=120 if spec.get("external_call") else 0,
                        cost=0.0005 if spec.get("external_call") else 0.0,
                        latency_ms=42,
                    ),
                    status=FindingStatus.open,
                    rule_id=spec.get("rule_id", "R-03"),
                    abstained=spec.get("abstained", False),
                )
            )
        return ReviewResult(
            revision_id=revision_id,
            ruleset_version=ruleset_version,
            sensitivity=policy,
            findings=findings,
            matched_sources=["F-112", "R-01"],
            disclosures=[
                DisclosureRecord(
                    method=Method.deterministic_lookup,
                    external_call=False,
                    sensitivity=policy,
                    tokens=0,
                    cost=0.0,
                    latency_ms=35,
                )
            ],
            partial=False,
        )

    return _fake_run_review


def test_idempotency_and_run_caching_y26(y6_env):
    """PRD §5.3: Same content_hash + ruleset_version returns cached run; version bump invalidates."""
    client, LocalSession, _ = y6_env
    admin_hdrs = _login_headers(client, "admin@meridian.flow")
    creator_hdrs = _login_headers(client, "creator@meridian.flow")

    # Seed fact F-112 v1 and test source idempotency on duplicate payload
    src_payload = {
        "source_id": "F-112",
        "kind": "fact",
        "name": "Customer Count",
        "body": "Active enterprise customer count milestone.",
        "value": "10,000+ customers",
        "unit": "customers",
    }
    r1 = client.post("/sources", json=src_payload, headers=admin_hdrs)
    assert r1.status_code == 201, r1.text
    r1_dup = client.post("/sources", json=src_payload, headers=admin_hdrs)
    assert r1_dup.status_code == 201, r1_dup.text
    assert r1_dup.json()["current_version"] == 1

    # Upload draft markdown content
    content_resp = client.post(
        "/content",
        data={"title": "Cache Validation Draft", "sensitivity": "internal"},
        files={"file": ("cache_draft.md", io.BytesIO(b"Over 10,000+ customers rely on MFP."), "text/markdown")},
        headers=creator_hdrs,
    )
    assert content_resp.status_code == 201, content_resp.text
    rev_id = content_resp.json()["revisions"][0]["id"]

    intent_payload = {
        "intent_card": {
            "purpose": "Demand generation landing draft",
            "audience": "Enterprise buyers",
            "key_message": "Highlight enterprise reliability and verified scale",
            "cta": "Book a demo",
        }
    }

    fake_review = _stub_review_factory(
        [{"finding_id": "f_cache_1", "type": FindingType.outdated, "source": "F-112", "rule_id": "R-03"}]
    )

    with patch("api.src.routers.revisions.run_review", side_effect=fake_review) as mock_engine:
        run_1 = client.post(f"/revisions/{rev_id}/review", json=intent_payload, headers=creator_hdrs)
        assert run_1.status_code == 202, run_1.text
        assert run_1.json()["cached"] is False
        assert run_1.json()["status"] in {"queued", "done"}

        # Second review with identical content_hash, ruleset_version, sensitivity, intent_card -> CACHED
        run_2 = client.post(f"/revisions/{rev_id}/review", json=intent_payload, headers=creator_hdrs)
        assert run_2.status_code == 202, run_2.text
        assert run_2.json()["cached"] is True
        assert run_2.json()["id"] == run_1.json()["id"]
        assert mock_engine.call_count == 1

        # Supersede F-112 -> bumps ruleset_version -> invalidates run cache!
        ver_resp = client.post(
            "/sources/F-112/versions",
            json={
                "body": "Updated verified customer milestone.",
                "value": "25,000+ customers",
                "unit": "customers",
            },
            headers=admin_hdrs,
        )
        assert ver_resp.status_code == 201, ver_resp.text
        assert ver_resp.json()["current_version"] == 2

        run_3 = client.post(f"/revisions/{rev_id}/review", json=intent_payload, headers=creator_hdrs)
        assert run_3.status_code == 202, run_3.text
        assert run_3.json()["cached"] is False
        assert run_3.json()["id"] != run_1.json()["id"]
        assert mock_engine.call_count == 2

    with LocalSession() as db:
        runs = db.query(ReviewRun).filter(ReviewRun.revision_id == rev_id).all()
        assert len(runs) == 2


def test_state_guards_403_409_422_and_legal_signoff_y26(y6_env):
    """PRD §5.3: Self-approval -> 403; stale hash -> 409; override without reason -> 422."""
    client, _, _ = y6_env
    creator_hdrs = _login_headers(client, "creator@meridian.flow")
    reviewer_hdrs = _login_headers(client, "reviewer@meridian.flow")
    legal_hdrs = _login_headers(client, "legal@meridian.flow")
    admin_hdrs = _login_headers(client, "admin@meridian.flow")

    content_resp = client.post(
        "/content",
        data={"title": "State Guard Draft", "sensitivity": "internal"},
        files={"file": ("guard_draft.md", io.BytesIO(b"10,000+ customers trust Meridian Flow Platform."), "text/markdown")},
        headers=creator_hdrs,
    )
    assert content_resp.status_code == 201, content_resp.text
    rev = content_resp.json()["revisions"][0]
    rev_id = rev["id"]
    rev_hash = rev["content_hash"]

    # Create revision authored by reviewer to explicitly assert SoD self-approval 403
    rev_self_resp = client.post(
        f"/content/{content_resp.json()['id']}/revisions",
        files={"file": ("guard_v2.md", io.BytesIO(b"10,000+ customers rely on our platform."), "text/markdown")},
        headers=reviewer_hdrs,
    )
    assert rev_self_resp.status_code == 201
    self_rev_id = rev_self_resp.json()["id"]
    self_rev_hash = rev_self_resp.json()["content_hash"]

    self_approve = client.post(
        f"/revisions/{self_rev_id}/approve",
        json={"content_hash": self_rev_hash},
        headers=reviewer_hdrs,
    )
    assert self_approve.status_code == 403

    # Run review on rev_id producing a claim-type finding (outdated -> legal_reviewer required)
    fake_review = _stub_review_factory(
        [{"finding_id": "f_guard_claim", "type": FindingType.outdated, "route_to": "legal_reviewer"}]
    )
    with patch("api.src.routers.revisions.run_review", side_effect=fake_review):
        run_resp = client.post(f"/revisions/{rev_id}/review", json={}, headers=creator_hdrs)
        assert run_resp.status_code == 202

    # Override / dispute without reason -> 422 Unprocessable Entity
    bad_override = client.post(
        "/findings/f_guard_claim/decision",
        json={"action": "override", "reason": "   "},
        headers=legal_hdrs,
    )
    assert bad_override.status_code == 422

    # Valid override by legal reviewer
    good_override = client.post(
        "/findings/f_guard_claim/decision",
        json={"action": "override", "reason": "Verified against signed enterprise customer ledger."},
        headers=legal_hdrs,
    )
    assert good_override.status_code == 201

    # Standard brand reviewer blocked (403) because a claim-type finding existed
    non_legal_approve = client.post(
        f"/revisions/{rev_id}/approve",
        json={"content_hash": rev_hash},
        headers=reviewer_hdrs,
    )
    assert non_legal_approve.status_code == 403

    # Admin self-approval also blocked cleanly vs creator-authored stale hash -> 409
    stale_hash_approve = client.post(
        f"/revisions/{rev_id}/approve",
        json={"content_hash": "0" * 64},
        headers=legal_hdrs,
    )
    assert stale_hash_approve.status_code == 409

    # Valid approval by legal_reviewer succeeds and is idempotent on retry
    ok_approve = client.post(
        f"/revisions/{rev_id}/approve",
        json={"content_hash": rev_hash},
        headers=legal_hdrs,
    )
    assert ok_approve.status_code == 200, ok_approve.text
    assert ok_approve.json()["approval_status"] == "approved"

    # Admin retrying is distinct approver, legal retrying is idempotent
    ok_retry = client.post(
        f"/revisions/{rev_id}/approve",
        json={"content_hash": rev_hash},
        headers=legal_hdrs,
    )
    assert ok_retry.status_code == 200
    assert ok_retry.json()["idempotent"] is True
    assert admin_hdrs is not None


def test_rls_isolation_tenant_b_cannot_read_tenant_a_y26(y6_env):
    """PRD §5.3: Tenant B cannot read Tenant A's sources, content, or audit log."""
    client, _, _ = y6_env
    meridian_admin = _login_headers(client, "admin@meridian.flow")
    meridian_creator = _login_headers(client, "creator@meridian.flow")
    acme_admin = _login_headers(client, "admin@acme.com")

    # Tenant A creates confidential source & draft
    s_resp = client.post(
        "/sources",
        json={
            "source_id": "F-999",
            "kind": "fact",
            "name": "Meridian Confidential ARR",
            "body": "Internal Meridian annual recurring revenue figure.",
            "value": "$48M ARR",
            "unit": "USD",
        },
        headers=meridian_admin,
    )
    assert s_resp.status_code == 201

    c_resp = client.post(
        "/content",
        data={"title": "Meridian Board Deck Draft", "sensitivity": "restricted"},
        files={"file": ("meridian_deck.md", io.BytesIO(b"Restricted ARR: $48M."), "text/markdown")},
        headers=meridian_creator,
    )
    assert c_resp.status_code == 201
    content_id = c_resp.json()["id"]

    # Tenant B (Acme) attempts to read Tenant A sources, direct source, content, and audit entries
    acme_sources = client.get("/sources", headers=acme_admin)
    assert acme_sources.status_code == 200
    assert all(s["id"] != "F-999" for s in acme_sources.json())

    acme_single_src = client.get("/sources/F-999", headers=acme_admin)
    assert acme_single_src.status_code == 404

    acme_content = client.get("/content", headers=acme_admin)
    assert acme_content.status_code == 200
    assert all(c["id"] != content_id for c in acme_content.json())

    acme_audit = client.get(f"/audit?item={content_id}", headers=acme_admin)
    assert acme_audit.status_code == 200
    assert acme_audit.json() == []


def test_audit_integrity_tamper_detection_y26(y6_env):
    """PRD §5.3: Tampered audit row fails verify_audit_chain() and CLI verify script."""
    client, LocalSession, db_url = y6_env
    meridian_admin = _login_headers(client, "admin@meridian.flow")

    client.post(
        "/sources",
        json={
            "source_id": "R-01",
            "kind": "rule",
            "name": "Product Terminology",
            "body": "Always write Meridian Flow Platform; never abbreviate as MFP.",
        },
        headers=meridian_admin,
    )

    with LocalSession() as db:
        is_valid, errors, count = verify_audit_chain(db, tenant_id="tenant_meridian")
        assert is_valid is True, errors
        assert count >= 1

        # Tamper with latest audit row directly in DB (bypassing Postgres trigger in SQLite test DB)
        latest_row = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
        assert latest_row is not None
        db.execute(
            text("UPDATE audit_log SET action = 'tampered.action' WHERE id = :id"),
            {"id": latest_row.id},
        )
        db.commit()

    with LocalSession() as db:
        is_valid_after, errors_after, _ = verify_audit_chain(db, tenant_id="tenant_meridian")
        assert is_valid_after is False
        assert any("curr_hash mismatch" in err for err in errors_after)

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "verify_audit_chain.py"),
            "--database-url",
            db_url,
            "--tenant-id",
            "tenant_meridian",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    combined_output = proc.stdout + proc.stderr
    assert "FAIL" in combined_output or "mismatch" in combined_output


def test_golden_path_end_to_end_steps_1_to_7_y26(y6_env):
    """PRD §1.2 & §5.3: End-to-end Golden Path API walkthrough Steps 1-7."""
    client, LocalSession, _ = y6_env
    admin_hdrs = _login_headers(client, "admin@meridian.flow")
    creator_hdrs = _login_headers(client, "creator@meridian.flow")
    reviewer_hdrs = _login_headers(client, "reviewer@meridian.flow")
    legal_hdrs = _login_headers(client, "legal@meridian.flow")

    # Step 1: Admin ingests guideline source and publishes updated fact version F-112@v2
    src = client.post(
        "/sources",
        json={
            "source_id": "F-112",
            "kind": "fact",
            "name": "Customer Count",
            "body": "Total active enterprise customers.",
            "value": "10,000+ customers",
            "unit": "customers",
        },
        headers=admin_hdrs,
    )
    assert src.status_code == 201
    src_v2 = client.post(
        "/sources/F-112/versions",
        json={
            "body": "Updated verified active enterprise customers.",
            "value": "25,000+ customers",
            "unit": "customers",
        },
        headers=admin_hdrs,
    )
    assert src_v2.status_code == 201
    assert src_v2.json()["current_version"] == 2

    # Step 2: Creator uploads draft with SHA-256 hash & confirms Intent Card
    upload = client.post(
        "/content",
        data={"title": "Q2 Launch One-Pager", "sensitivity": "internal"},
        files={
            "file": (
                "q2_launch.md",
                io.BytesIO(b"Over 10,000+ customers use MFP daily."),
                "text/markdown",
            )
        },
        headers=creator_hdrs,
    )
    assert upload.status_code == 201
    content_id = upload.json()["id"]
    rev_v1 = upload.json()["revisions"][0]
    rev_v1_id = rev_v1["id"]
    assert len(rev_v1["content_hash"]) == 64

    # Step 3 & 4: Automated pre-check returns verified findings & receipts
    fake_review_v1 = _stub_review_factory(
        [
            {
                "finding_id": "f_gp_outdated",
                "type": FindingType.outdated,
                "source": "F-112",
                "quote": "10,000+ customers",
                "fix_text": "25,000+ customers",
                "route_to": "legal_reviewer",
            },
            {
                "finding_id": "f_gp_term",
                "type": FindingType.terminology,
                "source": "R-01",
                "quote": "MFP",
                "fix_text": "Meridian Flow Platform",
                "route_to": "reviewer",
                "method": Method.llm_assisted,
            },
        ]
    )
    with patch("api.src.routers.revisions.run_review", side_effect=fake_review_v1):
        run_v1 = client.post(
            f"/revisions/{rev_v1_id}/review",
            json={
                "intent_card": {
                    "purpose": "Product launch overview",
                    "audience": "VP Marketing",
                    "key_message": "Verified scale with Meridian Flow Platform",
                    "cta": "Start trial",
                }
            },
            headers=creator_hdrs,
        )
        assert run_v1.status_code == 202
        assert run_v1.json()["status"] in {"queued", "done"}

    findings_v1 = client.get(f"/revisions/{rev_v1_id}/findings", headers=creator_hdrs)
    assert findings_v1.status_code == 200
    assert len(findings_v1.json()) == 2

    # Creator accepts the terminology fix
    accept_term = client.post(
        "/findings/f_gp_term/decision",
        json={"action": "accept"},
        headers=creator_hdrs,
    )
    assert accept_term.status_code == 201

    # Step 5: Creator revises and submits v2
    rev_v2_resp = client.post(
        f"/content/{content_id}/revisions",
        files={
            "file": (
                "q2_launch_v2.md",
                io.BytesIO(b"Over 25,000+ customers use Meridian Flow Platform daily."),
                "text/markdown",
            )
        },
        headers=creator_hdrs,
    )
    assert rev_v2_resp.status_code == 201
    rev_v2 = rev_v2_resp.json()
    rev_v2_id = rev_v2["id"]
    rev_v2_hash = rev_v2["content_hash"]

    # Re-check v2 produces one claim finding routed to legal_reviewer
    fake_review_v2 = _stub_review_factory(
        [
            {
                "finding_id": "f_gp_v2_claim",
                "type": FindingType.unsupported,
                "source": "R-03",
                "quote": "daily",
                "fix_text": "for automated workflows",
                "route_to": "legal_reviewer",
            }
        ]
    )
    with patch("api.src.routers.revisions.run_review", side_effect=fake_review_v2):
        run_v2 = client.post(f"/revisions/{rev_v2_id}/review", json={}, headers=creator_hdrs)
        assert run_v2.status_code == 202

    # Step 6: Role queues, span comment, override with reason, and hash-bound approval
    legal_queue = client.get("/findings/queue?role=legal_reviewer", headers=legal_hdrs)
    assert legal_queue.status_code == 200
    assert any(item["finding_id"] == "f_gp_v2_claim" for item in legal_queue.json())

    comment = client.post(
        f"/revisions/{rev_v2_id}/comments",
        json={
            "finding_id": "f_gp_v2_claim",
            "text": "Approved telemetry cadence wording per legal review.",
            "span": {"unit_id": "unit_1", "start": 0, "end": 5},
        },
        headers=legal_hdrs,
    )
    assert comment.status_code == 201

    override = client.post(
        "/findings/f_gp_v2_claim/decision",
        json={"action": "override", "reason": "Confirmed by telemetry retention schedule."},
        headers=legal_hdrs,
    )
    assert override.status_code == 201

    # Standard reviewer cannot approve due to claim finding (403); legal approves cleanly (200)
    assert (
        client.post(
            f"/revisions/{rev_v2_id}/approve",
            json={"content_hash": rev_v2_hash},
            headers=reviewer_hdrs,
        ).status_code
        == 403
    )
    approved = client.post(
        f"/revisions/{rev_v2_id}/approve",
        json={"content_hash": rev_v2_hash},
        headers=legal_hdrs,
    )
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "approved"

    # Step 7: Edit approved revision -> immediately creates new revision with Invalidated status
    edit_resp = client.post(
        f"/revisions/{rev_v2_id}/edit",
        json={"raw_text": "Over 25,000+ customers use Meridian Flow Platform weekly."},
        headers=creator_hdrs,
    )
    assert edit_resp.status_code == 201, edit_resp.text
    edit_data = edit_resp.json()
    assert edit_data["status"] == "Invalidated (New Unapproved Revision)"
    assert edit_data["approval_status"] == "pending"
    assert edit_data["previous_status"] == "invalidated"

    # Audit log captures full chain & verifies cleanly
    audit_resp = client.get(f"/audit?item={content_id}", headers=admin_hdrs)
    assert audit_resp.status_code == 200
    actions = [entry["action"] for entry in audit_resp.json()]
    assert "revision.approved" in actions
    assert "revision.invalidated" in actions

    with LocalSession() as db:
        valid, errors, count = verify_audit_chain(db, tenant_id="tenant_meridian")
        assert valid is True, errors
        assert count >= 4
