from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.src.models.tenant import Tenant


def test_sources_versioning_and_idempotency(client: TestClient, db_session: Session):
    # 1. Login as admin
    admin_login = client.post(
        "/auth/login",
        json={"email": "admin@meridian.flow", "password": "password123"},
    )
    token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create fact F-112 version 1
    create_resp = client.post(
        "/sources",
        json={
            "source_id": "F-112",
            "kind": "fact",
            "name": "Customer Count",
            "body": "Meridian Flow serves 10,000+ customers.",
            "value": "10,000+",
            "unit": "customers",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["id"] == "F-112"
    assert data["current_version"] == 1
    assert len(data["versions"]) == 1
    v1_hash = data["versions"][0]["content_hash"]

    # 3. Add version 2 via POST /sources/{id}/versions
    v2_resp = client.post(
        "/sources/F-112/versions",
        json={
            "body": "Meridian Flow serves 18,000+ customers.",
            "value": "18,000+",
            "unit": "customers",
        },
        headers=headers,
    )
    assert v2_resp.status_code == 201
    v2_data = v2_resp.json()
    assert v2_data["current_version"] == 2
    assert len(v2_data["versions"]) == 2
    # Verify superseding
    v1 = v2_data["versions"][0]
    v2 = v2_data["versions"][1]
    assert v1["superseded_by"] == 2
    assert v1["valid_until"] is not None
    assert v2["version"] == 2
    assert v2["value"] == "18,000+"
    assert v2["superseded_by"] is None

    # 4. Idempotency test on POST /sources/{id}/versions: re-post identical v2
    repost_resp = client.post(
        "/sources/F-112/versions",
        json={
            "body": "Meridian Flow serves 18,000+ customers.",
            "value": "18,000+",
            "unit": "customers",
        },
        headers=headers,
    )
    assert repost_resp.status_code == 201
    repost_data = repost_resp.json()
    assert repost_data["current_version"] == 2
    assert len(repost_data["versions"]) == 2  # No duplicate version created!

    # 5. GET /sources/F-112 returns full history
    get_resp = client.get("/sources/F-112", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["current_version"] == 2

    # 6. Verify ruleset_version was bumped
    tenant = db_session.query(Tenant).filter(Tenant.id == "tenant_meridian").first()
    assert tenant is not None
    assert tenant.ruleset_version >= 2

