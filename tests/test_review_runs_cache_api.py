from datetime import datetime, timedelta, timezone
import io
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.src.models.review import ReviewRun


def test_review_run_execution_and_caching(client: TestClient, db_session: Session):
    # 1. Login as creator
    login_resp = client.post(
        "/auth/login",
        json={"email": "creator@meridian.flow", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload draft
    content_resp = client.post(
        "/content",
        data={"title": "Review Test Document", "sensitivity": "internal"},
        files={"file": ("test_doc.md", io.BytesIO(b"Meridian Flow Platform delivers 99.95% uptime."), "text/markdown")},
        headers=headers,
    )
    assert content_resp.status_code == 201
    rev_id = content_resp.json()["revisions"][0]["id"]

    # 3. Trigger review run via POST /revisions/{id}/review
    review_req = {
        "sensitivity": "internal",
        "intent_card": {
            "purpose": "Marketing banner",
            "audience": "Enterprise leads",
            "key_message": "High compliance uptime",
            "cta": "Sign up",
        },
    }
    run_resp = client.post(f"/revisions/{rev_id}/review", json=review_req, headers=headers)
    assert run_resp.status_code == 202
    run_data = run_resp.json()
    run_id = run_data["id"]
    assert run_data["cached"] is False
    assert run_data["status"] in {"queued", "running", "done"}

    # 4. Check findings generated for the revision via GET /revisions/{id}/findings
    findings_resp = client.get(f"/revisions/{rev_id}/findings", headers=headers)
    assert findings_resp.status_code == 200
    findings = findings_resp.json()
    assert len(findings) >= 1
    assert findings[0]["revision_id"] == rev_id

    # 5. Caching test: re-triggering with same parameters should return cached result
    # Ensure run is marked done
    run_obj = db_session.query(ReviewRun).filter(ReviewRun.id == run_id).first()
    if run_obj:
        run_obj.status = "done"
        db_session.commit()

    cached_resp = client.post(f"/revisions/{rev_id}/review", json=review_req, headers=headers)
    assert cached_resp.status_code == 202
    cached_data = cached_resp.json()
    assert cached_data["cached"] is True
    assert cached_data["id"] == run_id

    # 6. Cache invalidation test: bump ruleset version via admin source update
    admin_login = client.post(
        "/auth/login",
        json={"email": "admin@meridian.flow", "password": "password123"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # First create source F-CACHE-BUMP
    src_resp = client.post(
        "/sources",
        json={"source_id": "F-CACHE-BUMP", "kind": "fact", "name": "Customer Count", "body": "Initial fact count"},
        headers=admin_headers,
    )
    assert src_resp.status_code == 201

    ver_resp = client.post(
        "/sources/F-CACHE-BUMP/versions",
        json={"body": "New fact bumping ruleset version", "value": "30k+"},
        headers=admin_headers,
    )
    assert ver_resp.status_code == 201

    # Now review request should NOT match the old cache because ruleset_version changed!
    invalidated_resp = client.post(f"/revisions/{rev_id}/review", json=review_req, headers=headers)
    assert invalidated_resp.status_code == 202
    assert invalidated_resp.json()["cached"] is False


def test_stale_run_watchdog(client: TestClient, db_session: Session):
    login_resp = client.post(
        "/auth/login",
        json={"email": "creator@meridian.flow", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    content_resp = client.post(
        "/content",
        data={"title": "Watchdog Test Doc"},
        files={"file": ("watchdog.md", io.BytesIO(b"Sample watchdog doc"), "text/markdown")},
        headers=headers,
    )
    rev_id = content_resp.json()["revisions"][0]["id"]

    # Insert a fake stale run stuck in 'running' started 10 minutes ago
    stale_start = datetime.now(timezone.utc) - timedelta(minutes=10)
    stale_run = ReviewRun(
        id="run_stale_123",
        tenant_id="tenant_meridian",
        revision_id=rev_id,
        ruleset_version=1,
        sensitivity="internal",
        status="running",
        started_at=stale_start,
        partial=False,
        matched_sources=[],
        run_progress=[],
    )
    db_session.add(stale_run)
    db_session.commit()

    # Triggering new review triggers watchdog
    client.post(f"/revisions/{rev_id}/review", json={"sensitivity": "internal"}, headers=headers)

    db_session.refresh(stale_run)
    assert stale_run.status == "failed"
    assert stale_run.finished_at is not None
