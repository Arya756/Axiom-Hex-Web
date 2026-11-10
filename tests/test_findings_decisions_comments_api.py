import io
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.src.models.review import FindingDecision, FindingModel


def test_finding_decisions_and_idempotency(client: TestClient, db_session: Session):
    # 1. Login as reviewer
    login_resp = client.post(
        "/auth/login",
        json={"email": "reviewer@meridian.flow", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload content and run review to get findings
    content_resp = client.post(
        "/content",
        data={"title": "Decision Test Document"},
        files={"file": ("dec_doc.md", io.BytesIO(b"Over 10,000+ customers trust MFP."), "text/markdown")},
        headers=headers,
    )
    rev_id = content_resp.json()["revisions"][0]["id"]
    client.post(f"/revisions/{rev_id}/review", json={"sensitivity": "internal"}, headers=headers)

    findings_resp = client.get(f"/revisions/{rev_id}/findings", headers=headers)
    assert findings_resp.status_code == 200
    findings = findings_resp.json()
    assert len(findings) >= 1
    finding_id = findings[0]["finding_id"]

    # 3. Decision validation: override without written reason must fail with 422
    fail_override = client.post(
        f"/findings/{finding_id}/decision",
        json={"action": "override"},
        headers=headers,
    )
    assert fail_override.status_code == 422
    assert "mandatory" in fail_override.json()["detail"].lower()

    # 4. Decision validation: dispute without written reason must fail with 422
    fail_dispute = client.post(
        f"/findings/{finding_id}/decision",
        json={"action": "dispute", "reason": "   "},
        headers=headers,
    )
    assert fail_dispute.status_code == 422
    assert "mandatory" in fail_dispute.json()["detail"].lower()

    # 5. Valid accept decision
    accept_resp = client.post(
        f"/findings/{finding_id}/decision",
        json={"action": "accept"},
        headers=headers,
    )
    assert accept_resp.status_code == 201
    assert accept_resp.json()["finding_status"] == "accepted"

    # 6. Idempotency on retry: repeating same decision returns existing record without duplicating
    dup_resp = client.post(
        f"/findings/{finding_id}/decision",
        json={"action": "accept"},
        headers=headers,
    )
    assert dup_resp.status_code == 201
    assert dup_resp.json()["id"] == accept_resp.json()["id"]

    # Verify in DB: only one decision for (finding_id, action='accept')
    db_count = (
        db_session.query(FindingDecision)
        .filter(FindingDecision.finding_id == finding_id, FindingDecision.action == "accept")
        .count()
    )
    assert db_count == 1

    # 7. Valid override decision with reason
    override_resp = client.post(
        f"/findings/{finding_id}/decision",
        json={"action": "override", "reason": "Approved exception by brand lead for Q3 press release."},
        headers=headers,
    )
    assert override_resp.status_code == 201
    assert override_resp.json()["finding_status"] == "overridden"
    assert "Approved exception" in override_resp.json()["reason"]


def test_comments_anchoring(client: TestClient):
    login_resp = client.post(
        "/auth/login",
        json={"email": "reviewer@meridian.flow", "password": "password123"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Upload doc
    content_resp = client.post(
        "/content",
        data={"title": "Comment Doc"},
        files={"file": ("comm_doc.md", io.BytesIO(b"Sample paragraph for comments."), "text/markdown")},
        headers=headers,
    )
    rev_id = content_resp.json()["revisions"][0]["id"]
    client.post(f"/revisions/{rev_id}/review", json={"sensitivity": "internal"}, headers=headers)
    findings = client.get(f"/revisions/{rev_id}/findings", headers=headers).json()
    finding_id = findings[0]["finding_id"]

    # 1. Comment without anchor should fail with 422
    fail_comment = client.post(
        f"/revisions/{rev_id}/comments",
        json={"text": "Unanchored comment"},
        headers=headers,
    )
    assert fail_comment.status_code == 422
    assert "anchored" in fail_comment.json()["detail"].lower()

    # 2. Comment anchored to finding
    finding_comment = client.post(
        f"/revisions/{rev_id}/comments",
        json={"text": "Please check the claim source.", "finding_id": finding_id},
        headers=headers,
    )
    assert finding_comment.status_code == 201
    assert finding_comment.json()["finding_id"] == finding_id

    # 3. Comment anchored to span
    span_comment = client.post(
        f"/revisions/{rev_id}/comments",
        json={
            "text": "Review wording here.",
            "span": {"unit_id": f"u_{rev_id}_1", "start": 0, "end": 16, "quote": "Sample paragraph"},
        },
        headers=headers,
    )
    assert span_comment.status_code == 201
    assert span_comment.json()["span"]["quote"] == "Sample paragraph"

    # 4. List comments
    comments_list = client.get(f"/revisions/{rev_id}/comments", headers=headers)
    assert comments_list.status_code == 200
    assert len(comments_list.json()) == 2

