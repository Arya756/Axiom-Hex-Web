import io
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from api.src.database import Base
from api.src.models.review import FindingModel
from api.src.models.tenant import Tenant
from api.src.models.workflow import Approval, AuditLog, UsageLedger
from api.src.services.governance import GENESIS_HASH, append_audit_log, route_finding_by_type
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
from scripts.verify_audit_chain import verify_audit_chain


def _login(client: TestClient, email: str, password: str = "password123") -> dict:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _upload_doc(
    client: TestClient,
    headers: dict,
    title: str = "Gov Test Doc",
    body: bytes = b"Meridian Flow helps teams ship compliant docs.",
) -> tuple[str, dict]:
    resp = client.post(
        "/content",
        data={"title": title, "sensitivity": "internal"},
        files={"file": ("gov_doc.md", io.BytesIO(body), "text/markdown")},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["id"], data["revisions"][0]


def test_finding_routing_rules_y12(client: TestClient, db_session: Session):
    """Y-12: Claim findings route to legal_reviewer; style/brand/visual route to reviewer."""
    assert route_finding_by_type("contradicted") == "legal_reviewer"
    assert route_finding_by_type("outdated") == "legal_reviewer"
    assert route_finding_by_type("unsupported") == "legal_reviewer"
    assert route_finding_by_type("terminology") == "reviewer"
    assert route_finding_by_type("violation") == "reviewer"
    assert route_finding_by_type("tone") == "reviewer"
    assert route_finding_by_type("accessibility") == "reviewer"
    assert route_finding_by_type("visual") == "reviewer"

    creator_hdrs = _login(client, "creator@meridian.flow")
    reviewer_hdrs = _login(client, "reviewer@meridian.flow")
    legal_hdrs = _login(client, "legal@meridian.flow")

    _, rev = _upload_doc(
        client,
        creator_hdrs,
        title="Routing Test",
        body=b"MFP serves 999 customers at 2024 pricing.",
    )
    rev_id = rev["id"]

    mock_result = ReviewResult(
        revision_id=rev_id,
        ruleset_version=1,
        sensitivity=Sensitivity.internal,
        findings=[
            Finding(
                finding_id="f_route_legal_1",
                type=FindingType.contradicted,
                severity=FindingSeverity.high,
                confidence=0.92,
                span=Span(unit_id=f"u_{rev_id}_1", start=0, end=10, quote="2024 price"),
                evidence=[Evidence(source="src_price", version=1, status="superseded", current_value="Updated 2026")],
                explanation="Pricing contradicted by current source.",
                route_to="creator",  # stub defaults to creator; API must override by Y-12 rules
                disclosure=DisclosureRecord(
                    method=Method.deterministic_lookup,
                    sensitivity=Sensitivity.internal,
                    external_call=False,
                ),
                status=FindingStatus.open,
            ),
            Finding(
                finding_id="f_route_rev_1",
                type=FindingType.terminology,
                severity=FindingSeverity.medium,
                confidence=0.88,
                span=Span(unit_id=f"u_{rev_id}_1", start=0, end=3, quote="MFP"),
                evidence=[Evidence(source="src_glossary", version=1, status="active", current_value="Meridian Flow")],
                explanation="Avoid abbreviation MFP.",
                route_to="creator",
                disclosure=DisclosureRecord(
                    method=Method.deterministic_lookup,
                    sensitivity=Sensitivity.internal,
                    external_call=False,
                ),
                status=FindingStatus.open,
            ),
        ],
        partial=False,
        disclosures=[],
        matched_sources=["src_price", "src_glossary"],
    )

    with patch("api.src.routers.revisions.run_review", return_value=mock_result):
        run_resp = client.post(
            f"/revisions/{rev_id}/review",
            json={"sensitivity": "internal"},
            headers=creator_hdrs,
        )
        assert run_resp.status_code == 202, run_resp.text

    # Filter findings by route_to on revision endpoint
    legal_rev_findings = client.get(
        f"/revisions/{rev_id}/findings?route_to=legal_reviewer",
        headers=legal_hdrs,
    )
    assert legal_rev_findings.status_code == 200
    assert [f["finding_id"] for f in legal_rev_findings.json()] == ["f_route_legal_1"]

    reviewer_rev_findings = client.get(
        f"/revisions/{rev_id}/findings?route_to=reviewer",
        headers=reviewer_hdrs,
    )
    assert reviewer_rev_findings.status_code == 200
    assert [f["finding_id"] for f in reviewer_rev_findings.json()] == ["f_route_rev_1"]

    # Role queue endpoints
    legal_queue = client.get("/findings/queue", headers=legal_hdrs)
    assert legal_queue.status_code == 200
    assert any(f["finding_id"] == "f_route_legal_1" for f in legal_queue.json())
    assert all(f["route_to"] == "legal_reviewer" for f in legal_queue.json())

    reviewer_queue = client.get("/findings/queue", headers=reviewer_hdrs)
    assert reviewer_queue.status_code == 200
    assert any(f["finding_id"] == "f_route_rev_1" for f in reviewer_queue.json())
    assert all(f["route_to"] == "reviewer" for f in reviewer_queue.json())


def test_approval_guards_sod_stale_hash_override_and_idempotency(
    client: TestClient, db_session: Session
):
    """Y-11 & Y-13: Self-approval 403, stale hash 409, override w/o reason 422, legal sign-off, idempotency."""
    creator_hdrs = _login(client, "creator@meridian.flow")
    reviewer_hdrs = _login(client, "reviewer@meridian.flow")
    legal_hdrs = _login(client, "legal@meridian.flow")

    _, rev = _upload_doc(
        client,
        creator_hdrs,
        title="Approval Guards Doc",
        body=b"MFP guarantees 100% uptime in 2024.",
    )
    rev_id = rev["id"]
    content_hash = rev["content_hash"]

    mock_result = ReviewResult(
        revision_id=rev_id,
        ruleset_version=1,
        sensitivity=Sensitivity.internal,
        findings=[
            Finding(
                finding_id="f_guard_claim",
                type=FindingType.outdated,
                severity=FindingSeverity.high,
                confidence=0.91,
                span=Span(unit_id=f"u_{rev_id}_1", start=0, end=11, quote="100% uptime"),
                evidence=[Evidence(source="src_sla", version=1, status="superseded", current_value="99.9% SLA")],
                explanation="Outdated SLA claim.",
                route_to="creator",
                disclosure=DisclosureRecord(
                    method=Method.deterministic_lookup,
                    sensitivity=Sensitivity.internal,
                    external_call=False,
                ),
                status=FindingStatus.open,
            )
        ],
        partial=False,
        disclosures=[],
        matched_sources=["src_sla"],
    )

    with patch("api.src.routers.revisions.run_review", return_value=mock_result):
        client.post(f"/revisions/{rev_id}/review", json={"sensitivity": "internal"}, headers=creator_hdrs)

    # 1. Self-approval returns 403
    self_approve = client.post(
        f"/revisions/{rev_id}/approve",
        json={"content_hash": content_hash},
        headers=creator_hdrs,
    )
    assert self_approve.status_code == 403

    # 2. Stale hash approval returns 409
    stale_hash_resp = client.post(
        f"/revisions/{rev_id}/approve",
        json={"content_hash": "deadbeef" * 8},
        headers=legal_hdrs,
    )
    assert stale_hash_resp.status_code == 409

    # 3. Overriding a finding without a reason returns 422
    override_no_reason = client.post(
        "/findings/f_guard_claim/decision",
        json={"action": "override", "reason": "   "},
        headers=legal_hdrs,
    )
    assert override_no_reason.status_code == 422

    # 4. Open findings block approval (409) even for legal_reviewer
    open_block = client.post(
        f"/revisions/{rev_id}/approve",
        json={"content_hash": content_hash},
        headers=legal_hdrs,
    )
    assert open_block.status_code == 409

    # Decide the claim finding validly
    decide_ok = client.post(
        "/findings/f_guard_claim/decision",
        json={"action": "override", "reason": "Confirmed updated SLA disclaimer in footer"},
        headers=legal_hdrs,
    )
    assert decide_ok.status_code == 201
    assert decide_ok.json()["finding_status"] == "overridden"

    # 5. Mandatory legal_reviewer sign-off: non-legal reviewer is blocked with 403
    reviewer_blocked = client.post(
        f"/revisions/{rev_id}/approve",
        json={"content_hash": content_hash},
        headers=reviewer_hdrs,
    )
    assert reviewer_blocked.status_code == 403

    # 6. Legal reviewer approves cleanly
    approve_1 = client.post(
        f"/revisions/{rev_id}/approve",
        json={"content_hash": content_hash, "comment": "Legal verified"},
        headers=legal_hdrs,
    )
    assert approve_1.status_code == 200, approve_1.text
    body_1 = approve_1.json()
    assert body_1["revision_status"] == "approved"
    assert body_1["approval_status"] == "approved"
    assert body_1["idempotent"] is False

    # 7. Idempotent approval replay (same revision_id, approver_id, content_hash)
    approve_2 = client.post(
        f"/revisions/{rev_id}/approve",
        json={"content_hash": content_hash, "comment": "Retry after network glitch"},
        headers=legal_hdrs,
    )
    assert approve_2.status_code == 200, approve_2.text
    body_2 = approve_2.json()
    assert body_2["id"] == body_1["id"]
    assert body_2["idempotent"] is True

    approvals_count = (
        db_session.query(Approval)
        .filter(
            Approval.revision_id == rev_id,
            Approval.approver_id == "u_legal",
            Approval.content_hash == content_hash,
        )
        .count()
    )
    assert approvals_count == 1

    approve_audits = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.entity_id == rev_id,
            AuditLog.action == "revision.approved",
        )
        .count()
    )
    assert approve_audits == 1


def test_editing_approved_revision_invalidates_and_creates_new_revision(
    client: TestClient, db_session: Session
):
    """Y-11: Editing an approved revision invalidates old revision & flips new status."""
    creator_hdrs = _login(client, "creator@meridian.flow")
    reviewer_hdrs = _login(client, "reviewer@meridian.flow")

    content_id, rev1 = _upload_doc(
        client,
        creator_hdrs,
        title="Invalidation Test Doc",
        body=b"Clean initial draft without claim issues.",
    )
    rev1_id = rev1["id"]

    # Non-claim review so regular reviewer can approve
    clean_result = ReviewResult(
        revision_id=rev1_id,
        ruleset_version=1,
        sensitivity=Sensitivity.internal,
        findings=[],
        partial=False,
        disclosures=[],
        matched_sources=[],
    )
    with patch("api.src.routers.revisions.run_review", return_value=clean_result):
        client.post(f"/revisions/{rev1_id}/review", json={"sensitivity": "internal"}, headers=creator_hdrs)

    apr_resp = client.post(
        f"/revisions/{rev1_id}/approve",
        json={"content_hash": rev1["content_hash"]},
        headers=reviewer_hdrs,
    )
    assert apr_resp.status_code == 200
    assert apr_resp.json()["revision_status"] == "approved"

    # Edit approved revision via POST /revisions/{id}/edit
    edit_resp = client.post(
        f"/revisions/{rev1_id}/edit",
        json={"raw_text": "Edited sentence added after approval.", "comment": "Added Q4 note"},
        headers=creator_hdrs,
    )
    assert edit_resp.status_code == 201, edit_resp.text
    rev2 = edit_resp.json()
    assert rev2["version_num"] == 2
    assert rev2["status"] == "Invalidated (New Unapproved Revision)"
    assert rev2["approval_status"] == "pending"
    assert rev2["content_hash"] != rev1["content_hash"]
    assert rev2["previous_revision_id"] == rev1_id
    assert rev2["previous_status"] == "invalidated"

    # Prior approved revision can no longer be approved
    reapprove_old = client.post(
        f"/revisions/{rev1_id}/approve",
        json={"content_hash": rev1["content_hash"]},
        headers=reviewer_hdrs,
    )
    assert reapprove_old.status_code == 409

    # New revision must go through approval flow cleanly
    new_apr = client.post(
        f"/revisions/{rev2['id']}/approve",
        json={"content_hash": rev2["content_hash"]},
        headers=reviewer_hdrs,
    )
    assert new_apr.status_code == 200
    assert new_apr.json()["revision_status"] == "approved"

    # Also test file re-upload invalidation path via POST /content/{id}/revisions
    reupload_resp = client.post(
        f"/content/{content_id}/revisions",
        files={"file": ("gov_doc_v3.md", io.BytesIO(b"Third uploaded revision."), "text/markdown")},
        headers=creator_hdrs,
    )
    assert reupload_resp.status_code == 201, reupload_resp.text
    rev3 = reupload_resp.json()
    assert rev3["version_num"] == 3
    assert rev3["status"] == "Invalidated (New Unapproved Revision)"
    assert rev3["approval_status"] == "pending"

    # Also test request-changes flow on rev3 -> changes_requested
    req_changes_empty = client.post(
        f"/revisions/{rev3['id']}/request-changes",
        json={"reason": "   "},
        headers=reviewer_hdrs,
    )
    assert req_changes_empty.status_code == 422

    req_changes = client.post(
        f"/revisions/{rev3['id']}/request-changes",
        json={"reason": "Clarify SLA wording"},
        headers=reviewer_hdrs,
    )
    assert req_changes.status_code == 200
    assert req_changes.json()["status"] == "changes_requested"


def test_audit_endpoint_and_tamper_detection_with_verify_script(
    client: TestClient, db_session: Session, tmp_path: Path
):
    """Y-14: GET /audit?item= returns linked hash chain; tampered row fails verify_audit_chain.py."""
    creator_hdrs = _login(client, "creator@meridian.flow")
    reviewer_hdrs = _login(client, "reviewer@meridian.flow")
    acme_hdrs = _login(client, "creator@acme.com")

    content_id, rev = _upload_doc(
        client,
        creator_hdrs,
        title="Audit Chain Doc",
        body=b"Original audited body.",
    )
    rev_id = rev["id"]

    # Generate additional audit events (comment + approve)
    client.post(
        f"/revisions/{rev_id}/comments",
        json={"text": "Checking audit trail", "span": {"start": 0, "end": 8}},
        headers=reviewer_hdrs,
    )
    client.post(
        f"/revisions/{rev_id}/approve",
        json={"content_hash": rev["content_hash"]},
        headers=reviewer_hdrs,
    )

    # Query GET /audit?item=<content_id>
    audit_resp = client.get(f"/audit?item={content_id}", headers=creator_hdrs)
    assert audit_resp.status_code == 200
    events = audit_resp.json()
    actions = [e["action"] for e in events]
    assert "content.created" in actions
    assert "revision.created" in actions
    assert "comment.created" in actions
    assert "revision.approved" in actions

    # Cross-tenant isolation: Acme cannot see Meridian's item audit
    acme_audit = client.get(f"/audit?item={content_id}", headers=acme_hdrs)
    assert acme_audit.status_code == 200
    assert acme_audit.json() == []

    # Full chain verification on in-memory session passes
    is_valid, errors, count = verify_audit_chain(db_session, tenant_id="tenant_meridian")
    assert is_valid is True, errors
    assert count >= 4

    # Standalone script test on a file-backed SQLite database (valid -> exit 0, tampered -> exit 1)
    db_file = tmp_path / "audit_verify_test.db"
    db_url = f"sqlite:///{db_file}"
    file_engine = create_engine(db_url)
    Base.metadata.create_all(bind=file_engine)
    FileSession = sessionmaker(bind=file_engine)

    with FileSession() as fdb:
        fdb.add(Tenant(id="tenant_verify", name="Verify Co", ruleset_version=1))
        fdb.flush()
        append_audit_log(
            fdb,
            tenant_id="tenant_verify",
            entity_type="revision",
            entity_id="rev_v1",
            action="revision.created",
            payload={"version": 1},
        )
        e2 = append_audit_log(
            fdb,
            tenant_id="tenant_verify",
            entity_type="revision",
            entity_id="rev_v1",
            action="revision.approved",
            payload={"approver": "u_reviewer"},
        )
        assert e2.prev_hash != GENESIS_HASH
        fdb.commit()

    script_path = Path(__file__).resolve().parent.parent / "scripts" / "verify_audit_chain.py"

    ok_proc = subprocess.run(
        [sys.executable, str(script_path), "--database-url", db_url],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok_proc.returncode == 0, ok_proc.stderr

    # Manually tamper a row in audit_log and verify CLI fails (exit 1)
    with file_engine.begin() as conn:
        conn.execute(
            text("UPDATE audit_log SET action = 'revision.tampered' WHERE entity_id = 'rev_v1' AND prev_hash = :g"),
            {"g": GENESIS_HASH},
        )

    tamper_proc = subprocess.run(
        [sys.executable, str(script_path), "--database-url", db_url],
        capture_output=True,
        text=True,
        check=False,
    )
    assert tamper_proc.returncode == 1
    assert "mismatch" in tamper_proc.stderr.lower()
    file_engine.dispose()


def test_usage_ledger_and_settings_no_external_processing(
    client: TestClient, db_session: Session
):
    """Y-15: Usage ledger telemetry + restricted zero external calls + settings switch."""
    admin_hdrs = _login(client, "admin@meridian.flow")
    creator_hdrs = _login(client, "creator@meridian.flow")

    # 1. GET /settings lists configured external services and default switch state
    settings_resp = client.get("/settings", headers=creator_hdrs)
    assert settings_resp.status_code == 200
    s_data = settings_resp.json()
    assert s_data["no_external_processing"] is False
    service_ids = {s["id"] for s in s_data["external_services"]}
    assert {"openrouter", "gemini", "local_embeddings"}.issubset(service_ids)

    # Non-admin cannot change settings
    non_admin_put = client.put(
        "/settings",
        json={"no_external_processing": True},
        headers=creator_hdrs,
    )
    assert non_admin_put.status_code == 403

    # 2. Internal run records external disclosures from ReviewResult in UsageLedger
    _, rev = _upload_doc(client, creator_hdrs, title="Usage Ledger Doc", body=b"Check usage tracking.")
    rev_id = rev["id"]

    ext_result = ReviewResult(
        revision_id=rev_id,
        ruleset_version=1,
        sensitivity=Sensitivity.internal,
        findings=[],
        partial=False,
        disclosures=[
            DisclosureRecord(
                method=Method.llm_assisted,
                provider="openrouter",
                model="gpt-4o-mini",
                external_call=True,
                data_categories=["document_spans"],
                sensitivity=Sensitivity.internal,
                tokens=420,
                cost=0.0021,
                latency_ms=310,
            )
        ],
        matched_sources=[],
    )
    with patch("api.src.routers.revisions.run_review", return_value=ext_result):
        r1 = client.post(
            f"/revisions/{rev_id}/review",
            json={"sensitivity": "internal"},
            headers=creator_hdrs,
        )
        assert r1.status_code == 202
        run1_id = r1.json()["id"]

    usage_r1 = client.get(f"/usage?run_id={run1_id}", headers=creator_hdrs)
    assert usage_r1.status_code == 200
    u1_data = usage_r1.json()
    assert u1_data["summary"]["total_external_calls"] == 1
    assert u1_data["summary"]["total_tokens"] == 420
    assert u1_data["summary"]["total_cost"] == 0.0021

    # 3. Enable no_external_processing switch via PUT /settings
    try:
        upd_resp = client.put(
            "/settings",
            json={"no_external_processing": True},
            headers=admin_hdrs,
        )
        assert upd_resp.status_code == 200
        upd_data = upd_resp.json()
        assert upd_data["no_external_processing"] is True
        openrouter_svc = next(s for s in upd_data["external_services"] if s["id"] == "openrouter")
        assert openrouter_svc["enabled"] is False

        # Edit to create a new revision with fresh hash and run review while switch is ON
        edit_resp = client.post(
            f"/revisions/{rev_id}/edit",
            json={"raw_text": "Strict privacy content with no external calls allowed."},
            headers=creator_hdrs,
        )
        assert edit_resp.status_code == 201
        rev2_id = edit_resp.json()["id"]

        captured_policy = {}

        def _fake_review(**kwargs):
            captured_policy["policy"] = kwargs["policy"]
            return ext_result

        with patch("api.src.routers.revisions.run_review", side_effect=_fake_review):
            r2 = client.post(
                f"/revisions/{rev2_id}/review",
                json={"sensitivity": "public"},  # caller asks public, switch forces restricted
                headers=creator_hdrs,
            )
            assert r2.status_code == 202
            run2 = r2.json()
            assert run2["sensitivity"] == "restricted"

        assert captured_policy["policy"] == Sensitivity.restricted

        usage_r2 = client.get(f"/usage?run_id={run2['id']}", headers=creator_hdrs)
        assert usage_r2.status_code == 200
        u2_data = usage_r2.json()
        assert u2_data["summary"]["total_external_calls"] == 0
        assert u2_data["summary"]["total_tokens"] == 0
        assert u2_data["summary"]["total_cost"] == 0.0
        assert u2_data["summary"]["restricted_runs_external_calls"] == 0
    finally:
        # Reset tenant switch back to False for clean shared session state
        client.patch(
            "/settings",
            json={"no_external_processing": False},
            headers=admin_hdrs,
        )
